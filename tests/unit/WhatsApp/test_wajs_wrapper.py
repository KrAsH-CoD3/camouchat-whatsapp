import os
from pathlib import Path, PureWindowsPath
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from camouchat_whatsapp.api.wa_js.wajs_wrapper import EventName, ListenerEntry, WapiWrapper
from camouchat_whatsapp.exceptions import WAJSError


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.evaluate = AsyncMock()
    return page


@pytest.mark.asyncio
async def test_wajs_wrapper_evaluate_stealth_success(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"

    mock_page.evaluate.return_value = {"success": True, "data": "some_data"}

    result = await wrapper._evaluate_stealth("WPP.chat.list()")
    assert result == "some_data"
    mock_page.evaluate.assert_called_once()


@pytest.mark.asyncio
async def test_wajs_wrapper_evaluate_stealth_failure(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"

    mock_page.evaluate.return_value = {"success": False, "error": "JS Error"}

    with pytest.raises(WAJSError, match="JS Error"):
        await wrapper._evaluate_stealth("WPP.chat.list()")


@pytest.mark.asyncio
async def test_wajs_wrapper_wait_for_ready(mock_page):
    wrapper = WapiWrapper(mock_page)

    # Mocking read_text and abspath to avoid disk access
    with (
        patch.object(WapiWrapper, "_read_text", return_value="console.log('wpp')"),
        patch("os.path.abspath", return_value="/fake/path"),
    ):
        # Mocking evaluate responses
        mock_page.evaluate.side_effect = [
            False,  # has_global
            None,  # injection script
            True,  # is_ready
            None,  # Smash & Grab setup
            True,  # sweep_ok verification
        ]

        assert await wrapper.wait_for_ready() is True
        assert wrapper._wpp_key.startswith("__react_devtools_")


@pytest.mark.asyncio
async def test_wajs_wrapper_api_methods(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"

    mock_page.evaluate.return_value = {"success": True, "data": "ok"}

    # Test more representative methods
    await wrapper.send_text_message("123", "hi")
    await wrapper.contact_get_profile_picture_url("123")
    await wrapper.group_get_participants("123")
    await wrapper.conn_get_platform()
    await wrapper.conn_is_online()
    await wrapper.group_create("New Group", ["123"])
    await wrapper.group_leave("123")
    await wrapper.conn_is_main_ready()
    await wrapper.contact_get_status("123")
    await wrapper.mark_is_read("123")
    await wrapper.mark_is_composing("123")
    await wrapper.newsletter_list()
    await wrapper.newsletter_search("test")
    await wrapper.newsletter_follow("123")
    await wrapper.newsletter_unfollow("123")
    await wrapper.newsletter_mute("123")
    await wrapper.newsletter_unmute("123")
    await wrapper.conn_get_my_user_id()
    await wrapper.conn_get_my_user_lid()
    await wrapper.conn_get_my_user_wid()
    await wrapper.conn_get_my_device_id()
    await wrapper.conn_is_multi_device()
    await wrapper.conn_is_idle()
    await wrapper.conn_get_theme()
    await wrapper.contact_list()
    await wrapper.contact_query_exists("123")
    await wrapper.contact_get_business_profile("123")
    await wrapper.contact_get_common_groups("123")
    await wrapper.group_get_all()
    await wrapper.group_get_invite_code("123")


@pytest.mark.asyncio
async def test_wajs_wrapper_setup_message_bridge(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"

    mock_page.evaluate.return_value = {"success": True, "data": True}

    await wrapper.setup_message_bridge()
    assert wrapper._bridge_active is True
    assert wrapper._queue_key is not None


@pytest.mark.asyncio
async def test_wajs_wrapper_poll_message_queue(mock_page):
    wrapper = WapiWrapper(mock_page)
    wrapper._wpp_key = "secret_key"
    wrapper._bridge_active = True
    wrapper._queue_key = "__camou_queue__"

    # Seed registry so drain_queue_for can resolve the WA-JS event string.
    wrapper._listener_registry[EventName.MESSAGE_EVENT] = ListenerEntry(
        name=EventName.MESSAGE_EVENT,
        event="chat.new_message",
        js_extractor="msg?.id?._serialized",
        guard_key="__cg_test_guard__",
    )

    mock_page.evaluate.return_value = ["id1", "id2"]

    ids = await wrapper.poll_message_queue()
    assert ids == ["id1", "id2"]
    mock_page.evaluate.assert_called_once()


# ── Media path containment ──────────────────────────────────────────────────
# Regression tests for path traversal via caller-supplied save_path and via the
# attacker-influenced id_serialized / type fields of a MsgModel dump.


def test_save_bytes_writes_inside_media_root(tmp_path, mock_page):
    wrapper = WapiWrapper(mock_page, media_root=tmp_path)

    target = tmp_path / "nested" / "file.bin"
    wrapper._save_bytes(str(target), b"payload")

    assert target.read_bytes() == b"payload"


def test_save_bytes_without_media_root_still_writes(tmp_path, mock_page):
    """No root configured: previous behaviour is preserved."""
    wrapper = WapiWrapper(mock_page)

    target = tmp_path / "nested" / "file.bin"
    wrapper._save_bytes(str(target), b"payload")

    assert target.read_bytes() == b"payload"


def test_save_bytes_rejects_dotdot_escape(tmp_path, mock_page):
    root = tmp_path / "media"
    root.mkdir()
    wrapper = WapiWrapper(mock_page, media_root=root)

    with pytest.raises(ValueError, match="outside media_root"):
        wrapper._save_bytes(str(root / ".." / "escaped.bin"), b"x")

    assert not (tmp_path / "escaped.bin").exists()


def test_save_bytes_rejects_absolute_path_outside_root(tmp_path, mock_page):
    root = tmp_path / "media"
    root.mkdir()
    wrapper = WapiWrapper(mock_page, media_root=root)

    with pytest.raises(ValueError, match="outside media_root"):
        wrapper._save_bytes(str(tmp_path / "elsewhere.bin"), b"x")


def test_save_bytes_rejects_symlink_escape(tmp_path, mock_page):
    root = tmp_path / "media"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")

    wrapper = WapiWrapper(mock_page, media_root=root)

    with pytest.raises(ValueError, match="outside media_root"):
        wrapper._save_bytes(str(link / "escaped.bin"), b"x")

    assert not (outside / "escaped.bin").exists()


def test_save_bytes_rejects_symlink_at_final_component(tmp_path, mock_page, monkeypatch):
    """O_NOFOLLOW: a symlink swapped in at the final component is refused, not followed.

    The race itself cannot be reproduced deterministically, so bypass the resolve
    step to hand ``_save_bytes`` a destination whose final component is already a
    symlink — the state the race would produce.
    """
    if not hasattr(os, "O_NOFOLLOW"):
        pytest.skip("O_NOFOLLOW unavailable on this platform")

    real = tmp_path / "real.bin"
    real.write_bytes(b"original")
    link = tmp_path / "link.bin"
    try:
        link.symlink_to(real)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")

    wrapper = WapiWrapper(mock_page)
    # Identity resolve: emulate the window where the symlink appears after validation.
    monkeypatch.setattr(wrapper, "_resolve_media_target", lambda p: p)

    with pytest.raises(ValueError, match="symlink"):
        wrapper._save_bytes(str(link), b"payload")

    assert real.read_bytes() == b"original", "the write followed the symlink"


def test_save_bytes_rejects_nul_byte(tmp_path, mock_page):
    wrapper = WapiWrapper(mock_page, media_root=tmp_path)

    with pytest.raises(ValueError, match="NUL"):
        wrapper._save_bytes(str(tmp_path / "bad\x00name.bin"), b"x")


def test_save_bytes_handles_bare_filename(tmp_path, mock_page, monkeypatch):
    """A bare filename has no dirname; makedirs must not be called with ''."""
    monkeypatch.chdir(tmp_path)
    wrapper = WapiWrapper(mock_page)

    wrapper._save_bytes("bare.bin", b"payload")

    assert (tmp_path / "bare.bin").read_bytes() == b"payload"


def test_save_bytes_returns_the_resolved_destination(tmp_path, mock_page, monkeypatch):
    """Callers that report a path must get the real one, not the literal argument.

    A relative path is resolved against the CWD, so reporting the input back to
    the user would name a location that does not exist.
    """
    monkeypatch.chdir(tmp_path)
    wrapper = WapiWrapper(mock_page)

    returned = wrapper._save_bytes("nested/rel.bin", b"payload")

    assert Path(returned).is_absolute()
    assert Path(returned) == (tmp_path / "nested" / "rel.bin").resolve()
    assert Path(returned).read_bytes() == b"payload"


def test_save_bytes_expands_user_in_the_returned_path(tmp_path, mock_page, monkeypatch):
    """`~/file` is written under $HOME, so the reported path must say so."""
    home = tmp_path / "fakehome"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    wrapper = WapiWrapper(mock_page)

    returned = wrapper._save_bytes("~/tilde.bin", b"payload")

    assert "~" not in returned
    assert Path(returned) == (home / "tilde.bin").resolve()
    assert Path(returned).read_bytes() == b"payload"


def test_media_save_path_neutralises_traversal_in_media_type(tmp_path):
    """`type` comes from the MsgModel dump and must not introduce separators."""
    message = {"id_serialized": "true_123@c.us_ABC", "type": "../../../etc/cron.d/evil"}

    result = WapiWrapper.media_save_path(message, str(tmp_path))

    assert Path(result).parent == tmp_path
    assert os.sep not in Path(result).name


def test_media_save_path_neutralises_windows_separator_in_msg_id(tmp_path):
    """A backslash in id_serialized is a separator on Windows."""
    message = {"id_serialized": "..\\..\\evil", "type": "image"}

    result = WapiWrapper.media_save_path(message, str(tmp_path))

    assert Path(result).parent == tmp_path
    assert "\\" not in Path(result).name


def test_media_save_path_neutralises_windows_drive_separator(tmp_path):
    """A "D:" type is drive-relative on Windows and discards save_dir entirely.

    ``Path("C:/media") / "D:_x.jpg"`` resolves to ``D:_x.jpg`` with drive ``D:``,
    so the write lands outside save_dir. ":" must not survive sanitisation.
    """
    message = {"id_serialized": "true_123@c.us_ABC", "type": "D:"}

    result = WapiWrapper.media_save_path(message, str(tmp_path))

    assert Path(result).parent == tmp_path
    assert ":" not in Path(result).name
    # The decisive check: interpreted as a Windows path, this must stay drive-less.
    assert PureWindowsPath(result).drive == ""


def test_media_save_path_preserves_normal_filenenames(tmp_path):
    """Ordinary identifiers keep the historical filename shape."""
    message = {
        "id_serialized": "true_916398014720@c.us_ABCDE123",
        "type": "image",
        "mimetype": "image/jpeg",
    }

    result = WapiWrapper.media_save_path(message, str(tmp_path))

    assert Path(result).name == "image_true_916398014720_c.us_ABCDE123.jpg"


def test_media_root_filesystem_root_permits_children(tmp_path, mock_page):
    """A root of "/" must not reject everything — naive prefixing would make it "//"."""
    target = tmp_path / "under-root.bin"

    WapiWrapper(mock_page, media_root=os.sep)._save_bytes(str(target), b"ok")

    assert target.read_bytes() == b"ok"


def test_media_root_with_trailing_separator_is_handled(tmp_path, mock_page):
    root = str(tmp_path) + os.sep

    WapiWrapper(mock_page, media_root=root)._save_bytes(str(tmp_path / "x.bin"), b"ok")

    assert (tmp_path / "x.bin").read_bytes() == b"ok"


def test_media_root_rejects_sibling_prefix(tmp_path, mock_page):
    """`/a/media` must not accept `/a/media-evil`, which a bare startswith would allow."""
    root = tmp_path / "media"
    root.mkdir()
    sibling = tmp_path / "media-evil"
    sibling.mkdir()

    wrapper = WapiWrapper(mock_page, media_root=root)

    with pytest.raises(ValueError, match="outside media_root"):
        wrapper._save_bytes(str(sibling / "escaped.bin"), b"x")

    assert not (sibling / "escaped.bin").exists()


def test_media_root_accepts_differently_cased_path(tmp_path, mock_page, monkeypatch):
    """Casing must not spuriously reject a path that is inside the root.

    macOS APFS and Windows are case-insensitive by default. ``normcase`` is a no-op
    on POSIX, so stand in a case-folding implementation to exercise the comparison
    the way those filesystems present it.
    """
    root = tmp_path / "MEDIA_ROOT"
    root.mkdir()
    monkeypatch.setattr(os.path, "normcase", str.lower)

    wrapper = WapiWrapper(mock_page, media_root=root)

    # Same directory, different casing.
    returned = wrapper._save_bytes(str(tmp_path / "media_root" / "f.bin"), b"x")

    assert Path(returned).read_bytes() == b"x"
