"""Ingestion commands for BABEL CLI."""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint

app = typer.Typer(
    help="Ingest novel files into the database"
)

console = Console()


def get_db_path() -> Path:
    """Get the database path from the CLI module."""
    from babel.cli import get_db_path as _get_db_path
    return _get_db_path()


def extract_metadata(file_path: Path, filename: str) -> dict:
    """
    Extract metadata from file with fallback strategy.
    
    Priority:
    1. EPUB Dublin Core metadata (if EPUB file)
    2. Filename parsing
    3. Default to filename as title
    """
    from babel.api.metadata_extraction import (
        extract_metadata_from_epub,
        extract_title_from_filename
    )
    
    result = {'title': None, 'author': None}
    
    # Check if file is EPUB
    is_epub = file_path.suffix.lower() == '.epub'
    
    if is_epub:
        # Try EPUB metadata extraction first
        epub_metadata = extract_metadata_from_epub(file_path)
        
        # Use EPUB metadata if we got a title
        if epub_metadata.get('title') and epub_metadata['title'].strip():
            result['title'] = epub_metadata['title']
            result['author'] = epub_metadata.get('author')
            return result
    
    # Fall back to filename extraction
    title = extract_title_from_filename(filename)
    result['title'] = title
    result['author'] = None
    
    return result


def extract_chapters_from_file(file_path: Path) -> list:
    """
    Extract chapters from a file.
    
    Supports:
    - EPUB files (using EPUBExtractor)
    - Text files (simple line-based extraction)
    
    Returns:
        List of chapter dictionaries with index, title, content, filename.
    """
    from babel.sanitize import EPUBExtractor, sanitize_chapter_text
    
    chapters = []
    
    if file_path.suffix.lower() == '.epub':
        # Extract from EPUB
        try:
            with EPUBExtractor(file_path) as extractor:
                metadata = extractor.extract_metadata()
                
                for chapter in metadata.chapters:
                    # Sanitize content
                    content = sanitize_chapter_text(chapter.get('content', ''))
                    
                    chapters.append({
                        'chapter_index': chapter.get('chapter_index', len(chapters) + 1),
                        'title': chapter.get('title', f"Chapter {len(chapters) + 1}"),
                        'content': content,
                        'filename': chapter.get('filename', f"chapter_{len(chapters) + 1}.txt")
                    })
        except Exception as e:
            console.print(f"[red]Error extracting chapters from EPUB: {e}[/red]")
            raise typer.Exit(1)
    
    else:
        # Text file - treat entire file as one chapter
        try:
            content = file_path.read_text(encoding='utf-8')
            content = sanitize_chapter_text(content)
            
            # Use filename for title
            title = file_path.stem.replace('_', ' ').replace('-', ' ').strip()
            title = title.title() if title else "Chapter 1"
            
            chapters.append({
                'chapter_index': 1,
                'title': title,
                'content': content,
                'filename': file_path.name
            })
        except Exception as e:
            console.print(f"[red]Error reading text file: {e}[/red]")
            raise typer.Exit(1)
    
    return chapters


def initialize_novel_directories(novel_id: int) -> None:
    """
    Create directory structure for a novel.
    
    Creates:
    - data/raw/novel_{id}/
    - data/clean/novel_{id}/
    - data/json/novel_{id}/
    - data/render/novel_{id}/
    """
    base_dirs = ['raw', 'clean', 'json', 'render']
    
    for phase in base_dirs:
        dir_path = Path(f"data/{phase}/novel_{novel_id}")
        dir_path.mkdir(parents=True, exist_ok=True)


@app.command()
def ingest(
    input_file: Path = typer.Argument(
        ...,
        help="Path to the novel file to ingest (EPUB or text file)"
    ),
    title: Optional[str] = typer.Option(
        None,
        "--title", "-t",
        help="Override novel title"
    ),
    author: Optional[str] = typer.Option(
        None,
        "--author", "-a",
        help="Override novel author"
    )
) -> None:
    """
    Ingest a novel file and create a database entry.
    
    Extracts metadata from the file (EPUB Dublin Core or filename),
    creates a novel entry in the database, and extracts chapters.
    
    Displays the novel_id and chapter count on success.
    """
    from babel.data.db import DatabaseManager
    
    # Validate input file
    if not input_file.exists():
        console.print(f"[red]Error: File not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    if not input_file.is_file():
        console.print(f"[red]Error: Not a file: {input_file}[/red]")
        raise typer.Exit(1)
    
    # Check file extension
    valid_extensions = ['.epub', '.txt']
    if input_file.suffix.lower() not in valid_extensions:
        console.print(
            f"[red]Error: Unsupported file format '{input_file.suffix}'[/red]\n"
            f"Supported formats: {', '.join(valid_extensions)}"
        )
        raise typer.Exit(1)
    
    db = DatabaseManager(get_db_path())
    
    try:
        # Extract metadata
        metadata = extract_metadata(input_file, input_file.name)
        
        # Override with CLI options if provided
        novel_title = title if title else metadata['title']
        novel_author = author if author else metadata['author']
        
        if not novel_title:
            novel_title = input_file.stem
        
        # Create novel entry with transaction safety
        with db.transaction():
            # Create novel
            novel_id = db.create_novel(
                title=novel_title,
                author=novel_author,
                status="active"
            )
            
            # Initialize directories
            try:
                initialize_novel_directories(novel_id)
            except OSError as e:
                # Rollback the transaction if directory creation fails
                db.rollback()
                console.print(f"[red]Error creating directories: {e}[/red]")
                raise typer.Exit(1)
            
            # Extract chapters
            chapters = extract_chapters_from_file(input_file)
            
            # Store chapters in database
            for chapter in chapters:
                db.create_chapter(
                    chapter_index=chapter['chapter_index'],
                    filename=chapter['filename'],
                    novel_id=novel_id,
                    title=chapter['title']
                )
        
        # Display success message
        console.print(f"\n[bold green]✓ Novel ingested successfully[/bold green]\n")
        
        table = Table(show_header=False, box=None)
        table.add_column("Field", style="dim")
        table.add_column("Value", style="green")
        
        table.add_row("Novel ID", str(novel_id))
        table.add_row("Title", novel_title)
        table.add_row("Author", novel_author or "Unknown")
        table.add_row("Chapters", str(len(chapters)))
        
        console.print(table)
        
        # Show chapter summary
        if chapters:
            console.print(f"\n[bold cyan]Chapters:[/bold cyan]")
            chapter_table = Table(show_header=True)
            chapter_table.add_column("#", style="cyan", width=4)
            chapter_table.add_column("Title", style="green")
            chapter_table.add_column("Filename", style="dim")
            
            for chapter in chapters[:10]:  # Show first 10
                chapter_table.add_row(
                    str(chapter['chapter_index']),
                    chapter['title'][:50],
                    chapter['filename']
                )
            
            if len(chapters) > 10:
                console.print(f"[dim]... and {len(chapters) - 10} more chapters[/dim]")
            
            console.print(chapter_table)
        
        console.print(f"\n[dim]Directories created: data/*/novel_{novel_id}/[/dim]")
    
    except Exception as e:
        console.print(f"[red]Error ingesting novel: {e}[/red]")
        raise typer.Exit(1)