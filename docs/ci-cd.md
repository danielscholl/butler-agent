# CI/CD Pipeline Documentation

This document describes the GitHub Actions-based CI/CD pipeline for Butler Agent, including workflows, best practices, and troubleshooting.

## Overview

Butler Agent uses three primary GitHub Actions workflows:

1. **CI Workflow** - Automated quality checks and testing
2. **Security Workflow** - Security scanning and vulnerability detection
3. **Release Workflow** - Automated versioning and release management

Additionally, **Dependabot** automates dependency updates.

## CI Workflow

### Purpose

The CI workflow ensures code quality by running automated checks on every push to `main` and on all pull requests. It validates formatting, linting, type safety, and test coverage.

### Triggers

- Push to `main` branch
- Pull requests to `main` branch
- Manual trigger via `workflow_dispatch`

### Checks Performed

#### 1. Black Formatting Check

Validates that code follows consistent formatting standards.

```bash
uv run black --check src/butler/ tests/ --diff --color
```

**Fix locally:**
```bash
uv run black src/butler/ tests/
```

#### 2. Ruff Linting

Checks for code quality issues, potential bugs, and style violations.

```bash
uv run ruff check src/butler/ tests/
```

**Fix locally:**
```bash
# See specific errors
uv run ruff check src/butler/ tests/

# Auto-fix many issues
uv run ruff check src/butler/ tests/ --fix
```

#### 3. MyPy Type Checking

Ensures type safety and catches type-related errors.

```bash
uv run mypy src/butler --pretty --color-output
```

**Fix locally:**
- Add type hints to functions and variables
- Fix type mismatches
- Use `# type: ignore` only when absolutely necessary (with comment explaining why)

#### 4. Pytest with Coverage

Runs test suite and enforces minimum 60% code coverage.

```bash
uv run pytest \
  --cov=src/butler \
  --cov-report=xml \
  --cov-report=term-missing \
  --cov-fail-under=60 \
  -v \
  --tb=short
```

**Fix locally:**
```bash
# Run tests
uv run pytest -v

# Run with coverage report
uv run pytest --cov=src/butler --cov-report=html
# Open htmlcov/index.html to see uncovered lines

# Run specific test file
uv run pytest tests/unit/test_agent.py -v
```

### Quality Check Summary

At the end of each CI run, a summary shows the status of all checks with emojis (✅ or ❌) and provides actionable guidance for failures.

### Artifacts

On test failure, the following artifacts are uploaded (retained for 7 days):
- `coverage.xml` - Coverage report
- `.coverage` - Raw coverage data
- Log files

### Coverage Reporting

Test coverage is automatically uploaded to Codecov (if configured) for Python 3.12 runs. This provides:
- Coverage trends over time
- Line-by-line coverage visualization
- Pull request coverage diff

## Security Workflow

### Purpose

The security workflow performs automated security scanning to detect vulnerabilities, analyze code for security issues, and generate Software Bill of Materials (SBOM) for supply chain security.

### Triggers

- Push to `main` branch
- Pull requests to `main` branch (both `pull_request` and `pull_request_target` for forks)
- Weekly schedule (Mondays at 00:00 UTC)
- Manual trigger via `workflow_dispatch`

### Jobs

#### 1. Dependency Review

**Runs on:** Pull requests only

Scans dependency changes in pull requests for known vulnerabilities.

- Uses GitHub's `dependency-review-action`
- Blocks PRs with dependencies that have vulnerabilities rated "moderate" or higher
- Requires GitHub Advanced Security (continues with warning if not enabled)

**Interpreting Results:**
- **Blocked**: PR introduces dependency with known vulnerability
- **Action**: Update to a patched version or find alternative package

#### 2. SBOM Generation

**Runs on:** All events (PRs, pushes, schedule, manual)

Generates a Software Bill of Materials (SBOM) in CycloneDX JSON format.

**Why SBOMs matter:**
- Supply chain security transparency
- Vulnerability tracking
- License compliance
- Audit requirements

**Accessing SBOM:**
1. Go to GitHub Actions run
2. Find "Generate SBOM" job
3. Download artifact: `sbom-{SHA}.json`

**SBOM Retention:** 90 days

#### 3. CodeQL Analysis

**Runs on:** All events (PRs, pushes, schedule, manual)

