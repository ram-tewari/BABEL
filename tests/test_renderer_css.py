"""
Unit tests for CSS styling in rendered HTML.

Tests specific color values, font families, alignment, and spacing
for each block type to ensure visual consistency and mobile-first design.

Validates: Requirements 4.7, 5.2, 5.3, 6.1-6.5, 7.1-7.3, 8.1-8.6
"""

import pytest
from pathlib import Path
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from babel.render.renderer import ChapterRenderer
from babel.transform.models import ChapterData, ScriptBlock, ScriptBlockType


@pytest.fixture
def renderer():
    """Create a ChapterRenderer instance for testing."""
    return ChapterRenderer(template_dir=Path("templates"))


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary output directory."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


def create_chapter_json(tmp_path, blocks):
    """Helper to create a temporary JSON file with given blocks."""
    chapter_data = ChapterData(
        blocks=blocks,
        source_hash="a" * 64,
        model_version="gemini-2.5-flash",
        processed_at=datetime.now(timezone.utc)
    )
    json_path = tmp_path / "test_chapter.json"
    json_path.write_text(chapter_data.model_dump_json(), encoding='utf-8')
    return json_path


def parse_html(html_path):
    """Helper to parse HTML file with BeautifulSoup."""
    html_content = html_path.read_text(encoding='utf-8')
    return BeautifulSoup(html_content, 'html.parser')


