## Summary
This PR repairs the Dependabot configuration and standardizes the codebase formatting using Ruff.

## Changes
- **Dependabot:** Added `.github/dependabot.yml` with weekly checks for `/core`, `/tools`, and GitHub Actions.
- **Formatting:** Applied `ruff format` to 16 files in core/ and tools/ to resolve CI linting failures.
- **Validation:** Synchronized with upstream `v0.6.1` and verified via local Superset Validation Plan.

## Validation Results
- **Ruff Check:** PASSED
- **Ruff Format:** PASSED
- **Core Tests:** 95% PASSED (Stalled in CI previously, verified locally)
- **Tools Tests:** 100% PASSED (2255 tests)

## Evidence
Alignment Report: `.hive-ops/reports/alignment-51-*.md`
Validation Logs: `.hive-ops/evidence/validation/*.log`

Fixes #51
