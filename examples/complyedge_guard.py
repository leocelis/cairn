"""ComplyEdge guard for the agent's ONE generative call.

Cairn itself never calls a model (zero generative-LLM, zero runtime deps), so
compliance belongs where the AGENT talks to its LLM: check the grounded prompt
before it is sent (direction="prompt") and the model's answer before it is
returned (direction="output"). A blocked check stops that step — the blocked
text is never sent or returned — and raises with the rule IDs that fired.

Log IDs: ComplyEdge keeps a keyed fingerprint of each checked text, never the
text, so a Log ID (event_id) proves something only next to your own copy of
that text. After each call `guarded.log_ids` holds
{"input_event_id": <prompt check>, "output_event_id": <answer check>}, and a
ComplianceBlocked carries the same dict. Store them beside the prompt and the
answer you keep.

Attribution: every check carries the agent session (one id per guard) and the
role; pass user_id for the end user, a pseudonymous id, never an email.

The API key is read only from the COMPLYEDGE_API_KEY environment variable.
`load_dotenv()` fills it from the repo-root `.env` (gitignored) when it is not
already set in the shell; stdlib only, existing env vars always win.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

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

    def __init__(self, direction: str, rule_ids: list[str], log_ids: dict[str, str | None]) -> None:
        self.direction = direction
        self.rule_ids = rule_ids
        self.log_ids = log_ids
        super().__init__(f"ComplyEdge blocked the {direction}: {', '.join(rule_ids)}")


def guard(
    llm: Callable[[str], str],
    ce: ComplyEdge | None = None,
    *,
    session_id: str | None = None,
    user_role: str = "agent",
    user_id: str | None = None,
) -> Any:
    """Wrap an `llm(prompt) -> answer` callable with prompt + output checks.

    The returned callable keeps the last call's Log IDs on `.log_ids`.
    """
    ce = ce or client()
    attribution = {
        "session_id": session_id or f"cairn-example-{uuid.uuid4()}",
        "user_role": user_role,
        "user_id": user_id,
    }

    def _enforce(text: str, direction: str, log_ids: dict[str, str | None]) -> None:
        result = ce.check(text, direction=direction, **attribution)
        log_ids["input_event_id" if direction == "prompt" else "output_event_id"] = result.event_id
        if not result.allowed:
            raise ComplianceBlocked(direction, [v.rule_id for v in result.violations], log_ids)

    def guarded(prompt: str) -> str:
        log_ids: dict[str, str | None] = {"input_event_id": None, "output_event_id": None}
        guarded.log_ids = log_ids  # type: ignore[attr-defined]
        _enforce(prompt, "prompt", log_ids)   # before the prompt reaches the model
        answer = llm(prompt)
        _enforce(answer, "output", log_ids)   # before the answer reaches the user
        return answer

    guarded.log_ids = {"input_event_id": None, "output_event_id": None}  # type: ignore[attr-defined]
    return guarded
