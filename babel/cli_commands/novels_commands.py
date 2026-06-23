"""Novel management commands for BABEL CLI."""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint

app = typer.Typer(
    name="novels",
    help="Manage novels in the database"
)

console = Console()


def get_db_path() -> Path:
    """Get the database path from the CLI module."""
    from babel.cli import get_db_path as _get_db_path
    return _get_db_path()


@app.command("list")
def list_novels(
    limit: int = typer.Option(100, "--limit", "-l", help="Maximum number of novels to display"),
    offset: int = typer.Option(0, "--offset", help="Number of novels to skip"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Filter by status (active, completed, paused, abandoned)")
) -> None:
    """
    List all novels in the database, sorted by most recently updated.
    
    Shows novel_id, title, author, status, and chapter count in a formatted table.
    """
    from babel.data.db import DatabaseManager
    
    db = DatabaseManager(get_db_path())
    
    # Get novels with chapter counts
    novels = db.list_novels_with_chapter_count(limit=limit, offset=offset)
    
    # Filter by status if provided
    if status:
        novels = [n for n in novels if n['status'] == status]
    
    if not novels:
        console.print("[yellow]No novels found in the database[/yellow]")
        return
    
    # Create table
    table = Table(title="Novels")
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Title", style="green")
    table.add_column("Author", style="magenta")
    table.add_column("Status", style="yellow")
    table.add_column("Chapters", style="blue", justify="right")
    table.add_column("Updated", style="dim")
    
    for novel in novels:
        updated_at = novel.get('updated_at', '')[:10] if novel.get('updated_at') else 'N/A'
        table.add_row(
            str(novel['id']),
            novel['title'],
            novel['author'] or 'Unknown',
            novel['status'],
            str(novel.get('chapter_count', 0)),
            updated_at
        )
    
    console.print(table)
    console.print(f"\n[dim]Showing {len(novels)} of {db.count_novels()} novels[/dim]")


@app.command("get")
def get_novel(
    novel_id: int = typer.Argument(..., help="The novel ID to retrieve")
) -> None:
    """
    Display detailed information for a specific novel.
    
    Shows all novel metadata including created_at and updated_at timestamps,
    and the count of associated chapters.
    """
    from babel.data.db import DatabaseManager
    
    db = DatabaseManager(get_db_path())
    
    # Get novel with chapter count
    novel = db.get_novel_with_chapter_count(novel_id)
    
    if not novel:
        console.print(f"[red]Error: Novel with ID {novel_id} not found[/red]")
        raise typer.Exit(1)
    
    # Display novel details
    console.print(f"\n[bold cyan]Novel Details[/bold cyan]\n")
    
    table = Table(show_header=False, box=None)
    table.add_column("Field", style="dim")
    table.add_column("Value", style="green")
    
    table.add_row("ID", str(novel['id']))
    table.add_row("Title", novel['title'])
    table.add_row("Author", novel['author'] or 'Unknown')
    table.add_row("Status", novel['status'])
    table.add_row("Chapters", str(novel.get('chapter_count', 0)))
    
    if novel.get('cover_url'):
        table.add_row("Cover URL", novel['cover_url'])
    
    if novel.get('synopsis'):
        console.print("[dim]Synopsis:[/dim]")
        console.print(f"[white]{novel['synopsis']}[/white]\n")
    
    if novel.get('tags'):
        table.add_row("Tags", novel['tags'])
    
    created_at = novel.get('created_at', '')[:19] if novel.get('created_at') else 'N/A'
    updated_at = novel.get('updated_at', '')[:19] if novel.get('updated_at') else 'N/A'
    table.add_row("Created", created_at)
    table.add_row("Updated", updated_at)
    
    console.print(table)


@app.command("update")
def update_novel(
    novel_id: int = typer.Argument(..., help="The novel ID to update"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Novel title"),
    author: Optional[str] = typer.Option(None, "--author", "-a", help="Novel author"),
    cover_url: Optional[str] = typer.Option(None, "--cover-url", "-c", help="Cover image URL"),
    status: Optional[str] = typer.Option(None, "--status", "-s", help="Status (active, completed, paused, abandoned)"),
    synopsis: Optional[str] = typer.Option(None, "--synopsis", help="Novel synopsis"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags")
) -> None:
    """
    Update novel metadata.
    
    At least one update field must be provided.
    """
    from babel.data.db import DatabaseManager
    
    db = DatabaseManager(get_db_path())
    
    # Verify novel exists
    novel = db.get_novel(novel_id)
    if not novel:
        console.print(f"[red]Error: Novel with ID {novel_id} not found[/red]")
        raise typer.Exit(1)
    
    # Check if any update fields provided
    update_fields = {}
    if title is not None:
        update_fields['title'] = title
    if author is not None:
        update_fields['author'] = author
    if cover_url is not None:
        update_fields['cover_url'] = cover_url
    if status is not None:
        update_fields['status'] = status
    if synopsis is not None:
        update_fields['synopsis'] = synopsis
    if tags is not None:
        update_fields['tags'] = tags
    
    if not update_fields:
        console.print("[yellow]Error: No update fields provided[/yellow]")
        console.print("Available options: --title, --author, --cover-url, --status, --synopsis, --tags")
        raise typer.Exit(1)
    
    # Perform update
    result = db.update_novel(novel_id, **update_fields)
    
    if result:
        console.print(f"[green]✓[/green] Novel {novel_id} updated successfully")
        
        # Display updated novel
        updated_novel = db.get_novel_with_chapter_count(novel_id)
        console.print(f"\n[bold cyan]Updated Novel[/bold cyan]")
        console.print(f"  ID: {updated_novel['id']}")
        console.print(f"  Title: {updated_novel['title']}")
        console.print(f"  Author: {updated_novel['author'] or 'Unknown'}")
        console.print(f"  Status: {updated_novel['status']}")
    else:
        console.print(f"[red]Error: Failed to update novel {novel_id}[/red]")
        raise typer.Exit(1)


@app.command("delete")
def delete_novel(
    novel_id: int = typer.Argument(..., help="The novel ID to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt")
) -> None:
    """
    Delete a novel and all associated data.
    
    This will:
    - Delete the novel from the database (cascades to chapters and pipeline state)
    - Display a warning about associated filesystem directories
    
    Prompts for confirmation unless --force is used.
    """
    from babel.data.db import DatabaseManager
    
    db = DatabaseManager(get_db_path())
    
    # Verify novel exists
    novel = db.get_novel_with_chapter_count(novel_id)
    if not novel:
        console.print(f"[red]Error: Novel with ID {novel_id} not found[/red]")
        raise typer.Exit(1)
    
    chapter_count = novel.get('chapter_count', 0)
    
    # Confirmation prompt
    if not force:
        console.print(f"\n[bold yellow]Warning: You are about to delete a novel![/bold yellow]\n")
        console.print(f"  Novel: [green]{novel['title']}[/green]")
        console.print(f"  Chapters: {chapter_count}")
        console.print(f"\n[red]This action will:[/red]")
        console.print("  - Delete the novel from the database")
        console.print("  - Cascade delete all associated chapters and pipeline state")
        console.print("  - [bold]NOT[/bold] automatically delete filesystem directories")
        
        confirm = typer.confirm("\nAre you sure you want to delete this novel?")
        if not confirm:
            console.print("[yellow]Deletion cancelled[/yellow]")
            raise typer.Exit(0)
    
    # Perform deletion
    result = db.delete_novel(novel_id)
    
    if result:
        console.print(f"[green]✓[/green] Novel '{novel['title']}' (ID: {novel_id}) deleted successfully")
        
        if chapter_count > 0:
            console.print(f"  - {chapter_count} chapters cascade deleted")
        
        console.print("\n[yellow]Note:[/yellow] Associated filesystem directories were NOT deleted.")
        console.print("  You may want to manually remove:")
        console.print(f"    - data/clean/novel_{novel_id}/")
        console.print(f"    - data/json/novel_{novel_id}/")
        console.print(f"    - data/render/novel_{novel_id}/")
        console.print(f"    - config/chapter_map_novel_{novel_id}.json")
    else:
        console.print(f"[red]Error: Failed to delete novel {novel_id}[/red]")
        raise typer.Exit(1)