"""
Property-based tests for EPUB Sanitization Module

These tests use Hypothesis to verify universal properties across randomized inputs.
Each test runs a minimum of 100 iterations to ensure robustness.
"""

import json
import re
from datetime import datetime
from hypothesis import given, strategies as st, settings, HealthCheck
from babel.sanitize import ChapterEntry, ChapterMap, TextCleaner


# ============================================================================
# Hypothesis Strategies
# ============================================================================

def chapter_entry_strategy():
    """Generate valid ChapterEntry instances."""
    return st.builds(
        ChapterEntry,
        index=st.integers(min_value=0, max_value=999),
        filename=st.from_regex(r'^[a-zA-Z0-9_-]{1,20}\.txt$', fullmatch=True),
        title=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=50),
        token_count_est=st.integers(min_value=0, max_value=10000),
        volume=st.one_of(st.none(), st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=10)),
        metadata=st.dictionaries(
            keys=st.text(alphabet=st.characters(min_codepoint=97, max_codepoint=122), min_size=1, max_size=10),
            values=st.one_of(
                st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=20),
                st.integers(min_value=-1000, max_value=1000),
                st.booleans()
            ),
            max_size=3
        )
    )


def chapter_map_strategy():
    """Generate valid ChapterMap instances."""
    return st.builds(
        ChapterMap,
        source_filename=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=50),
        processed_at=st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31)
        ),
        chapters=st.lists(chapter_entry_strategy(), min_size=0, max_size=10)
    )


# ============================================================================
# Property Tests
# ============================================================================

@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(chapter_map_strategy())
def test_property_13_manifest_serialization_round_trip(manifest: ChapterMap):
    """
    Feature: epub-sanitization, Property 13: Manifest Serialization Round Trip
    
    For any valid ChapterMap object, serializing to JSON then deserializing
    should produce an equivalent object with all fields preserved.
    
    Validates: Requirements 8.1
    """
    # Serialize to JSON string
    json_str = manifest.model_dump_json()
    
    # Deserialize back to object
    manifest_dict = json.loads(json_str)
    reconstructed = ChapterMap.model_validate(manifest_dict)
    
    # Verify all fields are preserved
    assert reconstructed.source_filename == manifest.source_filename
    assert reconstructed.processed_at == manifest.processed_at
    assert len(reconstructed.chapters) == len(manifest.chapters)
    
    # Verify each chapter entry is preserved
    for original_chapter, reconstructed_chapter in zip(manifest.chapters, reconstructed.chapters):
        assert reconstructed_chapter.index == original_chapter.index
        assert reconstructed_chapter.filename == original_chapter.filename
        assert reconstructed_chapter.title == original_chapter.title
        assert reconstructed_chapter.token_count_est == original_chapter.token_count_est
        assert reconstructed_chapter.volume == original_chapter.volume
        assert reconstructed_chapter.metadata == original_chapter.metadata


@settings(max_examples=100)
@given(
    base_text=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=10, max_size=500),
    url_type=st.sampled_from(['http://', 'https://', 'www.'])
)
def test_property_4_url_removal_completeness(base_text: str, url_type: str):
    """
    Feature: epub-sanitization, Property 4: URL Removal Completeness
    
    For any text containing URLs, after cleaning, no substring matching URL patterns
    (http://, https://, www.) should remain.
    
    Validates: Requirements 3.1
    """
    # Inject URL into text
    url = f"{url_type}example.com/path"
    text_with_url = f"{base_text[:len(base_text)//2]} {url} {base_text[len(base_text)//2:]}"
    
    # Clean the text
    cleaned = TextCleaner._remove_urls(text_with_url)
    
    # Verify no URL patterns remain
    assert 'http://' not in cleaned
    assert 'https://' not in cleaned
    assert 'www.' not in cleaned


