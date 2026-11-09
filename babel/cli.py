"""Command-line interface: `babel --help`."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table

from babel.config import Settings

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="BABEL — read webnovels as chat-style visual scenarios.")
novels_app = typer.Typer(no_args_is_help=True, help="Manage novels in the library.")
glossary_app = typer.Typer(no_args_is_help=True, help="The Akashic Record as YAML (characters, factions, locations, terms).")
db_app = typer.Typer(no_args_is_help=True, help="Database utilities.")
art_app = typer.Typer(no_args_is_help=True, help="Character art: designs, expression sheets, visual-novel readiness.")
theme_app = typer.Typer(no_args_is_help=True, help="The theatre's look: import optional art (e.g. from NOCTURNE).")
app.add_typer(novels_app, name="novels")
app.add_typer(glossary_app, name="glossary")
app.add_typer(db_app, name="db")
app.add_typer(art_app, name="art")
app.add_typer(theme_app, name="theme")
console = Console()


def _settings() -> Settings:
    return Settings.from_env()


def _store(settings: Settings | None = None):
    from babel.store.db import Store

    return Store((settings or _settings()).db_path)


def _novel(store, novel: str) -> dict:
    rows = store.list_novels()
    match = [n for n in rows if n["id"] == int(novel)] if novel.isdigit() else \
        [n for n in rows if n["title"].lower().startswith(novel.lower())]
    if len(match) != 1:
        console.print(f"[red]{'no' if not match else 'ambiguous'} novel matches {novel!r}[/] — see `babel novels list`")
        raise typer.Exit(1)
    return match[0]


def _describe_tiers(cascade) -> None:
    console.print("Cascade: [cyan]rules → memory[/]"
                  + (f" → [green]{cascade.local.label}[/] (local, free)" if cascade.local else " [dim](no local model)[/]")
                  + (f" → [magenta]{cascade.cloud.label}[/] (cloud)" if cascade.cloud else " [dim](no cloud provider)[/]"))


# ── library ────────────────────────────────────────────────────────────────
@app.command("import")
def import_cmd(file: Path = typer.Argument(..., exists=True, dir_okay=False, help=".epub or .txt"),
               chapter_pattern: str | None = typer.Option(None, help="regex for chapter headings in odd TXT files")) -> int:
    """Import a novel into the library."""
    from babel.ingest import IngestError
    from babel.library import import_book

    s = _settings()
    store = _store(s)
    try:
        nid, book = import_book(store, s.covers_dir, file, chapter_pattern=chapter_pattern)
    except IngestError as e:
        console.print(f"[red]Import failed:[/] {e}")
        raise typer.Exit(1) from e
    words = sum(len(c.text.split()) for c in book.chapters)
    console.print(f"[green]Imported[/] [bold]{book.title}[/] (id {nid}) — {len(book.chapters)} chapters, "
                  f"{words:,} words" + (f", by {book.author}" if book.author else ""))
    for w in book.warnings:
        console.print(f"  [dim]{w}[/]")
    return nid


@app.command()
def run(file: Path = typer.Argument(..., exists=True, dir_okay=False),
        tiers: str = typer.Option("auto", help="auto | rules | local | cloud"),
        export_epub: bool = typer.Option(False, "--epub", help="also write an EPUB when done")) -> None:
    """Import a book and transform all of it in one go."""
    nid = import_cmd(file, None)
    transform(str(nid), None, None, False, tiers, None)
    if export_epub:
        export(str(nid), "epub", None, None, None)


@novels_app.command("list")
def novels_list() -> None:
    """List novels."""
    store = _store()
    t = Table("id", "title", "author", "chapters", "transformed", "read")
    for n in store.list_novels():
        t.add_row(str(n["id"]), n["title"], n["author"] or "", str(n["chapter_count"]),
                  f"{n['done_count']}/{n['chapter_count']}", str(n["read_count"]))
    console.print(t)


@novels_app.command("show")
def novels_show(novel: str) -> None:
    """Details for one novel."""
    store = _store()
    n = _novel(store, novel)
    for k in ("id", "title", "author", "language", "status", "source_name", "source_url", "created_at"):
        if n.get(k):
            console.print(f"[dim]{k:>12}[/]  {n[k]}")
    if n["tags"]:
        console.print(f"[dim]{'tags':>12}[/]  {', '.join(n['tags'])}")
    console.print(f"[dim]{'chapters':>12}[/]  {n['chapter_count']} ({n['done_count']} transformed, {n['read_count']} read)")
    if n.get("description"):
        console.print(f"\n{n['description'][:600]}")


@novels_app.command("update")
def novels_update(novel: str, title: str | None = typer.Option(None), author: str | None = typer.Option(None),
                  description: str | None = typer.Option(None)) -> None:
    """Edit title/author/description."""
    store = _store()
    n = _novel(store, novel)
    store.update_novel(n["id"], **{k: v for k, v in dict(title=title, author=author, description=description).items() if v})
    console.print("[green]Updated[/]")


@novels_app.command("delete")
def novels_delete(novel: str, yes: bool = typer.Option(False, "--yes", "-y")) -> None:
    """Delete a novel and everything BABEL stored for it (not your original file)."""
    s = _settings()
    store = _store(s)
    n = _novel(store, novel)
    if not yes and not typer.confirm(f"Delete {n['title']!r} ({n['chapter_count']} chapters, cast, corrections)?"):
        raise typer.Exit(1)
    store.delete_novel(n["id"])
    (s.covers_dir / f"{n['id']}.jpg").unlink(missing_ok=True)
    console.print("[green]Deleted[/]")


@app.command()
def chapters(novel: str, status: str | None = typer.Option(None, help="pending | done | failed")) -> None:
    """List chapters with their transform status."""
    store = _store()
    n = _novel(store, novel)
    t = Table("#", "title", "words", "status", "tiers", "to review")
    for c in store.list_chapters(n["id"]):
        if status and c["status"] != status:
            continue
        t.add_row(str(c["idx"] + 1), c["title"][:60], str(c["word_count"]), c["status"],
                  " ".join(f"{k}:{v}" for k, v in c["tiers"].items()), str(c["review_count"] or ""))
    console.print(t)


# ── pipeline ───────────────────────────────────────────────────────────────
@app.command()
def transform(novel: str = typer.Argument(..., help="novel id or title prefix"),
              first: int | None = typer.Option(None, help="first chapter number (1-based)"),
              last: int | None = typer.Option(None, help="last chapter number (inclusive)"),
              force: bool = typer.Option(False, help="re-run chapters that are already done"),
              tiers: str = typer.Option("auto", help="auto | rules (offline, instant) | local | cloud"),
              concurrency: int | None = typer.Option(None)) -> None:
    """Transform chapters in the foreground (Ctrl-C pauses; run again to resume)."""
    from babel.pipeline.jobs import create_job, job_targets, run_job

    s = _settings()
    store = _store(s)
    n = _novel(store, novel)
    cascade = s.build_cascade()
    _describe_tiers(cascade)
    first_idx = first - 1 if first else None
    last_idx = last - 1 if last else None
    jid = create_job(store, n["id"], first_idx, last_idx, force, tiers)
    job = store.one("SELECT * FROM jobs WHERE id=?", (jid,))
    with Progress(TextColumn("[bold]{task.description}"), BarColumn(), MofNCompleteColumn(), TimeRemainingColumn(),
                  TextColumn("{task.fields[last]}"), console=console) as prog:
        task = prog.add_task(n["title"][:36], total=len(job_targets(store, job)), last="")

        def tick(ch: dict, result: str) -> None:
            prog.update(task, advance=1, last=("[green]✓[/] " if result == "ok" else "[red]✗[/] ") + ch["title"][:40])

        try:
            final = run_job(store, cascade, jid, concurrency or s.concurrency, on_chapter=tick)
        except KeyboardInterrupt:
            store.x("UPDATE jobs SET status='paused' WHERE id=?", (jid,))
            console.print("\n[yellow]Paused.[/] Run the same command again to resume.")
            raise typer.Exit(130) from None
    console.print(f"Job {final['status']}: {final['done']}/{final['total']} done, {final['failed']} failed")
    status(str(n["id"]))


@app.command()
def status(novel: str) -> None:
    """Progress, decision tiers, cost so far and the review queue for a novel."""
    store = _store()
    n = _novel(store, novel)
    rows = store.list_chapters(n["id"])
    done = sum(c["status"] == "done" for c in rows)
    failed = sum(c["status"] == "failed" for c in rows)
    tiers: dict[str, int] = {}
    for c in rows:
        for k, v in c["tiers"].items():
            tiers[k] = tiers.get(k, 0) + v
    total = sum(tiers.values()) or 1
    console.print(f"[bold]{n['title']}[/]: {done}/{len(rows)} transformed" + (f", [red]{failed} failed[/]" if failed else ""))
    if tiers:
        console.print("Lines decided by: " + "  ".join(f"{k} {v / total:.0%}" for k, v in sorted(tiers.items(), key=lambda kv: -kv[1])))
    review = sum(c["review_count"] or 0 for c in rows)
    console.print(f"Lines waiting for review: {review}")
    usage = store.usage_summary(n["id"])
    if usage:
        t = Table("tier", "model", "calls", "questions", "prompt tok", "output tok")
        for u in usage:
            t.add_row(u["tier"], f"{u['provider']}:{u['model']}", str(u["calls"]), str(u["questions"]),
                      f"{u['prompt_tokens']:,}", f"{u['completion_tokens']:,}")
        console.print(t)


@app.command()
def estimate(novel: str, first: int | None = None, last: int | None = None) -> None:
    """Estimate tokens/time for what's left to transform."""
    from fastapi.testclient import TestClient

    from babel.api.app import create_app

    s = _settings()
    store = _store(s)
    n = _novel(store, novel)
    with TestClient(create_app(s, store, start_worker=False)) as c:
        params = {k: v - 1 for k, v in (("first", first), ("last", last)) if v}
        e = c.get(f"/api/novels/{n['id']}/estimate", params=params).json()
    console.print(f"{e['chapters']} chapters ({e['words']:,} words) to go — based on {e['basis']}:")
    for tier, t in e["per_tier"].items():
        console.print(f"  {tier:>5}: ~{t['questions']:,} questions, ~{t['prompt']:,} prompt + {t['completion']:,} output tokens"
                      + ("  (free)" if tier == "local" else ""))
    if e["local_minutes"]:
        console.print(f"  local model time: ~{e['local_minutes']} min")


