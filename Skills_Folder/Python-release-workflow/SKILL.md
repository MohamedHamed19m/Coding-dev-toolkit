---
name: python-package-release-workflow
description: Complete workflow for releasing Python packages to PyPI with automated testing, documentation, and versioning. Use this skill when managing version bumps, automating releases with GitHub Actions, debugging publish failures, or linking PyPI with documentation. Streamlines the entire release process from local testing through PyPI publishing with semantic versioning and changelog management.

keywords: ["pypi publishing", "github actions", "semantic versioning", "commitizen", "mkdocs", "pytest coverage", "release automation", "changelog", "trusted publishing"]
---

# Python Package Release Workflow Skill

**Purpose**: Comprehensive guidance for releasing Python packages to PyPI with automated testing, documentation, and versioning.

**Scope**: Works with ANY Python project using uv, GitHub Actions, and PyPI. Abstracts away manual work through automation.

**Use Case**: When you need help with publishing a Python library, automating releases, debugging workflow failures, linking documentation, or managing version numbers.

---

## 🎯 Quick Start

Ask me to help with:
- "How do I release version 0.3.0?"
- "My PyPI publish failed with 400 Bad Request, help me debug"
- "Set up Commitizen for automated releases"
- "What's the order of steps before tagging?"
- "My GitHub tag doesn't match my version, how do I fix it?"
- "Configure GitHub Pages documentation linking"
- "Walk me through the complete release process"
- "My workflow is failing, what's wrong?"

---

## 🛠️ Tech Stack Overview

- **Package Manager**: `uv` (Fast Python packaging)
- **Documentation**: `mkdocs` with `mkdocstrings`
- **Testing**: `pytest` with `pytest-cov` (Target: >80% coverage)
- **CI/CD**: GitHub Actions (automated testing, docs, publishing)
- **Build System**: `hatchling`
- **Versioning**: Semantic Versioning (SemVer)
- **Changelog**: Keep a Changelog format
- **Auto-versioning**: Commitizen (optional, recommended)

---

## 📋 Core Concepts

### Semantic Versioning (SemVer)
Format: `MAJOR.MINOR.PATCH`

- **MAJOR** (X.0.0): Breaking changes to the API
- **MINOR** (0.X.0): New features (backward compatible)
- **PATCH** (0.0.X): Bug fixes (backward compatible)

**Examples:**
- `0.1.0` → `0.1.1` (Bug fix)
- `0.1.0` → `0.2.0` (New feature)
- `1.0.0` → `2.0.0` (Breaking change)

### ⭐ The Golden Rule: Git Tags ≠ PyPI Version

**CRITICAL**: PyPI doesn't care about your Git tag name. It only looks at the `version` field in `pyproject.toml`.

If your tag is `v0.2.3` but `pyproject.toml` still says `version = "0.2.1"`, PyPI will see it as a duplicate and reject it with a **400 Bad Request** error.

```
Git tag:        v0.2.3  ← Git cares about this
pyproject.toml: 0.2.1   ← PyPI cares about THIS ← Must match!
```

**The Fix**: Always update `pyproject.toml` FIRST, then create a matching Git tag:
```toml
[project]
version = "0.2.3"  # Must match your tag: v0.2.3
```

### Keep a Changelog Format
Always use: `## [X.X.X] - YYYY-MM-DD` for extraction tools to work
- ✅ `## [0.2.0] - 2026-01-04`
- ❌ `### 0.2.0` (missing brackets)
- ❌ `## Release 0.2.0` (wrong format)

---

## 🚀 Release Workflows

### Option 1: Manual Release (Learning Path)

For understanding the complete process step-by-step.

#### Phase 1: Preparation (Local)

**1.1 Run Tests**
```bash
uv run pytest --cov=src --cov-report=term-missing
```
Target: >80% coverage

**1.2 Update Version in pyproject.toml**
```toml
[project]
version = "0.2.1"  # Change from 0.2.0 to 0.2.1
```

**1.3 Update CHANGELOG.md**
Add at the very top (above [Unreleased]):
```markdown
## [0.2.1] - 2026-01-04

### Added
- New feature description

### Changed
- Improvement description

### Fixed
- Bug fix description

### Removed
- Deprecated feature
```

**1.4 Verify Documentation Builds**
```bash
uv run mkdocs serve
# Visit http://localhost:8000
# Ctrl+C to exit
```

**1.5 Commit Changes**
```bash
git add .
git commit -m "Release v0.2.1: Added feature X and fixed bug Y"
```

