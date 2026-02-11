"""
Phase 2 Implementation Guide - From Demo to Production

This file shows how to convert the standalone HTML demo into the actual
Phase 2 (Illusionist) renderer using Jinja2 templates and Python.

Directory Structure:
    babel/render/
    ├── __init__.py
    ├── engine.py          # Jinja2 template engine
    ├── renderer.py        # Core rendering logic
    └── models.py          # Render-specific models (if needed)
    
    templates/
    ├── layout.html        # Base template with CSS
    └── chapter.html       # Chapter rendering template
"""

from pathlib import Path
from typing import List, Optional
from datetime import datetime
import json
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Import Phase 1 models
from babel.transform import ChapterData, ScriptBlock, ScriptBlockType


# ===== STEP 1: CREATE THE JINJA2 ENGINE =====

class RenderEngine:
    """Jinja2 template engine for rendering chapters to HTML."""
    
    def __init__(self, template_dir: Path = Path("templates")):
        """
        Initialize the Jinja2 environment.
        
        Args:
            template_dir: Directory containing Jinja2 templates
        """
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml']),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # Register custom filters
        self.env.filters['speaker_color'] = self._speaker_color_filter
        self.env.filters['format_timestamp'] = self._format_timestamp_filter
    
    @staticmethod
    def _speaker_color_filter(speaker: Optional[str]) -> str:
        """
        Assign consistent color class to speaker based on name hash.
        
        This matches the JavaScript implementation in the demo.
        """
        if not speaker:
            return 'speaker-color-0'
        
        # Simple hash function (matches JavaScript)
        hash_value = 0
        for char in speaker:
            hash_value = ((hash_value << 5) - hash_value) + ord(char)
            hash_value = hash_value & 0xFFFFFFFF  # 32-bit integer
        
        color_index = abs(hash_value) % 10
        return f'speaker-color-{color_index}'
    
    @staticmethod
    def _format_timestamp_filter(timestamp: datetime) -> str:
        """Format datetime for display."""
        return timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')
    
    def render_chapter(self, chapter_data: ChapterData, chapter_title: str) -> str:
        """
        Render a chapter to HTML.
        
        Args:
            chapter_data: Structured chapter data from Phase 1
            chapter_title: Display title for the chapter
            
        Returns:
            Complete HTML string
        """
        template = self.env.get_template('chapter.html')
        return template.render(
            chapter=chapter_data,
            title=chapter_title,
            render_time=datetime.utcnow()
        )


# ===== STEP 2: CREATE THE RENDERER =====

class ChapterRenderer:
    """Renders ChapterData objects to HTML files."""
    
    def __init__(
        self,
        template_dir: Path = Path("templates"),
        output_dir: Path = Path("data/render")
    ):
        """
        Initialize the renderer.
        
        Args:
            template_dir: Directory containing Jinja2 templates
            output_dir: Directory to write HTML files
        """
        self.engine = RenderEngine(template_dir)
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def render_from_json(
        self,
        json_path: Path,
        chapter_title: Optional[str] = None
    ) -> Path:
        """
        Render a chapter from JSON file.
        
        Args:
            json_path: Path to JSON file from Phase 1
            chapter_title: Optional display title (defaults to filename)
            
        Returns:
            Path to generated HTML file
        """
        # Load JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Parse into ChapterData
        chapter_data = ChapterData(**data)
        
        # Generate title if not provided
        if chapter_title is None:
            chapter_title = json_path.stem.replace('_', ' ').title()
        
        # Render to HTML
        html_content = self.engine.render_chapter(chapter_data, chapter_title)
        
        # Write to file
        output_path = self.output_dir / f"{json_path.stem}.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def render_batch(
        self,
        json_dir: Path = Path("data/json"),
        chapter_titles: Optional[dict] = None
    ) -> List[Path]:
        """
        Render all chapters in a directory.
        
        Args:
            json_dir: Directory containing JSON files
            chapter_titles: Optional dict mapping filenames to titles
            
        Returns:
            List of generated HTML file paths
        """
        json_files = sorted(json_dir.glob("*.json"))
        output_paths = []
        
        for json_path in json_files:
            title = None
            if chapter_titles:
                title = chapter_titles.get(json_path.name)
            
            output_path = self.render_from_json(json_path, title)
            output_paths.append(output_path)
            print(f"✓ Rendered: {json_path.name} → {output_path.name}")
        
        return output_paths


