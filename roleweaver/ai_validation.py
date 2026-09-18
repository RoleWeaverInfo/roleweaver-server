"""Local Guardrails AI adapter. No LLM judge, reasks, or remote validation."""

import os
import threading
from importlib.metadata import version

# Set before importing SDKs: disable tracing and LiteLLM's remote cost-map fetch.
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

from guardrails import Guard
from guardrails.validators import Validator, register_validator, PassResult, FailResult
from guardrails_ai.regex_match import RegexMatch
from . import guardrails as policy
from . import safeguards


@register_validator(name="roleweaver/dialogue-policy", data_type="string")
class DialoguePolicy(Validator):
    def _validate(self, value, metadata):
        if metadata["direction"] == "input":
            reason = policy.input_reason(value)
        else:
            reason = policy.screen_reply(value, metadata.get("profile", {}))[1]
        return FailResult(error_message=reason) if reason else PassResult()


@register_validator(name="roleweaver/owner-policy", data_type="string")
class OwnerPolicy(Validator):
    def _validate(self, value, metadata):
        found = safeguards.flags(
            metadata["report"], metadata["policy"], metadata["direction"]
        )
        return FailResult(error_message=", ".join(found)) if found else PassResult()


class LocalValidation:
    version = version("guardrails-ai")

    def __init__(self):
        self.local = threading.local()

    def guard(self, direction):
        guard = getattr(self.local, direction, None)
        if guard is None:
            limit = 2000 if direction == "input" else 700
            guard = Guard(use_server=False, history_max_length=1)
            guard.configure(allow_metrics_collection=False)
            # Full-string match: no control bytes, empty/whitespace-only text,
            # or oversized dialogue. Tabs/newlines and Unicode RP remain valid.
            guard.use(
                RegexMatch(
                    regex=rf"\A(?=[\s\S]*\S)[^\x00-\x08\x0b\x0c\x0e-\x1f\x7f]{{1,{limit}}}\Z",
                    on_fail="noop",
                ),
                DialoguePolicy(on_fail="noop"),
            )
            setattr(self.local, direction, guard)
        return guard

    def validate(self, text, direction, profile):
        guard = self.guard(direction)
        try:
            result = guard.validate(
                text,
                metadata={"direction": direction, "profile": profile},
                num_reasks=0,
            )
            return bool(result.validation_passed)
        finally:
            # Do not keep another transcript in Guardrails' diagnostic history.
            guard.history.clear()

    def review_passed(self, report, settings, direction):
        guard = getattr(self.local, "review", None)
        if guard is None:
            guard = Guard(use_server=False, history_max_length=1)
            guard.configure(allow_metrics_collection=False)
            guard.use(OwnerPolicy(on_fail="noop"))
            self.local.review = guard
        try:
            return bool(
                guard.validate(
                    "assessment",
                    metadata={
                        "report": report,
                        "policy": settings,
                        "direction": direction,
                    },
                    num_reasks=0,
                ).validation_passed
            )
        finally:
            guard.history.clear()
