"""Utility commands - Diagnostics and maintenance"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

app = typer.Typer(help="Utility and diagnostic commands")
console = Console()


@app.command("diagnose")
def diagnose_provider(
    provider: str = typer.Argument(..., help="Provider to diagnose (nvidia/gemini/ollama)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name"),
):
    """Diagnose LLM provider connection and configuration"""
    from babel.transform.nvidia_client import NvidiaClient
    from babel.transform.gemini_client import GeminiClient
    from babel.transform.ollama_client import OllamaClient

    console.print(f"[bold cyan]Diagnosing {provider}...[/bold cyan]\n")

    try:
        if provider == "nvidia":
            client = NvidiaClient(model_name=model)
            console.print("[green]✓[/green] NVIDIA NIM client initialized")
            console.print(f"  Model: {client.model_name}")
            console.print(f"  Base URL: {client.base_url}")

        elif provider == "gemini":
            client = GeminiClient(model_name=model)
            console.print("[green]✓[/green] Gemini client initialized")
            console.print(f"  Model: {client.model_name}")
            
        elif provider == "ollama":
            client = OllamaClient(model_name=model)
            console.print("[green]✓[/green] Ollama client initialized")
            console.print(f"  Model: {client.model_name}")
            console.print(f"  Base URL: {client.base_url}")
            
        else:
            console.print(f"[red]✗[/red] Unknown provider: {provider}")
            raise typer.Exit(1)
        
        # Test connection
        with console.status("[bold green]Testing connection..."):
            test_result = client.test_connection()
        
        if test_result:
            console.print("[green]✓[/green] Connection successful")
        else:
            console.print("[red]✗[/red] Connection failed")
            raise typer.Exit(1)
            
    except Exception as e:
        console.print(f"[red]✗[/red] Error: {e}")
        raise typer.Exit(1)


@app.command("sanitize")
def sanitize_text(
    input_file: Path = typer.Argument(..., help="Input text file"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Sanitize raw text file"""
    from babel.sanitize import sanitize_text
    
    with console.status(f"[bold green]Reading {input_file}..."):
        text = input_file.read_text(encoding="utf-8")
    
    with console.status(f"[bold green]Sanitizing text..."):
        sanitized = sanitize_text(text)
    
    if output_file is None:
        output_file = input_file.with_stem(input_file.stem + "_clean")
    
    output_file.write_text(sanitized, encoding="utf-8")
    console.print(f"[green]✓[/green] Sanitized text saved to {output_file}")


@app.command("stats")
def show_stats(
    json_file: Path = typer.Argument(..., help="JSON file to analyze"),
):
    """Show statistics for a chapter JSON file"""
    from babel.render.models import Chapter
    from rich.table import Table
    import json
    
    data = json.loads(json_file.read_text(encoding="utf-8"))
    chapter = Chapter(**data)
    
    # Count blocks by type
    block_counts = {}
    total_words = 0
    
    for block in chapter.blocks:
        block_type = block.type
        block_counts[block_type] = block_counts.get(block_type, 0) + 1
        
        # Count words
        if hasattr(block, 'content'):
            total_words += len(block.content.split())
    
    # Display stats
    table = Table(title=f"Chapter Statistics: {chapter.metadata.title}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    
    table.add_row("Chapter Number", str(chapter.metadata.chapter_number))
    table.add_row("Total Blocks", str(len(chapter.blocks)))
    table.add_row("Total Words", str(total_words))
    table.add_row("", "")
    
    for block_type, count in sorted(block_counts.items()):
        table.add_row(f"{block_type} blocks", str(count))
    
    console.print(table)


@app.command("validate-all")
def validate_directory(
    input_dir: Path = typer.Argument(..., help="Directory with JSON files"),
):
    """Validate all JSON files in a directory"""
    from babel.transform.validator import Validator
    from rich.progress import track
    
    validator = Validator()
    json_files = sorted(input_dir.glob("*.json"))
    
    errors = []
    
    for json_file in track(json_files, description="Validating files"):
        result = validator.validate_file(json_file)
        if not result.is_valid:
            errors.append((json_file.name, result.errors))
    
    if errors:
        console.print(f"\n[red]Found {len(errors)} files with errors:[/red]\n")
        for filename, file_errors in errors:
            console.print(f"[yellow]{filename}:[/yellow]")
            for error in file_errors:
                console.print(f"  [red]•[/red] {error}")
        raise typer.Exit(1)
    else:
        console.print(f"\n[green]✓[/green] All {len(json_files)} files are valid")


@app.command("db-info")
def db_info():
    """Display database statistics and information"""
    from babel.data.db import DatabaseManager
    from babel.cli import get_db_path
    from rich.table import Table
    import os
    
    db_path = get_db_path()
    db = DatabaseManager(db_path)
    
    # Get statistics
    total_novels = db.count_novels()
    all_chapters = db.get_all_chapters()
    total_chapters = len(all_chapters)
    
    # Count chapters by novel
    novel_chapters = {}
    legacy_chapters = 0
    for chapter in all_chapters:
        if chapter['novel_id'] is None:
            legacy_chapters += 1
        else:
            novel_chapters[chapter['novel_id']] = novel_chapters.get(chapter['novel_id'], 0) + 1
    
    # Get file size
    db_size = os.path.getsize(db_path) if db_path.exists() else 0
    db_size_mb = db_size / (1024 * 1024)
    
    # Display info
    console.print("\n[bold cyan]Database Information[/bold cyan]\n")
    
    table = Table(show_header=False, box=None)
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="green")
    
    table.add_row("Database Path", str(db_path))
    table.add_row("Database Size", f"{db_size_mb:.2f} MB")
    table.add_row("Total Novels", str(total_novels))
    table.add_row("Total Chapters", str(total_chapters))
    table.add_row("Legacy Chapters", str(legacy_chapters))
    table.add_row("Novels with Chapters", str(len(novel_chapters)))
    
    console.print(table)


