"""
BABEL CLI - Command-line interface for all Babel operations
"""
import os
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

app = typer.Typer(
    name="babel",
    help="BABEL - Webnovel Processing Pipeline",
    add_completion=False,
)

console = Console()

# Global database path - read from environment variable at runtime
_db_path: Optional[Path] = None


def get_db_path() -> Path:
    """Get the database path, reading from environment variable if set."""
    global _db_path
    if _db_path is None:
        env_path = os.environ.get("BABEL_DB_PATH")
        if env_path:
            _db_path = Path(env_path)
        else:
            _db_path = Path("data/babel.db")
    return _db_path


# Import subcommands
from babel.cli_commands import (
    novels_commands,
    chapters_commands,
    transform_commands,
    render_commands,
    context_commands,
    pipeline_commands,
    utility_commands,
)

# Register subcommands
app.add_typer(novels_commands.app, name="novels", help="Manage novels")
app.add_typer(chapters_commands.app, name="chapters", help="Manage chapters")
app.add_typer(transform_commands.app, name="transform", help="Transform text using LLM")
app.add_typer(render_commands.app, name="render", help="Render JSON to HTML")
app.add_typer(context_commands.app, name="context", help="Manage context and glossary")
app.add_typer(pipeline_commands.app, name="pipeline", help="Run full processing pipeline")
app.add_typer(utility_commands.app, name="util", help="Utility and diagnostic commands")

# Import and register ingest command directly
from babel.cli_commands.ingest_commands import ingest
app.command()(ingest)


@app.command()
def version():
    """Show Babel version"""
    from babel import __version__
    console.print(f"[bold cyan]Babel[/bold cyan] version [green]{__version__}[/green]")


@app.callback()
def main(
    db_path: Optional[Path] = typer.Option(
        None,
        "--db-path",
        envvar="BABEL_DB_PATH",
        help="Path to SQLite database (default: data/babel.db)"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show verbose output")
):
    """
    BABEL - Webnovel Processing Pipeline
    
    Transform raw webnovel files into structured, clean output.
    """
    global _db_path
    if db_path:
        _db_path = db_path
    elif os.environ.get("BABEL_DB_PATH"):
        _db_path = Path(os.environ.get("BABEL_DB_PATH"))
    
    if verbose and _db_path:
        console.print(f"[dim]Using database: {_db_path}[/dim]")


if __name__ == "__main__":
    app()
