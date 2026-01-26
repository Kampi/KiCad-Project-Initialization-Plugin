# CI/CD Pipeline Documentation

This document describes the automated CI/CD pipeline for the KiCad Project Initialization Plugin.

## Overview

The CI/CD pipeline automates:
- Version management
- CHANGELOG maintenance
- Release creation
- Package distribution

## Workflow Files

### 1. `changelog-check.yaml`

Validates the CHANGELOG.md format on pull requests and pushes to main.

**Triggers:**
- Pull requests that modify `CHANGELOG.md`
- Pushes to `main` or `master` that modify `CHANGELOG.md`

**Validations:**
- Checks for `[Unreleased]` section
- Validates section headers (Added, Changed, Fixed, Removed)
- Checks for duplicate issue numbers (warning only)

### 2. `release.yaml`

Manages versioning and releases based on branch names and tags.

**Triggers:**
- Pushes to development branches (format: `x.y.z_Dev`)
- Pushes to `main` or `master`
- Tags matching pattern `[0-9]+.[0-9]+.[0-9]+`
- Manual workflow dispatch

## Development Workflow

### 1. Creating a Development Branch

Development branches must follow the naming convention: `Major.Minor.Patch_Dev`

Examples:
- `1.0.0_Dev`
- `2.3.4_Dev`
- `0.0.2_Dev`

```bash
# Create a new development branch
git checkout -b 1.0.1_Dev

# Make your changes
git add .
git commit -m "Add new feature"
git push origin 1.0.1_Dev
```

**What happens automatically:**
- Version is extracted from branch name
- `metadata.json` version field is updated
- Changes are committed back to the branch

### 2. Updating the CHANGELOG

While working on your development branch, update `CHANGELOG.md`:

```markdown
## [Unreleased]

### Added
- New feature description

### Changed
- Modified behavior description

### Fixed
- Bug fix description

### Removed
- Deprecated feature removal
```

**Rules:**
- All entries must be under a valid section header
- Use bullet points starting with `- `
- Keep entries concise but descriptive

### 3. Merging to Main

When your development branch is ready:

```bash
# Ensure your branch is up to date
git checkout main
git pull origin main
git checkout 1.0.1_Dev
git rebase main  # or merge

# Merge to main
git checkout main
git merge 1.0.1_Dev
git push origin main
```

**What happens automatically:**
1. Version is extracted from the merge commit message
2. `[Unreleased]` section in CHANGELOG is renamed to version with date:
   ```markdown
   ## [1.0.1] - 2026-01-26
   ```
3. New `[Unreleased]` section is added
4. `metadata.json` version is updated
5. Git tag is created (e.g., `1.0.1`)
6. Changes are committed to main

### 4. Automatic Release

When the tag is pushed:

**What happens automatically:**
1. CHANGELOG is validated
2. Release package is created:
   ```
   kicad-project-init-plugin-1.0.1.zip
   ```
3. Package includes:
   - `__init__.py`
   - `kicad_project_init.py`
   - `metadata.json`
   - `icon.png`
   - `README.md`
   - `LICENSE`
   - `CHANGELOG.md`
   - `__Project__/` directory
4. GitHub release is created with the package
5. Release notes are extracted from CHANGELOG

## Manual Release

You can also trigger a release manually:

1. Go to GitHub Actions
2. Select "Release" workflow
3. Click "Run workflow"
4. Select the tag to release

## Troubleshooting

### CHANGELOG Validation Fails

**Error:** `No valid sections found in [Unreleased]`

**Solution:** Ensure your CHANGELOG has at least one of:
- `### Added`
- `### Changed`
- `### Fixed`
- `### Removed`

### Version Not Extracted

**Error:** `Branch name does not match expected format`

**Solution:** Ensure your branch name follows the format `x.y.z_Dev`:
- ✅ `1.0.0_Dev`
- ✅ `2.3.4_Dev`
- ❌ `feature_branch`
- ❌ `1.0_Dev` (missing patch version)

### Release Not Created

**Error:** `Version not found in CHANGELOG.md`

**Solution:** Ensure the version exists in CHANGELOG before creating a tag:
```markdown
## [1.0.1] - 2026-01-26
```

## Version Management

### Version Components

Versions follow Semantic Versioning (SemVer):
- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes (backward compatible)

### Where Versions Are Stored

1. **Branch name**: `1.0.1_Dev`
2. **metadata.json**: `"version": "1.0.1"`
3. **CHANGELOG.md**: `## [1.0.1] - 2026-01-26`
4. **Git tag**: `1.0.1`

### Version Update Flow

```
Development Branch (1.0.1_Dev)
    ↓ (automatic)
metadata.json updated
    ↓ (manual)
CHANGELOG.md updated
    ↓ (merge to main)
CHANGELOG versioned + tag created
    ↓ (automatic)
Release created
```

## Best Practices

1. **Always work on development branches** with proper naming
2. **Keep CHANGELOG up to date** as you make changes
3. **Review CHANGELOG** before merging to main
4. **Test thoroughly** before merging to main
5. **Use semantic versioning** appropriately:
   - Increment **patch** for bug fixes (1.0.0 → 1.0.1)
   - Increment **minor** for new features (1.0.1 → 1.1.0)
   - Increment **major** for breaking changes (1.1.0 → 2.0.0)

## Example Complete Workflow

```bash
# 1. Create development branch for bug fix
git checkout -b 1.0.1_Dev

# 2. Fix the bug
# ... make changes ...

# 3. Update CHANGELOG
cat >> CHANGELOG.md << 'EOF'
## [Unreleased]

### Fixed
- Fixed issue with project template selection
EOF

# 4. Commit and push
git add .
git commit -m "Fix project template selection bug"
git push origin 1.0.1_Dev

# 5. Wait for CI to update metadata.json
git pull origin 1.0.1_Dev

# 6. Create PR and merge to main
# ... via GitHub UI or command line ...

# 7. Pull updated main with tag
git checkout main
git pull origin main

# 8. Release is automatically created!
# Check https://github.com/Kampi/KiCad-Project-Initialization-Plugin/releases
```

## GitHub Secrets Required

The release workflow requires the following secrets:
- `GITHUB_TOKEN`: Automatically provided by GitHub Actions (no setup needed)

## Maintenance

### Updating Workflows

When updating workflow files:
1. Test changes in a fork first
2. Ensure YAML syntax is valid
3. Test with dry-run if possible
4. Document changes in this file

### Monitoring

Check workflow status:
1. Go to repository → Actions tab
2. Review recent workflow runs
3. Check for failures and errors
4. Review logs for troubleshooting

## Reference

- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