@app.command()
def review(novel: str, limit: int = 20) -> None:
    """Show the lines BABEL is least sure about (fix them in the reader's Review page)."""
    from babel.library import chapter_view
    from babel.memory.akashic import Akashic

    store = _store()
    n = _novel(store, novel)
    ak = Akashic(store, n["id"])
    shown = 0
    for row in store.q("SELECT id FROM chapters WHERE novel_id=? AND review_count>0 ORDER BY idx", (n["id"],)):
        v = chapter_view(store, row["id"], ak)
        for b in v["blocks"]:
            if b["review"] and shown < limit:
                shown += 1
                console.print(f"[dim]{v['title'][:30]}[/]  [yellow]{b['conf']:.2f}[/] {b['type']} "
                              f"[bold]{b['speaker'] or '?'}[/] ← {', '.join(b['candidates'][:3])}\n    {b['text'][:110]}")
    if not shown:
        console.print("[green]Nothing to review.[/]")


@app.command("eval")
def eval_cmd(tiers: str = typer.Option("auto", help="rules | local | cloud | auto"),
             gold: Path | None = typer.Option(None, help="directory of <name>.txt + <name>.gold.json"),
             verbose: bool = typer.Option(False, "-v")) -> None:
    """Measure attribution quality and cost on gold-labeled chapters."""
    from babel.evals.run import GOLD_DIR, evaluate

    s = _settings()
    cascade = s.build_cascade()
    _describe_tiers(cascade)
    results = evaluate(cascade, mode=tiers, directory=gold or GOLD_DIR)
    t = Table("chapter", "type acc", "speaker acc", "local q", "cloud q", "cloud tokens")
    tot = {"t": 0, "to": 0, "s": 0, "so": 0}
    for r in results:
        loc, cl = r.usage.get("local", {}), r.usage.get("cloud", {})
        t.add_row(r.name, f"{r.type_ok}/{r.total}", f"{r.speaker_ok}/{r.speaker_total}", str(loc.get("questions", 0)),
                  str(cl.get("questions", 0)), f"{cl.get('prompt', 0) + cl.get('completion', 0):,}")
        tot["t"] += r.total
        tot["to"] += r.type_ok
        tot["s"] += r.speaker_total
        tot["so"] += r.speaker_ok
        if verbose:
            from rich.markup import escape

            for e in r.errors:
                console.print(f"  [dim]{r.name}[/] {escape(e)}", soft_wrap=True)
    console.print(t)
    console.print(f"[bold]type {tot['to'] / max(1, tot['t']):.1%}   speaker {tot['so'] / max(1, tot['s']):.1%}[/]")


