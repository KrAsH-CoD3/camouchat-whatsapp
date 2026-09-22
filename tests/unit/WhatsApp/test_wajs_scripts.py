"""Regression tests for the wa-js script generator.

Guards the fix for the JavaScript-injection issue in ``wajs_scripts.py``:
every identifier that originates outside the SDK must be embedded as a
JSON-encoded string literal, never spliced into a bare single-quoted JS string.

A crafted JID such as ``');alert(1)//`` would otherwise close the JS string
literal early and execute arbitrary code inside the authenticated WhatsApp Web
context.
"""

import json
import pathlib
import re

import pytest

from camouchat_whatsapp.api.wa_js.wajs_scripts import WAJS_Scripts

# Escapes a single-quoted JS string literal and runs code.
BREAKOUT = "');alert(1)//"

# One representative generator per tainted parameter, paired with the
# parameter name it interpolates.
TAINTED_SITES = [
    ("mark_is_read", "chat_id"),
    ("contact_query_exists", "contact_id"),
    ("group_get_participants", "group_id"),
    ("group_join", "invite_code"),
    ("newsletter_follow", "newsletter_id"),
    ("labels_get_by_id", "label_id"),
    ("community_get_subgroups", "community_id"),
    ("call_accept", "call_id"),
    ("status_send_read", "msg_id"),
    ("conn_set_theme", "theme"),
    ("privacy_set_last_seen", "value"),
]

TAINTED_PARAMS = [param for _, param in TAINTED_SITES]

SOURCE = (
    pathlib.Path(__file__).parents[3]
    / "src"
    / "camouchat_whatsapp"
    / "api"
    / "wa_js"
    / "wajs_scripts.py"
)


@pytest.mark.parametrize(("method_name", "param"), TAINTED_SITES)
def test_tainted_param_is_json_encoded(method_name, param):
    """The value is embedded as a JSON string literal, not a raw JS string."""
    script = getattr(WAJS_Scripts, method_name)(BREAKOUT)

    assert json.dumps(BREAKOUT) in script, f"{method_name}: {param} not JSON-encoded"
    assert f"'{BREAKOUT}'" not in script, f"{method_name}: {param} still interpolated raw"


@pytest.mark.parametrize(("method_name", "param"), TAINTED_SITES)
def test_breakout_payload_cannot_terminate_the_js_string(method_name, param):
    """The payload stays inside one literal: no stray quote is left unescaped."""
    script = getattr(WAJS_Scripts, method_name)(BREAKOUT)

    # json.dumps wraps the value in double quotes and escapes inner quotes,
    # so the payload's own single quote is inert.
    assert '"' in script
    assert script.count(json.dumps(BREAKOUT)) == 1
    # The payload must never appear as a bare, unquoted JS token sequence.
    assert f"({BREAKOUT})" not in script


def test_double_quote_and_backslash_payloads_are_escaped():
    """Values containing JS-significant characters are escaped, not just re-quoted."""
    payload = '");alert(2)//\\'
    script = WAJS_Scripts.mark_is_read(payload)

    encoded = json.dumps(payload)
    assert encoded in script
    assert '\\"' in script, "embedded double quote was not escaped"
    assert "\\\\" in script, "embedded backslash was not escaped"
    # Round-trips: the emitted literal decodes back to the original value.
    assert json.loads(encoded) == payload


def test_benign_ids_are_unchanged_in_meaning():
    """Normal WhatsApp identifiers still render as a usable JS string literal."""
    jid = "916398014720@c.us"
    script = WAJS_Scripts.mark_is_read(jid)

    assert script == f"wpp.chat.markIsRead({json.dumps(jid)})"


def test_source_contains_no_raw_single_quote_interpolation():
    """Static guard: stops the vulnerable pattern being reintroduced later."""
    source = SOURCE.read_text(encoding="utf-8")
    pattern = re.compile(r"'\{(" + "|".join(TAINTED_PARAMS) + r")\}'")

    offenders = sorted(set(pattern.findall(source)))

    assert offenders == [], "raw single-quote interpolation reintroduced for: " + ", ".join(
        offenders
    )


# Numeric parameters are interpolated unquoted into the JS source. Python does not enforce
# type hints at runtime, so without an explicit coercion they are injection sinks as well.

INJECTION = "1);alert(1)//"

NUMERIC_SINKS = [
    ("contact_list.count", lambda p: WAJS_Scripts.contact_list(count=p)),
    ("newsletter_search.limit", lambda p: WAJS_Scripts.newsletter_search("q", limit=p)),
    (
        "mark_is_composing.duration_ms",
        lambda p: WAJS_Scripts.mark_is_composing("x@c.us", duration_ms=p),
    ),
    (
        "indexdb_get_messages.min_row_id",
        lambda p: WAJS_Scripts.indexdb_get_messages(p, limit=10),
    ),
    ("indexdb_get_messages.limit", lambda p: WAJS_Scripts.indexdb_get_messages(1, limit=p)),
]


@pytest.mark.parametrize(("name", "call"), NUMERIC_SINKS)
def test_numeric_parameter_rejects_non_numeric_input(name, call):
    """A non-numeric value must raise rather than be spliced into the JS source."""
    with pytest.raises((TypeError, ValueError)):
        call(INJECTION)


@pytest.mark.parametrize(("name", "call"), NUMERIC_SINKS)
def test_numeric_parameter_accepts_numeric_strings(name, call):
    """Coercion must not break callers that pass a numeric string."""
    script = call("7")

    assert INJECTION not in script
    assert "7" in script


def test_numeric_defaults_are_unchanged():
    assert "slice(0, 20)" in WAJS_Scripts.contact_list()
    assert "limit: 20" in WAJS_Scripts.newsletter_search("q")
    assert "3000" in WAJS_Scripts.mark_is_composing("x@c.us")
    assert "minRowId: 1" in WAJS_Scripts.indexdb_get_messages(1)


def test_source_has_no_uncoerced_numeric_interpolation():
    """Static guard: a numeric param must never be interpolated straight from the argument."""
    source = SOURCE.read_text(encoding="utf-8")
    pattern = re.compile(r"\{(limit|count|min_row_id|duration_ms)\}")

    offenders = sorted(set(pattern.findall(source)))

    assert offenders == [], "uncoerced numeric interpolation reintroduced: " + ", ".join(offenders)
