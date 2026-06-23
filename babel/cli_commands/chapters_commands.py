"""Chapter management commands for BABEL CLI."""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="chapters",
    help="Manage chapters in the database"
)

console = Console()


def get_db_path() -> Path:
    """Get the database path from the CLI module."""
    from babel.cli import get_db_path as _get_db_path
    return _get_db_path()


@app.command("list")
def list_chapters(
    novel_id: Optional[int] = typer.Option(None, "--novel-id", "-n", help="Filter by novel ID"),
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of chapters to display"),
    offset: int = typer.Option(0, "--offset", help="Number of chapters to skip")
) -> None:
    """
    List chapters, optionally filtered by novel.
    
    Shows chapter_id, chapter_index, filename, and title in a formatted table.
    When --novel-id is not provided, lists all chapters including legacy chapters.
    """
    from babel.data.db import DatabaseManager
    
    db = DatabaseManager(get_db_path())
    
    # If novel_id is provided, verify it exists
    if novel_id is not None:
        novel = db.get_novel(novel_id)
        if not novel:
            console.print(f"[red]Error: Novel with ID {novel_id} not found[/red]")
            raise typer.Exit(1)
        
        # Get chapters for specific novel
        chapters = db.get_chapters_by_novel(novel_id)
        
        if not chapters:
            console.print(f"[yellow]Novel '{novel['title']}' has no chapters[/yellow]")
            return
        
        # Create table for novel-specific chapters
        table = Table(title=f"Chapters: {novel['title']}")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("#", style="blue", width=5, justify="right")
        table.add_column("Filename", style="green")
        table.add_column("Title", style="white")
        
        for chapter in chapters:
            table.add_row(
                str(chapter['id']),
                str(chapter['chapter_index']),
                chapter['filename'],
                chapter['title'] or 'Untitled'
            )
        
        console.print(table)
        console.print(f"\n[dim]Showing {len(chapters)} chapters[/dim]")
    else:
        # Get all chapters including legacy
        chapters = db.get_all_chapters()
        
        if not chapters:
            console.print("[yellow]No chapters found in the database[/yellow]")
            return
        
        # Create table for all chapters
        table = Table(title="All Chapters")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Novel ID", style="magenta", width=8, justify="right")
        table.add_column("#", style="blue", width=5, justify="right")
        table.add_column("Filename", style="green")
        table.add_column("Title", style="white")
        
        for chapter in chapters:
            novel_id_display = str(chapter['novel_id']) if chapter['novel_id'] is not None else 'Legacy'
            table.add_row(
                str(chapter['id']),
                novel_id_display,
                str(chapter['chapter_index']),
                chapter['filename'],
                chapter['title'] or 'Untitled'
            )
        
        console.print(table)
        console.print(f"\n[dim]Showing {len(chapters)} chapters[/dim]")