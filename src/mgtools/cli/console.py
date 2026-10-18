"""Output and error reporting shared by the commands."""

import functools
from collections.abc import Callable

import typer
from rich.console import Console
from rich.markup import escape
from rich.status import Status

# Wrapping would break the long paths of messages at the console's width.
console = Console(soft_wrap=True)
error_console = Console(stderr=True, soft_wrap=True)


def reports_errors[**P, R](command: Callable[P, R]) -> Callable[P, R]:
    """Turn the expected failures of a command into a message and exit code 1.

    Args:
        command: The command function to wrap.
    """

    @functools.wraps(command)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return command(*args, **kwargs)
        except (ValueError, OSError) as error:
            error_console.print(f"[bold red]Error:[/] {escape(str(error))}")
            raise typer.Exit(1) from error

    return wrapper


def working(message: str) -> Status:
    """Return a spinner to show while a command works.

    Args:
        message: What the command is doing.
    """
    # Unlike the default, this spinner prints in any console encoding, cp1250 included.
    return console.status(escape(message), spinner="line")


def done(message: str) -> None:
    """Print the outcome of a successful step of a command.

    Args:
        message: What the step did.
    """
    console.print(f"[green]{escape(message)}[/]")


def warn(message: str) -> None:
    """Print a warning to the standard error.

    Args:
        message: The warning's text.
    """
    error_console.print(f"[yellow]Warning:[/] {escape(message)}")
