"""Endogenous assessment: the selection operator.

Turns the telemetry ledger into per-skill *fitness* and evidence-gated lifecycle
recommendations (experimental -> core -> deprecated). This is what lets the
dreamer act with silent autonomy safely: it never promotes by fiat, only on
measured evidence of use and good outcomes.

Fitness combines four signals:
  usage      - how often the skill is actually exercised
  quality    - did its verify checks pass / did its script run ok
  feedback   - explicit +/- signals logged against it
  retention  - did its contributions survive (default neutral until observed)
"""

from __future__ import annotations

from typing import Any

from mcp_gerard.laplace import telemetry
from mcp_gerard.laplace.canon import Canon, get_canon
from mcp_gerard.laplace.verify import CHECK_SKILL  # re-exported for callers

__all__ = ["assess", "CHECK_SKILL"]

# Fitness weights (sum to 1).
W_USAGE, W_QUALITY, W_FEEDBACK, W_RETENTION = 0.30, 0.40, 0.15, 0.15
USAGE_SAT = 10          # usage count at which usage_norm saturates to 1
CONF_SAT = 5            # samples for full confidence in a transition

# Lifecycle thresholds.
PROMOTE_MIN_USES = 5
PROMOTE_FITNESS = 0.60
DEPRECATE_FITNESS = 0.30
OFFERED_UNUSED = 8      # offered this often but never used => stale