class TestDialogueBlockStyling:
    """Tests for dialogue block CSS styling."""
    
    def test_dialogue_uses_sans_serif_font(self, renderer, tmp_path, temp_output_dir):
        """
        Test that dialogue blocks use sans-serif font family.
        
        Validates: Requirement 4.7
        """
        # Setup - create chapter with dialogue
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Hero",
                content="Hello, world!"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify - check template CSS for sans-serif
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        assert style_tag is not None
        css_content = style_tag.string
        
        # Body should use sans-serif font stack
        assert 'font-family:' in css_content or 'font-family :' in css_content
        assert 'sans-serif' in css_content
        
        # Dialogue blocks should inherit sans-serif (no serif override)
        dialogue_section = css_content[css_content.find('.dialogue'):] if '.dialogue' in css_content else css_content
        # Ensure dialogue doesn't override to serif or monospace
        assert 'Georgia' not in dialogue_section[:dialogue_section.find('.action')] if '.action' in dialogue_section else True
        assert 'Courier' not in dialogue_section[:dialogue_section.find('.system')] if '.system' in dialogue_section else True
    
    def test_dialogue_bubble_has_rounded_corners(self, renderer, tmp_path, temp_output_dir):
        """
        Test that dialogue bubbles have rounded corners (border-radius).
        
        Validates: Requirement 4.1
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Hero",
                content="Test message"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for border-radius on .bubble class
        assert '.bubble' in css_content
        bubble_section = css_content[css_content.find('.bubble'):]
        bubble_section = bubble_section[:bubble_section.find('}')]
        assert 'border-radius' in bubble_section
        # Should be 18px as per design
        assert '18px' in bubble_section

    def test_dialogue_bubble_has_border(self, renderer, tmp_path, temp_output_dir):
        """
        Test that dialogue bubbles have a 2px solid border.
        
        Validates: Requirement 4.5
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Hero",
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for border on .bubble class
        bubble_section = css_content[css_content.find('.bubble'):]
        bubble_section = bubble_section[:bubble_section.find('}')]
        assert 'border:' in bubble_section or 'border :' in bubble_section
        assert '2px' in bubble_section
        assert 'solid' in bubble_section
    
    def test_dialogue_left_alignment(self, renderer, tmp_path, temp_output_dir):
        """
        Test that left-lane dialogue is aligned to the left.
        
        Validates: Requirement 4.2
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Hero",
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for left alignment styling
        assert '.dialogue.left' in css_content
        left_section = css_content[css_content.find('.dialogue.left'):]
        left_section = left_section[:left_section.find('}')]
        assert 'align-self' in left_section or 'text-align' in left_section
        assert 'flex-start' in left_section or 'left' in left_section

    def test_dialogue_right_alignment(self, renderer, tmp_path, temp_output_dir):
        """
        Test that right-lane dialogue is aligned to the right.
        
        Validates: Requirement 4.3
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Villain",
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for right alignment styling
        assert '.dialogue.right' in css_content
        right_section = css_content[css_content.find('.dialogue.right'):]
        right_section = right_section[:right_section.find('}')]
        assert 'align-self' in right_section or 'text-align' in right_section
        assert 'flex-end' in right_section or 'right' in right_section
    
    def test_dialogue_max_width_constraint(self, renderer, tmp_path, temp_output_dir):
        """
        Test that dialogue bubbles have max-width constraint (70%).
        
        Validates: Requirement 4.1
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Hero",
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for max-width on .dialogue class
        dialogue_section = css_content[css_content.find('.dialogue'):]
        dialogue_section = dialogue_section[:dialogue_section.find('.dialogue.left')]
        assert 'max-width' in dialogue_section
        assert '70%' in dialogue_section


class TestThoughtBlockStyling:
    """Tests for thought block CSS styling.
    
    NOTE: ScriptBlockType enum is missing THOUGHT type (see ISSUE-2026-02-03-017).
    The template has thought block styling, but the enum doesn't include it.
    These tests verify the CSS exists in the template for when THOUGHT is added.
    """

    def test_thought_uses_grey_color(self, renderer, tmp_path, temp_output_dir):
        """
        Test that thought blocks use grey color (#888 or #888888).
        
        Validates: Requirement 5.2
        
        NOTE: Using MONOLOGUE as placeholder since THOUGHT type doesn't exist yet.
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.MONOLOGUE,
                speaker="Hero",
                content="Internal thought"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for grey color on .thought class
        assert '.thought' in css_content
        thought_section = css_content[css_content.find('.thought'):]
        thought_section = thought_section[:thought_section.find('.thought.left')]
        assert 'color' in thought_section
        assert '#888' in thought_section
    
    def test_thought_uses_italic_style(self, renderer, tmp_path, temp_output_dir):
        """
        Test that thought blocks use italic font style.
        
        Validates: Requirement 5.3
        
        NOTE: Verifying CSS exists in template for thought blocks.
        """
        # Setup - verify CSS exists in template
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for italic style on .thought class
        thought_section = css_content[css_content.find('.thought'):]
        thought_section = thought_section[:thought_section.find('.thought.left')]
        assert 'font-style' in thought_section
        assert 'italic' in thought_section

    def test_thought_uses_sans_serif_font(self, renderer, tmp_path, temp_output_dir):
        """
        Test that thought blocks use sans-serif font (inherited from body).
        
        Validates: Requirement 5.6
        
        NOTE: Verifying CSS exists in template for thought blocks.
        """
        # Setup - verify CSS exists in template
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Body should use sans-serif, thought should not override to serif/monospace
        assert 'sans-serif' in css_content
        thought_section = css_content[css_content.find('.thought'):]
        # Ensure thought doesn't override to serif or monospace
        thought_section = thought_section[:thought_section.find('.action')] if '.action' in thought_section else thought_section
        assert 'Georgia' not in thought_section
        assert 'Courier' not in thought_section
    
    def test_thought_max_width_constraint(self, renderer, tmp_path, temp_output_dir):
        """
        Test that thought blocks have max-width constraint (70%).
        
        Validates: Requirement 5.4
        
        NOTE: Verifying CSS exists in template for thought blocks.
        """
        # Setup - verify CSS exists in template
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for max-width on .thought class
        thought_section = css_content[css_content.find('.thought'):]
        thought_section = thought_section[:thought_section.find('.thought.left')]
        assert 'max-width' in thought_section
        assert '70%' in thought_section


class TestActionBlockStyling:
    """Tests for action block CSS styling."""

    def test_action_uses_serif_font(self, renderer, tmp_path, temp_output_dir):
        """
        Test that action blocks use serif font (Georgia).
        
        Validates: Requirement 6.1
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="The hero walked forward."
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for serif font on .action class
        assert '.action' in css_content
        action_section = css_content[css_content.find('.action'):]
        action_section = action_section[:action_section.find('}')]
        assert 'font-family' in action_section
        assert 'Georgia' in action_section
        assert 'serif' in action_section
    
    def test_action_uses_light_grey_color(self, renderer, tmp_path, temp_output_dir):
        """
        Test that action blocks use light grey color (#ccc or #cccccc).
        
        Validates: Requirement 6.2
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="The hero walked forward."
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for light grey color on .action class
        action_section = css_content[css_content.find('.action'):]
        action_section = action_section[:action_section.find('}')]
        assert 'color' in action_section
        assert '#ccc' in action_section

    def test_action_center_alignment(self, renderer, tmp_path, temp_output_dir):
        """
        Test that action blocks are center-aligned.
        
        Validates: Requirement 6.3
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="The hero walked forward."
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for center alignment on .action class
        action_section = css_content[css_content.find('.action'):]
        action_section = action_section[:action_section.find('}')]
        assert 'text-align' in action_section
        assert 'center' in action_section
    
    def test_action_vertical_spacing(self, renderer, tmp_path, temp_output_dir):
        """
        Test that action blocks have vertical spacing (padding).
        
        Validates: Requirement 6.5
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="The hero walked forward."
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for padding on .action class
        action_section = css_content[css_content.find('.action'):]
        action_section = action_section[:action_section.find('}')]
        assert 'padding' in action_section
        # Should have vertical padding (16px 0 as per template)
        assert '16px' in action_section


class TestMonologueBlockStyling:
    """Tests for monologue block CSS styling."""

    def test_monologue_center_alignment(self, renderer, tmp_path, temp_output_dir):
        """
        Test that monologue blocks are center-aligned.
        
        Validates: Requirement 7.1
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.MONOLOGUE,
                speaker="Villain",
                content="My grand plan..."
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for center alignment on .monologue class
        assert '.monologue' in css_content
        monologue_section = css_content[css_content.find('.monologue'):]
        monologue_section = monologue_section[:monologue_section.find('}')]
        assert 'text-align' in monologue_section
        assert 'center' in monologue_section
    
    def test_monologue_uses_grey_color(self, renderer, tmp_path, temp_output_dir):
        """
        Test that monologue blocks use grey color (#888 or #888888).
        
        Validates: Requirement 7.2
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.MONOLOGUE,
                speaker="Villain",
                content="My grand plan..."
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for grey color on .monologue class
        monologue_section = css_content[css_content.find('.monologue'):]
        monologue_section = monologue_section[:monologue_section.find('}')]
        assert 'color' in monologue_section
        assert '#888' in monologue_section

    def test_monologue_uses_italic_style(self, renderer, tmp_path, temp_output_dir):
        """
        Test that monologue blocks use italic font style.
        
        Validates: Requirement 7.3
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.MONOLOGUE,
                speaker="Villain",
                content="My grand plan..."
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for italic style on .monologue class
        monologue_section = css_content[css_content.find('.monologue'):]
        monologue_section = monologue_section[:monologue_section.find('}')]
        assert 'font-style' in monologue_section
        assert 'italic' in monologue_section
    
    def test_monologue_uses_sans_serif_font(self, renderer, tmp_path, temp_output_dir):
        """
        Test that monologue blocks use sans-serif font (inherited from body).
        
        Validates: Requirement 7.5
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.MONOLOGUE,
                speaker="Villain",
                content="My grand plan..."
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Body should use sans-serif, monologue should not override
        assert 'sans-serif' in css_content
        monologue_section = css_content[css_content.find('.monologue'):]
        monologue_section = monologue_section[:monologue_section.find('}')]
        # Ensure monologue doesn't override to serif or monospace
        assert 'Georgia' not in monologue_section
        assert 'Courier' not in monologue_section


class TestSystemNotificationStyling:
    """Tests for system notification block CSS styling."""

    def test_system_uses_monospace_font(self, renderer, tmp_path, temp_output_dir):
        """
        Test that system notification blocks use monospace font (Courier New).
        
        Validates: Requirement 8.1
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.SYSTEM_NOTIFICATION,
                content="[Level Up!]"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for monospace font on .system class
        assert '.system' in css_content
        system_section = css_content[css_content.find('.system'):]
        system_section = system_section[:system_section.find('}')]
        assert 'font-family' in system_section
        assert 'Courier' in system_section or 'monospace' in system_section
    
    def test_system_uses_green_color(self, renderer, tmp_path, temp_output_dir):
        """
        Test that system notification blocks use green color (#4ade80).
        
        Validates: Requirement 8.2
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.SYSTEM_NOTIFICATION,
                content="[Level Up!]"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for green color on .system class
        system_section = css_content[css_content.find('.system'):]
        system_section = system_section[:system_section.find('}')]
        assert 'color' in system_section
        assert '#4ade80' in system_section

    def test_system_uses_green_border(self, renderer, tmp_path, temp_output_dir):
        """
        Test that system notification blocks have green border (#4ade80).
        
        Validates: Requirement 8.3
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.SYSTEM_NOTIFICATION,
                content="[Level Up!]"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for green border on .system class
        system_section = css_content[css_content.find('.system'):]
        system_section = system_section[:system_section.find('}')]
        assert 'border' in system_section
        assert '#4ade80' in system_section
        assert '2px' in system_section
        assert 'solid' in system_section
    
    def test_system_uses_green_background(self, renderer, tmp_path, temp_output_dir):
        """
        Test that system notification blocks have green background (rgba(74, 222, 128, 0.1)).
        
        Validates: Requirement 8.4
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.SYSTEM_NOTIFICATION,
                content="[Level Up!]"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for green background on .system class
        system_section = css_content[css_content.find('.system'):]
        system_section = system_section[:system_section.find('}')]
        assert 'background' in system_section
        # Should contain rgba with green values (74, 222, 128) and 0.1 opacity
        assert 'rgba(74, 222, 128, 0.1)' in system_section or 'rgba(74,222,128,0.1)' in system_section

    def test_system_center_alignment(self, renderer, tmp_path, temp_output_dir):
        """
        Test that system notification blocks are center-aligned.
        
        Validates: Requirement 8.5
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.SYSTEM_NOTIFICATION,
                content="[Level Up!]"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for center alignment on .system class
        system_section = css_content[css_content.find('.system'):]
        system_section = system_section[:system_section.find('}')]
        assert 'text-align' in system_section
        assert 'center' in system_section
    
    def test_system_has_padding(self, renderer, tmp_path, temp_output_dir):
        """
        Test that system notification blocks have padding.
        
        Validates: Requirement 8.6
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.SYSTEM_NOTIFICATION,
                content="[Level Up!]"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for padding on .system class
        system_section = css_content[css_content.find('.system'):]
        system_section = system_section[:system_section.find('}')]
        assert 'padding' in system_section
        # Should have 16px padding as per template
        assert '16px' in system_section


class TestMobileFirstDesign:
    """Tests for mobile-first responsive design CSS."""

    def test_viewport_meta_tag_exists(self, renderer, tmp_path, temp_output_dir):
        """
        Test that viewport meta tag exists for mobile optimization.
        
        Validates: Requirement 9.1
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        viewport_meta = soup.find('meta', attrs={'name': 'viewport'})
        assert viewport_meta is not None
        assert 'width=device-width' in viewport_meta.get('content', '')
        assert 'initial-scale=1.0' in viewport_meta.get('content', '')
    
    def test_body_max_width_constraint(self, renderer, tmp_path, temp_output_dir):
        """
        Test that body has max-width constraint (800px).
        
        Validates: Requirement 9.2
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for max-width on body
        body_section = css_content[css_content.find('body'):]
        body_section = body_section[:body_section.find('}')]
        assert 'max-width' in body_section
        assert '800px' in body_section

    def test_dark_background_color(self, renderer, tmp_path, temp_output_dir):
        """
        Test that body has dark background color (#1a1a1a).
        
        Validates: Requirement 10.1
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for dark background on body
        body_section = css_content[css_content.find('body'):]
        body_section = body_section[:body_section.find('}')]
        assert 'background' in body_section
        assert '#1a1a1a' in body_section
    
    def test_light_text_color(self, renderer, tmp_path, temp_output_dir):
        """
        Test that body has light text color for dark mode readability.
        
        Validates: Requirement 10.2
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for light text color on body
        body_section = css_content[css_content.find('body'):]
        body_section = body_section[:body_section.find('}')]
        assert 'color' in body_section
        # Should be light grey (#e0e0e0 as per template)
        assert '#e0e0e0' in body_section or '#e0e0e0' in body_section.lower()


class TestFontFamilies:
    """Tests for font family specifications across block types."""

    def test_body_uses_system_font_stack(self, renderer, tmp_path, temp_output_dir):
        """
        Test that body uses system font stack (no external fonts).
        
        Validates: Requirement 11.4
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for system font stack on body
        body_section = css_content[css_content.find('body'):]
        body_section = body_section[:body_section.find('}')]
        assert 'font-family' in body_section
        # Should include system fonts like -apple-system, BlinkMacSystemFont, Segoe UI, Roboto
        assert '-apple-system' in body_section or 'system' in body_section.lower()
        assert 'sans-serif' in body_section
    
    def test_no_external_font_references(self, renderer, tmp_path, temp_output_dir):
        """
        Test that HTML contains no external font references.
        
        Validates: Requirement 11.4
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        html_content = output_path.read_text(encoding='utf-8')
        
        # Should not contain external font URLs
        assert 'fonts.googleapis.com' not in html_content
        assert 'fonts.gstatic.com' not in html_content
        assert '@font-face' not in html_content
        assert 'font.woff' not in html_content
        assert 'font.ttf' not in html_content


class TestAlignmentAndSpacing:
    """Tests for alignment and spacing CSS properties."""

    def test_block_vertical_margin(self, renderer, tmp_path, temp_output_dir):
        """
        Test that blocks have vertical margin spacing.
        
        Validates: Requirements 6.5, 7.1
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for margin on .block class
        assert '.block' in css_content
        block_section = css_content[css_content.find('.block'):]
        block_section = block_section[:block_section.find('}')]
        assert 'margin' in block_section
        # Should have 20px vertical margin as per template
        assert '20px' in block_section
    
    def test_dialogue_bubble_padding(self, renderer, tmp_path, temp_output_dir):
        """
        Test that dialogue bubbles have internal padding.
        
        Validates: Requirement 4.1
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Hero",
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for padding on .bubble class
        bubble_section = css_content[css_content.find('.bubble'):]
        bubble_section = bubble_section[:bubble_section.find('}')]
        assert 'padding' in bubble_section
        # Should have 12px 16px padding as per template
        assert '12px' in bubble_section
        assert '16px' in bubble_section
    
    def test_navigation_spacing(self, renderer, tmp_path, temp_output_dir):
        """
        Test that navigation has proper spacing from content.
        
        Validates: Requirement 12.7
        """
        # Setup
        blocks = [
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Test"
            )
        ]
        json_path = create_chapter_json(tmp_path, blocks)
        output_path = temp_output_dir / "test.html"
        
        # Execute
        renderer.render_chapter(json_path, output_path)
        
        # Verify
        soup = parse_html(output_path)
        style_tag = soup.find('style')
        css_content = style_tag.string
        
        # Check for margin-top on .navigation class
        assert '.navigation' in css_content
        nav_section = css_content[css_content.find('.navigation'):]
        nav_section = nav_section[:nav_section.find('}')]
        assert 'margin-top' in nav_section
        # Should have 40px top margin as per template
        assert '40px' in nav_section
