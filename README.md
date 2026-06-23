# BABEL

**Transform raw webnovels into Visual Scenario format - completely free**

BABEL is an automated pipeline that converts 5,000+ chapter webnovels from raw text into screenplay/chat-style Visual Scenario format, optimized for dialogue flow and character consistency. Process chapters at zero cost using **NVIDIA NIM's free, OpenAI-compatible catalog** (default model `qwen/qwen3-235b-a22b`), with automatic Groq/Gemini fallback.

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/ram-tewari/babel)
[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen)](tests/)
[![Free Tier](https://img.shields.io/badge/cost-%240.00-success)](https://aistudio.google.com/app/apikey)

[Quick Start](#quick-start) • [Features](#features) • [Documentation](#documentation) • [Demo](demo/) • [Contributing](#contributing)

---

## Table of Contents

- [What is BABEL?](#what-is-babel)
- [Status](#status)
- [Quick Start](#quick-start)
- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Batch Processing](#batch-processing)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Cost Analysis](#cost-analysis)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [Roadmap](#roadmap)
- [License](#license)

---

## What is BABEL?

BABEL transforms massive webnovels (5,000+ chapters) from raw text into Visual Scenario format - a screenplay/chat-style presentation optimized for dialogue flow and character consistency.

### Why BABEL?

- **Dialogue-First Format**: Transform dense prose into scannable, character-driven scenes
- **Completely Free**: Process 1,500 chapters/day ($0.00) with Gemini's free tier
- **Production Speed**: 900 chapters/hour (15 RPM) with automatic rate limiting
- **Beautiful Output**: Self-contained HTML with dark theme, character colors, and click-to-edit customization
- **Idempotent Pipeline**: Resume interrupted batches, skip processed chapters automatically
- **Context-Aware**: Glossary system maintains character/faction consistency across thousands of chapters
- **Modern Web UI**: React-based SPA with instant navigation, keyboard shortcuts, and persistent settings


---

## Status

### All Phases Complete

- Phase 0 (Sanitization): Complete
- Phase 1 (Transformation): Complete
- Phase 2 (Rendering): Complete
- Phase 2.5 (Interactivity): Complete
- Phase 2.6 (Visual Polish): Complete
- Phase 2.7 (Hotfixes): Complete
- Phase 3 (Pipeline): Complete
- Phase 4 (Context): Complete
- Phase 6 (React Frontend): Complete

### Free Tier Optimization

Gemini 2.5 Flash generous free tier:
- $0.00 cost - Process up to 1,500 chapters/day completely free
- 15 RPM - 900 chapters/hour processing speed
- No billing required - Just use your API key
- Same quality - Identical output to paid tier

### Free Tier Limits
- RPM: 15 requests/minute (15 chapters/minute)
- RPD: 1,500 requests/day (1,500 chapters/day)
- TPM: 4M tokens/minute (plenty of headroom)

### When to Upgrade to Paid Tier
Only consider paid tier ($0.45 per 50 chapters) if:
- Processing >1,500 chapters/day
- Need faster processing (150+ RPM)
- Commercial use (free tier data used for training)

For typical use (50-100 chapters/day), free tier is perfect.

---

## Quick Start

Get your first chapter transformed in under 2 minutes:

```bash
# 1. Clone and install
git clone <repository-url>
cd BABEL
python -m venv .venv
.venv\Scripts\activate  # Windows (use source .venv/bin/activate on Unix)
pip install -r requirements.txt

# 2. Set up API key (free tier)
# Primary: NVIDIA NIM (free, OpenAI-compatible) — get a key at https://build.nvidia.com
echo NVIDIA_API_KEYS=nvapi-your_key_here > .env
# Optional fallbacks (comma-separated keys rotate automatically):
echo GROQ_API_KEYS=your_groq_key >> .env
echo GEMINI_API_KEY=your_gemini_key >> .env

# 3. Transform your novel
python -m babel.sanitize input.epub          # Extract chapters
python run_groq_batch.py                     # Transform to Visual Scenario
start data/render/000_chapter_1.html         # Open in browser

# 4. Or use the React UI
cd babel-ui
npm install
npm run dev                                  # Start React dev server
```

That's it! Your novel is now in Visual Scenario format with:
- Character-specific colors and positioning
- Click-to-edit customization (names, colors, alignment)
- Dark theme optimized for reading
- Chapter navigation with progress tracking

Get your free API key: [Google AI Studio](https://aistudio.google.com/app/apikey)


---

## Features

### Core Capabilities

| Phase | Status | Description |
|-------|--------|-------------|
| **Phase 0: Sanitization** | Complete | EPUB/TXT ingestion, chapter detection, watermark removal |
| **Phase 1: Transformation** | Complete | LLM-powered Visual Scenario conversion (FREE) |
| **Phase 2: Rendering** | Complete | Self-contained HTML with dark theme & customization |
| **Phase 2.5: Interactivity** | Complete | Click-to-edit characters, localStorage persistence |
| **Phase 2.6: Visual Polish** | Complete | Professional headers, narrator continuity, navigation |
| **Phase 2.7: Hotfixes** | Complete | Spacing overhaul, modal fixes, infinite scroll |
| **Phase 3: Pipeline** | Complete | End-to-end orchestration and automation |
| **Phase 4: Context** | Complete | Glossary management and RAG integration |
| **Phase 6: React Frontend** | Complete | Modern SPA with instant navigation and keyboard shortcuts |

### Phase 0: Sanitization (Complete)
- EPUB and TXT file ingestion
- Automatic chapter detection (multiple patterns)
- Watermark and URL removal
- Metadata preservation (titles, order)
- Token estimation for cost planning
- Comprehensive manifest generation

### Phase 1: Transformation (Complete)
- Native JSON Mode: Guaranteed valid JSON output
- Hash-Based Idempotency: Skip unchanged chapters automatically
- Placeholder Generation: Graceful failure handling
- Rate Limit Handling: Automatic exponential backoff
- FREE Tier Support: Process 1,500 chapters/day at $0.00
- Visual Scenario Format: Dialogue, thought, action, monologue, SFX, system notifications
- Metadata Tracking: Source hash, model version, timestamps

### Phase 2: Rendering (Complete)
- Self-Contained HTML: All CSS inline, no external dependencies
- Dark Theme: Cyber-noir aesthetic (#1a1a1a background, #e0e0e0 text)
- Character Colors: Deterministic HSL generation (WCAG AA compliant, 4.5:1 contrast)
- Lane Alignment: Left/right positioning for dialogue flow
- Speech Bubbles: Rounded borders with 10% opacity backgrounds
- 7 Block Types: Dialogue, thought, narrator, action, monologue, SFX, system notifications
- Thought Blocks: Italic grey text, no bubble (ghost text)
- Narrator Blocks: Centered italic text with border (third-person exposition)
- Action Blocks: Centered, serif font for narrative
- Navigation: Chapter-to-chapter links via manifest
- Template Caching: Jinja2 template compilation for performance

### Phase 2.5: Interactive Personalization (Complete)
- Click-to-Edit Characters: Click any character name to open customization modal
- Name Override: Change displayed names globally (e.g., "Kim" → "Jin")
- Color Picker: HTML5 color input for easy color selection
- Lane Toggle: Switch between left/right alignment per character
- localStorage Persistence: Preferences apply across all chapters automatically
- CSS Variables: Instant color updates without DOM iteration
- Self-Contained: No external JS/CSS files, fully inline
- Scene Break Handling: Converts `***` markers to visual separators
- Meta-Commentary Ban: Prevents awkward "time skip implied" text
- Visual Distinction: Clear separation between thoughts, narrator, and action

### Phase 2.6: Visual Polish & UX Improvements (Complete)

**Professional Chapter Headers:**
- Elegant Typography: Large, bold headers (2.5em) with proper spacing
- Gradient Backgrounds: Subtle 135° gradient (#2a2a2a → #1a1a1a)
- Accent Borders: Green (#4ade80) left/right borders with gradient lines
- Text Shadow: Depth and readability enhancement
- Integrated Theme: Seamless dark theme integration

**Narrator Block Continuity:**
- Visual Merging: Consecutive narrator blocks connect seamlessly
- Unified Sections: Thicker borders (3px) with subtle backgrounds
- Smart Spacing: Adjacent sibling selectors reduce gaps
- Border Radius: Rounded corners on first/last blocks in sequences
- Reading Flow: Improved narrative exposition continuity

**Functional Navigation:**
- Working Buttons: Previous/Next chapter navigation fully functional
- Chapter Map Integration: Orchestrator passes chapter_map to renderer
- Proper Titles: Chapter titles from manifest displayed correctly
- Seamless Experience: Navigate between chapters without manual file selection

### Phase 2.7: Hotfix - Spacing, Modals & Navigation (Complete)

**NarratorBlock Spacing Overhaul (DEVIATION-2026-02-10-001):**
- Paragraph Dividers: Visual `<hr>` separators between narrator paragraphs
- Improved Readability: Clear distinction between exposition blocks
- Consistent Spacing: 1.5rem gaps with subtle divider lines
- Semantic Structure: Maintains narrative flow while improving scannability

**Modal System Fixes (DEVIATION-2026-02-10-002, 003):**
- Proper Centering: IngestModal overlay restructured for true viewport centering
- Force Overrides: CSS `!important` rules to prevent style conflicts
- Z-Index Management: Proper layering (overlay: 9998, modal: 9999)
- Responsive Design: Works on all screen sizes

**Advanced Navigation (DEVIATION-2026-02-10-004, 005, 006):**
- Bi-Directional Infinite Scroll: Seamless prev/next chapter loading
- Sidebar Deep Linking: Click any chapter to jump directly via `data-chapter-id`
- Reading Progress: Tracks and displays read chapters with visual indicators
- State Persistence: localStorage maintains progress across sessions

### Phase 3: Pipeline Orchestration (Complete)
- End-to-End Automation: Single command to process entire novels
- Stream Processing: Incremental HTML output (see results immediately)
- Progress Tracking: Rich terminal UI with contextual progress bars
- Resume from Interruption: State persistence for crash recovery
- Rate Limit Handling: Automatic throttling with 4-second delays
- Batch Job Management: Process multiple novels sequentially
- Error Recovery: Graceful failure handling with detailed logging

### Phase 4: Context Management (Complete)
- Automatic Glossary Extraction: AI-powered entity discovery from chapters
- YAML Storage: Human-readable glossary with comment preservation
- Context Injection: Glossary data injected into transformation prompts
- Idempotent Merging: Safe re-runs preserve user edits
- Schema Validation: Invalid entries skipped with warnings
- CLI Commands: init-glossary, show-glossary, validate-glossary, test-glossary
- FREE Tier: Uses Gemini 1.5 Flash (no additional cost)

### Phase 6: React Frontend (Complete)

**Modern Single Page Application:**
- Instant Navigation: SPA architecture with no page refreshes
- Keyboard Shortcuts: Arrow keys for navigation, Ctrl+B for sidebar
- Real-time Search: Filter chapters instantly
- Theme Toggle: Dark/Light mode support
- Responsive Design: Works beautifully on mobile, tablet, and desktop
- Optimized Performance: < 200KB bundle, prefetching, caching

**Technical Stack:**
- Build Tool: Vite
- Framework: React 19 (TypeScript)
- Styling: Tailwind CSS + CSS Variables
- State Management: Zustand
- Data Fetching: TanStack Query (React Query v5)
- HTTP Client: Axios
- Routing: React Router v7
- Icons: Lucide React
- Testing: Vitest + Testing Library + Playwright

**Key Features:**
- Bi-directional infinite scroll (DEVIATION-2026-02-10-004)
- Sidebar deep linking via data-chapter-id (DEVIATION-2026-02-10-005)
- Reading progress tracking with localStorage (DEVIATION-2026-02-10-006)
- Character customization modal
- Settings persistence
- Command menu (Ctrl+K)
- Block editor for corrections
- Correction dashboard


---

## Installation

### Prerequisites

- Python 3.12+
- Node.js 18+ (for React UI)
- Gemini API key (free tier) - Get one at [Google AI Studio](https://aistudio.google.com/app/apikey)

### Backend Setup

```bash
# Clone repository
git clone <repository-url>
cd BABEL

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Unix

# Install dependencies
pip install -r requirements.txt

# Set up API key
echo GEMINI_API_KEY=your_api_key_here > .env
```

### Frontend Setup (Optional)

```bash
# Navigate to React UI
cd babel-ui

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local and set VITE_API_BASE_URL=http://localhost:8000

# Start development server
npm run dev
```

---

## Usage

### Phase 0: Sanitize raw files

```bash
# From EPUB
python -m babel.sanitize input.epub

# From TXT
python -m babel.sanitize input.txt

# Output: data/clean/*.txt + config/chapter_map.json
```

### Phase 1: Transform to Visual Scenario

BABEL uses **NVIDIA NIM** as the default provider with automatic Groq fallback.
NVIDIA's free hosted catalog is OpenAI-compatible (40 RPM, far above the
~1,500 chapters/day target), so the default model is a top-tier one:
`qwen/qwen3-235b-a22b`. Model aliases: `qwen`, `deepseek`, `llama`,
`mistral-nemotron`, `nemotron`.

#### CLI Commands
```bash
# Single chapter (NVIDIA default → Qwen3-235B, Groq fallback)
python -m babel.cli transform chapter input.txt

# Batch processing (NVIDIA default)
python -m babel.cli transform batch --input data/clean/

# Pick a different NVIDIA model by alias or full id
python -m babel.cli transform chapter input.txt --model deepseek

# Use another provider
python -m babel.cli transform chapter input.txt --provider groq
python -m babel.cli transform chapter input.txt --provider gemini

# Verify a provider's connection / key
python -m babel.cli diagnose nvidia

# Output: data/json/*.json
```

### Phase 2: Render to HTML

```bash
# Render all chapters
python -m babel.render data/json data/render --chapter-map config/chapter_map.json

# Output: data/render/*.html (self-contained, ready to read)
```

### Phase 6: React Frontend

```bash
# Start backend server
python babel_server.py

# In another terminal, start React UI
cd babel-ui
npm run dev

# Open browser to http://localhost:5173
```

### Complete Workflow Example

```bash
# 1. Sanitize
python -m babel.sanitize novel.epub

# 2. Transform (Groq default with Gemini fallback)
python run_groq_batch.py

# 3. Open in browser (HTML already rendered)
start data/render/000_chapter_1.html  # Windows
# open data/render/000_chapter_1.html  # Mac

# 4. Or use React UI
python babel_server.py  # Terminal 1
cd babel-ui && npm run dev  # Terminal 2
```


---

## Batch Processing

BABEL supports automated batch processing of large webnovels (1,000+ chapters) with intelligent rate limiting, automatic retries, and progress tracking.

### Quick Start

```bash
# 1. Ensure you have sanitized chapters
ls data/clean/*.txt  # Should show Ch_001.txt, Ch_002.txt, etc.

# 2. Configure API keys in .env
echo GROQ_API_KEYS=key1,key2,key3,key4,key5 >> .env
echo GEMINI_API_KEY=your_gemini_key >> .env

# 3. Run batch transformation
python run_groq_batch.py
```

### How It Works

1. **Chapter Discovery**: Scans `data/clean/` for `.txt` files, sorts numerically
2. **Idempotent Processing**: Skips already-processed chapters automatically
3. **Groq + Gemini Fallback**: Primary Groq API with automatic Gemini fallback
4. **Key Rotation**: Automatic failover across 5 Groq keys (150 RPM effective)
5. **Progress Tracking**: Real-time status with chapter count and success rate
6. **Auto-Update Chapter Map**: Updates every 10 chapters for navigation
7. **Automatic HTML Rendering**: Generates HTML after transformation completes

### Performance Metrics

| Provider | Speed | Throughput | Cost (1,267 chapters) |
|----------|-------|------------|----------------------|
| **Groq Only** | ~1-2s/chapter | 150 RPM (5 keys) | ~$2.79 |
| **Gemini Only** | ~2-4s/chapter | 15 RPM | $0.00 (free tier) |
| **Mixed** | ~1-3s/chapter | Variable | ~$0.00-$5.00 |

**Estimated Processing Time (1,267 chapters):**
- Groq Only: ~8-17 minutes
- Gemini Only: ~84-168 minutes
- Mixed (Groq + Gemini): ~20-40 minutes

### Monitoring Progress

```bash
# Count transformed chapters
ls data/json/*.json | wc -l

# Count rendered chapters
ls data/render/*.html | wc -l

# View recent logs
tail -f logs/babel.log
```

### Resume Interrupted Batch

```bash
# Just re-run the script - it will skip already-processed chapters
python run_groq_batch.py
```

---

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```bash
# LLM Provider Selection (NVIDIA is the default; others are fallbacks)

# Option 1: NVIDIA NIM (default, free, OpenAI-compatible, key rotation)
NVIDIA_API_KEYS=nvapi-key1,nvapi-key2  # Comma-separated for rotation

# Option 2: Groq (fast, with key rotation) — default fallback
GROQ_API_KEYS=key1,key2,key3,key4,key5  # Comma-separated for rotation

# Option 3: Gemini (free tier)
GEMINI_API_KEY=your_gemini_api_key_here

# Optional (defaults shown)
BABEL_CLEAN_DIR=data/clean
BABEL_JSON_DIR=data/json
BABEL_LOG_LEVEL=INFO
```

### API Provider Comparison

| Feature | Groq Llama 3.3 70B | Gemini 2.5 Flash |
|---------|---------------------|------------------|
| **Default** | Yes (Primary) | Fallback |
| **Free Tier** | Varies by key | 1,500 req/day |
| **Speed** | ~1-2s/chapter | ~2-4s/chapter |
| **Throughput** | 150 RPM (5 keys) | 15 RPM |
| **Context Window** | 128K tokens | 1M tokens |
| **Key Rotation** | Yes | No |
| **Best For** | Speed & throughput | Free processing, large context |

### Pipeline Configuration

Edit `config/pipeline.yaml` to customize behavior:

```yaml
rate_limiting:
  provider: "gemini"  # or "groq"
  min_delay: 4.0      # 4.0 for Gemini, 2.0 for Groq
  max_rpm: 15         # 15 for Gemini, 30 for Groq (per key)

rendering:
  theme: "dark"       # or "light"
  contrast_ratio: 4.5 # WCAG AA compliance
```

---

## Architecture

```
┌─────────────┐
│ Raw EPUB/TXT│
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Phase 0        │
│  Sanitization   │  ← Extract chapters, clean text
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Clean TXT      │
│  + Manifest     │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Phase 1        │
│  Transformation │  ← LLM converts to Visual Scenario
│  (Groq/Gemini)  │  ← Context injection (Phase 4)
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  JSON Blocks    │
│  (Validated)    │
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Phase 2        │
│  Rendering      │  ← Generate HTML with styling
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  HTML Output    │
│  (Self-Contained│  ← Ready to read
│   + Interactive)│
└──────┬──────────┘
       │
       ▼
┌─────────────────┐
│  Phase 6        │
│  React Frontend │  ← Modern SPA with instant navigation
└─────────────────┘
```

### Data Flow

1. **Input**: Raw EPUB or TXT files
2. **Phase 0**: Extract chapters, clean text, generate manifest
3. **Phase 1**: Transform to Visual Scenario JSON (FREE)
4. **Phase 2**: Render to styled HTML (self-contained, ready to read)
5. **Phase 3**: Orchestrate full pipeline (automated)
6. **Phase 4**: Inject character/scene context (glossary)
7. **Phase 6**: Serve via React SPA (instant navigation, keyboard shortcuts)


---

## Cost Analysis

### Free Tier (Recommended)

- **Cost**: $0.00
- **Limit**: 1,500 chapters/day (15 RPM)
- **Speed**: ~3-4 seconds/chapter
- **Perfect for**: Personal use, 50-100 chapters/day
- **Example**: 50 chapters in ~3 minutes, $0.00

### Paid Tier (If Needed)

- **Cost**: ~$0.45 per 50 chapters
- **Limit**: 150+ RPM
- **Speed**: ~1 second/chapter
- **Perfect for**: Commercial use, >1,500 chapters/day
- **Pricing**: $0.30/1M input tokens + $2.50/1M output tokens

### Batch API (50% Discount)

- **Cost**: ~$0.225 per 50 chapters
- **Pricing**: $0.15/1M input + $1.25/1M output
- **Trade-off**: Slower processing for lower cost

**For typical use (50-100 chapters/day), free tier is perfect.**

---

## Testing

BABEL has comprehensive test coverage with property-based testing:

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=babel --cov-report=html

# Run specific phase
pytest tests/test_sanitize_*.py  # Phase 0
pytest tests/test_transform_*.py # Phase 1
pytest tests/test_render*.py     # Phase 2

# Run property tests only
pytest -k "property"

# Run React UI tests
cd babel-ui
npm run test
npm run test:e2e
```

**Test Coverage:**
- Phase 0: 95%+ coverage, 15 property tests
- Phase 1: 95%+ coverage, 11 property tests
- Phase 2: 95%+ coverage, 18 property tests
- Phase 6: Vitest + Playwright E2E tests
- **Total**: 200+ tests (unit + property + integration + E2E)

---

## Troubleshooting

### Common Issues

**"No .txt files found in data/clean/"**

Solution: Run Phase 0 sanitization first:
```bash
python -m babel.sanitize input.epub
```

**"No Groq API keys provided"**

Solution: Add keys to `.env` file:
```bash
echo GROQ_API_KEYS=key1,key2,key3 >> .env
```

**"Rate limit exceeded on all API keys"**

Solution: Wait 1 minute for rate limits to reset, or add more keys:
```bash
# Add more keys to .env
GROQ_API_KEYS=key1,key2,key3,key4,key5,key6,key7
```

**"Gemini fallback failed"**

Solution: Check Gemini API key:
```bash
# Verify key in .env
cat .env | grep GEMINI_API_KEY

# Test Gemini API
python -c "from babel.transform.gemini_client import GeminiClient; print(GeminiClient())"
```

**"JSON validation failed"**

Solution: Check logs for details:
```bash
tail -100 logs/babel.log | grep ERROR
```

**React UI: "Failed to fetch chapter data"**

Solution:
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check `.env.local` has correct `VITE_API_BASE_URL`
3. Check browser console for CORS errors
4. Verify backend CORS settings allow your frontend origin

### Getting Help

- Documentation: See [docs/](docs/) for detailed guides
- Bug Reports: Open an issue with logs and reproduction steps
- Questions: Check existing issues or start a discussion

---

## Contributing

We welcome contributions! BABEL uses:

- **Property-based testing** (Hypothesis) for robust validation
- **Pydantic v2** for data validation
- **Tenacity** for retry logic
- **Issue tracking** in `docs/ISSUES.md`

### Development Setup

```bash
# 1. Fork and clone
git clone <your-fork-url>
cd BABEL

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dev dependencies
pip install -r requirements.txt
pip install pytest pytest-cov hypothesis

# 4. Run tests
pytest

# 5. Create feature branch
git checkout -b feature/your-feature-name
```

### Pull Request Guidelines

1. Write tests for new features
2. Update documentation (README, docstrings)
3. Follow code style (Black, isort, flake8)
4. Add changelog entry in CHANGELOG.md
5. Ensure tests pass (`pytest --cov`)

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.


---

## Roadmap

- [x] Phase 0: Sanitization (Complete)
- [x] Phase 1: Transformation (Complete)
- [x] Phase 2: HTML Rendering (Complete)
- [x] Phase 2.5: Interactive Personalization (Complete)
- [x] Phase 2.6: Visual Polish & UX Improvements (Complete)
- [x] Phase 2.7: Hotfix - Spacing, Modals & Navigation (Complete)
- [x] Phase 3: Pipeline Orchestration (Complete)
- [x] Phase 4: Context Management (Complete)
- [x] Phase 6: React Frontend (Complete)

**All Phases Complete**

### Future Enhancements

- [ ] EPUB output format
- [ ] Multi-language support (i18n)
- [ ] Advanced glossary features (RAG, embeddings)
- [ ] Mobile app (iOS/Android)
- [ ] Cloud deployment (Docker, Kubernetes)
- [ ] Collaborative editing features
- [ ] Advanced search and filtering
- [ ] Reading statistics and analytics

---

## Project Structure

```
BABEL/
├── babel/                      # Core package
│   ├── sanitize.py            # Phase 0: Ingestion and cleaning
│   ├── transform/             # Phase 1: LLM transformation
│   │   ├── gemini_client.py   # Gemini API client
│   │   ├── groq_client.py     # Groq API client
│   │   ├── transformer.py     # Core transformation logic
│   │   ├── batch_processor.py # Batch processing
│   │   ├── prompt.py          # Prompt construction
│   │   ├── validator.py       # JSON validation
│   │   └── models.py          # Pydantic data models
│   ├── render/                # Phase 2: HTML rendering
│   │   ├── renderer.py        # Core rendering engine
│   │   ├── style.py           # Color and styling utilities
│   │   ├── contrast.py        # WCAG contrast validation
│   │   └── __main__.py        # CLI entry point
│   ├── pipeline/              # Phase 3: Orchestration
│   │   ├── orchestrator.py    # Pipeline orchestration
│   │   ├── state.py           # State management
│   │   └── reporter.py        # Progress reporting
│   ├── context/               # Phase 4: Context management
│   │   ├── glossary.py        # Glossary extraction
│   │   ├── injector.py        # Context injection
│   │   └── store.py           # YAML storage
│   ├── api/                   # Phase 6: API endpoints
│   │   └── corrections.py     # Corrections API
│   └── cli.py                 # Main CLI entry point
├── babel-ui/                   # Phase 6: React Frontend
│   ├── src/
│   │   ├── components/        # React components
│   │   │   ├── layout/       # MainLayout, Header, Sidebar
│   │   │   ├── reader/       # ScriptBlock, DialogueBubble, etc.
│   │   │   ├── modals/       # SettingsModal, CharacterModal, IngestModal
│   │   │   ├── chapter/      # ChapterList
│   │   │   ├── editor/       # BlockEditor
│   │   │   ├── search/       # CommandMenu
│   │   │   └── ui/           # Button, Modal, Slider, etc.
│   │   ├── pages/            # Page components
│   │   │   ├── ChapterView.tsx
│   │   │   ├── CorrectionDashboard.tsx
│   │   │   ├── Home.tsx
│   │   │   └── NotFound.tsx
│   │   ├── stores/           # Zustand stores
│   │   │   ├── settingsStore.ts
│   │   │   └── readingProgressStore.ts
│   │   ├── hooks/            # Custom React hooks
│   │   │   ├── useChapter.ts
│   │   │   ├── useChapterList.ts
│   │   │   └── useKeyboard.ts
│   │   ├── lib/              # Utility functions
│   │   │   ├── api.ts        # Axios instance + endpoints
│   │   │   ├── style.ts      # Color/lane generation
│   │   │   └── utils.ts      # Helper functions
│   │   └── types/            # TypeScript type definitions
│   ├── package.json
│   ├── vite.config.ts
│   └── README.md
├── templates/                  # Jinja2 templates
│   └── chapter.html           # Chapter rendering template
├── tests/                      # Comprehensive test suite
│   ├── test_sanitize_*.py     # Phase 0 tests
│   ├── test_transform_*.py    # Phase 1 tests
│   ├── test_render*.py        # Phase 2 tests
│   └── test_context_*.py      # Phase 4 tests
├── demo/                       # Phase 2 renderer demo
│   ├── demo_renderer.html     # Standalone HTML demo
│   ├── sample_chapter.json    # Sample data
│   └── README.md              # Demo documentation
├── docs/                       # Documentation
│   ├── CLI_GUIDE.md           # CLI usage guide
│   ├── ISSUES.md              # Issue tracking (150 issues, 85 resolved)
│   └── GROQ_INTEGRATION.md    # Groq setup guide
├── config/                     # Configuration files
│   ├── pipeline.yaml          # Pipeline configuration
│   ├── glossary.yaml          # Character/faction glossary
│   └── chapter_map.json       # Chapter navigation manifest
├── data/                       # Data directories (gitignored)
│   ├── raw/                   # Original files
│   ├── clean/                 # Sanitized chapters
│   ├── json/                  # Transformed JSON
│   └── render/                # Final HTML output
├── logs/                       # Log files (gitignored)
├── .env                        # API keys (gitignored)
├── requirements.txt            # Python dependencies
├── babel_server.py             # FastAPI backend server
├── run_groq_batch.py           # Batch processing script
├── README.md                   # This file
├── CHANGELOG.md                # Version history
└── LICENSE                     # License information
```

---

## Phase 4: Context Management (Akashic Record)

The Akashic Record maintains narrative consistency across thousands of chapters by managing a central glossary of characters, factions, locations, and terms.

### Features

- **Automatic Extraction**: AI-powered entity discovery from chapters
- **YAML Storage**: Human-readable glossary with comment preservation
- **Context Injection**: Glossary data injected into transformation prompts
- **Idempotent Merging**: Safe re-runs preserve user edits
- **Schema Validation**: Invalid entries skipped with warnings

### CLI Commands

```bash
# Initialize glossary (extract entities from first 3 chapters)
python -m babel.cli init-glossary input.epub

# Show glossary (display current glossary)
python -m babel.cli show-glossary

# Validate glossary (check YAML syntax and schema)
python -m babel.cli validate-glossary

# Build with glossary (automatic prompt)
python -m babel.cli build input.epub
```

### Glossary Format

```yaml
characters:
  - name: "Chung Myung"              # English translation (REQUIRED)
    raw: "청명|Chung Myung"           # Original text/regex (REQUIRED)
    aliases:                          # Alternative names (OPTIONAL)
      - "The Divine Dragon"
      - "Sahyung"
    desc: "Protagonist. Former Divine Dragon."  # Context (OPTIONAL)

factions:
  - name: "Mount Hua Sect"
    raw: "화산파|Mount Hua Sect"
    aliases: ["Plum Blossom Sect"]
    desc: "One of the Nine Great Sects."

locations:
  - name: "Mount Hua"
    raw: "화산|Mount Hua"
    aliases: ["Hua Mountain"]
    desc: "Sacred mountain where Mount Hua Sect is located."

terms:
  - name: "Qi"
    raw: "기|Qi"
    aliases: ["Internal Energy", "Ki"]
    desc: "Life force energy used in martial arts."
```

See `config/glossary.example.yaml` for a complete example.

---

## Phase 6: React Frontend

### Overview

BABEL UI is a modern Single Page Application (SPA) built with React 19, TypeScript, and Tailwind CSS. It provides a beautiful, fast, and customizable reading experience with 1:1 visual parity to the Jinja2 templates while adding the performance and interactivity benefits of a client-side framework.

### Key Features

- **Instant Navigation**: SPA architecture with no page refreshes
- **Keyboard Shortcuts**: Arrow keys for navigation, Ctrl+B for sidebar, Ctrl+K for command menu
- **Real-time Search**: Filter chapters instantly
- **Theme Toggle**: Dark/Light mode support
- **Responsive Design**: Works beautifully on mobile, tablet, and desktop
- **Optimized Performance**: < 200KB bundle, prefetching, caching
- **Bi-directional Infinite Scroll**: Seamlessly load previous and next chapters
- **Sidebar Deep Linking**: Click any chapter to jump directly
- **Reading Progress**: Track and display read chapters with visual indicators
- **Character Customization**: Click-to-edit character names, colors, and alignment
- **Settings Persistence**: All preferences saved to localStorage
- **Correction Dashboard**: Edit and fix block classifications

### Tech Stack

- **Build Tool**: Vite
- **Framework**: React 19 (TypeScript)
- **Styling**: Tailwind CSS + CSS Variables
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query v5)
- **HTTP Client**: Axios
- **Routing**: React Router v7
- **Icons**: Lucide React
- **Testing**: Vitest + Testing Library + Playwright

### Getting Started

```bash
# Navigate to React UI
cd babel-ui

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local and set VITE_API_BASE_URL=http://localhost:8000

# Start backend server (in another terminal)
cd ..
python babel_server.py

# Start development server
npm run dev

# Open browser to http://localhost:5173
```

### Design Deviations

The React frontend implements several design deviations documented in `docs/ISSUES.md`:

- **DEVIATION-2026-02-10-001**: NarratorBlock spacing overhaul with paragraph dividers
- **DEVIATION-2026-02-10-002**: IngestModal overlay restructuring for proper centering
- **DEVIATION-2026-02-10-003**: Modal CSS force-overrides with `!important`
- **DEVIATION-2026-02-10-004**: Bi-directional infinite scroll navigation
- **DEVIATION-2026-02-10-005**: Sidebar deep linking via `data-chapter-id`
- **DEVIATION-2026-02-10-006**: Reading progress tracking & read indicators
- **DEVIATION-2026-02-09-001**: TypeScript hash function truncation for character colors

See `babel-ui/README.md` for detailed frontend documentation.

---

## Known Issues

See [docs/ISSUES.md](docs/ISSUES.md) for complete issue tracking.

**Quick Stats:**
- Total Issues: 150
- Resolved: 85
- Open: 65
- Last Updated: 2026-02-11

**Critical Issues (Recently Fixed):**
- ISSUE-2026-02-10-001: Malformed JSON in Chapter 7 - Fixed with timestamp repair
- ISSUE-2026-02-10-002: Widespread JSON malformation (22 files) - All repaired
- ISSUE-2026-02-10-003: Block classification improvements - Thought and dialogue detection enhanced

**Phase 2.7 Hotfixes (Feb 10, 2026):**
- DEVIATION-2026-02-10-001: NarratorBlock spacing overhaul with paragraph dividers
- DEVIATION-2026-02-10-002: IngestModal overlay restructuring for proper centering
- DEVIATION-2026-02-10-003: Modal CSS force-overrides with `!important`
- DEVIATION-2026-02-10-004: Bi-directional infinite scroll navigation
- DEVIATION-2026-02-10-005: Sidebar deep linking via `data-chapter-id`
- DEVIATION-2026-02-10-006: Reading progress tracking & read indicators

**All Core Functionality Complete:**
- All phases (0, 1, 2, 2.5, 2.6, 2.7, 3, 4, 6) fully operational
- 85 of 150 issues resolved (57% resolution rate)
- All critical bugs fixed, open issues are non-blocking
- Comprehensive test coverage (95%+)
- Production-ready with hotfixes applied

---

## License

MIT License

Copyright (c) 2026 BABEL Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

---

## Acknowledgments

- Powered by **Groq** (Llama 3.3 70B) and **Google Gemini 2.5 Flash**
- Built with **Pydantic**, **Hypothesis**, and **Tenacity**
- React UI built with **Vite**, **React 19**, and **Tailwind CSS**
- Inspired by the webnovel community

---

**Ready to transform your webnovels? It's completely FREE**

[Get Started](#quick-start) • [View Demo](demo/) • [Read Docs](docs/)
