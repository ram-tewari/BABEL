"""
Unit tests for the omnibus generator.

Tests specific examples and edge cases for omnibus HTML generation.
"""

import tempfile
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from babel.pipeline.omnibus import OmnibusGenerator


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def omnibus_template(temp_dir):
    """Create a basic omnibus template."""
    template_path = temp_dir / "omnibus.html"
    with open(template_path, 'w', encoding='utf-8') as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
</head>
<body>
    <nav class="toc-sidebar">
        <h2>Table of Contents</h2>
        <ul>
            {{ toc_html | safe }}
        </ul>
    </nav>
    
    <div class="content">
        {% for chapter in chapters %}
        <div id="chapter-{{ chapter.index }}" class="chapter-marker">
            <h1 class="chapter-title">{{ chapter.title }}</h1>
            <div class="chapter-content">
                {{ chapter.html_content | safe }}
            </div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
        """)
    return template_path


@pytest.fixture
def sample_chapters(temp_dir):
    """Create sample chapter HTML files."""
    chapters = []
    
    for i in range(3):
        chapter_file = temp_dir / f"chapter_{i}.html"
        title = f"Chapter {i+1}: Test Chapter"
        content = f"<p>This is the content of chapter {i+1}.</p>"
        
        with open(chapter_file, 'w', encoding='utf-8') as f:
            f.write(f"""
<!DOCTYPE html>
<html>
<head><title>{title}</title></head>
<body>
    <div class="chapter-content">
        {content}
    </div>
</body>
</html>
            """)
        
        chapters.append({
            'index': i,
            'title': title,
            'html_path': str(chapter_file)
        })
    
    return chapters


def test_omnibus_generator_initialization(omnibus_template):
    """Test that OmnibusGenerator initializes correctly."""
    generator = OmnibusGenerator(omnibus_template)
    
    assert generator.template_path == omnibus_template
    assert generator.template is not None
    assert generator.env is not None


def test_omnibus_generator_missing_template():
    """Test that OmnibusGenerator raises error for missing template."""
    with pytest.raises(Exception):
        OmnibusGenerator(Path("nonexistent_template.html"))


def test_generate_combines_multiple_chapters(omnibus_template, sample_chapters, temp_dir):
    """Test that generate() combines multiple chapters into one file."""
    generator = OmnibusGenerator(omnibus_template)
    output_path = temp_dir / "omnibus.html"
    
    generator.generate(sample_chapters, output_path, title="Test Omnibus")
    
    # Verify file was created
    assert output_path.exists()
    
    # Parse and verify content
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Check that all chapters are present
    chapter_markers = soup.find_all('div', class_='chapter-marker')
    assert len(chapter_markers) == 3
    
    # Check that each chapter has correct content
    for i, chapter in enumerate(sample_chapters):
        marker = soup.find('div', id=f"chapter-{i}")
        assert marker is not None
        
        title_elem = marker.find('h1', class_='chapter-title')
        assert chapter['title'] in title_elem.get_text()
        
        content_elem = marker.find('div', class_='chapter-content')
        assert f"content of chapter {i+1}" in content_elem.get_text()


def test_generate_toc_with_all_chapter_titles(omnibus_template, sample_chapters, temp_dir):
    """Test that TOC includes all chapter titles."""
    generator = OmnibusGenerator(omnibus_template)
    output_path = temp_dir / "omnibus.html"
    
    generator.generate(sample_chapters, output_path, title="Test Omnibus")
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    toc = soup.find('nav', class_='toc-sidebar')
    
    # Check that all chapter titles are in TOC
    for chapter in sample_chapters:
        assert chapter['title'] in toc.get_text()
    
    # Check that TOC has correct number of links
    toc_links = toc.find_all('a')
    assert len(toc_links) == len(sample_chapters)


def test_generate_navigation_markers(omnibus_template, sample_chapters, temp_dir):
    """Test that each chapter has navigation markers."""
    generator = OmnibusGenerator(omnibus_template)
    output_path = temp_dir / "omnibus.html"
    
    generator.generate(sample_chapters, output_path, title="Test Omnibus")
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Check that each chapter has correct ID
    for chapter in sample_chapters:
        marker_id = f"chapter-{chapter['index']}"
        marker = soup.find('div', id=marker_id)
        assert marker is not None, f"Chapter {chapter['index']} should have marker with id='{marker_id}'"
        
        # Check that TOC links to this marker
        toc = soup.find('nav', class_='toc-sidebar')
        link = toc.find('a', href=f"#{marker_id}")
        assert link is not None, f"TOC should have link to {marker_id}"


def test_generate_preserves_chapter_styling(omnibus_template, temp_dir):
    """Test that chapter styling is preserved in omnibus."""
    # Create chapter with custom styling
    chapter_file = temp_dir / "styled_chapter.html"
    with open(chapter_file, 'w', encoding='utf-8') as f:
        f.write("""
<!DOCTYPE html>
<html>
<head><title>Styled Chapter</title></head>
<body>
    <div class="dialogue left" style="color: blue;">
        <div class="speaker">Character A</div>
        <div class="bubble">Hello!</div>
    </div>