# ── Akashic Record ─────────────────────────────────────────────────────────
@app.command()
def cast(novel: str, top: int = typer.Option(30)) -> None:
    """Characters in the Akashic Record."""
    from babel.memory.akashic import Akashic

    store = _store()
    n = _novel(store, novel)
    ak = Akashic(store, n["id"])
    t = Table("id", "name", "g", "lines", "aliases", "note")
    for e in sorted(ak.characters, key=lambda e: -(e.get("lines") or 0))[:top]:
        others = [a for a in ak.alias_text.get(e["id"], []) if a.lower() != e["name"].lower()]
        t.add_row(str(e["id"]), e["name"] + (" ★" if e["id"] == ak.pov_id else ""), e.get("gender") or "",
                  str(e["lines"]), ", ".join(others[:4]), (e.get("note") or "")[:50])
    console.print(t)


@glossary_app.command("export")
def glossary_export(novel: str, out: Path | None = typer.Option(None, "-o"), min_lines: int = 0) -> None:
    """Write the glossary as YAML."""
    from babel.memory.akashic import Akashic
    from babel.memory.glossary import export_yaml

    store = _store()
    text = export_yaml(Akashic(store, _novel(store, novel)["id"]), min_lines)
    if out:
        out.write_text(text)
        console.print(f"[green]Wrote[/] {out}")
    else:
        console.print(text, highlight=False)


