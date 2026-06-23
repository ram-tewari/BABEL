"""Pipeline commands - Full pipeline orchestration"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

app = typer.Typer(help="Run full processing pipeline")
console = Console()


@app.command("run")
def run_pipeline(
    novel_id: int = typer.Option(..., "--novel-id", "-n", help="Novel ID to process (required)"),
    provider: str = typer.Option("nvidia", "--provider", "-p", help="LLM provider"),
    skip_transform: bool = typer.Option(False, "--skip-transform", help="Skip transformation step"),
    skip_render: bool = typer.Option(False, "--skip-render", help="Skip rendering step"),
):
    """Run the complete processing pipeline for a specific novel"""
    from babel.data.db import DatabaseManager
    from babel.cli import get_db_path
    from rich.progress import Progress, SpinnerColumn, TextColumn
    
    db = DatabaseManager(get_db_path())
    
    # Verify novel exists
    novel = db.get_novel_with_chapter_count(novel_id)
    if not novel:
        console.print(f"[red]Error: Novel with ID {novel_id} not found[/red]")
        raise typer.Exit(1)
    
    console.print(f"\n[bold cyan]Pipeline: {novel['title']}[/bold cyan]")
    console.print(f"Novel ID: {novel_id}")
    console.print(f"Chapters: {novel.get('chapter_count', 0)}\n")
    
    # Run transform
    if not skip_transform:
        console.print("[bold]Phase 1: Transform[/bold]")
        result = typer.run(f"babel transform batch --novel-id {novel_id} --provider {provider}")
        if result != 0:
            console.print("[red]✗[/red] Transform phase failed")
            raise typer.Exit(1)
    
    # Run render
    if not skip_render:
        console.print("\n[bold]Phase 2: Render[/bold]")
        result = typer.run(f"babel render batch --novel-id {novel_id}")
        if result != 0:
            console.print("[red]✗[/red] Render phase failed")
            raise typer.Exit(1)
    
    console.print(f"\n[green]✓[/green] Pipeline completed for '{novel['title']}'")
    console.print(f"  Novel ID: {novel_id}")
    console.print(f"  Chapters: {novel.get('chapter_count', 0)}")


@app.command("status")
def pipeline_status(
    novel_id: Optional[int] = typer.Option(None, "--novel-id", "-n", help="Filter by novel ID"),
):
    """Show pipeline status for a novel or all novels"""
    from babel.data.db import DatabaseManager
    from babel.cli import get_db_path
    from rich.table import Table
    
    db = DatabaseManager(get_db_path())
    
    if novel_id is not None:
        # Verify novel exists
        novel = db.get_novel(novel_id)
        if not novel:
            console.print(f"[red]Error: Novel with ID {novel_id} not found[/red]")
            raise typer.Exit(1)
        
        # Get pipeline states for this novel
        states = db.get_pipeline_states_by_novel(novel_id)
        
        if not states:
            console.print(f"[yellow]No pipeline state found for novel '{novel['title']}'[/yellow]")
            return
        
        table = Table(title=f"Pipeline Status: {novel['title']}")
        table.add_column("Phase", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Progress", style="white")
        table.add_column("Error", style="red")
        
        for state in states:
            progress = f"{state.get('last_chapter', 0)}/{state.get('total_chapters', 0)}"
            error = state.get('error_message', '')[:50] if state.get('error_message') else ''
            
            table.add_row(
                state['phase'],
                state['status'],
                progress,
                error
            )
        
        console.print(table)
    else:
        # Show all pipeline states
        states = db.get_all_pipeline_states()
        
        if not states:
            console.print("[yellow]No pipeline states found[/yellow]")
            return
        
        table = Table(title="All Pipeline States")
        table.add_column("Novel ID", style="blue")
        table.add_column("Phase", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Progress", style="white")
        
        for state in states:
            novel_id_display = str(state['novel_id']) if state['novel_id'] is not None else 'Legacy'
            progress = f"{state.get('last_chapter', 0)}/{state.get('total_chapters', 0)}"
            
            table.add_row(
                novel_id_display,
                state['phase'],
                state['status'],
                progress
            )
        
        console.print(table)


@app.command("run-all")
def run_all_pipelines(
    status: str = typer.Option("active", "--status", "-s", help="Filter novels by status"),
    provider: str = typer.Option("nvidia", "--provider", "-p", help="LLM provider"),
):
    """Run pipeline for all novels with specified status"""
    from babel.data.db import DatabaseManager
    from babel.cli import get_db_path
    from rich.progress import Progress, SpinnerColumn, TextColumn
    import subprocess
    
    db = DatabaseManager(get_db_path())
    
    # Get novels with specified status
    novels = db.list_novels_with_chapter_count(limit=10000)
    novels = [n for n in novels if n['status'] == status]
    
    if not novels:
        console.print(f"[yellow]No novels found with status '{status}'[/yellow]")
        return
    
    console.print(f"\n[bold cyan]Batch Pipeline Processing[/bold cyan]")
    console.print(f"Processing {len(novels)} novels with status '{status}'\n")
    
    successes = []
    failures = []
    
    for novel in novels:
        console.print(f"\n[bold]Processing: {novel['title']}[/bold] (ID: {novel['id']})")
        
        try:
            # Run pipeline for this novel
            result = subprocess.run(
                ["babel", "pipeline", "run", "--novel-id", str(novel['id']), "--provider", provider],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print(f"[green]✓[/green] Completed: {novel['title']}")
                successes.append(novel['title'])
            else:
                console.print(f"[red]✗[/red] Failed: {novel['title']}")
                failures.append((novel['title'], result.stderr))
        except Exception as e:
            console.print(f"[red]✗[/red] Error: {novel['title']} - {e}")
            failures.append((novel['title'], str(e)))
    
    # Summary
    console.print(f"\n[bold cyan]Batch Processing Summary[/bold cyan]")
    console.print(f"  Successful: [green]{len(successes)}[/green]")
    console.print(f"  Failed: [red]{len(failures)}[/red]")
    console.print(f"  Total: {len(novels)}")
    
    if failures:
        console.print("\n[red]Failed Novels:[/red]")
        for title, error in failures:
            console.print(f"  - {title}")
        raise typer.Exit(1)
