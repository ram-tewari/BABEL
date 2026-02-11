"""Pipeline commands - Full pipeline orchestration"""
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console

app = typer.Typer(help="Run full processing pipeline")
console = Console()


@app.command("run")
def run_pipeline(
    input_dir: Path = typer.Argument(..., help="Input directory with raw text files"),
    output_dir: Path = typer.Argument(..., help="Output directory"),
    config: Path = typer.Option("config/pipeline.yaml", "--config", "-c", help="Pipeline config file"),
    provider: str = typer.Option("gemini", "--provider", "-p", help="LLM provider"),
    skip_transform: bool = typer.Option(False, "--skip-transform", help="Skip transformation step"),
    skip_render: bool = typer.Option(False, "--skip-render", help="Skip rendering step"),
):
    """Run the complete processing pipeline"""
    from babel.pipeline.orchestrator import PipelineOrchestrator
    from babel.pipeline.core import PipelineConfig
    import yaml
    
    # Load config
    with console.status(f"[bold green]Loading config from {config}..."):
        config_data = yaml.safe_load(config.read_text())
        pipeline_config = PipelineConfig(**config_data)
    
    # Override provider
    pipeline_config.provider = provider
    
    # Create orchestrator
    orchestrator = PipelineOrchestrator(
        config=pipeline_config,
        input_dir=input_dir,
        output_dir=output_dir
    )
    
    # Run pipeline
    console.print("[bold cyan]Starting pipeline...[/bold cyan]")
    
    try:
        orchestrator.run(
            skip_transform=skip_transform,
            skip_render=skip_render
        )
        console.print("[green]✓[/green] Pipeline completed successfully")
    except Exception as e:
        console.print(f"[red]✗[/red] Pipeline failed: {e}")
        raise typer.Exit(1)


@app.command("status")
def pipeline_status(
    state_file: Path = typer.Option("config/pipeline_state.json", "--state", "-s", help="State file"),
):
    """Show pipeline status"""
    from babel.pipeline.state import PipelineState
    from rich.table import Table
    
    state = PipelineState.load(state_file)
    
    table = Table(title="Pipeline Status")
    table.add_column("Stage", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Progress", style="white")
    
    for stage, info in state.stages.items():
        table.add_row(
            stage,
            info.get("status", "pending"),
            f"{info.get('completed', 0)}/{info.get('total', 0)}"
        )
    
    console.print(table)


@app.command("resume")
def resume_pipeline(
    state_file: Path = typer.Option("config/pipeline_state.json", "--state", "-s", help="State file"),
):
    """Resume a failed pipeline from saved state"""
    from babel.pipeline.orchestrator import PipelineOrchestrator
    from babel.pipeline.state import PipelineState
    
    state = PipelineState.load(state_file)
    
    console.print(f"[bold cyan]Resuming pipeline from {state.current_stage}...[/bold cyan]")
    
    orchestrator = PipelineOrchestrator.from_state(state)
    
    try:
        orchestrator.resume()
        console.print("[green]✓[/green] Pipeline resumed and completed")
    except Exception as e:
        console.print(f"[red]✗[/red] Pipeline failed: {e}")
        raise typer.Exit(1)