Performs semantic code analysis to detect security vulnerabilities and code quality issues.

**Query Suites:** `security-and-quality`

**Languages:** Python

**Configuration:** `.github/codeql/codeql-config.yml`

**Common Findings:**
- SQL injection vulnerabilities
- Command injection risks
- Hardcoded credentials
- Insecure deserialization
- Path traversal issues
- Code quality issues (unused variables, etc.)

**False Positives:**
Some findings may be false positives, especially in test code. These are suppressed via query filters in the CodeQL configuration.

**Viewing Results:**
1. Go to repository's "Security" tab
2. Click "Code scanning alerts"
3. Review findings and dismiss false positives as needed

## Release Workflow

### Purpose

Automates semantic versioning, changelog generation, and package distribution using release-please.

### Triggers

- Push to `main` branch
- Manual trigger via `workflow_dispatch`

### How It Works

#### 1. Conventional Commits

Release-please analyzes commit messages following the [Conventional Commits](https://www.conventionalcommits.org/) specification:

**Commit Types:**

| Type | Description | Version Bump | Example |
|------|-------------|--------------|---------|
| `feat:` | New feature | Minor (0.1.0 → 0.2.0) | `feat: add cluster deletion confirmation` |
| `fix:` | Bug fix | Patch (0.1.0 → 0.1.1) | `fix: handle missing kubeconfig gracefully` |
| `feat!:` or `BREAKING CHANGE:` | Breaking change | Major (1.0.0 → 2.0.0) | `feat!: change CLI argument structure` |
| `docs:` | Documentation | No version bump | `docs: update README with examples` |
| `test:` | Tests | No version bump | `test: add unit tests for agent` |
| `chore:` | Maintenance | No version bump | `chore: update dependencies` |
| `refactor:` | Refactoring | No version bump | `refactor: simplify error handling` |
| `ci:` | CI/CD changes | No version bump | `ci: add security scanning workflow` |
| `perf:` | Performance | No version bump | `perf: optimize cluster status checks` |

**Note:** Pre-1.0.0 versions use different rules:
- `feat:` bumps minor version (0.1.0 → 0.2.0)
- `feat!:` bumps minor version (0.1.0 → 0.2.0)
- After 1.0.0, `feat!:` will bump major version (1.0.0 → 2.0.0)

#### 2. Release PR Creation

When commits with version-bumping types are merged to `main`:

1. Release-please creates or updates a release PR
2. The PR includes:
   - Updated version in `pyproject.toml`
   - Generated CHANGELOG.md with all changes
   - Grouped by commit type
3. The workflow automatically updates `uv.lock` with the new version

#### 3. Release Creation

When the release PR is merged:

1. Release-please creates a GitHub release with:
   - Tag (e.g., `v0.2.0`)
   - Release notes from changelog
2. The `build-artifacts` job runs:
   - Builds Python wheel (`.whl`) and source distribution (`.tar.gz`)
   - Uploads artifacts to GitHub release
   - Retains artifacts for 90 days

### Release Process Step-by-Step

**Developer Workflow:**

1. Make changes and commit with conventional commit messages
   ```bash
   git commit -m "feat: add cluster status monitoring"
   ```

2. Create PR and merge to `main` (after CI passes)

3. Release-please automatically creates/updates release PR

4. Review the release PR:
   - Check version bump is correct
   - Review changelog entries
   - Verify `uv.lock` was updated

5. Merge the release PR

6. GitHub release is created automatically with distribution packages

**Manual Release Trigger:**

If needed, you can manually trigger the release workflow:
```bash
gh workflow run release.yml
```

### Version Strategy

Butler Agent follows semantic versioning with pre-1.0 adjustments:

- **Current Phase:** 0.x.x (pre-1.0, development phase)
- **Breaking Changes:** Bump minor version (0.1.0 → 0.2.0)
- **New Features:** Bump minor version (0.1.0 → 0.2.0)
- **Bug Fixes:** Bump patch version (0.1.0 → 0.1.1)

**After 1.0.0 Release:**
- **Breaking Changes:** Bump major version (1.0.0 → 2.0.0)
- **New Features:** Bump minor version (1.0.0 → 1.1.0)
- **Bug Fixes:** Bump patch version (1.0.0 → 1.0.1)

## Dependabot

### Purpose

Automates dependency updates to keep packages secure and up-to-date.

### Configuration

**Schedule:** Weekly on Mondays at 04:00 UTC

**Ecosystems:**
1. Python (uv package manager)
2. GitHub Actions

### Dependency Grouping

To reduce PR noise, dependencies are grouped:

#### Python Dev Dependencies Group

**Group name:** `python-dev`

**Includes:**
- pytest and pytest plugins
- mypy
- black
- ruff

**Why grouped:** These tools are frequently updated and tested together

#### Python Production Dependencies Group

**Group name:** `python-prod`

**Includes:** All other Python dependencies (excluding dev tools)

**Why grouped:** Production dependencies should be updated and tested together

#### GitHub Actions

**Not grouped** - Each action update gets its own PR (limit: 3 concurrent)

**Why separate:** Action updates need individual review for breaking changes

### Reviewing Dependabot PRs

1. **Check CI Status:** Ensure all CI checks pass
2. **Review Changes:** Check changelogs for breaking changes
3. **Test Locally (if needed):**
   ```bash
   gh pr checkout <pr-number>
   uv sync
   uv run pytest
   ```
4. **Merge:** If CI passes and no issues found, merge the PR

### Dependabot Settings

**Open PR Limit:**
- Python dependencies: 5 concurrent PRs
- GitHub Actions: 3 concurrent PRs

**Auto-merge (optional):**
You can enable GitHub's auto-merge for Dependabot PRs with passing CI:
```bash
gh pr merge <pr-number> --auto --merge
```

## Troubleshooting

### CI Workflow Issues

#### Issue: `uv sync --frozen` fails

**Cause:** `uv.lock` is out of date

**Solution:**
```bash
uv lock
git add uv.lock
git commit -m "chore: update uv.lock"
git push
```

#### Issue: Coverage below 60% threshold

**Cause:** Insufficient test coverage

**Solution:**
1. Check coverage report to find uncovered lines:
   ```bash
   uv run pytest --cov=src/butler --cov-report=html
   open htmlcov/index.html
   ```
2. Add tests for uncovered code
3. Or adjust threshold in `.github/workflows/ci.yml` (line 79):
   ```yaml
   --cov-fail-under=60  # Adjust this value
   ```

#### Issue: Black formatting check fails

**Cause:** Code not formatted consistently

**Solution:**
```bash
uv run black src/butler/ tests/
git add .
git commit -m "style: format code with black"
git push
```

#### Issue: Ruff linting errors

**Cause:** Code quality issues detected

**Solution:**
1. View specific errors:
   ```bash
   uv run ruff check src/butler/ tests/
   ```
2. Auto-fix many issues:
   ```bash
   uv run ruff check src/butler/ tests/ --fix
   ```
3. Fix remaining issues manually
4. Commit changes

#### Issue: MyPy type errors

**Cause:** Type inconsistencies in code

**Solution:**
1. Review error messages carefully
2. Add missing type hints
3. Fix type mismatches
4. Use `# type: ignore[<error-code>]` sparingly with explanation

### Security Workflow Issues

#### Issue: CodeQL false positives

**Cause:** CodeQL flags test code or legitimate patterns

**Solution:**
Add query filter to `.github/codeql/codeql-config.yml`:
```yaml
query-filters:
  - exclude:
      id: py/your-query-id
      paths:
        - tests/**/*.py
```

#### Issue: Dependency review blocks PR

**Cause:** New dependency has known vulnerability

**Solution:**
1. Check for patched version of the dependency
2. Update to patched version in `pyproject.toml`
3. Run `uv lock`
4. If no patch available, consider alternative package

#### Issue: SBOM generation fails

**Cause:** CycloneDX installation or environment issues

**Solution:**
1. Check workflow logs for specific error
2. Ensure `uv sync` succeeds
3. Test locally:
   ```bash
   uv pip install cyclonedx-bom
   uv run cyclonedx-py environment -o sbom.json
   ```

### Release Workflow Issues

#### Issue: Release PR not created

**Cause:** Commits don't follow conventional commit format

**Solution:**
1. Check recent commit messages on `main`
2. Ensure commits use types: `feat:`, `fix:`, etc.
3. Trigger workflow manually:
   ```bash
   gh workflow run release.yml
   ```

#### Issue: Release PR doesn't update version

**Cause:** Only non-version-bumping commits (docs, test, chore without breaking changes)

**Solution:**
This is expected behavior. Version only bumps for `feat:` and `fix:` commits.

#### Issue: Build artifacts job fails

**Cause:** Build configuration issue or package structure problem

**Solution:**
1. Test build locally:
   ```bash
   uv pip install --system build
   python -m build
   ls -la dist/
   ```
2. Check `pyproject.toml` for build configuration errors
3. Review workflow logs for specific error

#### Issue: uv.lock not updated in release PR

**Cause:** Workflow step failed or no lock changes needed

**Solution:**
1. Check release workflow logs
2. Manually update lock in release PR if needed:
   ```bash
   gh pr checkout <release-pr-number>
   uv lock
   git add uv.lock
   git commit -m "chore: update uv.lock for release"
   git push
   ```

### Dependabot Issues

#### Issue: Dependabot PRs have merge conflicts

**Cause:** Manual changes to dependencies or lockfile

**Solution:**
1. Close the Dependabot PR (don't merge)
2. Manually update the dependency:
   ```bash
   # Update specific package
   uv pip install --upgrade <package-name>
   uv lock
   git add pyproject.toml uv.lock
   git commit -m "chore: update <package-name>"
   git push
   ```
3. Dependabot will close its PR automatically

#### Issue: Dependabot PRs fail CI

**Cause:** Dependency update introduces breaking changes

**Solution:**
1. Review dependency changelog
2. Update code to handle breaking changes
3. Push fixes to the Dependabot branch:
   ```bash
   gh pr checkout <dependabot-pr-number>
   # Make fixes
   git commit -am "fix: handle breaking changes in <package>"
   git push
   ```

## Best Practices

### For Developers

1. **Run quality checks locally before pushing:**
   ```bash
   uv run black src/butler/ tests/
   uv run ruff check src/butler/ tests/ --fix
   uv run mypy src/butler
   uv run pytest --cov=src/butler --cov-fail-under=60
   ```

2. **Use conventional commit messages:**
   - Be specific about what changed
   - Use correct type prefix
   - Include breaking change markers when appropriate

3. **Review CI failures promptly:**
   - Check quality check summary for actionable guidance
   - Fix issues and push to update PR

4. **Keep PRs focused:**
   - One feature or fix per PR
   - Makes CI results easier to interpret
   - Simplifies review process

### For Maintainers

1. **Review Dependabot PRs weekly:**
   - Keep dependencies up to date
   - Reduces security vulnerabilities
   - Prevents dependency drift

2. **Monitor security scanning results:**
   - Check CodeQL findings regularly
   - Dismiss false positives with comments
   - Address real security issues promptly

3. **Manage release PRs:**
   - Review changelog accuracy
   - Ensure version bump is appropriate
   - Verify uv.lock was updated
   - Merge when ready to release

4. **Archive old test artifacts:**
   - Artifacts older than retention period are auto-deleted
   - Download important artifacts if longer retention needed

## Workflow Files Reference

### Primary Workflows

- `.github/workflows/ci.yml` - CI workflow for quality checks
- `.github/workflows/security.yml` - Security scanning workflow
- `.github/workflows/release.yml` - Release automation workflow

### Configuration Files

- `.github/dependabot.yml` - Dependabot configuration
- `.github/codeql/codeql-config.yml` - CodeQL scanner configuration
- `release-please-config.json` - Release-please configuration
- `.release-please-manifest.json` - Current version tracking

### Project Configuration

- `pyproject.toml` - Project metadata, dependencies, tool configurations
- `uv.lock` - Locked dependency versions

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [Release Please Documentation](https://github.com/googleapis/release-please)
- [CodeQL Documentation](https://codeql.github.com/docs/)
- [Dependabot Documentation](https://docs.github.com/en/code-security/dependabot)
- [uv Documentation](https://github.com/astral-sh/uv)

## Support

If you encounter issues not covered in this guide:

1. Check GitHub Actions workflow run logs for detailed error messages
2. Search existing GitHub issues for similar problems
3. Create a new issue with:
   - Description of the problem
   - Workflow run URL
   - Steps to reproduce
   - Relevant log excerpts