@settings(max_examples=100)
@given(
    base_text=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=10, max_size=500),
    note_marker=st.sampled_from(["Translator's Note:", "Translator Note:", "TN:", "tn:"])
)
def test_property_5_translator_note_removal(base_text: str, note_marker: str):
    """
    Feature: epub-sanitization, Property 5: Translator Note Removal
    
    For any text containing translator note markers, after cleaning, no lines
    containing "Translator's Note:" or "Tn:" should remain.
    
    Validates: Requirements 3.2
    """
    # Inject translator note into text
    note_content = "This is a translator note explaining something."
    text_with_note = f"{base_text}\n\n{note_marker} {note_content}\n\nMore text here."
    
    # Clean the text
    cleaned = TextCleaner._remove_translator_notes(text_with_note)
    
    # Verify no translator note markers remain
    assert "translator's note:" not in cleaned.lower()
    assert "translator note:" not in cleaned.lower()
    assert "tn:" not in cleaned.lower()


@settings(max_examples=100)
@given(
    base_text=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=10, max_size=500),
    watermark_type=st.sampled_from(["Read at", "Read on", "Read more at"])
)
def test_property_6_watermark_removal(base_text: str, watermark_type: str):
    """
    Feature: epub-sanitization, Property 6: Watermark Removal
    
    For any text containing site watermarks, after cleaning, no substring matching
    watermark patterns like "Read at [Site]" should remain.
    
    Validates: Requirements 3.3
    """
    # Inject watermark into text
    watermark = f"{watermark_type} [NovelSite.com]"
    text_with_watermark = f"{base_text} {watermark}"
    
    # Clean the text
    cleaned = TextCleaner._remove_watermarks(text_with_watermark)
    
    # Verify no watermark patterns remain
    assert "read at" not in cleaned.lower()
    assert "read on" not in cleaned.lower()
    assert "read more at" not in cleaned.lower()


@settings(max_examples=100)
@given(
    base_text=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=10, max_size=200),
    newline_count=st.integers(min_value=3, max_value=10)
)
def test_property_7_newline_normalization(base_text: str, newline_count: int):
    """
    Feature: epub-sanitization, Property 7: Newline Normalization
    
    For any text with excessive newlines, after cleaning, no sequence of 3 or more
    consecutive newlines should remain.
    
    Validates: Requirements 3.4
    """
    # Create text with excessive newlines
    excessive_newlines = '\n' * newline_count
    text_with_newlines = f"{base_text}{excessive_newlines}{base_text}"
    
    # Clean the text
    cleaned = TextCleaner._normalize_whitespace(text_with_newlines)
    
    # Verify no sequences of 3+ newlines remain
    assert '\n\n\n' not in cleaned


@settings(max_examples=100)
@given(
    base_text=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=10, max_size=500),
    quote_type=st.sampled_from(['\u201c', '\u201d', '\u2018', '\u2019'])  # Smart quotes: " " ' '
)
def test_property_8_quote_normalization(base_text: str, quote_type: str):
    """
    Feature: epub-sanitization, Property 8: Quote Normalization
    
    For any text containing smart quotes (curly quotes), after cleaning, all quotes
    should be straight quotes (ASCII 34 for double, 39 for single).
    
    Validates: Requirements 3.5
    """
    # Inject smart quotes into text
    text_with_smart_quotes = f"{base_text[:len(base_text)//2]}{quote_type}quoted text{quote_type}{base_text[len(base_text)//2:]}"
    
    # Clean the text
    cleaned = TextCleaner._normalize_quotes(text_with_smart_quotes)
    
    # Verify no smart quotes remain
    assert '\u201c' not in cleaned  # "
    assert '\u201d' not in cleaned  # "
    assert '\u2018' not in cleaned  # '
    assert '\u2019' not in cleaned  # '


