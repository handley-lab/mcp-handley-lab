import re
import time


def _ends_prompt(text, prompt):
    for line in reversed(text.split("\n")):
        if line.strip():
            return bool(prompt.match(line))
    return False


def wait_for_completion(capture, baseline, prompt, timeout):
    now = time.time
    start = now()
    prev = baseline
    stable = None

    while (t := now() - start) < timeout:
        time.sleep(0.2 if t < 1 else 3)
        cur = capture()
        if cur != prev:
            prev = cur
            stable = now() if _ends_prompt(cur, prompt) else None
        elif stable and now() - stable > 0.15:
            return cur, False

    return prev, True


def extract_output(baseline, captured, prompt, sent_code, echo_commands, continuation=None):
    b, c = baseline.split("\n"), captured.split("\n")
    start = next((i for i, (x, y) in enumerate(zip(b, c)) if x != y), len(b))
    lines = c[start:]

    while lines and (not lines[-1].strip() or prompt.match(lines[-1])):
        lines.pop()

    if continuation:
        lines = [l for l in lines if not continuation.match(l)]

    code = sent_code.strip()
    if echo_commands and code:
        code_split = code.split("\n")
        code_lines = {l.strip() for l in code_split if l.strip()}
        if lines and code_split[0].strip() in lines[0]:
            lines.pop(0)
        lines = [l for l in lines if l.strip() not in code_lines]

    return "\n".join(lines)
