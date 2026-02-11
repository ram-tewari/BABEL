"""Utility commands - Diagnostics and maintenance"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

app = typer.Typer(help="Utility and diagnostic commands")
console = Console()


@app.command("diagnose")
def diagnose_provider(
    provider: str = typer.Argument(..., help="Provider to diagnose (gemini/groq/ollama)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name"),
):
    """Diagnose LLM provider connection and configuration"""
    from babel.transform.gemini_client import GeminiClient
    from babel.transform.groq_client import GroqClient
    from babel.transform.ollama_client import OllamaClient
    
    console.print(f"[bold cyan]Diagnosing {provider}...[/bold cyan]\n")
    
    try:
        if provider == "gemini":
            client = GeminiClient(model_name=model)
            console.print("[green]✓[/green] Gemini client initialized")
            console.print(f"  Model: {client.model_name}")
            
        elif provider == "groq":
            client = GroqClient(model_name=model)
            console.print("[green]✓[/green] Groq client initialized")
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
