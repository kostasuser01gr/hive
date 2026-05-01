"""Tests for the remaining file_system_toolkits — execute_command_tool only.

The file tools (read_file, write_file, edit_file, hashline_edit, search_files,
apply_patch) all live in aden_tools.file_ops and are tested in test_file_ops.py.
"""

import asyncio
import os
import sys
from unittest.mock import patch

import pytest
from fastmcp import FastMCP


@pytest.fixture
def mcp():
    """Create a FastMCP instance."""
    return FastMCP("test-server")


@pytest.fixture
def mock_workspace():
    """Mock agent ID for the shell tool."""
    return {"agent_id": "test-agent"}


@pytest.fixture
def mock_secure_path(tmp_path):
    """Patch the shell tool's sandbox resolver onto tmp_path."""

    def _get_sandboxed_path(path, agent_id):
        return os.path.join(tmp_path, path)

    with (
        patch(
            "aden_tools.tools.file_system_toolkits.execute_command_tool.execute_command_tool.get_sandboxed_path",
            side_effect=_get_sandboxed_path,
        ),
        patch(
            "aden_tools.tools.file_system_toolkits.execute_command_tool.execute_command_tool.AGENT_SANDBOXES_DIR",
            str(tmp_path),
        ),
    ):
        yield


class TestExecuteCommandTool:
    """Tests for execute_command_tool."""

    @pytest.fixture
    def execute_command_fn(self, mcp):
        from aden_tools.tools.file_system_toolkits.execute_command_tool import register_tools

        register_tools(mcp)
        return mcp._tool_manager._tools["execute_command_tool"].fn

    async def test_execute_simple_command(self, execute_command_fn, mock_workspace, mock_secure_path):
        """Executing a simple command returns output."""
        result = await execute_command_fn(command="echo 'Hello World'", **mock_workspace)

        assert result["success"] is True
        assert result["return_code"] == 0
        assert "Hello World" in result["stdout"]

    async def test_execute_failing_command(self, execute_command_fn, mock_workspace, mock_secure_path):
        """Executing a failing command returns non-zero exit code."""
        result = await execute_command_fn(command="exit 1", **mock_workspace)

        assert result["success"] is True
        assert result["return_code"] == 1

    async def test_execute_command_with_stderr(self, execute_command_fn, mock_workspace, mock_secure_path):
        """Executing a command that writes to stderr captures it."""
        result = await execute_command_fn(command="echo 'error message' >&2", **mock_workspace)

        assert result["success"] is True
        assert "error message" in result.get("stderr", "")

    async def test_execute_command_list_files(self, execute_command_fn, mock_workspace, mock_secure_path, tmp_path):
        """Executing ls command lists files."""
        (tmp_path / "testfile.txt").write_text("content", encoding="utf-8")

        result = await execute_command_fn(command=f"ls {tmp_path}", **mock_workspace)

        assert result["success"] is True
        assert result["return_code"] == 0
        assert "testfile.txt" in result["stdout"]

    async def test_execute_command_with_pipe(self, execute_command_fn, mock_workspace, mock_secure_path):
        """Executing a command with pipe works correctly."""
        result = await execute_command_fn(command="echo 'hello world' | tr 'a-z' 'A-Z'", **mock_workspace)

        assert result["success"] is True
        assert result["return_code"] == 0
        assert "HELLO WORLD" in result["stdout"]

    @pytest.fixture
    def bash_output_fn(self, mcp):
        from aden_tools.tools.file_system_toolkits.execute_command_tool import register_tools

        register_tools(mcp)
        return mcp._tool_manager._tools["bash_output"].fn

    @pytest.fixture
    def bash_kill_fn(self, mcp):
        from aden_tools.tools.file_system_toolkits.execute_command_tool import register_tools

        register_tools(mcp)
        return mcp._tool_manager._tools["bash_kill"].fn

    async def test_per_call_timeout_overrides_default(self, execute_command_fn, mock_workspace, mock_secure_path):
        """A per-call timeout under the default kills the command early."""
        import time

        start = time.monotonic()
        result = await execute_command_fn(
            command="sleep 10",
            timeout_seconds=1,
            **mock_workspace,
        )
        elapsed = time.monotonic() - start

        assert result.get("timed_out") is True
        assert "1 seconds" in result.get("error", "")
        assert elapsed < 5, f"timeout did not kill the command promptly ({elapsed:.2f}s)"

    async def test_timeout_is_clamped_upwards(self, execute_command_fn, mock_workspace, mock_secure_path):
        """A timeout above the 600s ceiling is silently clamped."""
        result = await execute_command_fn(
            command="echo fast",
            timeout_seconds=99999,
            **mock_workspace,
        )
        assert result["success"] is True
        assert "fast" in result["stdout"]

    async def test_event_loop_unblocked_while_command_runs(self, execute_command_fn, mock_workspace, mock_secure_path):
        """The event loop keeps servicing other tasks while a bash command runs."""
        ticks = 0

        async def ticker():
            nonlocal ticks
            for _ in range(20):
                await asyncio.sleep(0.05)
                ticks += 1

        ticker_task = asyncio.create_task(ticker())
        result = await execute_command_fn(command="sleep 0.5", **mock_workspace)
        await ticker_task

        assert result["success"] is True
        assert ticks >= 5, f"event loop looked blocked during subprocess (only {ticks} ticks in 1s)"

    async def test_background_job_start_poll_and_complete(
        self,
        execute_command_fn,
        bash_output_fn,
        mock_workspace,
        mock_secure_path,
    ):
        """A run_in_background job can be started, polled, and reports its exit status."""
        py_script = (
            "import time,sys;"
            "print('one');sys.stdout.flush();time.sleep(0.1);"
            "print('two');sys.stdout.flush();time.sleep(0.1);"
            "print('three')"
        )
        start_result = await execute_command_fn(
            command=f'"{sys.executable}" -c "{py_script}"',
            run_in_background=True,
            **mock_workspace,
        )
        assert start_result["background"] is True
        job_id = start_result["id"]

        deadline = asyncio.get_event_loop().time() + 5.0
        seen_text = ""
        while asyncio.get_event_loop().time() < deadline:
            poll = await bash_output_fn(id=job_id, **mock_workspace)
            seen_text += poll["stdout"]
            if poll["status"].startswith("exited"):
                break
            await asyncio.sleep(0.05)

        assert "one" in seen_text
        assert "two" in seen_text
        assert "three" in seen_text
        assert poll["status"] == "exited(0)"

    async def test_background_job_kill(
        self,
        execute_command_fn,
        bash_output_fn,
        bash_kill_fn,
        mock_workspace,
        mock_secure_path,
    ):
        """bash_kill terminates a long-running background job."""
        start_result = await execute_command_fn(
            command="sleep 30",
            run_in_background=True,
            **mock_workspace,
        )
        job_id = start_result["id"]

        kill_result = await bash_kill_fn(id=job_id, **mock_workspace)
        assert kill_result["id"] == job_id
        assert "terminated" in kill_result["status"] or "killed" in kill_result["status"]

        poll = await bash_output_fn(id=job_id, **mock_workspace)
        assert "no background job" in poll.get("error", "")

    async def test_bash_output_isolated_across_agents(self, execute_command_fn, bash_output_fn, mock_secure_path):
        """Agent A's job id is not reachable from agent B."""
        start = await execute_command_fn(
            command="sleep 5",
            run_in_background=True,
            agent_id="agent-A",
        )
        poll_b = await bash_output_fn(id=start["id"], agent_id="agent-B")
        assert "no background job" in poll_b.get("error", "")

        from aden_tools.tools.file_system_toolkits.execute_command_tool import background_jobs

        await background_jobs.clear_agent("agent-A")
