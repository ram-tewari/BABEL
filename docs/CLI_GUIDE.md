# BABEL CLI Guide

Complete guide to using the BABEL command-line interface.

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Create a `.env` file with your API keys:

```bash
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
```

## Basic Usage

```bash
# Show version
python -m babel version

# Show help
python -m babel --help

# Show help for a command
python -m babel transform --help
```

## Transform Commands

Transform raw text into structured JSON using LLM.

### Transform Single Chapter

```bash
python -m babel transform chapter input.txt
python -m babel transform chapter input.txt -o output.json
python -m babel transform chapter input.txt --provider groq
python -m babel transform chapter input.txt --provider ollama --model llama2
```

### Batch Transform

```bash
python -m babel transform batch input_dir/
python -m babel transform batch input_dir/ -o output_dir/
python -m babel transform batch input_dir/ --provider groq --pattern "chapter_*.txt"
```

### Validate Output

```bash
python -m babel transform validate output.json
```

## Render Commands

Convert structured JSON to HTML.

### Render Single Chapter

```bash
python -m babel render chapter chapter.json
python -m babel render chapter chapter.json -o output.html
python -m babel render chapter chapter.json --theme dark
python -m babel render chapter chapter.json --template custom.jinja2
```

### Render Omnibus

Combine multiple chapters into a single HTML file:

```bash
python -m babel render omnibus json_dir/ omnibus.html
python -m babel render omnibus json_dir/ omnibus.html --theme dark
```

### Batch Render

Render multiple chapters to individual HTML files:

```bash
python -m babel render batch json_dir/
python -m babel render batch json_dir/ -o html_dir/
python -m babel render batch json_dir/ --theme dark
```

## Context Commands

Manage glossary and context injection.

### Inject Context

```bash
python -m babel context inject chapter.json
python -m babel context inject chapter.json --glossary custom_glossary.yaml
python -m babel context inject chapter.json -o enriched.json
```

### List Glossary Entries

```bash
python -m babel context list
python -m babel context list --type character
python -m babel context list --type location
python -m babel context list --glossary custom_glossary.yaml
```

### Add Glossary Entry

```bash
python -m babel context add "Character Name" \
  --type character \
  --description "Main protagonist"

python -m babel context add "Location" \
  --type location \
  --description "Capital city"
```

### Generate Chapter Map

```bash
python -m babel context map json_dir/
python -m babel context map json_dir/ -o custom_map.json
```

## Pipeline Commands

Run the complete processing pipeline.

### Run Pipeline

```bash
python -m babel pipeline run input_dir/ output_dir/
python -m babel pipeline run input_dir/ output_dir/ --provider groq
python -m babel pipeline run input_dir/ output_dir/ --config custom_pipeline.yaml
python -m babel pipeline run input_dir/ output_dir/ --skip-transform
python -m babel pipeline run input_dir/ output_dir/ --skip-render
```

### Check Pipeline Status

```bash
python -m babel pipeline status
python -m babel pipeline status --state custom_state.json
```

### Resume Failed Pipeline

```bash
python -m babel pipeline resume
python -m babel pipeline resume --state custom_state.json
```

## Utility Commands

Diagnostic and maintenance tools.

### Diagnose Provider

Test LLM provider connection:

```bash
python -m babel util diagnose gemini
python -m babel util diagnose groq
python -m babel util diagnose ollama
python -m babel util diagnose ollama --model llama2
```

### Sanitize Text

Clean raw text files:

```bash
python -m babel util sanitize input.txt
python -m babel util sanitize input.txt -o clean.txt
```

### Show Statistics

Display chapter statistics:

```bash
python -m babel util stats chapter.json
```

### Validate All Files

Validate all JSON files in a directory:

```bash
python -m babel util validate-all json_dir/
```

## Common Workflows

### Complete Processing Workflow

```bash
# 1. Transform raw text to JSON
python -m babel transform batch raw_chapters/ -o json_chapters/

# 2. Inject context from glossary
for file in json_chapters/*.json; do
  python -m babel context inject "$file"
done

# 3. Render to HTML
python -m babel render batch json_chapters/ -o html_chapters/

# 4. Create omnibus
python -m babel render omnibus json_chapters/ complete_novel.html
```

### Single Chapter Workflow

```bash
# Transform
python -m babel transform chapter chapter_01.txt -o chapter_01.json

# Validate
python -m babel transform validate chapter_01.json

# Inject context
python -m babel context inject chapter_01.json

# Render
python -m babel render chapter chapter_01.json -o chapter_01.html
```

### Automated Pipeline

```bash
# Run everything at once
python -m babel pipeline run raw_chapters/ output/ --provider gemini
```

## Tips

1. **Use batch commands** for processing multiple files
2. **Validate output** after transformation to catch errors early
3. **Use the pipeline** for automated processing
4. **Check diagnostics** if you encounter provider issues
5. **Use --help** on any command to see all options

## Troubleshooting

### Provider Connection Issues

```bash
# Test connection
python -m babel util diagnose gemini

# Check API key in .env file
cat .env
```

### Validation Errors

```bash
# Validate single file
python -m babel transform validate chapter.json

# Validate all files
python -m babel util validate-all json_dir/
```

### Pipeline Failures

```bash
# Check status
python -m babel pipeline status

# Resume from last checkpoint
python -m babel pipeline resume
```

## Advanced Usage

### Custom Templates

```bash
python -m babel render chapter chapter.json --template custom.jinja2
```

### Custom Glossary

```bash
python -m babel context inject chapter.json --glossary custom_glossary.yaml
```

### Custom Pipeline Config

```bash
python -m babel pipeline run input/ output/ --config custom_pipeline.yaml
```

## Environment Variables

- `GEMINI_API_KEY` - Gemini API key
- `GROQ_API_KEY` - Groq API key
- `OLLAMA_BASE_URL` - Ollama server URL (default: http://localhost:11434)

## Exit Codes

- `0` - Success
- `1` - Error (validation failed, connection failed, etc.)
