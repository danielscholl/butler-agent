"""Progress indicators for long-running operations."""

from contextlib import contextmanager
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn


@contextmanager
def show_progress(message: str, console: Optional[Console] = None):
    """Context manager to show progress indicator during operation.

    Args:
        message: Progress message to display
        console: Optional Rich console (creates new one if not provided)

    Yields:
        Progress object
    """
    if console is None:
        console = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(message, total=None)
        yield progress


@contextmanager
def show_spinner(message: str, console: Optional[Console] = None):
    """Context manager to show a simple spinner.

    Args:
        message: Message to display
        console: Optional Rich console

    Yields:
        None
    """
    if console is None:
        console = Console()

    with console.status(f"[bold blue]{message}...", spinner="dots"):
        yield
