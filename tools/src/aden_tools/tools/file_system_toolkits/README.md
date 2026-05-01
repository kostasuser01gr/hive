# File System Toolkits (post-consolidation)

This package now contains only the shell tool. **All file tools live in
`aden_tools.file_ops`** (read_file, write_file, edit_file, hashline_edit,
search_files, apply_patch) — they share one path policy and one home dir.

## Sub-modules

| Module | Description |
|--------|-------------|
| `execute_command_tool/` | Shell command execution with sanitization (run_command, bash_kill, bash_output) |
| `command_sanitizer.py` | Validates and sanitizes shell command strings |
| `security.py` | Sandbox path resolver still used by execute_command_tool |

## File tools

For read/write/edit/search/patch, see `aden_tools.file_ops` and call
`register_file_tools(mcp, home=..., write_safe_root=...)` once. The path
model is uniform across all six tools:

- Relative paths anchor to `home`.
- Absolute paths are honored verbatim.
- Writes to system / credential paths are denied; reads of credential
  files are denied; system config files (`/etc/nginx/...`) remain readable.
- `write_safe_root` (str or list) is an optional hard ceiling for writes.

## Usage

```python
from aden_tools.file_ops import register_file_tools

register_file_tools(mcp, home="/path/to/agent/home")
```

For shell:

```python
from aden_tools.tools.file_system_toolkits.execute_command_tool import register_tools as register_shell

register_shell(mcp)
```