# ===== STEP 3: TEMPLATE STRUCTURE =====

# This is what templates/layout.html should look like:
LAYOUT_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}SYSTEM: BABEL{% endblock %}</title>
    <style>
        /* Copy ALL CSS from demo_renderer.html here */
        /* The CSS is identical - just paste it in */
    </style>
</head>
<body>
    <div class="header">
        <h1>SYSTEM: BABEL</h1>
        <p class="subtitle">{% block subtitle %}The Illusionist{% endblock %}</p>
    </div>
    
    <div class="container">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

# This is what templates/chapter.html should look like:
CHAPTER_TEMPLATE = """
{% extends "layout.html" %}

{% block title %}{{ title }} - SYSTEM: BABEL{% endblock %}

{% block content %}
<div class="chapter-title">{{ title }}</div>

{% for block in chapter.blocks %}
<div class="script-block block-{{ block.type.value }}">
    {% if block.type.value == 'dialogue' %}
        <div class="speaker {{ block.speaker|speaker_color }}">
            {{ block.speaker or 'Unknown' }}
        </div>
        <div class="content">{{ block.content }}</div>
        {% if block.tone %}
        <div class="tone">[{{ block.tone }}]</div>
        {% endif %}
    
    {% elif block.type.value == 'monologue' %}
        <div class="speaker">{{ block.speaker }}'s thoughts</div>
        <div class="content">{{ block.content }}</div>
    
    {% else %}
        <div class="content">{{ block.content }}</div>
    {% endif %}
</div>
{% endfor %}

<div class="metadata">
    <div class="metadata-item">
        <span class="metadata-label">Source Hash:</span> {{ chapter.source_hash }}
    </div>
    <div class="metadata-item">
        <span class="metadata-label">Model Version:</span> {{ chapter.model_version }}
    </div>
    <div class="metadata-item">
        <span class="metadata-label">Processed At:</span> {{ chapter.processed_at|format_timestamp }}
    </div>
    <div class="metadata-item">
        <span class="metadata-label">Total Blocks:</span> {{ chapter.blocks|length }}
    </div>
</div>
{% endblock %}
"""


# ===== STEP 4: USAGE EXAMPLES =====

def example_render_single_chapter():
    """Example: Render a single chapter from JSON."""
    renderer = ChapterRenderer()
    
    # Render one chapter
    output_path = renderer.render_from_json(
        json_path=Path("data/json/Ch_001.json"),
        chapter_title="Chapter 1: The Awakening"
    )
    
    print(f"Chapter rendered to: {output_path}")


def example_render_batch():
    """Example: Render all chapters in a directory."""
    renderer = ChapterRenderer()
    
    # Optional: Load chapter titles from manifest
    # (This would come from Phase 0's chapter_map.json)
    chapter_titles = {
        "Ch_001.json": "Chapter 1: The Awakening",
        "Ch_002.json": "Chapter 2: First Steps",
        "Ch_003.json": "Chapter 3: The Trial",
    }
    
    # Render all chapters
    output_paths = renderer.render_batch(
        json_dir=Path("data/json"),
        chapter_titles=chapter_titles
    )
    
    print(f"\nRendered {len(output_paths)} chapters")


def example_omnibus_mode():
    """
    Example: Render all chapters into a single HTML file (omnibus mode).
    
    This is a future feature - not implemented in the demo.
    """
    # TODO: Implement omnibus renderer
    # - Load all JSON files
    # - Render all chapters in sequence
    # - Add table of contents sidebar
    # - Add chapter navigation
    pass


# ===== STEP 5: CLI INTEGRATION =====

