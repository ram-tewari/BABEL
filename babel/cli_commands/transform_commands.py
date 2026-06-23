"""Transform commands - LLM-based text transformation"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.progress import Progress

# Client classes imported at module level so they are patchable in tests and
# selectable via the --provider switch. NVIDIA NIM is the only default path;
# Gemini/Ollama remain available as explicit opt-ins.
from babel.transform.nvidia_client import NvidiaClient
from babel.transform.gemini_client import GeminiClient
from babel.transform.ollama_client import OllamaClient
from babel.transform.batch_processor import BatchProcessor

# Secondary NVIDIA model used as the rate-limit / failure fallback so quality
# never drops to a weaker provider.
NVIDIA_FALLBACK_MODEL = "deepseek"

app = typer.Typer(help="Transform raw text using LLM")
console = Console()


@app.command("chapter")
def transform_chapter(
    input_file: Path = typer.Argument(..., help="Input text file"),
    output_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Output JSON file"),
    provider: str = typer.Option("nvidia", "--provider", "-p", help="LLM provider (nvidia/gemini/ollama)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name (or alias e.g. qwen/deepseek)"),
):
    """Transform a single chapter using LLM (default: NVIDIA NIM / Qwen3-235B)"""
    from babel.transform.transformer import Transformer

    # Select client
    if provider == "nvidia":
        client = NvidiaClient(model_name=model)
    elif provider == "gemini":
        client = GeminiClient(model_name=model)
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
    input_dir: Optional[Path] = typer.Option(None, "--input", "-i", help="Input directory with text files"),
    output_dir: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory"),
    provider: str = typer.Option("nvidia", "--provider", "-p", help="LLM provider (nvidia/gemini)"),
    pattern: str = typer.Option("*.txt", "--pattern", help="File pattern to match"),
    novel_id: Optional[int] = typer.Option(None, "--novel-id", "-n", help="Novel ID for database-first processing"),
    auto_fallback: bool = typer.Option(True, "--auto-fallback", help="Fall back to a secondary NVIDIA model on rate limits"),
):
    """Transform multiple chapters in batch (default: NVIDIA NIM Qwen3-235B,
    DeepSeek-V3.1 fallback). Set NVIDIA_API_KEYS (comma-separated) for key
    rotation to avoid rate limits."""
    from babel.data.db import DatabaseManager

    # Select the transform client (NVIDIA-only by default). Rate limits are
    # handled by multi-key rotation (NVIDIA_API_KEYS) inside the client.
    if provider == "nvidia":
        primary_client = NvidiaClient()
        console.print("[cyan]Using NVIDIA NIM (Qwen3-235B) — set NVIDIA_API_KEYS "
                      "(comma-separated) for key rotation[/cyan]")
    elif provider == "gemini":
        primary_client = GeminiClient()
        console.print("[cyan]Using Gemini[/cyan]")
    else:
        console.print(f"[red]Unknown provider: {provider}[/red]")
        raise typer.Exit(1)
    
    db = DatabaseManager()
    chapters = []
    
    if novel_id is not None:
        # Novel-specific processing
        novel = db.get_novel(novel_id)
        if not novel:
            console.print(f"[red]Novel with ID {novel_id} not found[/red]")
            raise typer.Exit(1)
        
        # Use novel-specific directories
        if input_dir is None:
            input_dir = Path(f"data/clean/novel_{novel_id}")
        if output_dir is None:
            output_dir = Path(f"data/json/novel_{novel_id}")
        
        # Get chapters from database
        chapters = db.get_chapters_by_novel(novel_id)
        
        # Update pipeline state to running
        db.update_pipeline_state(
            phase="transform",
            status="running",
            novel_id=novel_id,
            total_chapters=len(chapters)
        )
    else:
        # Legacy processing (backward compatibility)
        if input_dir is None:
            input_dir = Path("data/clean")
        if output_dir is None:
            output_dir = Path("data/json")
    
    output_dir.mkdir(parents=True, exist_ok=True)

    processor = BatchProcessor(input_dir, output_dir, client=primary_client)
    processed, skipped, failed = processor.process_all_chapters()
    console.print(
        f"[green]✓[/green] Batch complete: {processed} processed, "
        f"{skipped} skipped, {failed} failed"
    )

    # Update final state for novel-specific processing
    if novel_id is not None:
        db.update_pipeline_state(
            phase="transform",
            status="complete",
            novel_id=novel_id,
            last_chapter=len(chapters),
            total_chapters=len(chapters)
        )
    
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
