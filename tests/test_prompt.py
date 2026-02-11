"""
Unit tests for prompt construction module.

These tests verify specific prompt content requirements and token estimation.
"""

import pytest
from babel.transform.prompt import PromptConstructor
from babel.transform.models import ChapterData


class TestPromptConstructor:
    """Tests for PromptConstructor class."""
    
    def test_system_prompt_contains_expert_screenwriter(self):
        """
        Verify system prompt contains "Expert Screenwriter" phrase.
        
        Validates: Requirements 8.1
        """
        assert "Expert Screenwriter" in PromptConstructor.SYSTEM_PROMPT, \
            "System prompt should identify model as 'Expert Screenwriter'"
    
    def test_system_prompt_contains_dialogue_instructions(self):
        """
        Verify prompt includes instructions for dialogue block type.
        
        Validates: Requirements 8.2, 8.3
        """
        prompt = PromptConstructor.SYSTEM_PROMPT
        
        # Check for dialogue section
        assert "DIALOGUE" in prompt, "Prompt should include DIALOGUE instructions"
        assert "spoken words" in prompt.lower(), "Prompt should mention spoken words"
        assert "speaker" in prompt.lower(), "Prompt should mention speaker attribution"
    
    def test_system_prompt_contains_action_instructions(self):
        """
        Verify prompt includes instructions for action block type.
        
        Validates: Requirements 8.2
        """
        prompt = PromptConstructor.SYSTEM_PROMPT
        
        # Check for action section
        assert "ACTION" in prompt, "Prompt should include ACTION instructions"
        assert "prose descriptions" in prompt.lower() or "describe" in prompt.lower(), \
            "Prompt should mention converting prose descriptions"
    
    def test_system_prompt_contains_monologue_instructions(self):
        """
        Verify prompt includes instructions for monologue block type.
        
        Validates: Requirements 8.2, 8.4
        """
        prompt = PromptConstructor.SYSTEM_PROMPT
        
        # Check for monologue section
        assert "MONOLOGUE" in prompt, "Prompt should include MONOLOGUE instructions"
        assert "internal thoughts" in prompt.lower() or "inner voice" in prompt.lower(), \
            "Prompt should mention internal thoughts"
    
    def test_system_prompt_contains_sfx_instructions(self):
        """
        Verify prompt includes instructions for sfx block type.
        
        Validates: Requirements 8.2, 8.5
        """
        prompt = PromptConstructor.SYSTEM_PROMPT
        
        # Check for sfx section
        assert "SFX" in prompt, "Prompt should include SFX instructions"
        assert "sound effects" in prompt.lower() or "onomatopoeia" in prompt.lower(), \
            "Prompt should mention sound effects"
    
    def test_system_prompt_contains_system_notification_instructions(self):
        """
        Verify prompt includes instructions for system_notification block type.
        
        Validates: Requirements 8.2
        """
        prompt = PromptConstructor.SYSTEM_PROMPT
        
        # Check for system notification section
        assert "SYSTEM_NOTIFICATION" in prompt, "Prompt should include SYSTEM_NOTIFICATION instructions"
        assert "level up" in prompt.lower() or "quest" in prompt.lower() or "skill" in prompt.lower(), \
            "Prompt should mention game-like notifications"
    
    def test_system_prompt_contains_do_not_summarize_instruction(self):
        """
        Verify prompt includes "Do NOT summarize" instruction.
        
        Validates: Requirements 8.6
        """
        prompt = PromptConstructor.SYSTEM_PROMPT
        
        # Check for explicit no-summarization rule
        assert "Do NOT summarize" in prompt or "do not summarize" in prompt.lower(), \
            "Prompt should explicitly instruct not to summarize"
        assert "skip" in prompt.lower(), \
            "Prompt should instruct not to skip content"
    
    def test_system_prompt_contains_all_block_types(self):
        """
        Verify prompt includes instructions for all 5 block types.
        
        Validates: Requirements 8.2, 8.3, 8.4, 8.5
        """
        prompt = PromptConstructor.SYSTEM_PROMPT
        
        # All block types should be mentioned
        block_types = ["dialogue", "action", "monologue", "sfx", "system_notification"]
        for block_type in block_types:
            assert block_type in prompt.lower(), \
                f"Prompt should include instructions for '{block_type}' block type"
    
    def test_construct_prompt_includes_system_prompt(self):
        """
        Verify constructed prompt includes system instructions.
        
        Validates: Requirements 8.1, 8.7
        """
        chapter_text = "Sample chapter text."
        prompt = PromptConstructor.construct_prompt(chapter_text)
        
        # Should include system prompt
        assert PromptConstructor.SYSTEM_PROMPT in prompt, \
            "Constructed prompt should include system instructions"
    
    def test_construct_prompt_includes_chapter_text(self):
        """
        Verify constructed prompt includes the chapter text.
        
        Validates: Requirements 8.7
        """
        chapter_text = "This is a unique chapter text that should appear in the prompt."
        prompt = PromptConstructor.construct_prompt(chapter_text)
        
        # Should include chapter text
        assert chapter_text in prompt, \
            "Constructed prompt should include the chapter text"
    
    def test_construct_prompt_includes_json_schema(self):
        """
        Verify constructed prompt includes JSON schema for format guidance.
        
        Validates: Requirements 8.8
        """
        chapter_text = "Sample chapter text."
        prompt = PromptConstructor.construct_prompt(chapter_text)
        
        # Should include schema reference
        assert "schema" in prompt.lower(), \
            "Constructed prompt should reference JSON schema"
        
        # Should include ChapterData schema elements
        schema = ChapterData.model_json_schema()
        # Check for key schema elements
        assert "blocks" in prompt, "Prompt should include 'blocks' from schema"
    
    def test_get_token_estimate_empty_string(self):
        """
        Test token estimation for empty string.
        
        Validates: Requirements 7.1
        """
        text = ""
        estimated = PromptConstructor.get_token_estimate(text)
        
        assert estimated == 0, "Empty string should have 0 tokens"
    
    def test_get_token_estimate_short_text(self):
        """
        Test token estimation for short text.
        
        Validates: Requirements 7.1
        """
        text = "Hello"  # 5 characters
        estimated = PromptConstructor.get_token_estimate(text)
        
        # 5 // 4 = 1
        assert estimated == 1, f"Expected 1 token for 5 chars, got {estimated}"
    
    def test_get_token_estimate_exact_multiple(self):
        """
        Test token estimation for text with length exactly divisible by 4.
        
        Validates: Requirements 7.1
        """
        text = "1234" * 10  # 40 characters
        estimated = PromptConstructor.get_token_estimate(text)
        
        # 40 // 4 = 10
        assert estimated == 10, f"Expected 10 tokens for 40 chars, got {estimated}"
    
    def test_get_token_estimate_long_text(self):
        """
        Test token estimation for longer text.
        
        Validates: Requirements 7.1
        """
        text = "This is a longer piece of text " * 100  # ~3200 characters
        estimated = PromptConstructor.get_token_estimate(text)
        expected = len(text) // 4
        
        assert estimated == expected, \
            f"Expected {expected} tokens for {len(text)} chars, got {estimated}"
    
    def test_get_token_estimate_formula_consistency(self):
        """
        Test that token estimation uses consistent formula.
        
        Validates: Requirements 7.1
        """
        test_cases = [
            ("", 0),
            ("abc", 0),      # 3 // 4 = 0
            ("abcd", 1),     # 4 // 4 = 1
            ("abcde", 1),    # 5 // 4 = 1
            ("abcdefgh", 2), # 8 // 4 = 2
        ]
        
        for text, expected in test_cases:
            estimated = PromptConstructor.get_token_estimate(text)
            assert estimated == expected, \
                f"For text '{text}' (len={len(text)}), expected {expected} tokens, got {estimated}"