#### Phase 2: Git Tagging & Pushing

This triggers GitHub Actions:
```bash
# Create tag (MUST match version in pyproject.toml)
git tag -a v0.2.1 -m "Version 0.2.1"

# Push commits AND tags
git push origin main --tags
```

**Critical**: The `--tags` flag is mandatory.

#### Phase 3: Automated GitHub Actions

Three workflows execute automatically:
1. **test.yml** - Tests + coverage checks
2. **docs.yml** - Builds + deploys documentation
3. **release.yml** - Creates release + publishes to PyPI

---

### Option 2: Automated with Commitizen (Professional)

Commit messages automatically trigger version bumps and changelog updates.

#### Setup (One-time)

**Install Commitizen:**
```bash
uv add commitizen --dev
```

**Add to pyproject.toml:**
```toml
[tool.commitizen]
name = "cz_conventional_commits"
version = "0.2.5"  # Keep in sync with [project] version
tag_format = "v$version"
version_files = [
    "pyproject.toml:version"
]
```

#### Commit Format Rules

Only these prefixes trigger version bumps:

| Prefix | Bumps Version? | Example | Result |
|--------|---|---------|--------|
| `feat:` | **Yes (Minor)** | `feat: add CLI flag` | 0.2.5 → 0.3.0 |
| `fix:` | **Yes (Patch)** | `fix: resolve crash` | 0.2.5 → 0.2.6 |
| `BREAKING CHANGE:` | **Yes (Major)** | `feat!: redesign API` | 0.2.5 → 1.0.0 |
| `docs:` | No | `docs: update README` | No bump |
| `refactor:` | No | `refactor: simplify` | No bump |
| `test:` | No | `test: add edge cases` | No bump |
| `chore:` | No | `chore: update deps` | No bump |

#### For Every Release

**1. Make conventional commits:**
```bash
git commit -m "fix: resolve parsing bug"          # Patch bump
git commit -m "feat: add --dry-run flag"          # Minor bump
git commit -m "feat!: redesign API"               # Major bump
```

**2. Test the bump:**
```bash
uv run cz bump --dry-run
```

Shows what will happen without changes. Example output:
```
bump: version 0.2.5 → 0.3.0
increment detected: MINOR

tag to create: v0.3.0
commit to create: chore(release): 0.3.0
changelog will be updated in: CHANGELOG.md
```

**3. Apply the bump:**
```bash
uv run cz bump
```

Automatically:
- ✅ Updates `pyproject.toml` version
- ✅ Updates `CHANGELOG.md`
- ✅ Creates commit: `chore(release): 0.3.0`
- ✅ Creates git tag: `v0.3.0`

**4. Push:**
```bash
git push origin main --tags
```

---

## ⚙️ Configuration Files

### pyproject.toml (Complete)
```toml
[project]
name = "your-package-name"
version = "0.2.5"
description = "Your package description"
readme = "README.md"
authors = [
    { name = "Your Name", email = "email@example.com" }
]
requires-python = ">=3.11"
keywords = ["keyword1", "keyword2"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3.11",
]
dependencies = [
    "typer[all]>=0.12.0",
    "rich>=13.0.0",
]

[project.urls]
Homepage = "https://github.com/YourUser/YourRepo"
Documentation = "https://yourusername.github.io/YourRepo/"
Repository = "https://github.com/YourUser/YourRepo"
Issues = "https://github.com/YourUser/YourRepo/issues"

[project.scripts]
your-package = "your_package.cli:main"

[tool.uv]
package = true

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[dependency-groups]
dev = [
    "mkdocs-material>=9.7.1",
    "mkdocstrings[python]>=1.0.0",
    "pytest>=9.0.2",
    "pytest-cov>=7.0.0",
    "commitizen",
]

[tool.hatch.build.targets.wheel]
packages = ["src/your_package"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.commitizen]
name = "cz_conventional_commits"
version = "0.2.5"
tag_format = "v$version"
version_files = [
    "pyproject.toml:version"
]
```

### mkdocs.yml (Complete)
```yaml
site_name: your-package-name
site_url: https://yourusername.github.io/YourRepo/
repo_url: https://github.com/YourUser/YourRepo
repo_name: YourUser/YourRepo
edit_uri: edit/main/docs/

theme:
  name: material
  palette:
    scheme: default

plugins:
  - search

nav:
  - Home: index.md
  - Installation: installation.md
  - Usage: usage.md
  - API: api.md
```