@app.command("db-check")
def db_check():
    """Verify database integrity and detect issues"""
    from babel.data.db import DatabaseManager
    from babel.cli import get_db_path
    from rich.table import Table
    
    db_path = get_db_path()
    db = DatabaseManager(db_path)
    
    console.print("\n[bold cyan]Database Integrity Check[/bold cyan]\n")
    
    issues = []
    
    # Check for orphaned chapters (novel_id references non-existent novel)
    with console.status("[bold green]Checking for orphaned chapters..."):
        all_chapters = db.get_all_chapters()
        novels = db.list_novels(limit=10000)
        novel_ids = {n['id'] for n in novels}
        
        orphaned = [c for c in all_chapters if c['novel_id'] is not None and c['novel_id'] not in novel_ids]
        
        if orphaned:
            issues.append(("Orphaned Chapters", f"Found {len(orphaned)} chapters referencing non-existent novels"))
    
    # Check for missing files
    with console.status("[bold green]Checking for missing chapter files..."):
        missing_files = []
        for chapter in all_chapters:
            if chapter['novel_id']:
                file_path = Path(f"data/clean/novel_{chapter['novel_id']}/{chapter['filename']}")
            else:
                file_path = Path(f"data/clean/{chapter['filename']}")
            
            if not file_path.exists():
                missing_files.append((chapter['id'], chapter['filename']))
        
        if missing_files:
            issues.append(("Missing Files", f"Found {len(missing_files)} chapters with missing source files"))
    
    # Check for stuck pipeline states
    with console.status("[bold green]Checking for stuck pipeline states..."):
        all_states = db.get_all_pipeline_states()
        stuck_states = [s for s in all_states if s['status'] == 'running']
        
        if stuck_states:
            issues.append(("Stuck Pipeline States", f"Found {len(stuck_states)} pipeline states stuck in 'running' status"))
    
    # Display results
    if issues:
        console.print("[yellow]Issues Found:[/yellow]\n")
        
        table = Table()
        table.add_column("Issue Type", style="yellow")
        table.add_column("Description", style="white")
        
        for issue_type, description in issues:
            table.add_row(issue_type, description)
        
        console.print(table)
        console.print("\n[yellow]Recommendations:[/yellow]")
        console.print("  - Use [cyan]babel util db-vacuum[/cyan] to optimize the database")
        console.print("  - Manually review and clean up orphaned data")
        raise typer.Exit(1)
    else:
        console.print("[green]✓[/green] No integrity issues found")
        console.print("[dim]Database is healthy[/dim]")


@app.command("db-vacuum")
def db_vacuum():
    """Optimize and compact the database file"""
    from babel.data.db import DatabaseManager
    from babel.cli import get_db_path
    import os
    
    db_path = get_db_path()
    
    # Get size before
    size_before = os.path.getsize(db_path) if db_path.exists() else 0
    size_before_mb = size_before / (1024 * 1024)
    
    console.print(f"\n[bold cyan]Database Optimization[/bold cyan]\n")
    console.print(f"Size before: {size_before_mb:.2f} MB")
    
    # Run VACUUM
    with console.status("[bold green]Running VACUUM..."):
        db = DatabaseManager(db_path)
        conn = db.connection
        conn.execute("VACUUM")
        conn.commit()
        db.close()
    
    # Get size after
    size_after = os.path.getsize(db_path)
    size_after_mb = size_after / (1024 * 1024)
    saved_mb = (size_before - size_after) / (1024 * 1024)
    
    console.print(f"Size after:  {size_after_mb:.2f} MB")
    console.print(f"[green]✓[/green] Saved {saved_mb:.2f} MB")
    console.print("[dim]Database optimized successfully[/dim]")