@settings(max_examples=100)
@given(
    chapter_titles=st.lists(
        st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=100),
        min_size=2,
        max_size=20
    )
)
def test_property_10_filename_uniqueness(chapter_titles: list):
    """
    Feature: epub-sanitization, Property 10: Filename Uniqueness
    
    For any list of chapters processed from a single source, all generated
    filenames should be unique.
    
    Validates: Requirements 5.2
    """
    from babel.sanitize import FileWriter
    
    # Generate filenames for all chapter titles
    filenames = []
    for index, title in enumerate(chapter_titles):
        filename = FileWriter._generate_filename(index, title)
        filenames.append(filename)
    
    # Verify all filenames are unique
    assert len(filenames) == len(set(filenames)), \
        f"Generated filenames are not unique. Duplicates found: {[f for f in filenames if filenames.count(f) > 1]}"
    
    # Additional verification: check that each filename is valid
    for filename in filenames:
        # Should end with .txt
        assert filename.endswith('.txt'), f"Filename '{filename}' should end with .txt"
        
        # Should start with zero-padded index (3 digits)
        assert filename[:3].isdigit(), f"Filename '{filename}' should start with 3-digit index"
        
        # Should have underscore separator after index
        assert filename[3] == '_', f"Filename '{filename}' should have underscore after index"


@settings(max_examples=100)
@given(
    base_text=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=100, max_size=500),
    litrpg_marker=st.sampled_from(["Status Window", "Level Up", "[System]"])
)
def test_property_16_content_tag_detection(base_text: str, litrpg_marker: str):
    """
    Feature: epub-sanitization, Property 16: Content Tag Detection
    
    For any text containing LitRPG markers ("Status Window", "Level Up", "[System]"),
    the chapter metadata should include the "litrpg" tag.
    
    Validates: Requirements 9.2
    """
    # Inject LitRPG marker into text
    text_with_marker = f"{base_text} {litrpg_marker} {base_text}"
    
    # Detect content tags
    tags = TextCleaner.detect_content_tags(text_with_marker)
    
    # Verify "litrpg" tag is detected
    assert "litrpg" in tags


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    num_chapters=st.integers(min_value=2, max_value=5),
    content_seed=st.integers(min_value=0, max_value=1000000)
)
def test_property_1_epub_spine_order_preservation(num_chapters: int, content_seed: int):
    """
    Feature: epub-sanitization, Property 1: EPUB Spine Order Preservation
    
    For any EPUB file with a defined spine order, the output chapter indices
    should match the spine sequence exactly.
    
    Validates: Requirements 1.2
    """
    import tempfile
    import os
    from babel.sanitize import EPUBIngester
    from ebooklib import epub
    
    # Create a test EPUB with known spine order
    book = epub.EpubBook()
    book.set_identifier(f'test_spine_{content_seed}')
    book.set_title(f'Test Book {content_seed}')
    book.set_language('en')
    
    # Create chapters with unique identifiable content
    chapters = []
    for i in range(num_chapters):
        chapter = epub.EpubHtml(
            title=f'Chapter {i+1}',
            file_name=f'chap_{i+1:02d}.xhtml',
            lang='en'
        )
        # Use content_seed to create varied content
        chapter.content = f'<html><body><h1>Chapter {i+1}</h1><p>Content for chapter {i+1} with seed {content_seed}. {"X" * (i * 10)}</p></body></html>'
        chapters.append(chapter)
        book.add_item(chapter)
    
    # Add required EPUB components
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Define spine in the order we created chapters
    book.spine = chapters
    
    # Write EPUB to temporary file
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        temp_path = f.name
    
    try:
        # Write EPUB
        epub.write_epub(temp_path, book, {'epub3_pages': False})
        
        # Extract chapters using EPUBIngester
        extracted_chapters = EPUBIngester.extract_chapters(temp_path)
        
        # Verify spine order preservation
        assert len(extracted_chapters) == num_chapters, \
            f"Expected {num_chapters} chapters, got {len(extracted_chapters)}"
        
        # Verify each chapter has the correct index matching spine order
        for i, chapter in enumerate(extracted_chapters):
            assert chapter.index == i, \
                f"Chapter at spine position {i} has incorrect index {chapter.index}"
            
            # Verify content matches expected chapter
            expected_marker = f"Chapter {i+1}"
            assert expected_marker in chapter.content, \
                f"Chapter at index {i} should contain '{expected_marker}', got: {chapter.content[:100]}"
    
    finally:
        # Cleanup
        import time
        time.sleep(0.1)  # Brief delay for Windows file locking
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except PermissionError:
            pass  # File still locked, skip cleanup


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    num_chapters=st.integers(min_value=2, max_value=5),
    content_seed=st.integers(min_value=0, max_value=1000000)
)
def test_property_2_chapter_title_preservation(num_chapters: int, content_seed: int):
    """
    Feature: epub-sanitization, Property 2: Chapter Title Preservation
    
    For any EPUB file with chapter titles in metadata, those titles should appear
    in the corresponding ChapterEntry in the manifest.
    
    Validates: Requirements 1.5
    """
    import tempfile
    import os
    from babel.sanitize import EPUBIngester
    from ebooklib import epub
    
    # Create a test EPUB with explicit chapter titles in TOC
    book = epub.EpubBook()
    book.set_identifier(f'test_titles_{content_seed}')
    book.set_title(f'Test Book {content_seed}')
    book.set_language('en')
    
    # Create chapters with unique, identifiable titles
    chapters = []
    expected_titles = []
    toc_entries = []
    
    for i in range(num_chapters):
        # Generate unique title using seed for variety
        title = f'Chapter {i+1}: The Adventure Continues (Seed {content_seed})'
        expected_titles.append(title)
        
        chapter = epub.EpubHtml(
            title=title,  # Set title (though this won't be preserved in EPUB)
            file_name=f'chap_{i+1:02d}.xhtml',
            lang='en'
        )
        chapter.content = f'<html><body><h1>{title}</h1><p>Content for chapter {i+1}.</p></body></html>'
        chapters.append(chapter)
        book.add_item(chapter)
        
        # Add to TOC with title - this is what gets preserved in EPUB metadata
        toc_entries.append(epub.Link(f'chap_{i+1:02d}.xhtml', title, f'chap_{i+1:02d}'))
    
    # Set the table of contents with our titles
    book.toc = toc_entries
    
    # Add required EPUB components
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Define spine
    book.spine = chapters
    
    # Write EPUB to temporary file
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        temp_path = f.name
    
    try:
        # Write EPUB
        epub.write_epub(temp_path, book, {'epub3_pages': False})
        
        # Extract chapters using EPUBIngester
        extracted_chapters = EPUBIngester.extract_chapters(temp_path)
        
        # Verify all chapters were extracted
        assert len(extracted_chapters) == num_chapters, \
            f"Expected {num_chapters} chapters, got {len(extracted_chapters)}"
        
        # Verify each chapter preserves its title from TOC metadata
        for i, chapter in enumerate(extracted_chapters):
            expected_title = expected_titles[i]
            
            # The title should be preserved from the TOC in the RawChapter object
            assert chapter.title == expected_title, \
                f"Chapter {i} title mismatch: expected '{expected_title}', got '{chapter.title}'"
    
    finally:
        # Cleanup
        import time
        time.sleep(0.1)  # Brief delay for Windows file locking
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except PermissionError:
            pass  # File still locked, skip cleanup