### .github/workflows/release.yml (Combined - Simplest)
```yaml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'

permissions:
  contents: write
  id-token: write

jobs:
  publish:
    name: Build, Release, and Publish
    runs-on: ubuntu-latest
    environment: pypi

    steps:
      - uses: actions/checkout@v4

      - name: Extract Release Notes
        id: extract-release-notes
        uses: ffurrer2/extract-release-notes@v2

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Build Package
        run: uv build

      - name: Create GitHub Release
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          NOTES=$(cat << 'EOF'
          ${{ steps.extract-release-notes.outputs.release_notes }}
          EOF
          )
          
          gh release create "${{ github.ref_name }}" \
            ./dist/* \
            --title "Release ${{ github.ref_name }}" \
            --notes "$NOTES" \
            --if-not-exists

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

### .github/workflows/release.yml (Separated - Part 1)
```yaml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'

permissions:
  contents: write

jobs:
  release:
    name: Create GitHub Release
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Extract Release Notes
        id: extract-release-notes
        uses: ffurrer2/extract-release-notes@v2

      - name: Create GitHub Release
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          NOTES=$(cat << 'EOF'
          ${{ steps.extract-release-notes.outputs.release_notes }}
          EOF
          )
          
          gh release create "${{ github.ref_name }}" \
            --title "Release ${{ github.ref_name }}" \
            --notes "$NOTES" \
            --if-not-exists
```

### .github/workflows/publish.yml (Separated - Part 2)
```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  pypi-publish:
    name: Upload to PyPI
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write

    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.ref }}

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Build package
        run: uv build

      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
```

### .github/workflows/docs.yml
```yaml
name: Deploy Documentation

on:
  push:
    branches: [main]
    tags: ['v*']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: astral-sh/setup-uv@v3

      - name: Build docs
        run: uv run mkdocs build

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./site
```

### .github/workflows/test.yml
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Run tests
        run: uv run pytest --cov=src --cov-report=term-missing
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 📋 Standard CHANGELOG.md Template

```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- (Upcoming features)

## [0.2.1] - 2026-01-04

### Added
- Feature A
- Feature B

### Changed
- Improvement description

### Fixed
- Bug fix description

### Removed
- Deprecated feature

## [0.1.0] - 2025-12-25

