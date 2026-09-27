"""Bounded proposal recovery without repairing or acting on malformed model output."""

import json
import unittest
from unittest.mock import patch
from roleweaver import dm_assistant as assistant


class AssistantJSONTests(unittest.TestCase):
    config = dict(
        provider="openai-compatible",
        base_url="http://127.0.0.1:1234/v1",
        model="test",
        request_timeout=25,
    )

    def envelope(self, content, reason="stop"):
        return dict(choices=[dict(message=dict(content=content), finish_reason=reason)])

    def test_complete_fenced_json_is_accepted(self):
        self.assertEqual(
            assistant.decode_response(
                self.envelope('```json\n{"summary":"hello"}\n```')
            ),
            {"summary": "hello"},
        )

    def test_truncated_or_malformed_json_is_never_repaired(self):
        for content, reason in [
            ("{}", "length"),
            ('{"a":"bad "quote""}', "stop"),
            ("text {}", "stop"),
            ("[]", "stop"),
            ("", "stop"),
        ]:
            with (
                self.subTest(content=content),
                self.assertRaises(assistant.AssistantResponseError),
            ):
                assistant.decode_response(self.envelope(content, reason))

    def test_retry_has_more_budget_and_preserves_user_context(self):
        calls = []

        def complete(url, body, headers, timeout, limit, decode, **kw):
            calls.append(json.loads(body))
            return decode(
                self.envelope('{"broken":' if len(calls) == 1 else '{"ok":true}')
            )

        with patch("roleweaver.provider.complete", side_effect=complete):
            result = assistant.generate(
                self.config, "Robber, no combat", {"allow_combat": False}
            )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0]["max_tokens"], 4096)
        self.assertEqual(calls[1]["max_tokens"], 8192)
        self.assertEqual(calls[0]["messages"][1], calls[1]["messages"][1])
        self.assertNotIn("broken", calls[1]["messages"][0]["content"])

    def test_two_bad_responses_give_friendly_error(self):
        with patch(
            "roleweaver.provider.complete",
            side_effect=json.JSONDecodeError("secret raw response", "", 0),
        ) as call:
            with self.assertRaisesRegex(
                assistant.AssistantResponseError, "Nothing was placed"
            ) as error:
                assistant.generate(self.config, "A scene", {})
        self.assertEqual(call.call_count, 2)
        self.assertNotIn("secret", str(error.exception))

    def test_provider_errors_are_not_retried_as_format_errors(self):
        with patch("roleweaver.provider.complete", side_effect=TimeoutError()) as call:
            with self.assertRaises(TimeoutError):
                assistant.generate(self.config, "A scene", {})
        self.assertEqual(call.call_count, 1)

    def test_refusal_is_not_retried(self):
        def complete(url, body, headers, timeout, limit, decode, **kw):
            return decode(self.envelope(None, "content_filter"))

        with patch("roleweaver.provider.complete", side_effect=complete) as call:
            with self.assertRaisesRegex(ValueError, "declined"):
                assistant.generate(self.config, "A scene", {})
        self.assertEqual(call.call_count, 1)

    def test_director_does_not_gain_automatic_retry(self):
        with patch(
            "roleweaver.provider.complete",
            side_effect=assistant.AssistantResponseError("invalid"),
        ) as call:
            with self.assertRaises(assistant.AssistantResponseError):
                assistant.request(self.config, "system", {})
        self.assertEqual(call.call_count, 1)
