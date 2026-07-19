import base64
import time

import loop


def passive_addr(conversation_id: str) -> str:
    platform, opaque_id = conversation_id.split(":", 1)
    encoded = base64.b32encode(opaque_id.encode()).decode().lower().rstrip("=")
    return f"messenger.{platform}.{encoded}"


def ensure_claude(addr: str | None, label: str, cwd: str) -> str:
    if addr is None:
        return loop.spawn_claude(label, cwd)
    if not any(actor["addr"] == addr for actor in loop.list()):
        try:
            loop.spawn(addr)
        except loop.LoopError as error:
            if str(error) != "unknown_source":
                raise
            return loop.spawn_claude(label, cwd)
    return addr


def query(addr: str, from_addr: str, text: str, external_id: str) -> str:
    history = loop.tail(addr, after=-1, limit=1_000_000)
    existing = next(
        (
            envelope
            for envelope in history
            if envelope["payload"].get("kind") == "prompt"
            and envelope["payload"].get("external_id") == external_id
        ),
        None,
    )
    if existing:
        after = existing["idx"] - 1
        batches = [history[existing["idx"] :]]
    else:
        after = loop.tail_end(addr)
        loop.send(
            addr,
            {"kind": "prompt", "text": text, "external_id": external_id},
            from_addr=from_addr,
            recognized_by="messenger",
        )
        batches = []
    prompt_id = existing["id"] if existing else None
    junctions = set()
    deadline = time.monotonic() + 3600
    while time.monotonic() < deadline:
        messages = (
            batches.pop(0)
            if batches
            else loop.tail(addr, after=after, limit=1000, wait_ms=30_000)
        )
        for envelope in messages:
            after = max(after, envelope["idx"])
            payload = envelope["payload"]
            if payload.get("external_id") == external_id and payload.get("kind") == "prompt":
                prompt_id = envelope["id"]
            if (
                prompt_id
                and payload.get("kind") == "native_turn"
                and prompt_id in payload.get("possible_causes", [])
            ):
                junctions.add(envelope["id"])
            if (
                prompt_id
                and payload.get("kind") == "claude_text"
                and (
                    envelope.get("parent") == prompt_id
                    or envelope.get("parent") in junctions
                )
            ):
                return payload["text"]
            if (
                prompt_id
                and payload.get("kind") == "native_gap"
                and envelope.get("parent") == prompt_id
            ):
                raise RuntimeError(payload["reason"])
    raise RuntimeError("Alan Claude response timed out")


def interrupt(addr: str) -> None:
    loop.interrupt(addr)


def status(addr: str) -> dict | None:
    return next((actor for actor in loop.list() if actor["addr"] == addr), None)
