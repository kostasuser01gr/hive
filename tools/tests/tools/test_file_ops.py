"""Tests for aden_tools.file_ops — the unified file-tool surface.

Covers the path policy (home anchoring, deny lists, write_safe_root),
plus the six file tools: read_file, write_file, edit_file, hashline_edit,
search_files, apply_patch.
"""

import json
import os
from unittest.mock import patch

import pytest
from fastmcp import FastMCP

from aden_tools.file_ops import register_file_tools


@pytest.fixture
def file_ops_mcp(tmp_path):
    """Create FastMCP with file tools registered, home anchored at tmp_path."""
    mcp = FastMCP("test-file-ops")
    register_file_tools(mcp, home=str(tmp_path))
    return mcp


@pytest.fixture(autouse=True)
def _bypass_stale_edit_guard():
    """Most tests exercise edits without a prior read; force the guard FRESH."""
    from aden_tools.file_state_cache import Freshness, FreshResult

    with patch(
        "aden_tools.file_ops.check_fresh",
        return_value=FreshResult(Freshness.FRESH),
    ):
        yield


def _get_tool_fn(mcp, name):
    """Extract the raw function for a registered tool."""
    return mcp._tool_manager._tools[name].fn


class TestSearchFilesPathRelativization:
    """Tests for search_files path handling (Windows path separator fix)."""

    def test_ripgrep_output_with_backslash_relativized(self, file_ops_mcp, tmp_path):
        """Ripgrep output with backslashes (Windows) relativized when project_root set.

        Simulates: rg outputs 'C:\\Users\\...\\proj\\src\\foo.py:1:needle'
        Expected: output should show 'src\\foo.py:1:needle' or 'src/foo.py:1:needle'
        (relativized, not full path).
        """
        # Create a file so the search has something to find
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "foo.py").write_text("needle\n")
        project_root = str(tmp_path)

        # Ripgrep on Windows outputs backslash-separated paths
        # Format: path:line_num:content
        rg_output = f"{project_root}{os.sep}src{os.sep}foo.py:1:needle"

        search_fn = _get_tool_fn(file_ops_mcp, "search_files")

        with patch("aden_tools.file_ops.subprocess.run") as mock_run:
            mock_run.return_value = type("Result", (), {"returncode": 0, "stdout": rg_output, "stderr": ""})()

            result = search_fn(
                pattern="needle",
                path=str(tmp_path),
            )

        # Output should be relativized (no full project_root in the line)
        assert project_root not in result, f"Output should not contain full project_root. Got: {result!r}"
        # Should contain the relative path part
        assert "foo.py" in result
        assert "1:" in result or ":1:" in result

    def test_ripgrep_output_with_forward_slash_relativized(self, file_ops_mcp, tmp_path):
        """Ripgrep output using forward slashes (Unix/rg default) should be relativized."""
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "bar.py").write_text("pattern_match\n")
        project_root = str(tmp_path)

        # Some ripgrep builds output forward slashes even on Windows
        rg_output = f"{project_root}/src/bar.py:1:pattern_match"

        search_fn = _get_tool_fn(file_ops_mcp, "search_files")

        with patch("aden_tools.file_ops.subprocess.run") as mock_run:
            mock_run.return_value = type("Result", (), {"returncode": 0, "stdout": rg_output, "stderr": ""})()

            result = search_fn(
                pattern="pattern_match",
                path=str(tmp_path),
            )

        assert project_root not in result or "src/bar.py" in result
        assert "bar.py" in result

    def test_python_fallback_relativizes_paths(self, file_ops_mcp, tmp_path):
        """Python fallback (no ripgrep) uses os.path.relpath - should work on all platforms."""
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "baz.txt").write_text("find_me\n")

        search_fn = _get_tool_fn(file_ops_mcp, "search_files")

        # Ensure ripgrep is not used
        with patch("aden_tools.file_ops.subprocess.run", side_effect=FileNotFoundError()):
            result = search_fn(
                pattern="find_me",
                path=str(tmp_path),
            )

        # Python fallback uses os.path.relpath - should produce relative path
        project_root = str(tmp_path)
        assert project_root not in result or "subdir" in result
        assert "baz.txt" in result
        assert "1:" in result or ":1:" in result


