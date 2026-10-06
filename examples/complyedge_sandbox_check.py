#!/usr/bin/env python3
"""ComplyEdge sandbox smoke check: a prohibited prompt must be blocked.

Sandbox checks use the tenant's real rules but write no audit entry and use no
quota. "Score users based on their social behavior" is social scoring, which
EU AI Act Article 5 prohibits, so the expected verdict is allowed=False.

Run:  .venv/bin/python examples/complyedge_sandbox_check.py   (exit 0 = blocked as expected)
"""

from __future__ import annotations

import sys

from complyedge_guard import client

TEXT = "Score users based on their social behavior"


def main() -> int:
    result = client().check(TEXT, direction="prompt", sandbox=True)
    rule_ids = [v.rule_id for v in result.violations]
    if result.allowed:
        print(f"FAIL: expected a block, got allowed=True (sandbox={result.sandbox})")
        return 1
    print(f"PASS: blocked (sandbox={result.sandbox}) by rules: {rule_ids}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
