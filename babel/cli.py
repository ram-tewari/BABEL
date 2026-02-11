"""
BABEL CLI - Command-line interface for all Babel operations
"""
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

# Import subcommands
from babel.cli_commands import (
    transform_commands,
    render_commands,
    context_commands,
    pipeline_commands,
    utility_commands,
)

# Register subcommands
app.add_typer(transform_commands.app, name="transform", help="Transform text using LLM")
app.add_typer(render_commands.app, name="render", help="Render JSON to HTML")
app.add_typer(context_commands.app, name="context", help="Manage context and glossary")
app.add_typer(pipeline_commands.app, name="pipeline", help="Run full processing pipeline")
app.add_typer(utility_commands.app, name="util", help="Utility and diagnostic commands")


@app.command()
def version():
    """Show Babel version"""
    from babel import __version__
    console.print(f"[bold cyan]Babel[/bold cyan] version [green]{__version__}[/green]")


@app.callback()
def main():
    """
    BABEL - Webnovel Processing Pipeline
    
    Transform raw webnovel files into structured, clean output.
    """
    pass


if __name__ == "__main__":
    app()
