## Summary
Prevent `IndexError` crashes in the LiteLLM integration by adding bounds checking for `response.choices` before accessing the first element.

## Issue
Fixes #4767

## Root Cause
Several locations in `litellm.py` assumed `response.choices` would always be non-empty, leading to `IndexError: list index out of range` when the LLM returns an empty response (e.g., due to specific retry conditions or provider behavior).

## Solution
Added safety checks using ternary operators or explicit `if not response.choices` guards across `complete()`, `complete_with_tools()`, `acomplete()`, and `acomplete_with_tools()`.

### Changes Made
- `core/framework/llm/litellm.py`: Added defensive checks for `response.choices[0]` access.

## Validation
- Created a reproduction script with `unittest.mock` to verify empty `choices` handling.
- `make check`: PASS
- `make test` (LiteLLM tests): PASS (64 passed, 9 skipped)