@glossary_app.command("import")
def glossary_import(novel: str, file: Path = typer.Argument(..., exists=True)) -> None:
    """Merge a YAML glossary into memory (imported fields are never overwritten by models)."""
    from babel.memory.akashic import Akashic
    from babel.memory.glossary import GlossaryError, import_yaml

    store = _store()
    try:
        r = import_yaml(Akashic(store, _novel(store, novel)["id"]), file.read_text())
    except GlossaryError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(1) from e
    console.print(f"[green]Imported[/]: {r['created']} new, {r['updated']} updated")


@glossary_app.command("validate")
def glossary_validate(file: Path = typer.Argument(..., exists=True)) -> None:
    """Check a glossary file's YAML and structure."""
    from babel.memory.glossary import GlossaryError, parse_yaml

    try:
        data = parse_yaml(file.read_text())
    except GlossaryError as e:
        console.print(f"[red]Invalid:[/] {e}")
        raise typer.Exit(1) from e
    console.print("[green]Valid[/]: " + ", ".join(f"{len(v or {})} {k}" for k, v in data.items()))


@glossary_app.command("sync")
def glossary_sync(novel: str, file: Path) -> None:
    """Add what BABEL has learned to an existing glossary file, keeping its comments."""
    from babel.memory.akashic import Akashic
    from babel.memory.glossary import sync_file

    store = _store()
    sync_file(Akashic(store, _novel(store, novel)["id"]), file)
    console.print(f"[green]Synced[/] {file}")


@glossary_app.command("test")
def glossary_test(novel: str, text: str) -> None:
    """Show which known entities BABEL recognizes in a piece of text."""
    from babel.memory.akashic import Akashic

    store = _store()
    ak = Akashic(store, _novel(store, novel)["id"])
    hits = ak.mentioned_in(text, kind=None)
    if not hits:
        console.print("[dim]No known names in that text.[/]")
    for eid, n in hits.most_common():
        console.print(f"{ak.ents[eid]['kind']:>9}  {ak.brief(eid)}  ×{n}")


