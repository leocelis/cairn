"""ComplyEdge guard for the agent's ONE generative call.

Cairn itself never calls a model (zero generative-LLM, zero runtime deps), so
compliance belongs where the AGENT talks to its LLM: check the grounded prompt
before it is sent (direction="prompt") and the model's answer before it is
returned (direction="output"). A blocked check stops that step — the blocked
text is never sent or returned — and raises with the rule IDs that fired.

The API key is read only from the COMPLYEDGE_API_KEY environment variable.
`load_dotenv()` fills it from the repo-root `.env` (gitignored) when it is not
already set in the shell; stdlib only, existing env vars always win.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from complyedge import ComplyEdge

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
AGENT_ID = "cairn-agent-example"


def load_dotenv(path: Path = ENV_FILE) -> None:
    """Load KEY=VALUE lines from `path` into os.environ without overriding."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        if value:
            os.environ.setdefault(key.strip(), value)


def client() -> ComplyEdge:
    """A ComplyEdge client keyed from COMPLYEDGE_API_KEY (never hard-coded)."""
    load_dotenv()
    api_key = os.environ.get("COMPLYEDGE_API_KEY")
    if not api_key:
        raise RuntimeError(
            f"COMPLYEDGE_API_KEY is not set. Paste your key into {ENV_FILE} "
            "(COMPLYEDGE_API_KEY=...) or export it in your shell."
        )
    return ComplyEdge(api_key=api_key, agent_id=AGENT_ID)


class ComplianceBlocked(Exception):
    """A ComplyEdge check returned allowed=False; the text was not used."""

    def __init__(self, direction: str, rule_ids: list[str]) -> None:
        self.direction = direction
        self.rule_ids = rule_ids
        super().__init__(f"ComplyEdge blocked the {direction}: {', '.join(rule_ids)}")


def _enforce(ce: ComplyEdge, text: str, direction: str) -> None:
    result = ce.check(text, direction=direction)
    if not result.allowed:
        raise ComplianceBlocked(direction, [v.rule_id for v in result.violations])


def guard(llm: Callable[[str], str], ce: ComplyEdge | None = None) -> Callable[[str], str]:
    """Wrap an `llm(prompt) -> answer` callable with prompt + output checks."""
    ce = ce or client()

    def guarded(prompt: str) -> str:
        _enforce(ce, prompt, "prompt")   # before the prompt reaches the model
        answer = llm(prompt)
        _enforce(ce, answer, "output")   # before the answer reaches the user
        return answer

    return guarded