@settings(max_examples=100, deadline=None)
@given(
    chapter_marker=st.sampled_from(["Episode", "Ep.", "standalone_numbers"]),
    num_chapters=st.integers(min_value=2, max_value=5),
    content_seed=st.integers(min_value=0, max_value=1000000)
)
def test_property_14_fuzzy_chapter_pattern_support(chapter_marker: str, num_chapters: int, content_seed: int):
    """
    Feature: epub-sanitization, Property 14: Fuzzy Chapter Pattern Support
    
    For any TXT file with chapters marked using "Episode", "Ep.", or standalone
    sequential numbers, the module should correctly identify chapter boundaries.
    
    Validates: Requirements 2.3
    """
    import tempfile
    import os
    from babel.sanitize import TXTIngester
    
    # Generate varied chapter content using the seed for variety
    content_pieces = [f"This is chapter {i+1} content with seed {content_seed}. " * 10 for i in range(num_chapters)]
    
    # Test Episode/Ep. markers
    if chapter_marker in ["Episode", "Ep."]:
        # Build text with fuzzy chapter markers
        text_parts = []
        for i in range(num_chapters):
            chapter_num = i + 1
            text_parts.append(f"{chapter_marker} {chapter_num}\n\n{content_pieces[i]}\n\n")
        
        full_text = "".join(text_parts)
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(full_text)
            temp_path = f.name
        
        try:
            # Extract chapters
            chapters = TXTIngester.extract_chapters(temp_path)
            
            # Verify correct number of chapters detected
            assert len(chapters) == num_chapters, f"Expected {num_chapters} chapters, got {len(chapters)}"
            
            # Verify chapter markers are in titles
            for i, chapter in enumerate(chapters):
                assert chapter_marker in chapter.title or str(i + 1) in chapter.title, \
                    f"Chapter {i} title '{chapter.title}' should contain marker '{chapter_marker}' or number '{i + 1}'"
        finally:
            os.unlink(temp_path)
    
    # Test standalone sequential numbers
    else:
        # Build text with standalone sequential numbers
        text_parts = []
        for i in range(num_chapters):
            chapter_num = i + 1
            text_parts.append(f"{chapter_num}\n\n{content_pieces[i]}\n\n")
        
        full_text = "".join(text_parts)
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write(full_text)
            temp_path = f.name
        
        try:
            # Extract chapters
            chapters = TXTIngester.extract_chapters(temp_path)
            
            # Verify correct number of chapters detected
            assert len(chapters) == num_chapters, f"Expected {num_chapters} chapters, got {len(chapters)}"
            
            # Verify chapters are in correct order
            for i, chapter in enumerate(chapters):
                assert chapter.index == i, f"Chapter at position {i} has incorrect index {chapter.index}"
        finally:
            os.unlink(temp_path)