### Added
- Initial release
```

---

## 🔗 Linking PyPI, GitHub Pages & Documentation

### Step 1: Update pyproject.toml
```toml
[project.urls]
Homepage = "https://github.com/YourUser/YourRepo"
Documentation = "https://yourusername.github.io/YourRepo/"
Repository = "https://github.com/YourUser/YourRepo"
Issues = "https://github.com/YourUser/YourRepo/issues"
```

### Step 2: Update mkdocs.yml
```yaml
site_url: https://yourusername.github.io/YourRepo/
repo_url: https://github.com/YourUser/YourRepo
edit_uri: edit/main/docs/
```

### Step 3: Update README.md Badges
```markdown
[![PyPI](https://img.shields.io/pypi/v/your-package.svg)](https://pypi.org/project/your-package/)
[![Docs](https://img.shields.io/badge/docs-GitHub%20Pages-blue.svg)](https://yourusername.github.io/YourRepo/)
[![Release](https://github.com/YourUser/YourRepo/actions/workflows/release.yml/badge.svg)](https://github.com/YourUser/YourRepo/actions/workflows/release.yml)
```

### Result
- PyPI sidebar links to GitHub Pages
- GitHub Pages header links back to repo
- README badges link everywhere
- User can navigate: PyPI → Docs → Repo → Issues

---

## ⚠️ Critical Setup Requirements (One-time)

### 1. PyPI Trusted Publishing
1. Go to [pypi.org](https://pypi.org) → Settings → Publishing
2. Click "Add a new trusted publisher"
3. Select "GitHub Actions"
4. Fill in: Repository: `YourUser/YourRepo`, Workflow: `release.yml`
5. Click "Add trusted publisher"

### 2. GitHub Repository Settings
1. Settings → Actions → General
2. ✅ Enable "Read and write permissions"
3. ✅ Enable "Allow GitHub Actions to create PRs"

### 3. GitHub Pages
1. Settings → Pages
2. Source: Deploy from a branch
3. Branch: `gh-pages` (auto-created by docs.yml)
4. Save

---

## ✅ Pre-Release Checklist

Before you push your tag:

- [ ] Tests pass: `uv run pytest --cov=src --cov-report=term-missing`
- [ ] Coverage ≥80%
- [ ] Version in `pyproject.toml` matches tag (e.g., `0.2.3`)
- [ ] CHANGELOG.md has `## [0.2.3] - YYYY-MM-DD` header
- [ ] Docs build: `uv run mkdocs serve`
- [ ] Working directory clean: `git status`
- [ ] PyPI Trusted Publishing configured
- [ ] GitHub Actions has write permissions

---

## 📊 Step-by-Step Commands

### Manual Release
```bash
# 1. Test
uv run pytest --cov=src --cov-report=term-missing

# 2. Update files
# - Edit pyproject.toml version
# - Edit CHANGELOG.md (add ## [X.X.X] - YYYY-MM-DD)

# 3. Verify docs
uv run mkdocs serve  # Ctrl+C to exit

# 4. Commit
git add .
git commit -m "Release v0.2.3"

# 5. Tag (MUST match pyproject.toml version)
git tag -a v0.2.3 -m "Version 0.2.3"

# 6. Push
git push origin main --tags
```

### Commitizen Release
```bash
# 1. Make conventional commits
git commit -m "feat: add feature"
git commit -m "fix: resolve bug"

# 2. Test bump
uv run cz bump --dry-run

# 3. Apply bump
uv run cz bump

# 4. Push
git push origin main --tags
```

---

## 🐛 Troubleshooting

### PyPI: 400 Bad Request
**Problem**: `pyproject.toml` version ≠ git tag
```toml
version = "0.2.1"  # But tag is v0.2.3
```
**Fix**: Update version BEFORE tagging:
```bash
# Edit pyproject.toml
git add pyproject.toml
git commit -m "Bump version to 0.2.3"
git tag -a v0.2.3 -m "Version 0.2.3"  # Now they match
git push origin main --tags
```

### Workflow doesn't trigger
**Problem**: Forgot `--tags` flag
**Fix**: `git push origin main --tags` (--tags is mandatory)

### CHANGELOG extraction fails
**Problem**: Wrong format like `## Release 0.2.0`
**Fix**: Use exactly: `## [0.2.0] - 2026-01-04`

### gh release create: "unknown flag"
**Problem**: Wrong argument order
**Wrong**: `gh release create v0.2.0 ./dist/* --title "..."`
**Correct**:
```bash
gh release create v0.2.0 \
  --title "Release v0.2.0" \
  --notes "Notes" \
  --if-not-exists \
  ./dist/*
```

### Release already exists
**Problem**: Workflow ran twice for same tag
**Fix**:
```bash
git tag -d v0.2.3
git push --delete origin v0.2.3
git tag -a v0.2.3 -m "Version 0.2.3"
git push origin main --tags
```

### Docs don't deploy
**Problem**: `mkdocs.yml` missing or misconfigured
**Fix**: Ensure `mkdocs.yml` exists in repo root

### Commitizen: "no commits found"
**Problem**: Commits don't follow conventional format
**Fix**:
- ✅ `fix: bug description`
- ✅ `feat: feature description`
- ❌ `Updated stuff` (won't bump)

### Tests fail in GitHub but pass locally
**Causes**:
- Different Python version
- Missing dependency in `pyproject.toml`
- File path issues

**Fix**: Check workflow logs

---

## 🎯 Workflow Comparison

| Aspect | Manual | Commitizen |
|--------|--------|-----------|
| **Learning Curve** | Easy, understand each step | Moderate, learn conventions |
| **Time per Release** | 10+ minutes | 2 minutes |
| **Version Bumping** | Manual | Automatic |
| **Changelog** | Manual copy/paste | Auto-generated |
| **Consistency** | Easy to make mistakes | Always follows SemVer |
| **Best For** | Learning, small projects | Production, teams |

---

## 📚 External Resources

- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)
- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
- [uv Documentation](https://docs.astral.sh/uv/)
- [MkDocs](https://www.mkdocs.org/)
- [Commitizen](https://commitizen-tools.github.io/commitizen/)

---

## 🤖 How to Use This Skill

**When asking for help, mention:**
- Current version you're releasing
- Any error messages
- Manual or Commitizen approach
- What step you're stuck on

**Example questions:**
- "Releasing v0.3.0, got a 400 error from PyPI"
- "Set up Commitizen for my repo"
- "My release.yml workflow failed, debug this"
- "Walk me through releasing v0.2.2"
- "Version mismatch between tag and pyproject.toml"
- "How do I automate this release process?"