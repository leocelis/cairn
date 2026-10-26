"""The ComplyEdge guard example hands its Log IDs and attribution to the agent.

ComplyEdge keeps a keyed fingerprint of each checked text, never the text, so
a Log ID (event_id) proves something only next to the integrator's own copy.
The example used to drop the event_id and send no session or role, which
taught integrators to do the same. These tests run the real guard with a
stand-in client (no network).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("complyedge")

EXAMPLES = Path(__file__).resolve().parents[4] / "examples"


def _guard_module():
    spec = importlib.util.spec_from_file_location("complyedge_guard", EXAMPLES / "complyedge_guard.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["complyedge_guard"] = mod
    spec.loader.exec_module(mod)
    return mod


class FakeCE:
    """Records each check; `block` names a direction to refuse."""

    def __init__(self, block: str | None = None) -> None:
        self.calls: list[dict] = []
        self.block = block

    def check(self, text: str, **kwargs):
        self.calls.append({"text": text, **kwargs})
        direction = kwargs["direction"]
        blocked = direction == self.block
        return SimpleNamespace(
            allowed=not blocked,
            violations=[SimpleNamespace(rule_id="rule-x")] if blocked else [],
            event_id=f"evt-{direction}-{len(self.calls)}",
        )


def test_allowed_call_keeps_both_log_ids_and_sends_attribution():
    mod = _guard_module()
    ce = FakeCE()
    guarded = mod.guard(lambda p: f"answer to {p}", ce=ce, user_id="u-123")

    assert guarded("hello") == "answer to hello"
    assert guarded.log_ids == {"input_event_id": "evt-prompt-1", "output_event_id": "evt-output-2"}
    assert [c["text"] for c in ce.calls] == ["hello", "answer to hello"]
    sessions = {c["session_id"] for c in ce.calls}
    assert len(sessions) == 1 and next(iter(sessions)).startswith("cairn-example-")
    assert all(c["user_role"] == "agent" and c["user_id"] == "u-123" for c in ce.calls)

    guarded("again")  # each call gets its own Log IDs; the session stays
    assert guarded.log_ids == {"input_event_id": "evt-prompt-3", "output_event_id": "evt-output-4"}
    assert len({c["session_id"] for c in ce.calls}) == 1


def test_blocked_prompt_carries_its_log_id_and_never_reaches_the_model():
    mod = _guard_module()
    ce = FakeCE(block="prompt")
    sent = []
    guarded = mod.guard(lambda p: sent.append(p) or "x", ce=ce)

    with pytest.raises(mod.ComplianceBlocked) as exc:
        guarded("bad")
    assert sent == []
    assert exc.value.rule_ids == ["rule-x"]
    assert exc.value.log_ids == {"input_event_id": "evt-prompt-1", "output_event_id": None}


def test_blocked_answer_carries_both_log_ids():
    mod = _guard_module()
    guarded = mod.guard(lambda p: "answer", ce=FakeCE(block="output"))
    with pytest.raises(mod.ComplianceBlocked) as exc:
        guarded("q")
    assert exc.value.direction == "output"
    assert exc.value.log_ids == {"input_event_id": "evt-prompt-1", "output_event_id": "evt-output-2"}