def cli_render_command(args):
    """
    CLI command for rendering chapters.
    
    This would be integrated into babel/__main__.py:
    
    Usage:
        python -m babel render --input data/json --output data/render
        python -m babel render --chapter Ch_001.json
        python -m babel render --omnibus --output novel.html
    """
    renderer = ChapterRenderer(
        output_dir=Path(args.output)
    )
    
    if args.chapter:
        # Render single chapter
        output_path = renderer.render_from_json(Path(args.chapter))
        print(f"✓ Rendered: {output_path}")
    
    elif args.omnibus:
        # Render all chapters into one file
        # TODO: Implement omnibus mode
        print("Omnibus mode not yet implemented")
    
    else:
        # Render all chapters
        output_paths = renderer.render_batch(Path(args.input))
        print(f"✓ Rendered {len(output_paths)} chapters")


# ===== STEP 6: TESTING =====

def test_renderer():
    """
    Unit tests for the renderer.
    
    This would go in tests/test_renderer.py
    """
    import tempfile
    from babel.transform import ChapterData, ScriptBlock, ScriptBlockType
    
    # Create test data
    test_chapter = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Alice",
                content="Hello, world!",
                tone="cheerful"
            ),
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="She waved enthusiastically."
            )
        ],
        source_hash="test123",
        model_version="gemini-2.5-flash"
    )
    
    # Create temporary template directory
    with tempfile.TemporaryDirectory() as tmpdir:
        template_dir = Path(tmpdir) / "templates"
        template_dir.mkdir()
        
        # Write minimal templates
        (template_dir / "layout.html").write_text(LAYOUT_TEMPLATE)
        (template_dir / "chapter.html").write_text(CHAPTER_TEMPLATE)
        
        # Render
        engine = RenderEngine(template_dir)
        html = engine.render_chapter(test_chapter, "Test Chapter")
        
        # Assertions
        assert "Alice" in html
        assert "Hello, world!" in html
        assert "cheerful" in html
        assert "She waved enthusiastically." in html
        assert "speaker-color-" in html  # Color class assigned
        
        print("✓ All tests passed")


# ===== IMPLEMENTATION CHECKLIST =====

"""
Phase 2 Implementation Checklist:

[ ] 1. Create directory structure
    [ ] babel/render/__init__.py
    [ ] babel/render/engine.py
    [ ] babel/render/renderer.py
    [ ] templates/layout.html
    [ ] templates/chapter.html

[ ] 2. Copy CSS from demo
    [ ] Paste all CSS into templates/layout.html
    [ ] Verify responsive design works
    [ ] Test on mobile and desktop

[ ] 3. Implement RenderEngine class
    [ ] Jinja2 environment setup
    [ ] Custom filters (speaker_color, format_timestamp)
    [ ] Template loading and rendering

[ ] 4. Implement ChapterRenderer class
    [ ] render_from_json() method
    [ ] render_batch() method
    [ ] Error handling for missing files

[ ] 5. Create Jinja2 templates
    [ ] layout.html (base template)
    [ ] chapter.html (extends layout)
    [ ] Test with sample data

[ ] 6. Write unit tests
    [ ] Test RenderEngine filters
    [ ] Test ChapterRenderer methods
    [ ] Test template rendering
    [ ] Test error cases

[ ] 7. Integration testing
    [ ] Test with real Phase 1 output
    [ ] Verify all block types render correctly
    [ ] Check speaker colors are consistent
    [ ] Validate HTML structure

[ ] 8. CLI integration
    [ ] Add 'render' command to babel/__main__.py
    [ ] Support single chapter rendering
    [ ] Support batch rendering
    [ ] Add progress indicators

[ ] 9. Documentation
    [ ] Update README.md
    [ ] Add docstrings to all classes/methods
    [ ] Create usage examples
    [ ] Document template customization

[ ] 10. Future features (Phase 2.5)
    [ ] Omnibus mode (all chapters in one file)
    [ ] Table of contents sidebar
    [ ] Chapter navigation (prev/next)
    [ ] Search functionality
    [ ] Theme switcher
    [ ] Export to PDF
"""


if __name__ == "__main__":
    print("Phase 2 Implementation Guide")
    print("=" * 50)
    print("\nThis file shows how to convert the demo into production code.")
    print("See the implementation checklist at the bottom of this file.")
    print("\nTo run examples:")
    print("  - example_render_single_chapter()")
    print("  - example_render_batch()")
    print("  - test_renderer()")
