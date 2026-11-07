"""Command-line interface: `babel --help`."""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

from babel.config import Settings

app = typer.Typer(add_completion=False, no_args_is_help=True, help="BABEL — webnovels as chat-style visual scenarios.")
console = Console()


def _store(settings: Settings):
    from babel.store.db import Store

    return Store(settings.db_path)


def _novel(store, novel: str) -> dict:
    """Find a novel by id or (case-insensitive) title prefix."""
    rows = store.list_novels()
    if novel.isdigit():
        match = [n for n in rows if n["id"] == int(novel)]
    else:
        match = [n for n in rows if n["title"].lower().startswith(novel.lower())]
    if len(match) != 1:
        console.print(f"[red]{'no' if not match else 'ambiguous'} novel matches {novel!r}[/] — see `babel list`")
        raise typer.Exit(1)
    return match[0]


@app.command("import")
def import_cmd(file: Path = typer.Argument(..., exists=True, dir_okay=False, help=".epub or .txt file")) -> None:
    """Import a novel into the library."""
    from babel.ingest import IngestError
    from babel.library import import_book

    settings = Settings.from_env()
    store = _store(settings)
    try:
        nid, book = import_book(store, settings.covers_dir, file)
    except IngestError as e:
        console.print(f"[red]Import failed:[/] {e}")
        raise typer.Exit(1) from e
    console.print(f"[green]Imported[/] [bold]{book.title}[/] (id {nid}) — {len(book.chapters)} chapters"
                  + (f", by {book.author}" if book.author else ""))
    for w in book.warnings:
        console.print(f"  [dim]{w}[/]")
    console.print(f"Next: [cyan]babel transform {nid}[/]  or  [cyan]babel serve[/]")


@app.command("list")
def list_cmd() -> None:
    """List novels in the library."""
    store = _store(Settings.from_env())
    t = Table("id", "title", "author", "chapters", "transformed")
    for n in store.list_novels():
        t.add_row(str(n["id"]), n["title"], n["author"] or "", str(n["chapter_count"]),
                  f"{n['done_count']}/{n['chapter_count']}")
    console.print(t)


@app.command()
def transform(
    novel: str = typer.Argument(..., help="novel id or title prefix"),
    first: int | None = typer.Option(None, help="first chapter index (0-based)"),
    last: int | None = typer.Option(None, help="last chapter index (inclusive)"),
    force: bool = typer.Option(False, help="re-transform chapters that are already done"),
    mode: str = typer.Option("auto", help="auto (LLM with fallback) | llm (strict) | heuristic (offline)"),
    concurrency: int | None = typer.Option(None, help="chapters in flight at once"),
) -> None:
    """Transform chapters in the foreground with a progress bar."""
    from babel.llm.providers import build_router
    from babel.pipeline.jobs import create_job, run_job
    from babel.transform.engine import Engine

    settings = Settings.from_env()
    store = _store(settings)
    n = _novel(store, novel)
    router = build_router(settings.providers, settings.models)
    if mode != "heuristic":
        if router.providers:
            console.print(f"LLM chain: [cyan]{router.label}[/]")
        else:
            console.print("[yellow]No LLM provider configured — using the offline heuristic labeler.[/]\n"
                          "  Set NVIDIA_API_KEYS / GROQ_API_KEYS / GEMINI_API_KEY in .env, or run Ollama.")
            if mode == "llm":
                raise typer.Exit(1)
    engine = Engine(router, settings.chunk_tokens, settings.summary_window)
    jid = create_job(store, n["id"], first, last, force, mode)
    with Progress(TextColumn("[bold]{task.description}"), BarColumn(), MofNCompleteColumn(),
                  TimeRemainingColumn(), TextColumn("{task.fields[last]}"), console=console) as prog:
        job = store.one("SELECT * FROM jobs WHERE id=?", (jid,))
        from babel.pipeline.jobs import job_targets

        task = prog.add_task(n["title"][:40], total=len(job_targets(store, job)), last="")

        def tick(ch: dict, result: str) -> None:
            mark = "[green]✓[/]" if result == "ok" else "[red]✗[/]"
            prog.update(task, advance=1, last=f"{mark} {ch['title'][:40]}")

        try:
            final = run_job(store, engine, jid, concurrency or settings.concurrency, on_chapter=tick)
        except KeyboardInterrupt:
            store.x("UPDATE jobs SET status='paused' WHERE id=?", (jid,))
            console.print("\n[yellow]Paused.[/] Run the same command again to resume.")
            raise typer.Exit(130) from None
    console.print(f"Job {final['status']}: {final['done']}/{final['total']} done, {final['failed']} failed")