@app.command()
def metadata(novel: str, source: list[str] = typer.Option(None, help="openlibrary, googlebooks, royalroad, novelupdates"),
             apply: bool = typer.Option(False, help="save the result and download the cover")) -> None:
    """Fetch cover art and details from external sources."""
    from babel.library import save_image
    from babel.meta.sources import download, fetch

    s = _settings()
    store = _store(s)
    n = _novel(store, novel)
    meta, notes = fetch(n["title"], source or None)
    for note in notes:
        console.print(f"[dim]{note}[/]")
    if meta is None:
        console.print("[yellow]No match found.[/]")
        raise typer.Exit(1)
    console.print(json.dumps(meta.__dict__, indent=2, ensure_ascii=False)[:1500])
    if apply:
        store.update_novel(n["id"], author=n["author"] or meta.author, description=meta.description or n["description"],
                           tags=meta.tags, status=meta.status, source_url=meta.url)
        if meta.cover_url:
            save_image(store, s.covers_dir, n["id"], download(meta.cover_url))
        console.print("[green]Applied[/]")


# ── output ─────────────────────────────────────────────────────────────────
@app.command()
def export(novel: str, fmt: str = typer.Option("epub", "--format", "-f", help="epub | html | json"),
           out: Path | None = typer.Option(None, "--out", "-o"), first: int | None = None, last: int | None = None) -> None:
    """Export the visual scenario (EPUB for e-readers, single HTML file, or the standardized JSON)."""
    s = _settings()
    store = _store(s)
    n = _novel(store, novel)
    f_idx, l_idx = (first - 1 if first else None), (last - 1 if last else None)
    if fmt == "epub":
        from babel.export.epub import build_epub

        data = build_epub(store, n["id"], f_idx, l_idx)
    elif fmt == "html":
        from babel.export.html import build_html

        data = build_html(store, n["id"], f_idx, l_idx).encode()
    elif fmt == "json":
        from fastapi.testclient import TestClient

        from babel.api.app import create_app

        with TestClient(create_app(s, store, start_worker=False)) as c:
            data = c.get(f"/api/novels/{n['id']}/export/json", params={k: v for k, v in (("first", f_idx), ("last", l_idx)) if v is not None}).content
    else:
        console.print("[red]--format must be epub, html or json[/]")
        raise typer.Exit(1)
    out = out or Path(f"{n['title'][:60].replace('/', '-')}.babel.{fmt}")
    out.write_bytes(data)
    console.print(f"[green]Wrote[/] {out} ({len(data) // 1024} KB)")


@app.command()
def preview(file: Path = typer.Argument(..., exists=True), chapter: int = typer.Option(1)) -> None:
    """Show the instant rules+memory labeling of one chapter of a file (no import)."""
    from babel.ingest import load_book
    from babel.memory.akashic import Akashic
    from babel.models import BlockType
    from babel.scenario.assemble import assemble
    from babel.scenario.convert import convert
    from babel.scenario.resolve import Resolver, is_first_person
    from babel.scenario.segment import segment_text
    from babel.store.db import Store

    book = load_book(file)
    ch = book.chapters[chapter - 1]
    store = Store(":memory:")
    nid = store.create_novel(book.title, [(ch.title, ch.text, ch.sha)])
    segs = segment_text(ch.text)
    decisions, paras = convert(segs)
    Resolver(Akashic(store, nid), is_first_person(segs)).run(segs, decisions, paras)
    styles = {BlockType.DIALOGUE: "cyan", BlockType.THOUGHT: "magenta", BlockType.SYSTEM: "yellow",
              BlockType.SFX: "red", BlockType.TAG: "dim", BlockType.ACTION: "green"}
    console.rule(ch.title)
    for b in assemble(segs, decisions):
        who = f"[bold]{b.speaker or '?'}[/] " if b.speaker else ""
        conf = f"[dim]{b.conf:.2f}[/] " if b.type in (BlockType.DIALOGUE, BlockType.THOUGHT) else ""
        console.print(f"[{styles.get(b.type, 'white')}]{b.type.value:>9}[/] {conf}{who}{b.text}")