@settings(max_examples=100, deadline=None)
@given(
    token_multiplier=st.floats(min_value=1.1, max_value=5.0)
)
def test_property_15_safety_limit_enforcement(token_multiplier: float):
    """
    Feature: epub-sanitization, Property 15: Safety Limit Enforcement
    
    For any chapter with estimated token count exceeding 50,000, the module
    should raise a SafetyLimitExceeded warning.
    
    Validates: Requirements 2.7
    """
    import warnings
    import tempfile
    import os
    from babel.sanitize import TXTIngester, SafetyLimitExceeded
    
    # Calculate content size that will exceed the limit
    # TOKEN_SAFETY_LIMIT = 50,000 tokens
    # CHARS_PER_TOKEN = 4
    # So we need > 200,000 characters to exceed the limit
    chars_needed = int(50000 * 4 * token_multiplier)
    
    # Create oversized chapter content
    oversized_content = "A" * chars_needed
    
    # Create a simple TXT file with one chapter
    full_text = f"Chapter 1\n\n{oversized_content}"
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        f.write(full_text)
        temp_path = f.name
    
    try:
        # Extract chapters and expect a warning
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            chapters = TXTIngester.extract_chapters(temp_path)
            
            # Verify that a SafetyLimitExceeded warning was raised
            assert len(w) >= 1, "Expected at least one warning to be raised"
            
            # Check that at least one warning is SafetyLimitExceeded
            safety_warnings = [warning for warning in w if issubclass(warning.category, SafetyLimitExceeded)]
            assert len(safety_warnings) >= 1, f"Expected SafetyLimitExceeded warning, got: {[warning.category for warning in w]}"
            
            # Verify the warning message contains relevant information
            warning_msg = str(safety_warnings[0].message)
            assert "exceeds safety limit" in warning_msg.lower(), f"Warning message should mention safety limit: {warning_msg}"
            assert "50000" in warning_msg or "50,000" in warning_msg, f"Warning message should mention the limit value: {warning_msg}"
            
            # Verify chapter was still extracted (warning, not error)
            assert len(chapters) == 1, "Chapter should still be extracted despite warning"
            
            # Verify the estimated token count is indeed over the limit
            estimated_tokens = len(chapters[0].content) // 4
            assert estimated_tokens > 50000, f"Estimated tokens {estimated_tokens} should exceed 50,000"
    finally:
        os.unlink(temp_path)


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    num_volumes=st.integers(min_value=2, max_value=3),
    chapters_per_volume=st.integers(min_value=2, max_value=3),
    content_seed=st.integers(min_value=0, max_value=1000000)
)
def test_property_17_volume_information_preservation(num_volumes: int, chapters_per_volume: int, content_seed: int):
    """
    Feature: epub-sanitization, Property 17: Volume Information Preservation
    
    For any EPUB with volume structure in its table of contents, the corresponding
    chapters should have volume information in the manifest.
    
    Validates: Requirements 4.9
    """
    import tempfile
    import os
    from babel.sanitize import EPUBIngester
    from ebooklib import epub
    
    # Create a test EPUB with volume structure in TOC
    book = epub.EpubBook()
    book.set_identifier(f'test_volumes_{content_seed}')
    book.set_title(f'Test Book with Volumes {content_seed}')
    book.set_language('en')
    
    # Track expected volume assignments
    expected_volumes = {}
    all_chapters = []
    toc_structure = []
    
    # Create volumes with chapters
    for vol_idx in range(num_volumes):
        volume_name = f"Volume {vol_idx + 1}"
        volume_chapters = []
        
        for ch_idx in range(chapters_per_volume):
            global_ch_idx = vol_idx * chapters_per_volume + ch_idx
            chapter_title = f"Chapter {global_ch_idx + 1}"
            file_name = f'chap_{global_ch_idx + 1:03d}.xhtml'
            
            # Create chapter
            chapter = epub.EpubHtml(
                title=chapter_title,
                file_name=file_name,
                lang='en'
            )
            chapter.content = f'<html><body><h1>{chapter_title}</h1><p>Content for {chapter_title} in {volume_name} (seed {content_seed}).</p></body></html>'
            
            all_chapters.append(chapter)
            book.add_item(chapter)
            
            # Track expected volume for this chapter
            expected_volumes[file_name] = volume_name
            
            # Create TOC link for this chapter
            volume_chapters.append(epub.Link(file_name, chapter_title, f'chap_{global_ch_idx + 1}'))
        
        # Create volume section in TOC with nested chapters
        volume_section = epub.Section(volume_name)
        toc_structure.append((volume_section, volume_chapters))
    
    # Set the table of contents with volume structure
    book.toc = toc_structure
    
    # Add required EPUB components
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    
    # Define spine (all chapters in order)
    book.spine = all_chapters
    
    # Write EPUB to temporary file
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        temp_path = f.name
    
    try:
        # Write EPUB
        epub.write_epub(temp_path, book, {'epub3_pages': False})
        
        # Extract chapters using EPUBIngester
        extracted_chapters = EPUBIngester.extract_chapters(temp_path)
        
        # Verify all chapters were extracted
        total_chapters = num_volumes * chapters_per_volume
        assert len(extracted_chapters) == total_chapters, \
            f"Expected {total_chapters} chapters, got {len(extracted_chapters)}"
        
        # Verify each chapter has correct volume information
        chapters_with_volumes = 0
        for chapter in extracted_chapters:
            # Get the filename from source_location
            # Format is: "path/to/file.epub:filename.xhtml"
            source_parts = chapter.source_location.split(':')
            if len(source_parts) >= 2:
                filename = source_parts[-1]
                
                # Check if this chapter should have volume info
                if filename in expected_volumes:
                    expected_volume = expected_volumes[filename]
                    
                    # Verify volume information is preserved
                    assert chapter.volume is not None, \
                        f"Chapter '{chapter.title}' (file: {filename}) should have volume information"
                    
                    assert chapter.volume == expected_volume, \
                        f"Chapter '{chapter.title}' should be in '{expected_volume}', got '{chapter.volume}'"
                    
                    chapters_with_volumes += 1
        
        # Verify that at least some chapters have volume information
        # (The implementation might not catch all chapters depending on TOC structure)
        assert chapters_with_volumes > 0, \
            "At least some chapters should have volume information preserved"
        
        # Ideally, all chapters should have volume info in this test structure
        assert chapters_with_volumes == total_chapters, \
            f"Expected all {total_chapters} chapters to have volume info, but only {chapters_with_volumes} do"
    
    finally:
        # Cleanup
        import time
        time.sleep(0.1)  # Brief delay for Windows file locking
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except PermissionError:
            pass  # File still locked, skip cleanup


