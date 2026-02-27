## Summary
- Prevents `email_tool.py` from crashing tool registration when the optional `resend` library is missing.
- Addresses [#4816](https://github.com/aden-hive/hive/issues/4816)

## Root Cause
`email_tool.py` had a top-level `import resend`. If the package was not installed, importing the module (which happens during `register_all_tools()`) would raise `ModuleNotFoundError`, crashing the entire tool server.

## Solution
- Removed the top-level `import resend`.
- Added a lazy `import resend` inside `_send_via_resend`, guarded by `try/except ImportError`.
- Returns a helpful error message when `resend` is missing, following the established pattern in `excel_tool.py` and other tools.

## Validation
**Local Testing:**
```bash
# Verify email_tool can be imported without resend installed
python3 repro_4816.py

# Run updated tests
cd tools && uv run pytest tests/tools/test_email_tool.py -v
```

**Results:**
- ✅ Lint: Passed
- ✅ Tests: Passed (38 tests, 1 added)
- ✅ Build: N/A (Python tool)

**Evidence:** See `validation-evidence/` in commit history.

## Risk Assessment
**Potential regressions:**
- None. The fix only affects environments where `resend` is missing, preventing a crash. Environments with `resend` installed will continue to work as expected.

## Additional Context
Standardized the error message to match other optional dependency tools.

Fixes #4816