@app.command()
def providers(test: bool = typer.Option(False, "--test", help="send a tiny request to each model")) -> None:
    """Show the local model and cloud providers BABEL will use."""
    from babel.llm.providers import PRESETS, LLMError, ollama_models

    s = _settings()
    cascade = s.build_cascade()
    _describe_tiers(cascade)
    installed = ollama_models()
    console.print(f"Ollama: {'running, models: ' + ', '.join(installed) if installed else '[dim]not running / no models[/]'}")
    active = {p.name: p for p in (cascade.cloud.providers if cascade.cloud else [])}
    t = Table("cloud provider", "status", "model")
    for name, preset in PRESETS.items():
        p = active.get(name)
        st = "[green]configured[/]" if p else "[dim]not configured[/]"
        if p and test:
            try:
                p.chat([{"role": "user", "content": 'Reply with {"ok": true}'}], max_tokens=20)
                st = "[green]ok[/]"
            except LLMError as e:
                st = f"[red]{str(e)[:60]}[/]"
        t.add_row(name, st, p.model if p else preset.model)
    console.print(t)
    if test and cascade.local:
        try:
            r = cascade.local.chat([{"role": "user", "content": 'Reply with {"ok": true}'}], max_tokens=20)
            console.print(f"local model: [green]ok[/] ({r.completion_tokens} tokens)")
        except LLMError as e:
            console.print(f"local model: [red]{e}[/]")


@app.command()
def serve(host: str | None = typer.Option(None), port: int | None = typer.Option(None),
          reload: bool = typer.Option(False, help="auto-reload on code changes (development)")) -> None:
    """Run the reader UI + API + background worker."""
    import uvicorn

    s = _settings()
    h, p = host or s.host, port or s.port
    console.print(f"BABEL running at [cyan]http://{h}:{p}[/]")
    uvicorn.run("babel.api.app:create_app", factory=True, host=h, port=p, reload=reload, log_level="info")


# ── db ─────────────────────────────────────────────────────────────────────
@db_app.command("info")
def db_info() -> None:
    """Where the database is and what's in it."""
    s = _settings()
    store = _store(s)
    console.print(f"database: {s.db_path.resolve()} ({s.db_path.stat().st_size // 1024:,} KB)")
    for t in ("novels", "chapters", "entities", "aliases", "overrides", "jobs", "usage"):
        console.print(f"  {t:>10}: {store.one(f'SELECT COUNT(*) n FROM {t}')['n']:,}")


@db_app.command("check")
def db_check() -> None:
    """Run SQLite's integrity and foreign-key checks."""
    store = _store()
    ok = store.one("PRAGMA integrity_check")
    fk = store.q("PRAGMA foreign_key_check")
    console.print(f"integrity: {list(ok.values())[0]}; foreign keys: {'ok' if not fk else f'{len(fk)} problems'}")


@db_app.command("vacuum")
def db_vacuum() -> None:
    """Compact the database file."""
    _store().x("VACUUM")
    console.print("[green]Done[/]")


ART_MFLUX = "mflux==0.24.0"


@art_app.command("setup")
def art_setup(python: str = typer.Option("3.12", help="Python version for the art environment")) -> None:
    """Create the art environment (.venv-art) with the image models' runtime (Apple Silicon / MLX)."""
    import platform
    import shutil
    import subprocess

    if platform.system() != "Darwin" or platform.machine() != "arm64":
        console.print("[yellow]Character art currently runs on Apple Silicon Macs (MLX).[/]")
        raise typer.Exit(1)
    uv = shutil.which("uv")
    if uv:
        subprocess.run([uv, "venv", ".venv-art", "--python", python], check=True)
        subprocess.run([uv, "pip", "install", "--python", ".venv-art/bin/python", ART_MFLUX], check=True)
    else:
        subprocess.run([shutil.which("python3") or "python3", "-m", "venv", ".venv-art"], check=True)
        subprocess.run([".venv-art/bin/python", "-m", "pip", "install", ART_MFLUX], check=True)
    console.print("[green]Art environment ready.[/] The image models (~22 GB) download on first use.")


