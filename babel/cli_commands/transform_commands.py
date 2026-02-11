"""Transform commands - LLM-based text transformation"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress

app = typer.Typer(help="Transform raw text using LLM")
console = Console()


@app.command("chapter")
def transform_chapter(
    input_file: Path = typer.Argument(..., help="Input text file"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    provider: str = typer.Option("gemini", "--provider", "-p", help="LLM provider (gemini/groq/ollama)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name"),
):
    """Transform a single chapter using LLM"""
    from babel.transform.transformer import Transformer
    from babel.transform.gemini_client import GeminiClient
    from babel.transform.groq_client import GroqClient
    from babel.transform.ollama_client import OllamaClient
    
    # Select client
    if provider == "gemini":
        client = GeminiClient(model_name=model)
    elif provider == "groq":
        client = GroqClient(model_name=model)
    elif provider == "ollama":
        client = OllamaClient(model_name=model)
    else:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        raise typer.Exit(1)
    
    transformer = Transformer(client)
    
    # Read input
    with console.status(f"[bold green]Reading {input_file}..."):
        text = input_file.read_text(encoding="utf-8")
    
    # Transform
    with console.status(f"[bold green]Transforming with {provider}..."):
        result = transformer.transform(text)
    
    # Write output
    if output_file is None:
        output_file = input_file.with_suffix(".json")
    
    output_file.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"[green]✓[/green] Transformed chapter saved to {output_file}")


@app.command("batch")
def transform_batch(
    input_dir: Path = typer.Argument(..., help="Input directory with text files"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    provider: str = typer.Option("gemini", "--provider", "-p", help="LLM provider"),
    pattern: str = typer.Option("*.txt", "--pattern", help="File pattern to match"),
):
    """Transform multiple chapters in batch"""
    from babel.transform.batch_processor import BatchProcessor
    from babel.transform.gemini_client import GeminiClient
    from babel.transform.groq_client import GroqClient
    
    if provider == "gemini":
        client = GeminiClient()
    elif provider == "groq":
        client = GroqClient()
    else:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        raise typer.Exit(1)
    
    if output_dir is None:
        output_dir = input_dir / "output"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    processor = BatchProcessor(client, input_dir, output_dir)
    
    with Progress() as progress:
        task = progress.add_task("[green]Processing chapters...", total=None)
        processor.process_all(pattern=pattern)
        progress.update(task, completed=True)
    
    console.print(f"[green]✓[/green] Batch processing complete")


@app.command("validate")
def validate_output(
    json_file: Path = typer.Argument(..., help="JSON file to validate"),
):
    """Validate transformed JSON output"""
    from babel.transform.validator import Validator
    
    validator = Validator()
    
    with console.status(f"[bold green]Validating {json_file}..."):
        result = validator.validate_file(json_file)
    
    if result.is_valid:
        console.print(f"[green]✓[/green] Valid JSON structure")
    else:
        console.print(f"[red]✗[/red] Validation failed:")
        for error in result.errors:
            console.print(f"  [red]•[/red] {error}")
        raise typer.Exit(1)
