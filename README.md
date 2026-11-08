# BABEL

**Read webnovels as chat-style visual scenarios.**

BABEL imports a novel (EPUB or TXT) and turns every chapter into a *visual scenario*: dialogue becomes chat bubbles attributed to the right character, inner thoughts get their own style, action beats sit in the actor's lane like stage directions, game-system windows look like system windows, sound effects pop, and narration stays as clean prose. It is built for very long webnovels (thousands of chapters), runs on your own machine, and costs close to nothing.

## How it decides who says what

Most "LLM reformats a book" tools ask a big model to rewrite every chapter. That is slow, expensive, and can drop or invent lines. BABEL never lets a model touch the text. It turns each chapter into a **standardized JSON of decisions** and sends a model only the decisions it couldn't settle on its own, as **small multiple-choice questions**:

```
chapter ─▶ segments ─▶ ① rules ─▶ ② memory ─▶ ③ local model ─▶ ④ cloud model ─▶ ⑤ you
             (exact text)  speech tags    Akashic Record    only uncertain     only still-uncertain   review queue
                           action beats   scene state       lines (free)       or disputed lines
                           tone, SFX      gender, aliases
```

1. **Rules.** Each chapter is split deterministically into quotes, *italics* (kept from the EPUB, including CSS-class italics), `[system]` brackets, scene breaks and prose. Speech tags ("Tobin said", "the fortune-teller said"), action beats, tone verbs and sound words are recognized. Every decision gets a confidence score and a ranked candidate list.
2. **Memory (the Akashic Record).** A per-novel memory of characters, places, factions and terms, with aliases, gender, notes and portraits. A scene tracker adds turn-taking, who is present, who is being addressed ("Tobin, look!" isn't Tobin speaking), who was just asked a question, run-on speech, newcomers and first-person narrators.
3. **Local model** (Ollama, free). Only lines below the confidence bar are sent, as multiple choice: `Who says ⟦Q3⟧ "Not yet."? A) Tobin B) Mira Vell C) someone else`. A JSON-schema grammar forces exactly one letter per question, so a batch of twenty answers costs about 60 output tokens. It overrides weak heuristics but not strong textual evidence.
4. **Cloud model** (optional, any OpenAI-compatible API). Only lines that are still uncertain, or where the local model disagreed with the rules, go here.
5. **You.** Whatever is still below the bar lands in the **Review** queue. One click fixes or confirms a line. Corrections survive re-transforms and export as gold data.

New names are classified (person, place, faction, term, or not a name, plus gender and "same as someone known?") *before* speakers are resolved, so pronoun reasoning has the facts it needs. A summary of each chapter becomes "story so far" context for the next.

### Measured

On the bundled gold-labeled chapters (`babel eval`, original text written for the test set: untagged three-way arguments, pronouns, LitRPG system windows, first-person narration):

| Tiers | Speaker accuracy | Type accuracy | Cloud tokens per chapter |
|---|---|---|---|
| rules + memory only | 86% | 100% | 0 |
| + local model (qwen3:8b) | 95–96% | 100% | 0 |
| full cascade (local + cloud)¹ | 96.5% | 100% | ~430 |
| cloud only, no local model¹ | 95% | 100% | ~1,700 |

¹ Measured with the same 8B model standing in for the cloud tier, so these are a lower bound; a 70B-class cloud model should do better on the hard lines.

On real chapters of a published webnovel, the local tier runs at about 23 s per chapter on an Apple M-series laptop, and about 2 lines per 8 chapters end up in the review queue.

## Quick start

Requires Python 3.11+ and Node 20+. Ollama is recommended (free, local).

```bash
git clone https://github.com/ram-tewari/BABEL && cd BABEL
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .
npm --prefix web ci && npm --prefix web run build

# optional but recommended: the free local tier
ollama pull qwen3:8b            # any instruct model works; qwen3:8b is the default pick

cp .env.example .env            # optional: add a cloud key for the hardest lines
babel serve                     # → http://127.0.0.1:8000
```

Drop an EPUB on the page and press **Transform all**. Chapters you open before they're transformed show an instant rules + memory preview.

## Models

| Tier | How to enable | Cost |
|---|---|---|
| Local | Run Ollama with any model pulled. Auto-detected; pick one with `BABEL_LOCAL_MODEL`, disable with `BABEL_LOCAL=off`. | free |
| Cloud | Any of `NVIDIA_API_KEYS`, `GROQ_API_KEYS`, `GEMINI_API_KEYS`, `OPENROUTER_API_KEYS`, `OPENAI_API_KEYS`, or `BABEL_CUSTOM_BASE_URL` (LM Studio, vLLM, …). Several form a fallback chain. Comma-separated keys rotate on rate limits. | free tiers go a long way |

Reasoning models (Qwen3, R1-style) are asked to answer directly (`reasoning_effort: none` / `/no_think`, with automatic fallback). Check your setup with `babel providers --test`.

## The reader

- **Library:** cover grid, transform progress, continue reading, drag-and-drop import.
- **Reader:** chat bubbles with the point-of-view character on the right, grouped lines, portraits, tone styling (shouts, whispers), action beats, system windows, sound effects, glossary tooltips for places, factions and terms, and bi-directional infinite scroll with the URL following along. Ctrl+B opens a chapter sidebar with read marks; Ctrl+K jumps to any chapter, character or action; ← → change chapter. Themes: dark, light, sepia and system. You can also toggle to the original text.
- **Correction mode (`e`):** uncertain lines are marked. Click one to see who decided it and why, pick a suggested speaker, set the tone, or confirm it.
- **Novel page:**
  - Chapters: filters for unread, review, failed and so on, plus full-text search.
  - Cast: rename, recolor, set chat side, gender, protagonist, portrait, faction, aliases, or merge duplicates (e.g. a transmigrator's two names).
  - Glossary: places, factions and terms, with YAML import/export.
  - Review: queue plus corrections log.
  - Graph: who talks to whom.
  - Export: EPUB, single HTML, Visual Scenario JSON, corrections JSONL.
  - Settings: metadata search via Open Library or Google Books (RoyalRoad and NovelUpdates are tried but usually block bots), cover upload, append new chapters of an ongoing novel, delete.
- Transform jobs show tier choice and a cost estimate, run several novels in parallel, and can be paused, resumed or stopped. Restarts resume where they left off.

## CLI

```bash
babel run novel.epub --epub           # import + transform everything + write an EPUB
babel import novel.txt --chapter-pattern '^=== .* ===$'
babel novels list | show | update | delete
babel chapters 1 --status failed
babel transform 1 --first 10 --last 50 --tiers auto|rules|local|cloud [--force]
babel status 1                        # progress, who decided the lines, tokens spent, review count
babel estimate 1                      # cost/time for what's left
babel review 1                        # least-certain lines
babel cast 1
babel glossary export 1 -o glossary.yaml | import 1 glossary.yaml | validate glossary.yaml | sync 1 glossary.yaml | test 1 "text"
babel metadata 1 --apply
babel export 1 -f epub|html|json
babel eval --tiers local -v           # quality + cost on gold chapters
babel providers --test
babel db info | check | vacuum
babel serve
```

## Glossary YAML

```yaml
characters:
  Klein Moretti:
    aliases: [Klein, Zhou Mingrui, The Fool]
    gender: m
    faction: Tarot Club
    description: Transmigrator; history graduate in Tingen.
    color: "#e8b86b"
    pov: true
factions:
  Tarot Club: {color: "#a855f7", description: Secret gathering above the gray fog.}
locations:
  Tingen: {description: A city in the Loen Kingdom.}
terms:
  Beyonder: {description: Someone who has drunk a potion and gained powers.}
```

Imported fields count as yours: models never overwrite them. `babel glossary sync` writes what BABEL learned back into your file without touching your comments.

## Architecture

```
babel/
  ingest/      EPUB (spine, TOC titles, CSS italics, bundled chapters, cover) · TXT (heading detection, custom regex)
  scenario/    segment → convert (rules) → resolve (memory) → ask (multiple choice) → cascade → assemble
  memory/      akashic.py (entities, aliases, gender, locking) · glossary.py (YAML)
  llm/         LocalModel (Ollama native, JSON-schema grammars) · Provider/Router (OpenAI-compatible chain)
  pipeline/    resumable jobs, several novels at once
  store/       SQLite: chapters + decision documents, overrides, entities, aliases, usage ledger, reads
  meta/        Open Library / Google Books / RoyalRoad / NovelUpdates
  export/      EPUB, HTML · api/ FastAPI (+ serves the web UI) · evals/ gold chapters + runner
web/           React 19 · Vite · Tailwind 4 · TanStack Query
```

A chapter stores its source text and one decision per segment (type, speaker, tone, confidence, tier, candidates, reason), never rendered output. Speakers resolve through the alias table at read time, so renames and merges apply to all chapters instantly.

## Development

```bash
pip install -e ".[dev]" && pytest && ruff check babel tests
npm --prefix web run dev            # UI on :5173, proxying /api to :8000
npm --prefix web test               # unit tests
npm --prefix web exec playwright test   # browser end-to-end
babel eval --tiers rules            # quick quality check, no models needed
```

Add gold chapters to `babel/evals/gold/` (`name.txt` + `name.gold.json`) to measure your own changes.

## Legal

BABEL is a reading tool for books you own. Don't commit or redistribute copyrighted novels; `data/` and root-level book files are git-ignored for that reason. MIT License.
