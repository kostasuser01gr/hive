## PR Overview
This PR implements Dependabot configuration for the fork to automate security updates for Python dependencies and GitHub Actions.

Fixes #47

## Root Cause
Both official and fork repositories lacked automated dependency monitoring, increasing the risk of unpatched CVEs in core libraries (litellm, anthropic).

## Solution
- Added `.github/dependabot.yml`.
- Configured weekly updates for `pip` in `/core` and `/tools`.
- Configured weekly updates for `github-actions`.

## Validation Results
- **Lint**: `ruff check` passed (SUCCESS) after surgical repair of lingering E501 violations.
- **YAML**: Verified `dependabot.yml` structure.
- **Regression**: Standardized codebase formatting previously committed to main to ensure a clean PR diff.

## Evidence
- Logs: `.hive-ops/evidence/validation/ruff-final-audit-*.log`
- Report: `.hive-ops/reports/alignment-47-*.md`

## Risks + Mitigations
- **Risk**: PR noise. **Mitigation**: Set to weekly schedule and limited to 10 open PRs.