@settings(max_examples=100)
@given(
    num_chapters=st.integers(min_value=1, max_value=5),
    depth=st.integers(min_value=1, max_value=3),
    content_seed=st.integers(min_value=0, max_value=1000000)
)
def test_property_11_output_directory_creation(num_chapters: int, depth: int, content_seed: int):
    """
    Feature: epub-sanitization, Property 11: Output Directory Creation
    
    For any output directory path that does not exist, the module should create it
    before writing files without raising errors.
    
    Validates: Requirements 5.4
    """
    import tempfile
    import os
    import shutil
    from pathlib import Path
    from babel.sanitize import FileWriter, CleanChapter
    
    # Create a temporary base directory
    with tempfile.TemporaryDirectory() as temp_base:
        # Generate a nested directory path that doesn't exist yet
        # Use depth to create nested directories
        nested_parts = [f"level_{i}_{content_seed}" for i in range(depth)]
        output_dir = Path(temp_base) / Path(*nested_parts) / "output"
        
        # Verify the directory does NOT exist yet
        assert not output_dir.exists(), f"Directory {output_dir} should not exist yet"
        
        # Create test chapters
        chapters = []
        for i in range(num_chapters):
            chapter = CleanChapter(
                index=i,
                title=f"Chapter {i + 1} (seed {content_seed})",
                content=f"This is the content for chapter {i + 1} with seed {content_seed}.\n" * 10,
                token_count_est=100 + i * 10,
                filename=FileWriter._generate_filename(i, f"Chapter {i + 1}"),
                volume=None,
                tags=[]
            )
            chapters.append(chapter)
        
        # Write chapters - this should create the directory automatically
        try:
            FileWriter.write_chapters(chapters, output_dir)
            
            # Verify the directory was created
            assert output_dir.exists(), f"Directory {output_dir} should have been created"
            assert output_dir.is_dir(), f"Path {output_dir} should be a directory"
            
            # Verify all chapter files were written
            for chapter in chapters:
                file_path = output_dir / chapter.filename
                assert file_path.exists(), f"File {file_path} should exist"
                assert file_path.is_file(), f"Path {file_path} should be a file"
                
                # Verify file content matches
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    assert content == chapter.content, \
                        f"File content should match chapter content for {chapter.filename}"
        
        except IOError as e:
            # If an IOError is raised, the test should fail
            raise AssertionError(f"FileWriter should not raise IOError when creating directories: {e}")
        
        # Directory cleanup is handled by TemporaryDirectory context manager