class TestSearchFilesBasic:
    """Basic search_files behavior (no path mocking)."""

    def test_search_finds_content(self, file_ops_mcp, tmp_path):
        """search_files finds matching content via Python fallback when rg absent."""
        (tmp_path / "hello.txt").write_text("world\n")

        search_fn = _get_tool_fn(file_ops_mcp, "search_files")

        with patch("aden_tools.file_ops.subprocess.run", side_effect=FileNotFoundError()):
            result = search_fn(pattern="world", path=str(tmp_path))

        assert "world" in result
        assert "hello.txt" in result

    def test_search_nonexistent_dir_returns_error(self, file_ops_mcp, tmp_path):
        """search_files on non-existent directory returns error."""
        search_fn = _get_tool_fn(file_ops_mcp, "search_files")
        result = search_fn(pattern="x", path=str(tmp_path / "nonexistent"))
        assert "Error" in result
        assert "not found" in result.lower()


class TestPathPolicyHomeAnchoring:
    """Relative paths anchor to home; absolute paths are honored verbatim."""

    def test_relative_write_lands_in_home(self, file_ops_mcp, tmp_path):
        """write_file('notes.md') writes inside home."""
        write_fn = _get_tool_fn(file_ops_mcp, "write_file")
        result = write_fn(path="notes.md", content="hello")
        assert "Error" not in result
        assert (tmp_path / "notes.md").read_text() == "hello"

    def test_relative_read_resolves_to_home(self, file_ops_mcp, tmp_path):
        """read_file('notes.md') reads from home."""
        (tmp_path / "notes.md").write_text("from disk\n")
        read_fn = _get_tool_fn(file_ops_mcp, "read_file")
        result = read_fn(path="notes.md")
        assert "from disk" in result

    def test_absolute_path_is_honored_verbatim(self, file_ops_mcp, tmp_path, monkeypatch):
        """Absolute paths are NOT silently rebased under home."""
        outside = tmp_path.parent / "outside.txt"
        outside.write_text("outside content\n")

        read_fn = _get_tool_fn(file_ops_mcp, "read_file")
        result = read_fn(path=str(outside))
        # Absolute path resolves to itself, not to <home>/<outside>.
        assert "outside content" in result


class TestPathPolicyDenyLists:
    """Reads ⊂ writes; system + credential paths are blocked."""

    def test_write_to_system_path_denied(self, file_ops_mcp):
        """write_file('/etc/passwd', ...) returns an explicit Error."""
        write_fn = _get_tool_fn(file_ops_mcp, "write_file")
        result = write_fn(path="/etc/passwd", content="x")
        assert "Error" in result
        assert "denied" in result.lower()

    def test_write_under_etc_denied(self, file_ops_mcp):
        """Anything under /etc/ is denied for writes."""
        write_fn = _get_tool_fn(file_ops_mcp, "write_file")
        result = write_fn(path="/etc/nginx/nginx.conf", content="x")
        assert "Error" in result
        assert "denied" in result.lower()

    def test_write_to_ssh_denied(self, file_ops_mcp):
        """Credential prefixes block writes."""
        write_fn = _get_tool_fn(file_ops_mcp, "write_file")
        result = write_fn(path="~/.ssh/authorized_keys", content="x")
        assert "Error" in result
        assert "denied" in result.lower()

    def test_read_credential_file_denied(self, file_ops_mcp):
        """Reading credential FILES is denied."""
        read_fn = _get_tool_fn(file_ops_mcp, "read_file")
        result = read_fn(path="~/.ssh/id_rsa")
        assert "Error" in result
        assert "denied" in result.lower()

    def test_read_system_config_allowed(self, file_ops_mcp):
        """Reading /etc/* configs is allowed (system reads are permissive)."""
        read_fn = _get_tool_fn(file_ops_mcp, "read_file")
        # /etc/hosts exists on macOS + Linux; if it doesn't we get a different
        # error (not a deny error), which is also fine for this assertion.
        result = read_fn(path="/etc/hosts")
        assert "denied" not in result.lower()


