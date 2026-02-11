# /// script
# dependencies = [
#   "rich",
# ]
# ///
"""
Git Worktree Manager (WTM)
--------------------------
Description:
An interactive CLI tool to streamline the creation and cleanup of Git worktrees.
This version is Context-Aware: it compares worktrees against your CURRENT branch.
Enhanced with Rich library for beautiful CLI output.
"""

import subprocess
import os
import time
import shutil
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import box

console = Console()


def run_git(args):
    """Helper to run git commands and return output."""
    try:
        result = subprocess.run(
            ["git"] + args, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def get_current_branch():
    """Detects the branch you are currently on in the main repo."""
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"])

def get_branch_sha(branch_name, short=False):
    """Return the commit SHA for a branch."""
    args = ["rev-parse"]
    if short:
        args.append("--short")
    args.append(branch_name)
    return run_git(args)


def get_branch_shad(branch_name):
    """ return the short commit for branch """
    return get_branch_sha(branch_name, short=True)



def get_worktree_age(path):
    """Gets the age of a worktree based on its last modification time."""
    try:
        age_seconds = time.time() - os.path.getmtime(path)

        if age_seconds < 3600:
            unit, divisor = "m", 60
        elif age_seconds < 86400:
            unit, divisor = "h", 3600
        elif age_seconds < 604800:
            unit, divisor = "d", 86400
        else:
            unit, divisor = "w", 604800

        return f"{int(age_seconds / divisor)}{unit}"
    except OSError:
        return "?"


def get_merge_status(branch_name, parent_branch):
    """
    Returns (status, status_color) based on SHA comparison and merge status:
    - FRESH: branch SHA == parent SHA (hasn't diverged)
    - MERGED: branch SHA != parent SHA but git says it's merged
    - NOT MERGED: branch has unique commits not in parent
    """
    if not branch_name or not parent_branch or branch_name == parent_branch:
        return "N/A", "dim"

    branch_sha = get_branch_sha(branch_name)
    parent_sha = get_branch_sha(parent_branch)

    if not branch_sha or not parent_sha:
        return "ERROR", "red"

    # 1. SHAs match → FRESH (branch at same commit as parent)
    if branch_sha == parent_sha:
        return "FRESH", "cyan"

    # 2. Use git branch --merged to check if branch was actually merged
    merged_output = run_git(["branch", "--merged", parent_branch])
    if merged_output and branch_name in [b.strip().replace("* ", "") for b in merged_output.splitlines()]:
        return "MERGED", "green"

    # 3. Branch has unique commits not in parent
    return "NOT MERGED", "yellow"


def get_worktrees():
    """
    Returns a list of worktree dictionaries, excluding the main repo.
    Uses SHA-based comparison to accurately determine merge status.
    """
    output = run_git(["worktree", "list"])
    if not output:
        return []

    parent_branch = get_current_branch()
    parent_sha = get_branch_sha(parent_branch, short=True) if parent_branch else "?"
    lines = output.splitlines()

    linked_trees = []
    for line in lines[1:]:
        parts = line.split()
        path = parts[0]

        branch = next(
            (p.strip("[]") for p in parts if p.startswith("[") and p.endswith("]")),
            None,
        )
        age = get_worktree_age(path)

        if branch:
            branch_sha = get_branch_sha(branch, short=True) or "?"
            status, status_color = get_merge_status(branch, parent_branch)
        else:
            status, status_color = "DETACHED", "red"
            branch_sha = "?"

        linked_trees.append(
            {
                "path": path,
                "branch": branch or "N/A",
                "status": status,
                "status_color": status_color,
                "age": age,
                "parent_branch": parent_branch,
                "parent_sha": parent_sha,
                "branch_sha": branch_sha,
            }
        )
    return linked_trees

def _create_worktree_table(title, show_number=True, show_age=False, show_sha=False):
    """Helper to create a consistent worktree table."""
    table = Table(
        title=title, box=box.ROUNDED, show_header=True, header_style="bold magenta"
    )

    if show_number:
        table.add_column("#", style="dim", width=4)
    table.add_column("Path", style="cyan")
    table.add_column("Branch", style="bold green")
    table.add_column("Status", width=12)
    if show_age:
        table.add_column("Age", justify="right", width=6)
    if show_sha:
        table.add_column("SHA", style="dim", width=8)

    return table


def list_worktrees():
    """Display worktrees in a beautiful table with SHA information."""
    parent = get_current_branch()
    parent_sha = get_branch_sha(parent, short=True) if parent else "?"
    output = run_git(["worktree", "list"])
    if not output:
        console.print("[yellow]No worktrees found.[/yellow]")
        return []

    lines = output.splitlines()
    main_path = lines[0].split()[0]

    console.print()
    console.print(
        Panel(
            f"[bold cyan]Main Repository:[/bold cyan] {main_path}\n"
            f"[bold cyan]Current Branch:[/bold cyan] [bold green]{parent}[/bold green] "
            f"[dim]({parent_sha})[/dim]",
            title="🌳 Git Worktree Manager",
            border_style="cyan",
        )
    )

    linked = get_worktrees()
    if not linked:
        console.print("[yellow]No linked worktrees found.[/yellow]")
        return []

    table = _create_worktree_table(
        f"Linked Worktrees (comparing to: {parent})", show_age=True, show_sha=True
    )

    for i, wt in enumerate(linked, 1):
        status_text = f"[{wt['status_color']}]{wt['status']}[/{wt['status_color']}]"
        table.add_row(
            str(i), wt["path"], wt["branch"], status_text, wt["age"], wt["branch_sha"]
        )

    console.print(table)
    console.print()
    return linked


def create_worktree():
    """Create a new worktree with Chronological naming."""
    parent = get_current_branch()
    counter = len(get_worktrees())
    default_suffix = datetime.now().strftime(f"fix-%b%d-%H%M-{counter}")

    console.print(
        f"\n[cyan]Creating worktree from branch:[/cyan] [bold green]{parent}[/bold green]"
    )
    suffix = Prompt.ask("Enter branch name suffix", default=default_suffix)

    path = f"../{suffix}"

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Creating worktree at {path}...", total=None)
        result = run_git(["worktree", "add", path, "-b", suffix])
        progress.update(task, completed=True)

    if result is not None:
        console.print(
            f"[green]✓[/green] Worktree [bold green]{suffix}[/bold green] created successfully!"
        )
    else:
        console.print("[red]✗[/red] Failed to create worktree.")


def _parse_selection(selection, max_index):
    """Parse selection string (e.g., '1,2,3', '1-3', or 'all') into a list of indices."""
    indices = set()
    selection = selection.strip().lower()

    if selection == "all":
        return list(range(max_index))

    for part in selection.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start, end = map(int, part.split("-"))
                indices.update(range(start - 1, min(end, max_index)))
            except ValueError:
                return None
        else:
            try:
                indices.add(int(part) - 1)
            except ValueError:
                return None

    return sorted(i for i in indices if 0 <= i < max_index)


def _remove_worktrees(targets, delete_branches, show_progress=True):
    """Core worktree removal logic used by both remove and bulk cleanup."""
    if show_progress:
        progress_ctx = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        )
    else:
        progress_ctx = nullcontext()

    with progress_ctx as progress:
        if show_progress:
            task = progress.add_task("Removing worktrees...", total=len(targets))

        for target in targets:
            if run_git(["worktree", "remove", "--force", target["path"]]) is not None:
                console.print(f"  [green]✓[/green] Removed: {target['path']}")
                if delete_branches and target["branch"] != "N/A":
                    run_git(["branch", "-D", target["branch"]])
                    console.print(
                        f"    [dim]✓ Deleted branch: [green]{target['branch']}[/green][/dim]"
                    )
            if show_progress:
                progress.advance(task)

    run_git(["worktree", "prune"])


