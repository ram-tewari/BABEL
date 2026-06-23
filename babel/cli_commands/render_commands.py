"""Render commands - Convert JSON to HTML"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

app = typer.Typer(help="Render JSON to HTML")
console = Console()


@app.command("chapter")
def render_chapter(
    json_file: Path = typer.Argument(..., help="Input JSON file"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output HTML file"),
    template: Optional[Path] = typer.Option(None, "--template", "-t", help="Custom template file"),
    theme: str = typer.Option("default", "--theme", help="Color theme"),
):
    """Render a single chapter to HTML"""
    from babel.render.renderer import ChapterRenderer as Renderer
    from babel.render.models import Chapter
    import json
    
    # Read JSON
    with console.status(f"[bold green]Reading {json_file}..."):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        chapter = Chapter(**data)
    
    # Render
    renderer = Renderer(template_path=template, theme=theme)
    
    with console.status(f"[bold green]Rendering HTML..."):
        html = renderer.render_chapter(chapter)
    
    # Write output
    if output_file is None:
        output_file = json_file.with_suffix(".html")
    
    output_file.write_text(html, encoding="utf-8")
    console.print(f"[green]✓[/green] Rendered HTML saved to {output_file}")


@app.command("omnibus")
def render_omnibus(
    input_dir: Path = typer.Argument(..., help="Directory with JSON files"),
    output_file: Path = typer.Argument(..., help="Output HTML file"),
    template: Optional[Path] = typer.Option(None, "--template", "-t", help="Custom template file"),
    theme: str = typer.Option("default", "--theme", help="Color theme"),
):
    """Render multiple chapters into a single HTML file"""
    from babel.render.renderer import ChapterRenderer as Renderer
    from babel.render.models import Chapter
    import json
    
    renderer = Renderer(template_path=template, theme=theme)
    chapters = []
    
    # Load all chapters
    json_files = sorted(input_dir.glob("*.json"))
    
    with console.status(f"[bold green]Loading {len(json_files)} chapters..."):
        for json_file in json_files:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            chapters.append(Chapter(**data))
    
    # Render omnibus
    with console.status(f"[bold green]Rendering omnibus HTML..."):
        html = renderer.render_omnibus(chapters)
    
    output_file.write_text(html, encoding="utf-8")
    console.print(f"[green]✓[/green] Omnibus HTML saved to {output_file}")


@app.command("batch")
def render_batch(
    input_dir: Optional[Path] = typer.Option(None, "--input", "-i", help="Directory with JSON files"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    template: Optional[Path] = typer.Option(None, "--template", "-t", help="Custom template file"),
    theme: str = typer.Option("default", "--theme", help="Color theme"),
    novel_id: Optional[int] = typer.Option(None, "--novel-id", "-n", help="Novel ID for novel-specific processing"),
):
    """Render multiple chapters to individual HTML files"""
    from babel.render.renderer import ChapterRenderer as Renderer
    from babel.render.models import Chapter
    from babel.data.db import DatabaseManager
    from babel.cli import get_db_path
    from rich.progress import track
    import json
    
    db = DatabaseManager(get_db_path())
    
    # Handle novel-specific paths
    if novel_id is not None:
        novel = db.get_novel(novel_id)
        if not novel:
            console.print(f"[red]Error: Novel with ID {novel_id} not found[/red]")
            raise typer.Exit(1)
        
        if input_dir is None:
            input_dir = Path(f"data/json/novel_{novel_id}")
        if output_dir is None:
            output_dir = Path(f"data/render/novel_{novel_id}")
        
        # Update pipeline state
        chapters = db.get_chapters_by_novel(novel_id)
        db.update_pipeline_state(
            phase="render",
            status="running",
            novel_id=novel_id,
            total_chapters=len(chapters)
        )
    else:
        # Legacy paths
        if input_dir is None:
            input_dir = Path("data/json")
        if output_dir is None:
            output_dir = Path("data/render")
    
    if not input_dir.exists():
        console.print(f"[red]Error: Input directory {input_dir} does not exist[/red]")
        raise typer.Exit(1)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    renderer = Renderer(template_path=template, theme=theme)
    json_files = sorted(input_dir.glob("*.json"))
    
    if not json_files:
        console.print(f"[yellow]No JSON files found in {input_dir}[/yellow]")
        if novel_id is not None:
            db.update_pipeline_state(
                phase="render",
                status="complete",
                novel_id=novel_id,
                last_chapter=0,
                total_chapters=0
            )
        return
    
    for json_file in track(json_files, description="Rendering chapters"):
        data = json.loads(json_file.read_text(encoding="utf-8"))
        chapter = Chapter(**data)
        html = renderer.render_chapter(chapter)
        
        output_file = output_dir / json_file.with_suffix(".html").name
        output_file.write_text(html, encoding="utf-8")
    
    # Update final state for novel-specific processing
    if novel_id is not None:
        db.update_pipeline_state(
            phase="render",
            status="complete",
            novel_id=novel_id,
            last_chapter=len(json_files),
            total_chapters=len(json_files)
        )
    
    console.print(f"[green]✓[/green] Rendered {len(json_files)} chapters to {output_dir}")