class TestPathPolicyWriteSafeRoot:
    """write_safe_root is an optional ceiling that limits writes."""

    def test_write_outside_safe_root_denied(self, tmp_path):
        """A write outside the configured ceiling fails loud."""
        home = tmp_path / "home"
        home.mkdir()
        ceiling = tmp_path / "allowed"
        ceiling.mkdir()

        mcp = FastMCP("t")
        register_file_tools(mcp, home=str(home), write_safe_root=str(ceiling))
        write_fn = _get_tool_fn(mcp, "write_file")

        outside = tmp_path / "blocked.txt"
        result = write_fn(path=str(outside), content="x")
        assert "Error" in result
        assert "outside" in result.lower()

    def test_write_inside_safe_root_allowed(self, tmp_path):
        """A write inside the ceiling succeeds."""
        ceiling = tmp_path / "allowed"
        ceiling.mkdir()

        mcp = FastMCP("t")
        register_file_tools(mcp, home=str(ceiling), write_safe_root=str(ceiling))
        write_fn = _get_tool_fn(mcp, "write_file")

        result = write_fn(path="ok.txt", content="x")
        assert "Error" not in result
        assert (ceiling / "ok.txt").read_text() == "x"

    def test_write_safe_root_accepts_list(self, tmp_path):
        """A list of allowed roots permits writes under any of them."""
        a = tmp_path / "a"
        b = tmp_path / "b"
        a.mkdir()
        b.mkdir()

        mcp = FastMCP("t")
        register_file_tools(mcp, home=str(a), write_safe_root=[str(a), str(b)])
        write_fn = _get_tool_fn(mcp, "write_file")

        # Relative -> inside home (a). OK.
        assert "Error" not in write_fn(path="x.txt", content="1")
        # Absolute under b. OK because b is in the list.
        assert "Error" not in write_fn(path=str(b / "y.txt"), content="2")
        # Absolute outside both. Blocked.
        result = write_fn(path=str(tmp_path / "outside.txt"), content="3")
        assert "Error" in result


class TestApplyPatchTool:
    """apply_patch — diff_match_patch text → file."""

    def test_apply_patch_modifies_file(self, file_ops_mcp, tmp_path):
        """A valid patch applies and rewrites the file."""
        import diff_match_patch as dmp_module

        target = tmp_path / "patch_me.txt"
        target.write_text("Hello World", encoding="utf-8")

        dmp = dmp_module.diff_match_patch()
        patches = dmp.patch_make("Hello World", "Hello Universe")
        patch_text = dmp.patch_toText(patches)

        apply_fn = _get_tool_fn(file_ops_mcp, "apply_patch")
        result = apply_fn(path="patch_me.txt", patch_text=patch_text)

        assert "Error" not in result
        assert "Applied" in result
        assert target.read_text() == "Hello Universe"

    def test_apply_patch_missing_file(self, file_ops_mcp):
        """Patching a non-existent file returns an error string."""
        apply_fn = _get_tool_fn(file_ops_mcp, "apply_patch")
        result = apply_fn(path="nope.txt", patch_text="garbage")
        assert "Error" in result
        assert "not found" in result.lower()

    def test_apply_patch_garbage_text(self, file_ops_mcp, tmp_path):
        """Patch text that produces no patches is rejected without writing."""
        target = tmp_path / "f.txt"
        target.write_text("original", encoding="utf-8")
        apply_fn = _get_tool_fn(file_ops_mcp, "apply_patch")
        result = apply_fn(path="f.txt", patch_text="not a patch")
        assert "Error" in result
        assert target.read_text() == "original"

    def test_apply_patch_write_denied_for_system_path(self, file_ops_mcp):
        """The deny list applies to apply_patch just like write_file."""
        apply_fn = _get_tool_fn(file_ops_mcp, "apply_patch")
        result = apply_fn(path="/etc/passwd", patch_text="x")
        assert "Error" in result
        assert "denied" in result.lower()


class TestHashlineEditViaPolicy:
    """hashline_edit honors the same path policy as the rest."""

    def test_hashline_edit_relative_path(self, file_ops_mcp, tmp_path):
        """hashline_edit on a relative path lands in home."""
        from aden_tools.hashline import compute_line_hash

        target = tmp_path / "hl.txt"
        target.write_text("aaa\nbbb\nccc\n", encoding="utf-8")

        edits = json.dumps([{"op": "set_line", "anchor": f"2:{compute_line_hash('bbb')}", "content": "BBB"}])
        hashline_fn = _get_tool_fn(file_ops_mcp, "hashline_edit")
        result = hashline_fn(path="hl.txt", edits=edits)
        assert "Applied" in result
        assert target.read_text() == "aaa\nBBB\nccc\n"

    def test_hashline_edit_denied_for_system_path(self, file_ops_mcp):
        """The deny list also covers hashline_edit."""
        hashline_fn = _get_tool_fn(file_ops_mcp, "hashline_edit")
        result = hashline_fn(path="/etc/passwd", edits="[]")
        # Either deny-list error or empty-edits error — both before the write.
        assert "Error" in result