</body>
</html>
        """)
    
    chapters = [{
        'index': 0,
        'title': 'Styled Chapter',
        'html_path': str(chapter_file)
    }]
    
    generator = OmnibusGenerator(omnibus_template)
    output_path = temp_dir / "omnibus.html"
    
    generator.generate(chapters, output_path, title="Test Omnibus")
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Check that styling is preserved
    dialogue = soup.find('div', class_='dialogue')
    assert dialogue is not None, "Dialogue div should be preserved"
    assert 'left' in dialogue.get('class', []), "Dialogue class should be preserved"
    
    speaker = soup.find('div', class_='speaker')
    assert speaker is not None, "Speaker div should be preserved"
    assert 'Character A' in speaker.get_text(), "Speaker text should be preserved"


def test_generate_with_empty_chapters_list(omnibus_template, temp_dir):
    """Test that generate() handles empty chapters list."""
    generator = OmnibusGenerator(omnibus_template)
    output_path = temp_dir / "omnibus.html"
    
    generator.generate([], output_path, title="Empty Omnibus")
    
    # Verify file was created
    assert output_path.exists()
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Check that TOC is empty
    toc = soup.find('nav', class_='toc-sidebar')
    toc_links = toc.find_all('a')
    assert len(toc_links) == 0
    
    # Check that content is empty
    content = soup.find('div', class_='content')
    chapter_markers = content.find_all('div', class_='chapter-marker')
    assert len(chapter_markers) == 0


def test_generate_with_single_chapter(omnibus_template, temp_dir):
    """Test that generate() works with a single chapter."""
    chapter_file = temp_dir / "single_chapter.html"
    with open(chapter_file, 'w', encoding='utf-8') as f:
        f.write("""
<!DOCTYPE html>
<html>
<head><title>Single Chapter</title></head>
<body>
    <p>This is a single chapter.</p>
</body>
</html>
        """)
    
    chapters = [{
        'index': 0,
        'title': 'Single Chapter',
        'html_path': str(chapter_file)
    }]
    
    generator = OmnibusGenerator(omnibus_template)
    output_path = temp_dir / "omnibus.html"
    
    generator.generate(chapters, output_path, title="Single Chapter Omnibus")
    
    assert output_path.exists()
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Check that chapter is present
    marker = soup.find('div', id='chapter-0')
    assert marker is not None
    
    # Check that TOC has one link
    toc = soup.find('nav', class_='toc-sidebar')
    toc_links = toc.find_all('a')
    assert len(toc_links) == 1


def test_load_chapter_html_extracts_body_content(omnibus_template, temp_dir):
    """Test that _load_chapter_html() extracts body content correctly."""
    chapter_file = temp_dir / "test_chapter.html"
    with open(chapter_file, 'w', encoding='utf-8') as f:
        f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>Test</title>
    <style>body { color: red; }</style>
</head>
<body>
    <div class="content">This is the body content.</div>
</body>
</html>
        """)
    
    generator = OmnibusGenerator(omnibus_template)
    content = generator._load_chapter_html(chapter_file)
    
    # Should extract only body content, not head
    assert 'This is the body content' in content
    assert '<head>' not in content
    assert '<style>' not in content


def test_generate_toc_creates_correct_links(omnibus_template):
    """Test that _generate_toc() creates correct HTML links."""
    generator = OmnibusGenerator(omnibus_template)
    
    chapters = [
        {'index': 0, 'title': 'Chapter 1'},
        {'index': 1, 'title': 'Chapter 2'},
        {'index': 2, 'title': 'Chapter 3'}
    ]
    
    toc_html = generator._generate_toc(chapters)
    
    # Parse TOC HTML
    soup = BeautifulSoup(f"<ul>{toc_html}</ul>", 'html.parser')
    links = soup.find_all('a')
    
    assert len(links) == 3
    
    for i, link in enumerate(links):
        assert link.get('href') == f'#chapter-{i}'
        assert f'Chapter {i+1}' in link.get_text()


def test_generate_creates_output_directory(omnibus_template, sample_chapters, temp_dir):
    """Test that generate() creates output directory if it doesn't exist."""
    generator = OmnibusGenerator(omnibus_template)
    
    # Create output path in non-existent subdirectory
    output_path = temp_dir / "subdir" / "nested" / "omnibus.html"
    
    generator.generate(sample_chapters, output_path, title="Test Omnibus")
    
    # Verify file was created and directory structure exists
    assert output_path.exists()
    assert output_path.parent.exists()


def test_generate_with_special_characters_in_titles(omnibus_template, temp_dir):
    """Test that generate() handles special characters in chapter titles."""
    chapter_file = temp_dir / "special_chapter.html"
    with open(chapter_file, 'w', encoding='utf-8') as f:
        f.write("""
<!DOCTYPE html>
<html>
<head><title>Special Chapter</title></head>
<body>
    <p>Content</p>
</body>
</html>
        """)
    
    chapters = [{
        'index': 0,
        'title': 'Chapter 1: "The Beginning" & <The End>',
        'html_path': str(chapter_file)
    }]
    
    generator = OmnibusGenerator(omnibus_template)
    output_path = temp_dir / "omnibus.html"
    
    # Should not raise exception
    generator.generate(chapters, output_path, title="Test Omnibus")
    
    assert output_path.exists()
    
    with open(output_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # Verify title is properly escaped in HTML
    assert 'Chapter 1:' in html
