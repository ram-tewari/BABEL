"""Context commands - Manage glossary and context injection"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage context and glossary")
console = Console()


@app.command("inject")
def inject_context(
    json_file: Path = typer.Argument(..., help="JSON file to inject context into"),
    glossary: Path = typer.Option("config/glossary.yaml", "--glossary", "-g", help="Glossary file"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file"),
):
    """Inject context from glossary into chapter JSON"""
    from babel.context.injector import ContextInjector
    from babel.context.store import ContextStore
    import json
    
    # Load glossary
    store = ContextStore(glossary)
    injector = ContextInjector(store)
    
    # Load chapter
    with console.status(f"[bold green]Loading {json_file}..."):
        data = json.loads(json_file.read_text(encoding="utf-8"))
    
    # Inject context
    with console.status(f"[bold green]Injecting context..."):
        enriched = injector.inject(data)
    
    # Save
    if output_file is None:
        output_file = json_file
    
    output_file.write_text(json.dumps(enriched, indent=2), encoding="utf-8")
    console.print(f"[green]✓[/green] Context injected into {output_file}")


@app.command("list")
def list_entries(
    glossary: Path = typer.Option("config/glossary.yaml", "--glossary", "-g", help="Glossary file"),
    entry_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by type (character/location/term)"),
):
    """List all glossary entries"""
    from babel.context.store import ContextStore
    
    store = ContextStore(glossary)
    entries = store.get_all_entries()
    
    if entry_type:
        entries = [e for e in entries if e.get("type") == entry_type]
    
    table = Table(title="Glossary Entries")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Description", style="white")
    
    for entry in entries:
        table.add_row(
            entry.get("name", ""),
            entry.get("type", ""),
            entry.get("description", "")[:50] + "..." if len(entry.get("description", "")) > 50 else entry.get("description", "")
        )
    
    console.print(table)
    console.print(f"\n[green]Total entries:[/green] {len(entries)}")


@app.command("add")
def add_entry(
    name: str = typer.Argument(..., help="Entry name"),
    entry_type: str = typer.Option(..., "--type", "-t", help="Entry type (character/location/term)"),
    description: str = typer.Option(..., "--description", "-d", help="Entry description"),
    glossary: Path = typer.Option("config/glossary.yaml", "--glossary", "-g", help="Glossary file"),
):
    """Add a new glossary entry"""
    from babel.context.store import ContextStore
    
    store = ContextStore(glossary)
    
    entry = {
        "name": name,
        "type": entry_type,
        "description": description
    }
    
    store.add_entry(entry)
    console.print(f"[green]✓[/green] Added {entry_type} '{name}' to glossary")


@app.command("map")
def generate_map(
    input_dir: Optional[Path] = typer.Option(None, "--input", "-i", help="Directory with JSON files"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output map file"),
    novel_id: Optional[int] = typer.Option(None, "--novel-id", "-n", help="Novel ID for novel-specific map"),
):
    """Generate chapter map from JSON files"""
    from babel.context.cartographer import Cartographer
    from babel.data.db import DatabaseManager
    from babel.cli import get_db_path
    
    # Handle novel-specific paths
    if novel_id is not None:
        db = DatabaseManager(get_db_path())
        novel = db.get_novel(novel_id)
        if not novel:
            console.print(f"[red]Error: Novel with ID {novel_id} not found[/red]")
            raise typer.Exit(1)
        
        if input_dir is None:
            input_dir = Path(f"data/json/novel_{novel_id}")
        if output_file is None:
            output_file = Path(f"config/chapter_map_novel_{novel_id}.json")
    else:
        # Legacy paths
        if input_dir is None:
            input_dir = Path("data/json")
        if output_file is None:
            output_file = Path("config/chapter_map.json")
    
    if not input_dir.exists():
        console.print(f"[red]Error: Input directory {input_dir} does not exist[/red]")
        raise typer.Exit(1)
    
    cartographer = Cartographer(input_dir)
    
    with console.status(f"[bold green]Analyzing chapters..."):
        chapter_map = cartographer.generate_map()
    
    # Add novel_id to metadata if provided
    if novel_id is not None:
        chapter_map_dict = chapter_map.model_dump()
        if 'metadata' not in chapter_map_dict:
            chapter_map_dict['metadata'] = {}
        chapter_map_dict['metadata']['novel_id'] = novel_id
        
        import json
        output_file.write_text(json.dumps(chapter_map_dict, indent=2), encoding="utf-8")
    else:
        output_file.write_text(chapter_map.model_dump_json(indent=2), encoding="utf-8")
    
    console.print(f"[green]✓[/green] Chapter map saved to {output_file}")