@art_app.command("status")
def art_status(novel: str = typer.Argument(..., help="novel id or title")) -> None:
    """Who needs a design, in reading order, and which chapters are ready as a visual novel."""
    from babel.art import designs, plan
    from babel.memory.akashic import Akashic

    s = _settings()
    store = _store(s)
    n = _novel(store, novel)
    ak = Akashic(store, n["id"])
    console.print(f"art environment: {s.art_python_path() or '[yellow]not installed — babel art setup[/]'}")
    console.print(f"settings: {designs.art_settings(store, n['id'])}")
    r = plan.readiness(store, ak)
    through = "none yet" if r["ready_through"] is None else f"chapter {r['ready_through'] + 1}"
    console.print(f"visual novel: {r['ready']}/{r['transformed']} transformed chapters ready; "
                  f"straight through to {through}")
    t = Table("first ch", "character", "tier", "lines", "status")
    for c in plan.characters(store, ak):
        if c["tier"] in plan.REQUIRED or c["status"] != "new":
            first = "" if c["first_idx"] is None else str(c["first_idx"] + 1)
            t.add_row(first, c["name"], c["tier"], str(c["lines"]), c["status"])
    console.print(t)


@art_app.command("auto")
def art_auto(novel: str = typer.Argument(..., help="novel id or title"),
             on: bool = typer.Option(True, "--on/--off", help="draw characters automatically in reading order")) -> None:
    """Turn automatic design drafting on/off (you still pick each main/supporting character's look)."""
    from babel.art import designs

    store = _store()
    n = _novel(store, novel)
    designs.set_art_settings(store, n["id"], auto=on)
    console.print(f"auto art {'on' if on else 'off'} for {n['title']} — runs while `babel serve` is up")


# (published name, source path inside a NOCTURNE checkout, max width) — the Theatre of Stories kit
THEME_FILES = [
    ("curtain-left.webp", "art/m9-production/batch-m9b-1-babel/babel-curtain-left.png", 4000),
    ("curtain-right.webp", "art/m9-production/batch-m9b-1-babel/babel-curtain-right.png", 4000),
    ("valance.webp", "art/m9-production/batch-m9b-1-babel/babel-valance.png", 1020),
    ("apron.webp", "art/m9-production/batch-m9b-1-babel/babel-apron.png", 1180),
    ("footlights.webp", "art/m9-production/batch-m9b-1-babel/babel-footlights.png", 3540),
    ("stage.webp", "art/m9-production/batch-m9b-1-babel/babel-stage.png", 1060),
    ("hud-bar.webp", "assets/ui/hud-bar.webp", None),
    ("brass-idle.webp", "assets/ui/button-brass-idle.webp", None),
    ("brass-hover.webp", "assets/ui/button-brass-hover.webp", None),
    ("brass-pressed.webp", "assets/ui/button-brass-pressed.webp", None),
    ("panel-glass.webp", "assets/ui/panel-glass.webp", None),
    ("flourish.webp", "assets/ui/corner-flourish.webp", None),
]


@theme_app.command("import")
def theme_import(source: Path = typer.Argument(Path.home() / "NOCTURNE", help="a NOCTURNE checkout")) -> None:
    """Copy the Theatre of Stories art from NOCTURNE into the library (kept out of git; the UI works without it)."""
    from PIL import Image

    s = _settings()
    out = s.data_dir / "theme"
    out.mkdir(parents=True, exist_ok=True)
    done, missing = [], []
    for name, rel, max_w in THEME_FILES:
        src = source / rel
        if not src.exists():
            missing.append(rel)
            continue
        with Image.open(src) as im:
            im = im.convert("RGBA")
            if max_w and im.width > max_w:
                im = im.resize((max_w, round(im.height * max_w / im.width)), Image.Resampling.NEAREST)
            im.save(out / name, "WEBP", quality=90, method=6)
        done.append(name)
    (out / "SOURCE.txt").write_text(f"Imported from {source} (NOCTURNE review exports, owner's own art).\n")
    console.print(f"[green]{len(done)} theatre files[/] → {out}")
    if missing:
        console.print(f"[yellow]not found:[/] {', '.join(missing)}")


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    app()


if __name__ == "__main__":
    main()