@app.command()
def serve(
    host: str | None = typer.Option(None),
    port: int | None = typer.Option(None),
    reload: bool = typer.Option(False, help="auto-reload on code changes (development)"),
) -> None:
    """Run the reader UI + API (and the background transform worker)."""
    import uvicorn

    settings = Settings.from_env()
    h, p = host or settings.host, port or settings.port
    console.print(f"BABEL running at [cyan]http://{h}:{p}[/]")
    uvicorn.run("babel.api.app:create_app", factory=True, host=h, port=p, reload=reload, log_level="info")


@app.command()
def export(
    novel: str = typer.Argument(...),
    fmt: str = typer.Option("epub", "--format", "-f", help="epub | html"),
    out: Path | None = typer.Option(None, "--out", "-o"),
    first: int | None = typer.Option(None),
    last: int | None = typer.Option(None),
) -> None:
    """Export the visual scenario as EPUB (e-readers) or a single HTML file."""
    settings = Settings.from_env()
    store = _store(settings)
    n = _novel(store, novel)
    if fmt == "epub":
        from babel.export.epub import build_epub

        data: bytes = build_epub(store, n["id"], first, last)
    elif fmt == "html":
        from babel.export.html import build_html

        data = build_html(store, n["id"], first, last).encode()
    else:
        console.print("[red]--format must be epub or html[/]")
        raise typer.Exit(1)
    out = out or Path(f"{n['title'][:60].replace('/', '-')}.babel.{fmt}")
    out.write_bytes(data)
    console.print(f"[green]Wrote[/] {out} ({len(data) // 1024} KB)")


@app.command()
def cast(novel: str = typer.Argument(...), top: int = typer.Option(30)) -> None:
    """Show the character codex for a novel."""
    store = _store(Settings.from_env())
    n = _novel(store, novel)
    rows = store.q("SELECT * FROM characters WHERE novel_id=? ORDER BY lines DESC LIMIT ?", (n["id"], top))
    t = Table("id", "name", "lines", "aliases", "note")
    for r in rows:
        aliases = [a["alias"] for a in store.q("SELECT alias FROM aliases WHERE character_id=?", (r["id"],))
                   if a["alias"].lower() != r["name"].lower()]
        t.add_row(str(r["id"]), r["name"] + (" ★" if r["id"] == n["pov_character_id"] else ""),
                  str(r["lines"]), ", ".join(aliases[:5]), (r["note"] or "")[:50])
    console.print(t)


@app.command()
def providers(test: bool = typer.Option(False, "--test", help="send a tiny request to each provider")) -> None:
    """Show which LLM providers are configured (and optionally test them)."""
    from babel.llm.providers import PRESETS, LLMError, build_router

    settings = Settings.from_env()
    router = build_router(settings.providers, settings.models)
    active = {p.name: p for p in router.providers}
    t = Table("provider", "status", "model")
    for name, preset in PRESETS.items():
        p = active.get(name)
        status = "[green]configured[/]" if p else "[dim]not configured[/]"
        if p and test:
            try:
                p.chat([{"role": "user", "content": 'Reply with {"ok": true}'}], max_tokens=20)
                status = "[green]ok[/]"
            except LLMError as e:
                status = f"[red]{str(e)[:60]}[/]"
        t.add_row(name, status, p.model if p else preset.model)
    console.print(t)
    console.print(f"Chain: [cyan]{router.label}[/]" if router.providers else
                  "[yellow]No provider configured — transforms use the offline heuristic.[/]")


@app.command()
def preview(file: Path = typer.Argument(..., exists=True), chapter: int = typer.Option(0)) -> None:
    """Print how one chapter of a file would be labeled offline (no library changes)."""
    from babel.ingest import load_book
    from babel.models import BlockType
    from babel.transform.assemble import assemble
    from babel.transform.heuristic import label_segments
    from babel.transform.segment import segment_text

    book = load_book(file)
    ch = book.chapters[chapter]
    segs = segment_text(ch.text)
    styles = {BlockType.DIALOGUE: "cyan", BlockType.THOUGHT: "magenta", BlockType.SYSTEM: "yellow",
              BlockType.SFX: "red", BlockType.TAG: "dim"}
    console.rule(ch.title)
    for b in assemble(segs, label_segments(segs)):
        who = f"[bold]{b.speaker or '?'}:[/] " if b.type in (BlockType.DIALOGUE, BlockType.THOUGHT) else ""
        console.print(f"[{styles.get(b.type, 'white')}]{b.type.value:>9}[/] {who}{b.text}")


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    app()


if __name__ == "__main__":
    main()
