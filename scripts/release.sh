#!/bin/bash
set -e

# Check if argument is provided
if [ -z "$1" ]; then
    echo "Usage: ./scripts/release.sh <version | patch | minor | major>"
    exit 1
fi

# Bump version using uv
# This handles updating pyproject.toml and syncing the lockfile
if [[ "$1" =~ ^(patch|minor|major|prerelease)$ ]]; then
    uv version --bump "$1"
else
    uv version "$1"
fi

# Get the new version number from pyproject.toml to use in git tag
# uv version outputs the new version, but it's safer to read it from the source of truth
NEW_VERSION=$(uv run python -c "import tomli; print(tomli.load(open('pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || grep '^version = ' pyproject.toml | cut -d '"' -f 2)

echo "Committing and tagging v$NEW_VERSION..."
git add pyproject.toml uv.lock
git commit -m "bump version to $NEW_VERSION"
git tag "v$NEW_VERSION"

echo "Pushing to git..."
git push
git push origin "v$NEW_VERSION"

echo "Done! Released v$NEW_VERSION"