def remove_worktree():
    """Remove one or more worktrees with rich interface."""
    linked = list_worktrees()
    if not linked:
        return

    try:
        selection = Prompt.ask(
            "\n[bold]Enter worktree number(s) to remove[/bold] [dim](e.g., 1 or 1,2,3 or 1-3 or all)[/dim]",
            default="",
        ).strip()

        if not selection:
            console.print("[yellow]Cancelled.[/yellow]")
            return

        indices = _parse_selection(selection, len(linked))
        if indices is None or not indices:
            console.print("[yellow]Invalid selection.[/yellow]")
            return

        targets = [linked[i] for i in indices]

        console.print(
            f"\n[bold]Selected {len(targets)} worktree(s) for removal:[/bold]"
        )
        table = Table(box=box.SIMPLE)
        table.add_column("#", style="dim")
        table.add_column("Path", style="cyan")
        table.add_column("Branch", style="bold green")
        table.add_column("Status")
        table.add_column("SHA", style="dim")

        not_merged_count = 0
        for i, target in enumerate(targets, 1):
            status = f"[{target['status_color']}]{target['status']}[/{target['status_color']}]"
            table.add_row(str(i), target["path"], target["branch"], status, target["branch_sha"])
            if target["status"] == "NOT MERGED":
                not_merged_count += 1

        console.print(table)

        if not_merged_count > 0:
            console.print(
                f"\n[bold yellow]⚠ WARNING:[/bold yellow] {not_merged_count} worktree(s) are NOT merged"
            )

        if not Confirm.ask(f"\nRemove {len(targets)} worktree(s)?", default=False):
            return

        delete_branches = Confirm.ask(
            "Also delete the associated branches?", default=False
        )

        _remove_worktrees(targets, delete_branches)
        console.print("\n[green]✓ Complete![/green]")

    except (ValueError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled.[/yellow]")


def open_in_editor():
    """Open worktree in VS Code."""
    linked = list_worktrees()
    if not linked:
        return

    try:
        choice = IntPrompt.ask(
            "\nEnter worktree number to open in VS Code",
            choices=[str(i) for i in range(1, len(linked) + 1)],
            show_choices=False,
        )
        target_path = linked[choice - 1]["path"]

        if shutil.which("code"):
            subprocess.run(["code", target_path], shell=True)
            console.print("[green]✓[/green] Opened in VS Code")
        else:
            os.startfile(target_path)
    except (ValueError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled.[/yellow]")



class nullcontext:
    """Minimal context manager for when progress is not needed."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

def merge_worktree():
    """Merge a worktree's branch into the current branch."""
    parent = get_current_branch()
    linked = list_worktrees()
    if not linked:
        return

    try:
        choice = IntPrompt.ask(
            f"\nEnter worktree number to merge INTO [bold green]{parent}[/bold green]",
            choices=[str(i) for i in range(1, len(linked) + 1)],
            show_choices=False,
        )
        target = linked[choice - 1]
        target_branch = target["branch"]

        if target_branch == "N/A":
            console.print("[red]✗[/red] Cannot merge a detached worktree.")
            return
        
        if target_branch == parent:
            console.print("[yellow]⚠[/yellow] Cannot merge a branch into itself.")
            return

        if not Confirm.ask(f"Merge [bold]{target_branch}[/bold] into [bold green]{parent}[/bold green]?"):
            return

        # Perform the merge
        with console.status(f"[bold line]Merging {target_branch}..."):
            result = run_git(["merge", target_branch])

        if result is not None:
            console.print(f"[green]✓[/green] Successfully merged [bold]{target_branch}[/bold].")
            
            # Optional Cleanup
            if Confirm.ask("\nWould you like to remove the worktree and delete the branch now?", default=True):
                _remove_worktrees([target], delete_branches=True)
                console.print("[green]✓[/green] Worktree and branch cleaned up.")
        else:
            console.print("[red]✗ Merge failed.[/red] You may have conflicts to resolve manually.")

    except (ValueError, KeyboardInterrupt):
        console.print("\n[yellow]Cancelled.[/yellow]")

def show_menu():
    """Display the main menu."""
    console.print()
    menu = Table(box=box.ROUNDED, show_header=False, border_style="blue")
    menu.add_column("Option", style="cyan", width=4)
    menu.add_column("Description", style="white")
    menu.add_row("1", "📋 List Worktrees")
    menu.add_row("2", "➕ Create New Worktree")
    menu.add_row("3, m", "🔀 Merge Worktree into Current") # New Option
    menu.add_row("4, r", "🗑️  Remove Worktree")
    menu.add_row("5", "💻 Open Worktree in VS Code")
    menu.add_row("6, q", "🚪 Exit")
    console.print(
        Panel(menu, title="[bold]Git Worktree Manager[/bold]", border_style="blue")
    )

def main():
    """Main application loop."""
    console.print(
        "[bold cyan]Git Worktree Manager[/bold cyan] - Enhanced with Rich", style="bold"
    )

    while True:
        show_menu()
        try:
            choice = Prompt.ask(
                "\n[bold]Select an option[/bold]",
                choices=["1", "2", "3", "4", "5", "6", "m", "r", "q"],
                show_choices=False,
            )

            if choice == "1":
                list_worktrees()
            elif choice == "2":
                create_worktree()
            elif choice == "3" or choice == "m":
                merge_worktree() # New handler
            elif choice == "4" or choice == "r":
                remove_worktree()
            elif choice == "5":
                open_in_editor()
            elif choice == "6" or choice == "q":
                console.print("\n[cyan]👋 Goodbye![/cyan]")
                break
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"\n[red]Error: {e}[/red]")
            
if __name__ == "__main__":
    main()