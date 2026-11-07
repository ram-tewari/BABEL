# BABEL

**Read webnovels as chat-style visual scenarios.**

BABEL imports a novel (EPUB or TXT) and turns every chapter into a *visual scenario*: dialogue becomes colored chat bubbles attributed to the right character, inner thoughts get their own style, game-system windows look like system windows, sound effects pop, and the prose stays as clean narration in between. It's built for very long webnovels (thousands of chapters), runs on your own machine, and works on free LLM tiers or fully offline.

```
 EPUB / TXT ──▶ chapters ──▶ segments ──▶ labels (LLM or offline) ──▶ reader · EPUB · HTML
                               │               ▲
                               └── codex ──────┘   characters, aliases, story-so-far
```

## What's different about BABEL 2

Most "LLM reformats a book" pipelines ask the model to rewrite each chapter. That drops or invents lines, truncates long chapters, and burns tokens. BABEL doesn't let the model touch the text:

1. **Deterministic segmentation.** Each chapter is split into numbered segments by surface form: quoted speech, *italics* (kept from the EPUB, including CSS-class italics), `[bracketed]` system text, scene breaks and prose.
2. **The LLM only labels.** For each segment it returns a type (`dialogue`, `thought`, `system`, `sfx`, `tag`, `narration`) and a speaker. Plain narration is omitted from the reply, so output is roughly 10× smaller than a rewrite. The text you read is always exactly the source text.
3. **Story memory (the "Akashic Record").** A per-novel codex tracks every character with their aliases ("Klein" = "Klein Moretti" = "The Fool"). Each request gets the relevant cast plus summaries of the previous chapters, so attribution stays consistent across thousands of chapters.
4. **Corrections are first-class.** Fix any line's type or speaker in the reader. Fixes are stored as an override layer, so they survive re-transforms and can be exported as JSONL for evaluation or fine-tuning. Renaming or merging a character applies to every chapter instantly, because speakers are resolved through the alias table at read time.
5. **Offline fallback.** A rule-based labeler (speech tags, sentence subjects, turn-taking, italics, sound words) works with zero API keys. It is also used for any chunk where the LLM fails, so a chapter never comes back empty.

## Quick start

Requires Python 3.11+ and Node 20+.

```bash
git clone https://github.com/ram-tewari/BABEL && cd BABEL
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -e .
npm --prefix web ci && npm --prefix web run build     # builds the reader UI

cp .env.example .env    # optional: add an API key (see below)
babel serve             # → http://127.0.0.1:8000
```

Drop an EPUB onto the page, press **Transform all**, and start reading. Chapters you open before they're transformed show an instant offline preview.

## LLM providers

Add any of these to `.env`. Every key variable accepts a comma-separated list, and keys rotate automatically when one is rate-limited. If you configure several providers, they form a fallback chain.

| Provider | Variable | Default model | Notes |
|---|---|---|---|
| NVIDIA NIM | `NVIDIA_API_KEYS` | `qwen/qwen3-235b-a22b` | free, 40 RPM/key |
| Groq | `GROQ_API_KEYS` | `llama-3.3-70b-versatile` | free tier, very fast |
| Google Gemini | `GEMINI_API_KEYS` | `gemini-2.5-flash` | free tier |
| OpenRouter | `OPENROUTER_API_KEYS` | `meta-llama/llama-3.3-70b-instruct:free` | `:free` models |
| OpenAI | `OPENAI_API_KEYS` | `gpt-4.1-mini` | paid |
| Ollama | auto-detected | `qwen2.5:7b` (`OLLAMA_MODEL`) | fully local |
| Any OpenAI-compatible server | `BABEL_CUSTOM_BASE_URL` | `BABEL_CUSTOM_MODEL` | LM Studio, vLLM, llama.cpp |

Override models with `BABEL_<PROVIDER>_MODEL`, set the chain order with `BABEL_PROVIDERS=groq,nvidia`, or force offline mode with `BABEL_PROVIDERS=none`. Check your setup with `babel providers --test`.

## CLI

```bash
babel import novel.epub              # add to the library (prints the novel id)
babel list                           # library overview
babel transform 1                    # transform everything not yet done (resumable; Ctrl-C pauses)
babel transform 1 --first 0 --last 99 --force --mode llm
babel cast 1                         # the character codex
babel export 1 -f epub -o out.epub   # e-reader edition of the scenario (also: -f html)
babel preview novel.epub --chapter 3 # see the offline labeling of one chapter, no import
babel serve                          # web UI + API + background worker
```

`--mode` is `auto` (LLM, falling back per chunk), `llm` (strict: failures are marked failed) or `heuristic` (offline).

## The reader

- **Library:** cover grid, transform progress, continue-reading shortcuts, drag-and-drop import.
- **Novel page:** start, pause, resume or stop transform jobs over any chapter range; filter chapters by status; full-text search across the book; export; add newly released chapters from a newer file (only new chapters are appended).
- **Reader:** chat bubbles with the point-of-view character on the right, grouped consecutive lines, speech tags as captions, system windows, sound effects and scene breaks. Dark, light, sepia and system themes; adjustable size and width; ← → to change chapter; toggle to the original text.
- **Cast:** rename, recolor, choose the chat side, set the protagonist, add or remove aliases, merge duplicates ("Old Neil" into "Neil").
- **Correction mode** (`e`): click any line to fix its type or speaker.

## Architecture

```
babel/
  ingest/       EPUB (spine, TOC titles, CSS italics, bundled chapters, cover) and TXT (heading detection) → chapters
  transform/    segment.py → heuristic.py / llm_labeler.py → engine.py → assemble.py (blocks for display)
  memory/       codex.py: characters, aliases, partial-name resolution, cast context, line counts
  llm/          one OpenAI-compatible client for every provider; per-key RPM, rotation, failover
  pipeline/     resumable, pausable jobs; one worker thread, N chapters in flight
  store/        SQLite: novels, chapter text + labels, overrides, characters, aliases, jobs, progress
  export/       EPUB and single-file HTML
  api/          FastAPI app; also serves the built web UI
web/            React 19 + Vite + Tailwind 4 + TanStack Query
```

All data lives in one SQLite file (`data/babel.db`, configurable via `BABEL_DATA_DIR`). Chapters store their source text and segment labels, never rendered output, so the display can evolve without re-running the LLM.

## Development

```bash
pip install -e ".[dev]"
pytest                          # backend tests, LLM traffic simulated over the OpenAI protocol
ruff check babel tests
npm --prefix web run dev        # UI on :5173 with /api proxied to :8000 (run `babel serve` too)
npm --prefix web test           # unit tests
npm --prefix web exec playwright test   # browser end-to-end: import → transform → read → correct
```

## Roadmap

- Character portraits from an image model, slotted into the existing avatar component
- A labeling-quality benchmark built from exported corrections, to compare models and prompts
- Few-shot prompting from a novel's own corrections
- Batch APIs (Gemini/OpenAI) for very large backlogs at half the cost

## Legal

BABEL is a reading tool for books you own. Don't commit or redistribute copyrighted novels. `data/` and root-level book files are git-ignored for that reason.

MIT License.