# Refinement thresholds (orthogonal to lifecycle: "needs a content rewrite").
REFINE_MIN_CONFIDENCE = 0.5  # enough evidence to trust a complaint
REFINE_QUALITY = 0.7         # measured pass/ok-rate below this counts as friction


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _skill_signals(name: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    usage = 0
    offered = 0
    verify_pass = verify_total = 0
    exec_ok = exec_total = 0
    feedback = 0
    retention_obs: list[float] = []

    for ev in events:
        phase = ev.get("phase")
        if phase == "orient" and name in (ev.get("offered") or []):
            offered += 1
        elif phase == "execute" and ev.get("skill") == name:
            usage += 1
            # A script run carries an `ok` outcome and scores exec quality. A bare
            # protocol fetch (no `ok`) counts as usage only, leaving quality neutral
            # until a real verify/feedback outcome is observed.
            if "ok" in ev:
                exec_total += 1
                if ev["ok"]:
                    exec_ok += 1
        elif phase == "verify_check" and ev.get("skill") == name:
            usage += 1
            verify_total += 1
            if ev.get("passed"):
                verify_pass += 1
        elif phase == "feedback" and ev.get("skill") == name:
            feedback += int(ev.get("signal", 0))
        elif phase == "retention" and ev.get("skill") == name:
            retention_obs.append(float(ev.get("value", 0.5)))

    return {
        "usage": usage,
        "offered": offered,
        "verify_pass": verify_pass,
        "verify_total": verify_total,
        "exec_ok": exec_ok,
        "exec_total": exec_total,
        "feedback": feedback,
        "retention_obs": retention_obs,
    }


def _fitness(sig: dict[str, Any]) -> dict[str, Any]:
    usage_norm = min(1.0, sig["usage"] / USAGE_SAT)

    quals = []
    if sig["verify_total"]:
        quals.append(sig["verify_pass"] / sig["verify_total"])
    if sig["exec_total"]:
        quals.append(sig["exec_ok"] / sig["exec_total"])
    quality = sum(quals) / len(quals) if quals else 0.5  # neutral when unknown

    feedback_norm = (_clamp(sig["feedback"], -3, 3) + 3) / 6
    retention = (
        sum(sig["retention_obs"]) / len(sig["retention_obs"])
        if sig["retention_obs"]
        else 0.5
    )

    fitness = (
        W_USAGE * usage_norm
        + W_QUALITY * quality
        + W_FEEDBACK * feedback_norm
        + W_RETENTION * retention
    )
    samples = sig["usage"] + abs(sig["feedback"])
    confidence = min(1.0, samples / CONF_SAT)
    return {
        "fitness": round(fitness, 3),
        "quality": round(quality, 3),
        "usage_norm": round(usage_norm, 3),
        "confidence": round(confidence, 3),
    }


def _recommend(status: str, sig: dict[str, Any], fit: dict[str, Any]) -> tuple[str, str]:
    """Return (recommended_status, reason). Conservative: only act on evidence."""
    usage = sig["usage"]
    fitness = fit["fitness"]

    if status == "deprecated":
        # Resurrect if it is suddenly being used well again.
        if usage >= PROMOTE_MIN_USES and fitness >= PROMOTE_FITNESS:
            return "experimental", f"deprecated skill used again ({usage}x, fit {fitness})"
        return "deprecated", "remains unused"

    if status == "experimental":
        if usage >= PROMOTE_MIN_USES and fitness >= PROMOTE_FITNESS:
            return "core", f"earned promotion: {usage} uses, fitness {fitness}"
        if sig["offered"] >= OFFERED_UNUSED and usage == 0:
            return "deprecated", f"offered {sig['offered']}x, never used"
        if usage >= PROMOTE_MIN_USES and fitness < DEPRECATE_FITNESS:
            return "deprecated", f"used but low fitness {fitness}"
        return "experimental", "still on probation"

    # status == core
    if usage >= PROMOTE_MIN_USES and fitness < DEPRECATE_FITNESS:
        return "deprecated", f"core skill degraded to fitness {fitness}"
    if sig["offered"] >= OFFERED_UNUSED * 2 and usage == 0:
        return "deprecated", f"core skill fell out of use (offered {sig['offered']}x)"
    return "core", "healthy"


def _refine(status: str, sig: dict[str, Any], fit: dict[str, Any]) -> dict[str, Any]:
    """Does a *trusted* skill show friction worth a content rewrite?

    This is orthogonal to lifecycle. Frequent use does not by itself call for
    refinement - it makes a *complaint* trustworthy. So the refine signal fires
    only when confidence is high enough (the skill is genuinely exercised) AND a
    *measured* quality rate is poor or feedback is net-negative. The neutral
    "unknown quality" default (no verify/exec data) never triggers it.

    refine_signal = confidence x worst measured friction. This is exactly why a
    high-usage, low-quality skill - which lifecycle calls "healthy" because usage
    props up its fitness - still surfaces here: usage makes the bad quality
    *believed*, not excused.
    """
    if status == "deprecated" or fit["confidence"] < REFINE_MIN_CONFIDENCE:
        return {"needs_refine": False, "refine_signal": 0.0, "refine_reason": None}
    frictions: list[float] = []
    reasons: list[str] = []
    if sig["verify_total"]:
        rate = sig["verify_pass"] / sig["verify_total"]
        if rate < REFINE_QUALITY:
            frictions.append(REFINE_QUALITY - rate)
            reasons.append(f"verify pass-rate {round(rate, 3)}")
    if sig["exec_total"]:
        rate = sig["exec_ok"] / sig["exec_total"]
        if rate < REFINE_QUALITY:
            frictions.append(REFINE_QUALITY - rate)
            reasons.append(f"script ok-rate {round(rate, 3)}")
    if sig["feedback"] < 0:
        frictions.append(min(1.0, -sig["feedback"] / 3))
        reasons.append(f"net feedback {sig['feedback']}")
    if not frictions:
        return {"needs_refine": False, "refine_signal": 0.0, "refine_reason": None}
    return {
        "needs_refine": True,
        "refine_signal": round(fit["confidence"] * max(frictions), 3),
        "refine_reason": "; ".join(reasons),
    }


def assess(canon: Canon | None = None, session: str | None = None, since: str | None = None) -> dict[str, Any]:
    """Compute the fitness report and lifecycle recommendations for all skills."""
    canon = canon or get_canon()
    _META = {"dream_complete"}
    evs = [ev for ev in telemetry.events(since_session=session, since=since)
           if ev.get("phase") not in _META]
    skills_report: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []

    for name, sk in canon.skills.items():
        sig = _skill_signals(name, evs)
        fit = _fitness(sig)
        rec, reason = _recommend(sk.status, sig, fit)
        ref = _refine(sk.status, sig, fit)
        # Keep "healthy" honest: a kept skill that needs a rewrite says so.
        if ref["needs_refine"] and rec == sk.status:
            reason = f"{reason} (refine: {ref['refine_reason']})"
        row = {
            "name": name,
            "status": sk.status,
            "recommended_status": rec,
            "reason": reason,
            "usage": sig["usage"],
            "offered": sig["offered"],
            "verify_pass_rate": (
                round(sig["verify_pass"] / sig["verify_total"], 3)
                if sig["verify_total"]
                else None
            ),
            "feedback": sig["feedback"],
            **fit,
            **ref,
        }
        skills_report.append(row)
        if rec != sk.status:
            transitions.append(
                {"name": name, "from": sk.status, "to": rec, "reason": reason}
            )

    skills_report.sort(key=lambda r: r["fitness"], reverse=True)
    return {
        "events_seen": len(evs),
        "skills": skills_report,
        "transitions": transitions,
        "unused": [r["name"] for r in skills_report if r["usage"] == 0],
        "refine_recommended": [
            {
                "name": r["name"],
                "refine_signal": r["refine_signal"],
                "refine_reason": r["refine_reason"],
            }
            for r in sorted(
                skills_report, key=lambda r: r["refine_signal"], reverse=True
            )
            if r["needs_refine"]
        ],
    }
