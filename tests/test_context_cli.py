"""
Unit tests for CLI commands in babel/cli.py (Phase 4: Akashic Record).

Tests the init-glossary, show-glossary, validate-glossary, and build commands.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typer.testing import CliRunner
from babel.context.models import Glossary, GlossaryEntry

# Import CLI functions
from babel.cli import (
    init_glossary_command,
    show_glossary_command,
    validate_glossary_command,
    build_command
)


@pytest.fixture
def runner():
    """Create a CLI test runner."""
    return CliRunner()


@pytest.fixture
def sample_glossary():
    """Create a sample glossary for testing."""
    return Glossary(
        characters=[
            GlossaryEntry(
                name="Chung Myung",
                raw="청명",
                aliases=["The Divine Dragon", "Sahyung"],
                desc="Protagonist. Former Divine Dragon, reincarnated."
            )
        ],
        factions=[
            GlossaryEntry(
                name="Mount Hua Sect",
                raw="화산파",
                aliases=["Plum Blossom Sect"],
                desc="One of the Nine Great Sects."
            )
        ],
        locations=[
            GlossaryEntry(
                name="Mount Hua",
                raw="화산",
                aliases=["Hua Mountain"],
                desc="Sacred mountain where Mount Hua Sect is located."
            )
        ],
        terms=[
            GlossaryEntry(
                name="Qi",
                raw="기",
                aliases=["Internal Energy", "Ki"],
                desc="Life force energy used in martial arts."
            )
        ]
    )


@pytest.fixture
def temp_input_file(tmp_path):
    """Create a temporary input file for testing."""
    input_file = tmp_path / "test_novel.txt"
    input_file.write_text("Chapter 1\n\nTest content for chapter 1.\n\nChapter 2\n\nTest content for chapter 2.")
    return input_file


class TestInitGlossaryCommand:
    """Test suite for init-glossary command."""
    
    def test_init_glossary_with_valid_input(self, tmp_path, temp_input_file, sample_glossary, mocker):
        """Test init-glossary command with valid input file."""
        # Mock dependencies
        mock_ingester = mocker.patch('babel.cli.TXTIngester')
        mock_cartographer = mocker.patch('babel.cli.Cartographer')
        mock_store = mocker.patch('babel.cli.GlossaryStore')
        mock_gemini = mocker.patch('babel.cli.GeminiClient')
        
        # Setup mock chapter map
        from babel.sanitize import ChapterMap, ChapterEntry
        mock_chapter_map = ChapterMap(
            source_filename="test_novel.txt",
            chapters=[
                ChapterEntry(index=0, filename="Ch_001.txt", title="Chapter 1", token_count_est=1000),
                ChapterEntry(index=1, filename="Ch_002.txt", title="Chapter 2", token_count_est=1000)
            ]
        )
        mock_ingester.return_value.ingest.return_value = mock_chapter_map
        
        # Setup mock cartographer
        mock_cartographer.return_value.extract_glossary.return_value = sample_glossary
        
        # Setup mock store
        mock_store_instance = Mock()
        mock_store_instance.load.return_value = Glossary()
        mock_store.return_value = mock_store_instance
        
        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # Run command
            result = init_glossary_command(input_file=temp_input_file, num_chapters=2)
            
            # Verify result
            assert result == 0
            
            # Verify ingester was called
            mock_ingester.return_value.ingest.assert_called_once()
            
            # Verify cartographer was called
            mock_cartographer.return_value.extract_glossary.assert_called_once()
            
            # Verify store save was called
            mock_store_instance.save.assert_called_once()
        
        finally:
            os.chdir(original_cwd)
    
    def test_init_glossary_with_nonexistent_file(self, tmp_path):
        """Test init-glossary command with nonexistent input file."""
        nonexistent_file = tmp_path / "nonexistent.txt"
        
        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            result = init_glossary_command(input_file=nonexistent_file, num_chapters=3)
            assert result == 1  # Should fail
        finally:
            os.chdir(original_cwd)
    
    def test_init_glossary_with_unsupported_format(self, tmp_path):
        """Test init-glossary command with unsupported file format."""
        unsupported_file = tmp_path / "test.pdf"
        unsupported_file.write_text("dummy content")
        
        # Change to temp directory
        import os
        original_cwd = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            result = init_glossary_command(input_file=unsupported_file, num_chapters=3)
            assert result == 1  # Should fail
        finally:
            os.chdir(original_cwd)
    
    def test_init_glossary_merges_with_existing(self, tmp_path, temp_input_file, sample_glossary, mocker):
        """Test init-glossary command merges with existing glossary."""
        # Mock dependencies
        mock_ingester = mocker.patch('babel.cli.TXTIngester')
        mock_cartographer = mocker.patch('babel.cli.Cartographer')
        mock_store = mocker.patch('babel.cli.GlossaryStore')
        mock_gemini = mocker.patch('babel.cli.GeminiClient')
        
        # Setup mock chapter map
        from babel.sanitize import ChapterMap, ChapterEntry
        mock_chapter_map = ChapterMap(
            source_filename="test_novel.txt",
            chapters=[
                ChapterEntry(index=0, filename="Ch_001.txt", title="Chapter 1", token_count_est=1000)
            ]
        )
        mock_ingester.return_value.ingest.return_value = mock_chapter_map
        
        # Setup mock cartographer
        new_glossary = Glossary(
            characters=[
                GlossaryEntry(name="New Character", raw="新", aliases=[], desc="A new character")
            ]
        )
        mock_cartographer.return_value.extract_glossary.return_value = new_glossary
        
        # Setup mock store with existing glossary
        mock_store_instance = Mock()
        mock_store_instance.load.return_value = sample_glossary
        mock_store.return_value = mock_store_instance
        
        # Mock Path.exists to return True for glossary
        with patch('babel.cli.Path.exists', return_value=True):
            # Change to temp directory
            import os
            original_cwd = os.getcwd()
            os.chdir(tmp_path)
            
            try:
                result = init_glossary_command(input_file=temp_input_file, num_chapters=1)
                
                # Verify result
                assert result == 0
                
                # Verify store save was called (merge happened)
                # The actual merge logic is tested in test_context_store.py
                mock_store_instance.save.assert_called_once()
            
            finally:
                os.chdir(original_cwd)


class TestShowGlossaryCommand:
    """Test suite for show-glossary command."""
    
    def test_show_glossary_with_existing_glossary(self, tmp_path, sample_glossary, mocker):
        """Test show-glossary command with existing glossary."""
        # Mock store
        mock_store = mocker.patch('babel.cli.GlossaryStore')
        mock_store_instance = Mock()
        mock_store_instance.load.return_value = sample_glossary
        mock_store.return_value = mock_store_instance
        
        # Mock Path.exists to return True
        with patch('babel.cli.Path.exists', return_value=True):
            result = show_glossary_command()
            
            # Verify result
            assert result == 0
            
            # Verify store load was called
            mock_store_instance.load.assert_called_once()
    
    def test_show_glossary_with_missing_glossary(self, tmp_path):
        """Test show-glossary command with missing glossary."""
        # Mock Path.exists to return False
        with patch('babel.cli.Path.exists', return_value=False):
            result = show_glossary_command()
            
            # Verify result
            assert result == 1  # Should fail gracefully
    
    def test_show_glossary_with_empty_glossary(self, tmp_path, mocker):
        """Test show-glossary command with empty glossary."""
        # Mock store with empty glossary
        mock_store = mocker.patch('babel.cli.GlossaryStore')
        mock_store_instance = Mock()
        mock_store_instance.load.return_value = Glossary()
        mock_store.return_value = mock_store_instance
        
        # Mock Path.exists to return True
        with patch('babel.cli.Path.exists', return_value=True):
            result = show_glossary_command()
            
            # Verify result
            assert result == 0  # Should succeed but show empty


class TestValidateGlossaryCommand:
    """Test suite for validate-glossary command."""
    
    def test_validate_glossary_with_valid_glossary(self, tmp_path, sample_glossary, mocker):
        """Test validate-glossary command with valid glossary."""
        # Mock store
        mock_store = mocker.patch('babel.cli.GlossaryStore')
        mock_store_instance = Mock()
        mock_store_instance.validate.return_value = []  # No errors
        mock_store_instance.load.return_value = sample_glossary
        mock_store.return_value = mock_store_instance
        
        # Mock Path.exists to return True
        with patch('babel.cli.Path.exists', return_value=True):
            result = validate_glossary_command()
            
            # Verify result
            assert result == 0
            
            # Verify validate was called
            mock_store_instance.validate.assert_called_once()
    
    def test_validate_glossary_with_invalid_glossary(self, tmp_path, mocker):
        """Test validate-glossary command with invalid glossary."""
        # Mock store with validation errors
        mock_store = mocker.patch('babel.cli.GlossaryStore')
        mock_store_instance = Mock()
        mock_store_instance.validate.return_value = [
            "Line 5: Missing required field 'name'",
            "Line 10: Invalid field type for 'aliases'"
        ]
        mock_store.return_value = mock_store_instance
        
        # Mock Path.exists to return True
        with patch('babel.cli.Path.exists', return_value=True):
            result = validate_glossary_command()
            
            # Verify result
            assert result == 1  # Should fail
    
    def test_validate_glossary_with_missing_glossary(self, tmp_path):
        """Test validate-glossary command with missing glossary."""
        # Mock Path.exists to return False
        with patch('babel.cli.Path.exists', return_value=False):
            result = validate_glossary_command()
            
            # Verify result
            assert result == 1  # Should fail gracefully


class TestBuildCommandGlossaryPrompt:
    """Test suite for build command glossary prompt."""
    
    def test_build_prompts_for_missing_glossary(self, tmp_path, temp_input_file, mocker):
        """Test build command prompts user when glossary is missing."""
        # Mock Path.exists to return False for glossary
        with patch('babel.cli.Path.exists') as mock_exists:
            # First call (glossary check) returns False, subsequent calls return True
            mock_exists.side_effect = [False, True, True, True]
            
            # Mock typer.confirm to return False (user declines)
            with patch('typer.confirm', return_value=False):
                # Mock other dependencies to prevent actual execution
                from babel.pipeline.orchestrator import PipelineConfig
                mock_config_obj = PipelineConfig()
                mock_config_obj.cleanup_json = False  # Disable cleanup to avoid path issues
                
                mock_config = mocker.patch('babel.cli.load_config_from_yaml', return_value=mock_config_obj)
                mock_orchestrator = mocker.patch('babel.cli.PipelineOrchestrator')
                mock_state = mocker.patch('babel.cli.JobStateManager')
                mock_limiter = mocker.patch('babel.cli.RateLimiter')
                mock_changelog = mocker.patch('babel.cli.ChangelogUpdater')
                mock_issue = mocker.patch('babel.cli.IssueReporter')
                
                # Setup mock orchestrator result
                mock_result = Mock()
                mock_result.success = True
                mock_result.total_chapters = 10
                mock_result.successful_chapters = 10
                mock_result.failed_chapters = 0
                mock_result.execution_time = 30.0
                mock_orchestrator.return_value.execute.return_value = mock_result
                
                # Change to temp directory
                import os
                original_cwd = os.getcwd()
                os.chdir(tmp_path)
                
                try:
                    result = build_command(
                        input_file=temp_input_file,
                        retry_failed=False,
                        clean=False,
                        skip_omnibus=False,
                        cleanup=False,
                        keep_json=False,
                        config_path=None
                    )
                    
                    # Verify build proceeded without glossary
                    assert result == 0
                
                finally:
                    os.chdir(original_cwd)
    
    def test_build_generates_glossary_when_user_confirms(self, tmp_path, temp_input_file, sample_glossary, mocker):
        """Test build command generates glossary when user confirms."""
        # Mock Path.exists to return False for glossary initially
        with patch('babel.cli.Path.exists') as mock_exists:
            # First call (glossary check) returns False, subsequent calls return True
            mock_exists.side_effect = [False, True, True, True, True]
            
            # Mock typer.confirm to return True (user confirms)
            with patch('typer.confirm', return_value=True):
                # Mock init_glossary_command
                with patch('babel.cli.init_glossary_command', return_value=0) as mock_init:
                    # Mock other dependencies
                    from babel.pipeline.orchestrator import PipelineConfig
                    mock_config_obj = PipelineConfig()
                    mock_config_obj.cleanup_json = False  # Disable cleanup to avoid path issues
                    
                    mock_config = mocker.patch('babel.cli.load_config_from_yaml', return_value=mock_config_obj)
                    mock_orchestrator = mocker.patch('babel.cli.PipelineOrchestrator')
                    mock_state = mocker.patch('babel.cli.JobStateManager')
                    mock_limiter = mocker.patch('babel.cli.RateLimiter')
                    mock_changelog = mocker.patch('babel.cli.ChangelogUpdater')
                    mock_issue = mocker.patch('babel.cli.IssueReporter')
                    
                    # Setup mock orchestrator result
                    mock_result = Mock()
                    mock_result.success = True
                    mock_result.total_chapters = 10
                    mock_result.successful_chapters = 10
                    mock_result.failed_chapters = 0
                    mock_result.execution_time = 30.0
                    mock_orchestrator.return_value.execute.return_value = mock_result
                    
                    # Change to temp directory
                    import os
                    original_cwd = os.getcwd()
                    os.chdir(tmp_path)
                    
                    try:
                        result = build_command(
                            input_file=temp_input_file,
                            retry_failed=False,
                            clean=False,
                            skip_omnibus=False,
                            cleanup=False,
                            keep_json=False,
                            config_path=None
                        )
                        
                        # Verify init_glossary_command was called
                        mock_init.assert_called_once()
                        
                        # Verify build succeeded
                        assert result == 0
                    
                    finally:
                        os.chdir(original_cwd)
