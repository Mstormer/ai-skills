#!/usr/bin/env python3
"""Check a hook against tests/cases_<os>.jsonl. Never executes the test commands.

Each case is sent to the hook as a JSON payload on stdin, exactly as an agent would send it.
A fake home folder and working directory are used, so results are the same on every machine,
and every OS's hook can be tested from any OS.

Usage: python3 run_cases.py <macos|linux|windows> [path/to/Destruction_blocker.py]
Exit code is the number of failures (0 = all passed).
"""
import base64
import json
import os
import subprocess
import sys

SETUPS = {
    "macos": ({"HOME": "/Users/tester"}, "/Users/tester/Documents/Project"),
    "linux": ({"HOME": "/home/tester"}, "/home/tester/projects/app"),
    "windows": (
        {"USERPROFILE": "C:\\Users\\tester", "SYSTEMDRIVE": "C:", "HOME": "C:\\Users\\tester"},
        "C:\\Users\\tester\\Documents\\Project",
    ),
}

if len(sys.argv) < 2 or sys.argv[1] not in SETUPS:
    sys.exit(__doc__)
target_os = sys.argv[1]
here = os.path.dirname(os.path.abspath(__file__))
hook = os.path.expanduser(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(here, "..", target_os, "Destruction_blocker.py")
env_overrides, cwd = SETUPS[target_os]
env = {key: value for key, value in os.environ.items() if key.upper() not in {k.upper() for k in env_overrides}}
env.update(env_overrides)

failures = 0
with open(os.path.join(here, f"cases_{target_os}.jsonl")) as f:
    for n, line in enumerate(f, 1):
        case = json.loads(line)
        command = case["command"]
        if case.get("encode"):  # wrap as powershell -EncodedCommand <base64 UTF-16LE>
            command = "powershell -EncodedCommand " + base64.b64encode(command.encode("utf-16-le")).decode()
        payload = {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}}
        out = subprocess.run([sys.executable, hook], input=json.dumps(payload), capture_output=True, text=True, env=env)
        got = "deny" if '"deny"' in out.stdout else "allow"
        if got != case["expect"]:
            failures += 1
            print(f"FAIL case {n}: expected {case['expect']}, got {got}  {out.stderr.strip()}")
print(f"{target_os}: {n - failures}/{n} passed")
sys.exit(failures)