@settings(max_examples=100)
@given(
    text=st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=100, max_size=10000)
)
def test_property_9_token_estimation_bounds(text: str):
    """
    Feature: epub-sanitization, Property 9: Token Estimation Bounds
    
    For any text string, the estimated token count should be within 20% of the
    actual character count divided by 4.
    
    Validates: Requirements 4.6
    """
    from babel.sanitize import ManifestGenerator
    
    # Calculate expected token count (chars / 4)
    expected_tokens = len(text) / 4.0
    
    # Get estimated token count from ManifestGenerator
    estimated_tokens = ManifestGenerator._estimate_tokens(text)
    
    # Verify estimation is within 20% of expected
    # Since we use integer division, the estimate should be exactly floor(chars / 4)
    # So the "within 20%" is actually testing that our implementation matches the spec
    lower_bound = expected_tokens * 0.8
    upper_bound = expected_tokens * 1.2
    
    assert lower_bound <= estimated_tokens <= upper_bound, \
        f"Token estimation {estimated_tokens} is outside 20% bounds [{lower_bound}, {upper_bound}] for {len(text)} characters"
    
    # Additional verification: the estimate should be the floor of chars/4
    # This is the actual implementation, so it should always be exact
    assert estimated_tokens == len(text) // 4, \
        f"Token estimation should be exactly len(text) // 4, got {estimated_tokens}, expected {len(text) // 4}"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    num_chapters=st.integers(min_value=3, max_value=6),
    num_empty=st.integers(min_value=1, max_value=2),
    content_seed=st.integers(min_value=0, max_value=1000000)
)
def test_property_12_empty_chapter_exclusion(num_chapters: int, num_empty: int, content_seed: int):
    """
    Feature: epub-sanitization, Property 12: Empty Chapter Exclusion
    
    For any chapter that becomes empty after cleaning (zero non-whitespace characters),
    it should not appear in the output files or manifest chapters array.
    
    Validates: Requirements 3.7, 6.2
    """
    import tempfile
    import os
    from babel.sanitize import sanitize
    from ebooklib import epub
    
    # Ensure we don't try to make more chapters empty than we have
    if num_empty >= num_chapters:
        num_empty = num_chapters - 1
    
    # Create an EPUB with some chapters that will become empty after cleaning
    # EPUB allows us to create chapters with ONLY artifacts (no title in content)
    book = epub.EpubBook()
    book.set_identifier(f'test_empty_{content_seed}')
    book.set_title(f'Test Empty Chapters {content_seed}')
    book.set_language('en')
    
    chapters = []
    empty_indices = set(range(0, num_empty))  # First num_empty chapters will be empty
    
    for i in range(num_chapters):
        chapter_num = i + 1
        title = f'Chapter {chapter_num}'
        
        chapter = epub.EpubHtml(
            title=title,
            file_name=f'chap_{chapter_num:02d}.xhtml',
            lang='en'
        )
        
        if i in empty_indices:
            # Create HTML content that will be completely removed by cleaning
            # ONLY artifacts: URLs, translator notes, watermarks, whitespace
            chapter.content = f'''<html><body>
                <p>https://example.com/chapter</p>
                <p>https://anothersite.com/read</p>
                <p>Translator's Note: This chapter is just a note.</p>
                <p>TN: Another translator note here.</p>
                <p>Read at [NovelSite.com]</p>
                <p>Read more at [AnotherSite]</p>
                <p>   </p>
                <p>   </p>
            </body></html>'''
        else:
            # Create normal content
            chapter.content = f'''<html><body>
                <h1>{title}</h1>
                <p>This is the actual content for chapter {chapter_num} with seed {content_seed}.</p>
                <p>Some dialogue and action happens here. Some dialogue and action happens here.</p>
            </body></html>'''
        
        chapters.append(chapter)
        book.add_item(chapter)
    
    # Add required EPUB components
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = chapters
    
    # Write EPUB to temporary file
    with tempfile.NamedTemporaryFile(suffix='.epub', delete=False) as f:
        temp_input_path = f.name
    
    try:
        epub.write_epub(temp_input_path, book, {'epub3_pages': False})
        
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_output_dir:
            # Run sanitize
            manifest = sanitize(temp_input_path, temp_output_dir)
            
            # Verify that empty chapters are excluded from manifest
            expected_chapter_count = num_chapters - num_empty
            assert len(manifest.chapters) == expected_chapter_count, \
                f"Expected {expected_chapter_count} chapters in manifest (excluding {num_empty} empty), got {len(manifest.chapters)}"
            
            # Verify that only non-empty chapters have output files
            from pathlib import Path
            output_path = Path(temp_output_dir)
            output_files = list(output_path.glob("*.txt"))
            
            # Should have one file per non-empty chapter
            assert len(output_files) == expected_chapter_count, \
                f"Expected {expected_chapter_count} output files, got {len(output_files)}"
            
            # Verify each output file has non-empty content
            for output_file in output_files:
                with open(output_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    assert content.strip(), \
                        f"Output file {output_file.name} should not be empty"
            
            # Verify no chapter in manifest has zero or very low token count
            # (empty chapters would have 0 tokens)
            for chapter_entry in manifest.chapters:
                assert chapter_entry.token_count_est > 5, \
                    f"Chapter '{chapter_entry.title}' has suspiciously low token count: {chapter_entry.token_count_est}"
    
    finally:
        # Cleanup input file
        import time
        time.sleep(0.1)  # Brief delay for Windows file locking
        try:
            if os.path.exists(temp_input_path):
                os.unlink(temp_input_path)
        except PermissionError:
            pass  # File still locked, skip cleanup
