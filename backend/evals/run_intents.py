"""Measures how well the current "understanding" model maps requests to HARIKA's actions.

Usage (from backend/):  .venv/Scripts/python.exe evals/run_intents.py [limit]
Uses the service chosen in Settings > Brain; nothing is executed, only interpreted.
Each case is [message, expected first operation ("" = conversation), word expected in the target].
"""
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.tools  # noqa: F401  (registers the capabilities the interpreter can use)
from app.cognition.llm.manager import RoleProvider
from app.cognition.semantic.interpreter import default_semantic_interpreter


async def main(limit: int) -> None:
    cases = json.loads((Path(__file__).parent / "intents.json").read_text(encoding="utf-8"))[:limit]
    interpreter = default_semantic_interpreter()
    choice = RoleProvider("understanding").chain()[0]
    print(f"Model: {choice['service']} / {choice['model']}  ({len(cases)} cases)\n")
    await interpreter.interpret("hello", timeout=300)  # warm the model so the first case isn't a cold start
    passed, times = 0, []
    for message, operation, word in cases:
        start = time.perf_counter()
        try:
            request = await interpreter.interpret(message, timeout=120)
            steps = request.steps
            got_op = "" if request.is_conversational else (steps[0].operation if steps else (request.operation or "?"))
            got_target = (steps[0].target or "") if steps else ""
        except Exception as exc:
            got_op, got_target = f"error: {exc}"[:40], ""
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        ok = got_op == operation and (not word or word in got_target.lower())
        passed += ok
        print(f"{'ok  ' if ok else 'MISS'} {elapsed:5.1f}s  {message!r} -> {got_op} {got_target!r}"
              + ("" if ok else f"   (expected {operation or 'conversation'} {word!r})"))
    times.sort()
    print(f"\nAccuracy {passed}/{len(cases)} = {100 * passed / len(cases):.0f}%   "
          f"median {statistics.median(times):.1f}s   p90 {times[int(len(times) * 0.9) - 1]:.1f}s")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 10_000))
