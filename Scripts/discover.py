# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer>=0.9.0",
#     "pyyaml>=6.0",
# ]
# ///

"""
Context Discovery Script – Generic tool for any repository.
Scans markdown files for YAML front matter and generates AI-optimized context lists.

## Installation

**Note:** When using Gemini CLI (or similar tools), global script access may not work
because these CLIs prevent inheriting from your shell profile.

### First Best Practice – Install as Global Tool

Create a standalone library package and install it globally:

```bash
uv init --lib discover-docs
cd discover-docs

# Create src/discover_docs with your code
# Update pyproject.toml with:
# [project.scripts]
# discover-docs = "discover_docs:main"

uv add typer pyyaml type_extensions
uv tool install . -e
```

Then use it anywhere:
```bash
uvx discover-docs
uvx discover-docs --ai
uvx discover-docs --dirs docs,src
```

### Second Best Practice – Use in Repository

Copy the script to your repo and run with uv:

```bash
uv run discover.py                    # Human-readable list
uv run discover.py --ai               # AI-optimized format
uv run discover.py --dirs docs,src    # Custom directories
```
"""
from pathlib import Path
from typing import Optional, Dict, Any, List, Annotated

import typer
import yaml

app = typer.Typer(
    name="discover",
    help="Scan project documentation with front matter metadata.",
    add_completion=False,
)


# =========================================================
# Front matter extraction
# =========================================================
def extract_front_matter(md_file: Path) -> Optional[Dict[str, Any]]:
    """
    Efficiently extract YAML front matter without reading the whole file.
    """
    lines: List[str] = []

    try:
        with md_file.open("r", encoding="utf-8") as f:
            first_line = f.readline().strip()

            if first_line != "---":
                return None

            for line in f:
                stripped = line.strip()
                if stripped == "---":
                    break
                lines.append(line)
            else:
                return None

        return yaml.safe_load("".join(lines))

    except Exception:
        return None


# =========================================================
# Discovery
# =========================================================
def discover_docs(
    root_dir: Path,
    search_dirs: List[str],
) -> List[Dict[str, Any]]:
    """
    Scan for markdown files and ONLY include those
    with valid summary + read_when metadata.
    """

    docs: List[Dict[str, Any]] = []

    NULL_VALUES = [None, "", "null", "n/a", "N/A", "none", "no summary"]
    ALLOWED_KEYS = {"summary", "read_when"}

    for d in search_dirs:
        search_dir = root_dir / d

        if not search_dir.exists() or not search_dir.is_dir():
            continue

        for md_file in search_dir.rglob("*.md"):

            # skip non-documentation
            if any(x in md_file.name.lower() for x in ["changelog", "license", "contributing"]):
                continue

            front_matter = extract_front_matter(md_file)

            if not front_matter:
                continue

            # strict key validation
            current_keys = set(front_matter.keys())
            if current_keys != ALLOWED_KEYS:
                continue

            summary = front_matter.get("summary")

            if summary is None or str(summary).lower().strip() in NULL_VALUES:
                summary = "No Summary"

            read_when = front_matter.get("read_when", [])

            if isinstance(read_when, str):
                read_when = [read_when]
            elif read_when is None:
                read_when = []

            try:
                rel_path = md_file.relative_to(root_dir).as_posix()

                docs.append(
                    {
                        "path": rel_path,
                        "summary": summary,
                        "read_when": read_when,
                    }
                )
            except ValueError:
                continue

    return docs


# =========================================================
# Human readable output
# =========================================================
def print_list(docs: List[Dict[str, Any]], project_name: str) -> None:
    """Print simple list format for humans."""

    if not docs:
        typer.echo("No documentation with valid front matter found.")
        return

    typer.secho("\n" + "=" * 70, fg=typer.colors.CYAN)
    typer.secho(f"{project_name.upper()} – DOCUMENTATION INDEX", bold=True, fg=typer.colors.CYAN)
    typer.secho("=" * 70 + "\n")

    for doc in sorted(docs, key=lambda x: x["path"]):
        typer.secho(doc["path"], fg=typer.colors.GREEN, bold=True)
        typer.echo(f"  Summary: {doc['summary']}")

        read_when = ", ".join(doc["read_when"]) if doc["read_when"] else "N/A"
        typer.echo(f"  Trigger: {read_when}\n")


# =========================================================
# AI optimized output
# =========================================================
def print_ai_format(docs: List[Dict[str, Any]]) -> None:
    """
    Format for AI system prompts.
    """
    if not docs:
        return

    typer.echo("\n### PROJECT CONTEXT GUIDE")

    for doc in sorted(docs, key=lambda x: x["path"]):
        typer.echo(f"FILE: {doc['path']}")
        typer.echo(f"DESC: {doc['summary']}")

        read_when = ", ".join(doc["read_when"]) if doc["read_when"] else "N/A"
        typer.echo(f"WHEN: {read_when}\n")


# =========================================================
# CLI
# =========================================================
@app.command()
def main(
    ai: Annotated[bool, typer.Option("--ai", help="Output in AI-optimized format")] = False,
    root: Annotated[str, typer.Option("--root", "-r", help="Root project directory")] = ".",
    dirs: Annotated[str, typer.Option("--dirs", "-d", help="Comma separated directories")] = "docs",
    name: Annotated[str, typer.Option("--name", "-n", help="Project display name")] = "Project",
) -> None:
    """
    Discover project docs and generate context lists.
    """

    root_dir = Path(str(root)).resolve()
    search_dirs = [d.strip() for d in dirs.split(",")]

    docs = discover_docs(root_dir, search_dirs)

    if ai:
        print_ai_format(docs)
    else:
        print_list(docs, name)


# =========================================================
if __name__ == "__main__":
    app()