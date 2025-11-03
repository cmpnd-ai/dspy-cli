# Release Process

This document describes how to release new versions of dspy-cli to PyPI.

## Release Workflow

### 1. Prepare the Release

```bash
cd dspy-cli

# Ensure you're on main and up to date
git checkout main
git pull origin main

# Run tests locally
pytest

# Run linter
ruff check .
```

### 2. Update Version

Edit `pyproject.toml` and update the version:

```toml
[project]
name = "dspy-cli"
version = "0.2.0"  # Update this
```

### 3. Commit and Tag

```bash
# Commit the version bump
git add pyproject.toml
git commit -m "Release v0.2.0"
git push origin main

# Create an annotated tag (must match pyproject.toml version)
git tag -a v0.2.0 -m "Release v0.2.0"

# Push the tag to trigger the workflow
git push origin v0.2.0
```

### 4. Monitor the Workflow

1. Go to: https://github.com/caisco/optimization-platform/actions
2. Watch the "Publish to PyPI" workflow run
3. The workflow will:
   - ✅ Test on Python 3.11 and 3.12
   - ✅ Lint with ruff
   - ✅ Verify tag matches pyproject.toml version
   - ✅ Build sdist and wheel
   - ✅ Validate with twine check
   - ✅ Publish to PyPI (using OIDC, no secrets needed!)

### 5. Verify the Release

After the workflow succeeds:

```bash
# Check PyPI
open https://pypi.org/project/dspy-cli/

# Test installation
pip install --upgrade dspy-cli

# Verify version
dspy-cli --version
```

## Version Scheme

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** version (1.0.0): Incompatible API changes
- **MINOR** version (0.2.0): New functionality, backwards compatible
- **PATCH** version (0.1.1): Bug fixes, backwards compatible

Tags must follow the format: `v{MAJOR}.{MINOR}.{PATCH}`

Examples:
- `v0.1.0` - Initial alpha release
- `v0.2.0` - New features added
- `v0.2.1` - Bug fix
- `v1.0.0` - Stable release

## Troubleshooting

### Tag/Version Mismatch

If you get an error like:
```
❌ Version mismatch: pyproject.toml=0.2.0 tag=0.1.9
```

The tag doesn't match the version in pyproject.toml. Fix it:

```bash
# Delete the incorrect tag locally and remotely
git tag -d v0.1.9
git push origin :refs/tags/v0.1.9

# Update pyproject.toml to the correct version, commit, and retag
```

### Failed Publish

If the workflow fails before publishing to PyPI:
- Fix the issue
- Delete the tag: `git push origin :refs/tags/vX.Y.Z`
- Re-tag and push again

If the workflow succeeded but the release has issues:
- **Yank** the release on PyPI (Settings → "Yank release")
- Create a new patch version (e.g., if v0.2.0 failed, release v0.2.1)
- PyPI uploads are immutable - you cannot delete or replace them

### First-Time Publish

The first publish requires the PyPI Trusted Publisher to be configured. If you see:
```
Error: Invalid or non-existent authentication information
```

Double-check the Trusted Publisher configuration on PyPI matches:
- Owner: `caisco`
- Repository: `optimization-platform`
- Workflow: `publish.yml`
- Environment: `pypi`

## Rolling Back

If a release needs to be rolled back:

1. **Yank on PyPI:** Mark the version as yanked (prevents new installs)
   ```bash
   # Via web UI: https://pypi.org/manage/project/dspy-cli/release/X.Y.Z/
   # Or via CLI:
   twine upload --skip-existing --repository pypi dist/*  # if you have credentials
   ```

2. **Release a fix:** Bump to the next patch version with fixes
   ```bash
   # If v0.2.0 was bad, release v0.2.1 with fixes
   ```

3. **Communicate:** Update GitHub Releases and changelog to warn users

## Testing Releases (Optional)

To test the release process without publishing to PyPI:

1. Set up a TestPyPI Trusted Publisher (same steps, but on https://test.pypi.org)
2. Modify the workflow to use TestPyPI repository URL temporarily
3. Use pre-release tags like `v0.2.0rc1` for testing

See [TestPyPI docs](https://packaging.python.org/en/latest/guides/using-testpypi/) for details.
