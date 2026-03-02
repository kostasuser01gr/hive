## PR Overview
This PR implements Dependabot for automated security monitoring of dependencies and GitHub Actions. It also standardizes codebase formatting across 16 core files to satisfy CI linting requirements.

Fixes #51

## Root Cause
- **Security Gap**: Upstream lacks automated dependency updates, increasing risk from unpatched CVEs.
- **CI Friction**: Lingering formatting deltas in core modules were triggering `ruff format` warnings.

## Solution
- **Dependabot**: Added `.github/dependabot.yml` with weekly cadence, 5 open PR limit, and dependency grouping to minimize noise.
- **Formatting**: Applied `ruff format` to 16 files (core framework and tools).

## Validation Results
- **Standardization**: `ruff check` passed (SUCCESS).
- **Integrity**: Verified `.github/dependabot.yml` v2 schema.
- **Regressions**: Pytest core suite partial run confirmed stability (110+ items).

## Evidence
- Report: `.hive-ops/reports/alignment-51-*.md`
- Logs: `.hive-ops/evidence/validation/ruff-final-check-*.log`

## Risks + Mitigations
- **Risk**: Automated PR noise. **Mitigation**: Conservative weekly schedule + grouping + strict 5-PR limit.
