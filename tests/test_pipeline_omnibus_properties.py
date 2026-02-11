"""
Property-based tests for the omnibus generator.

These tests validate universal correctness properties that should hold
across all valid executions of the omnibus generation system.
"""

import tempfile
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from hypothesis import given, strategies as st, settings, HealthCheck

from babel.pipeline.omnibus import OmnibusGenerator


# Strategy for generating chapter data
@st.composite
def chapter_data(draw):
    """Generate valid chapter data with HTML content."""
    index = draw(st.integers(min_value=0, max_value=100))
    # Filter out surrogate characters and ALL control characters (including \x0c form feed)
    title = draw(st.text(
        min_size=1,
        max_size=100,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),  # Cc = control characters
            blacklist_characters='<>'
        )
    ))
    # Generate simple HTML content
    content = draw(st.text(
        min_size=10,
        max_size=500,
        alphabet=st.characters(
            blacklist_categories=('Cs', 'Cc'),  # Cc = control characters
            blacklist_characters='<>'
        )
    ))
    html_content = f"<div><p>{content}</p></div>"
    
    return {
        'index': index,
        'title': title,
        'html_content': html_content
    }


# Strategy for generating lists of chapters
chapters_list = st.lists(
    chapter_data(),
    min_size=2,
    max_size=10,
    unique_by=lambda x: x['index']
).map(lambda chapters: sorted(chapters, key=lambda x: x['index']))


@settings(max_examples=50, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(chapters=chapters_list)
def test_property_8_omnibus_completeness(chapters):
    """
    Feature: automation-pipeline, Property 8: Omnibus Completeness
    
    For any set of chapters that complete Phase 2 rendering, the
    Omnibus_Generator should produce an Omnibus.html file that includes
    all chapter HTML content, a Table of Contents with all chapter titles,
    preserved styling from individual files, and navigation markers for
    each chapter.
    
    Validates: Requirements 8.2, 8.4, 8.5
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        
        # Create temporary chapter HTML files
        chapter_files = []
        for chapter in chapters:
            chapter_file = tmpdir_path / f"chapter_{chapter['index']}.html"
            with open(chapter_file, 'w', encoding='utf-8') as f:
                f.write(f"""
                <!DOCTYPE html>
                <html>
                <head><title>{chapter['title']}</title></head>
                <body>
                    {chapter['html_content']}
                </body>
                </html>
                """)
            chapter_files.append({
                'index': chapter['index'],
                'title': chapter['title'],
                'html_path': str(chapter_file)
            })
        
        # Create omnibus template
        template_path = tmpdir_path / "omnibus.html"
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
        
        # Generate omnibus
        generator = OmnibusGenerator(template_path)
        output_path = tmpdir_path / "omnibus.html"
        generator.generate(chapter_files, output_path, title="Test Omnibus")
        
        # Verify omnibus was created
        assert output_path.exists(), "Omnibus file should be created"
        
        # Parse omnibus HTML
        with open(output_path, 'r', encoding='utf-8') as f:
            omnibus_html = f.read()
        
        soup = BeautifulSoup(omnibus_html, 'html.parser')
        
        # Property 1: All chapter titles should be in TOC
        toc = soup.find('nav', class_='toc-sidebar')
        assert toc is not None, "TOC sidebar should exist"
        
        toc_links = toc.find_all('a')
        assert len(toc_links) == len(chapters), (
            f"TOC should have {len(chapters)} links, found {len(toc_links)}"
        )
        
        for chapter in chapters:
            # Check that chapter title appears in TOC
            toc_text = toc.get_text()
            assert chapter['title'] in toc_text, (
                f"Chapter title '{chapter['title']}' should appear in TOC"
            )
        
        # Property 2: All chapter content should be present
        content_div = soup.find('div', class_='content')
        assert content_div is not None, "Content div should exist"
        
        chapter_markers = content_div.find_all('div', class_='chapter-marker')
        assert len(chapter_markers) == len(chapters), (
            f"Should have {len(chapters)} chapter markers, found {len(chapter_markers)}"
        )
        
        # Property 3: Each chapter should have navigation marker with correct ID
        for chapter in chapters:
            marker_id = f"chapter-{chapter['index']}"
            marker = soup.find('div', id=marker_id)
            assert marker is not None, (
                f"Chapter {chapter['index']} should have navigation marker with id='{marker_id}'"
            )
            
            # Check that chapter title is present
            title_elem = marker.find('h1', class_='chapter-title')
            assert title_elem is not None, (
                f"Chapter {chapter['index']} should have title element"
            )
            assert chapter['title'] in title_elem.get_text(), (
                f"Chapter title '{chapter['title']}' should appear in title element"
            )
        
        # Property 4: TOC links should point to correct chapter markers
        for chapter in chapters:
            expected_href = f"#chapter-{chapter['index']}"
            link = toc.find('a', href=expected_href)
            assert link is not None, (
                f"TOC should have link to chapter {chapter['index']} with href='{expected_href}'"
            )
        
        # Property 5: Chapter content should be preserved
        for chapter in chapters:
            marker_id = f"chapter-{chapter['index']}"
            marker = soup.find('div', id=marker_id)
            content_div = marker.find('div', class_='chapter-content')
            assert content_div is not None, (
                f"Chapter {chapter['index']} should have content div"
            )
            
            # Check that original HTML content is present (at least partially)
            # We extract the text content from the original HTML
            original_soup = BeautifulSoup(chapter['html_content'], 'html.parser')
            original_text = original_soup.get_text().strip()
            
            if original_text:  # Only check if there's actual text content
                content_text = content_div.get_text()
                # Normalize whitespace for comparison (HTML parsers normalize \r to \n)
                original_normalized = ' '.join(original_text.split())
                content_normalized = ' '.join(content_text.split())
                assert original_normalized in content_normalized, (
                    f"Chapter {chapter['index']} content should be preserved"
                )
