"""
Unit tests for GlossaryStore error handling.

Tests Fail-Hard and Fail-Soft behavior, descriptive error messages.
"""

import pytest
from pathlib import Path
from ruamel.yaml.error import YAMLError
from pydantic import ValidationError

from babel.context.store import GlossaryStore
from babel.context.models import Glossary, GlossaryEntry


class TestGlossaryStoreErrorHandling:
    """Test error handling in GlossaryStore."""
    
    def test_fail_soft_missing_glossary_file(self, tmp_path):
        """
        Test Fail-Soft for missing glossary file.
        
        When glossary.yaml does not exist, load() should return an empty
        glossary and log a warning (not raise an exception).
        
        Validates: Requirements 1.9, 7.2
        """
        # Create store with non-existent file
        glossary_path = tmp_path / "nonexistent.yaml"
        store = GlossaryStore(glossary_path)
        
        # Verify file doesn't exist
        assert not glossary_path.exists()
        
        # Load should return empty glossary (Fail-Soft)
        glossary = store.load()
        
        # Verify empty glossary
        assert isinstance(glossary, Glossary)
        assert glossary.total_entries() == 0
        assert len(glossary.characters) == 0
        assert len(glossary.factions) == 0
        assert len(glossary.locations) == 0
        assert len(glossary.terms) == 0
    
    def test_fail_hard_invalid_yaml_syntax(self, tmp_path):
        """
        Test Fail-Hard for invalid YAML syntax.
        
        When glossary.yaml has syntax errors, load() should raise a
        descriptive YAMLError.
        
        Validates: Requirements 1.8, 7.1
        """
        # Create file with invalid YAML syntax
        glossary_path = tmp_path / "invalid.yaml"
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write("characters:\n")
            f.write("  - name: Test\n")
            f.write("    raw: test\n")
            f.write("  - invalid yaml syntax here: [unclosed bracket\n")
        
        store = GlossaryStore(glossary_path)
        
        # Load should raise YAMLError (Fail-Hard)
        with pytest.raises(YAMLError) as exc_info:
            store.load()
        
        # Verify error message is descriptive
        error_msg = str(exc_info.value)
        assert len(error_msg) > 0  # Has some error message
    
    def test_fail_hard_schema_validation_error(self, tmp_path):
        """
        Test Fail-Hard for schema validation errors.
        
        When glossary.yaml has valid YAML but invalid schema, load() should
        raise a descriptive ValidationError.
        
        Validates: Requirements 1.8, 7.1
        """
        # Create file with valid YAML but one invalid and one valid entry
        glossary_path = tmp_path / "partial_invalid.yaml"
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write("characters:\n")
            f.write("  - name: Invalid Character\n")
            f.write("    # Missing 'raw' field (required)\n")
            f.write("    aliases: []\n")
            f.write("  - name: Valid Character\n")
            f.write("    raw: valid_raw\n")
            f.write("    aliases: []\n")
        
        store = GlossaryStore(glossary_path)
        
        # Load should succeed, skipping invalid entry (Fail-Soft per Requirement 7.8)
        glossary = store.load()
        
        # Verify only valid entry was loaded
        assert len(glossary.characters) == 1
        assert glossary.characters[0].name == "Valid Character"
    
    def test_descriptive_error_message_yaml_syntax(self, tmp_path):
        """
        Test that YAML syntax errors have descriptive messages.
        
        Error messages should help users identify and fix the problem.
        
        Validates: Requirements 7.1, 7.2
        """
        # Create file with specific YAML syntax error
        glossary_path = tmp_path / "syntax_error.yaml"
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write("characters:\n")
            f.write("  - name: 'Unclosed quote\n")  # Missing closing quote
        
        store = GlossaryStore(glossary_path)
        
        # Capture the error
        with pytest.raises(YAMLError) as exc_info:
            store.load()
        
        # Verify error is descriptive (not just "YAML error")
        error_msg = str(exc_info.value)
        assert len(error_msg) > 20  # Has substantial error message
    
    def test_descriptive_error_message_validation(self, tmp_path):
        """
        Test that entries with invalid field types are skipped with warnings.
        
        Per Requirement 7.8, invalid entries should be skipped, not raise errors.
        
        Validates: Requirements 7.1, 7.2, 7.8
        """
        # Create file with validation error (wrong type) and one valid entry
        glossary_path = tmp_path / "validation_error.yaml"
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write("characters:\n")
            f.write("  - name: Invalid\n")
            f.write("    raw: test\n")
            f.write("    aliases: not_a_list\n")  # Should be a list
            f.write("  - name: Valid\n")
            f.write("    raw: test\n")
            f.write("    aliases: []\n")
        
        store = GlossaryStore(glossary_path)
        
        # Load should succeed, skipping invalid entry
        glossary = store.load()
        
        # Verify only valid entry was loaded
        assert len(glossary.characters) == 1
        assert glossary.characters[0].name == "Valid"
    
    def test_empty_file_returns_empty_glossary(self, tmp_path):
        """
        Test that empty YAML file returns empty glossary.
        
        An empty file should be treated as an empty glossary, not an error.
        
        Validates: Requirements 1.9, 7.2
        """
        # Create empty file
        glossary_path = tmp_path / "empty.yaml"
        glossary_path.touch()
        
        store = GlossaryStore(glossary_path)
        
        # Load should return empty glossary (Fail-Soft)
        glossary = store.load()
        
        # Verify empty glossary
        assert isinstance(glossary, Glossary)
        assert glossary.total_entries() == 0
    
    def test_validate_method_missing_file(self, tmp_path):
        """
        Test validate() method with missing file.
        
        Should return error list with descriptive message.
        
        Validates: Requirements 1.8, 7.1
        """
        # Create store with non-existent file
        glossary_path = tmp_path / "nonexistent.yaml"
        store = GlossaryStore(glossary_path)
        
        # Validate should return errors
        errors = store.validate()
        
        # Verify error list
        assert len(errors) == 1
        assert "not found" in errors[0].lower()
        assert str(glossary_path) in errors[0]
    
    def test_validate_method_invalid_yaml(self, tmp_path):
        """
        Test validate() method with invalid YAML syntax.
        
        Should return error list with YAML syntax error details.
        
        Validates: Requirements 1.8, 7.1
        """
        # Create file with invalid YAML
        glossary_path = tmp_path / "invalid.yaml"
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write("characters: [unclosed\n")
        
        store = GlossaryStore(glossary_path)
        
        # Validate should return errors
        errors = store.validate()
        
        # Verify error list
        assert len(errors) > 0
        assert any("yaml" in err.lower() for err in errors)
    
    def test_validate_method_invalid_schema(self, tmp_path):
        """
        Test validate() method with invalid entries.
        
        validate() only checks YAML syntax, not individual entry schemas.
        Invalid entries are skipped during load() per Requirement 7.8.
        
        Validates: Requirements 1.8, 7.8
        """
        # Create file with valid YAML but invalid entry
        glossary_path = tmp_path / "invalid_entries.yaml"
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write("characters:\n")
            f.write("  - name: Test\n")
            f.write("    # Missing 'raw' field\n")
        
        store = GlossaryStore(glossary_path)
        
        # Validate should return empty list (no YAML syntax errors)
        # Invalid entries are handled during load(), not validate()
        errors = store.validate()
        
        # Verify no YAML syntax errors
        assert len(errors) == 0
    
    def test_validate_method_valid_file(self, tmp_path):
        """
        Test validate() method with valid file.
        
        Should return empty error list.
        
        Validates: Requirements 1.8
        """
        # Create valid glossary
        glossary_path = tmp_path / "valid.yaml"
        store = GlossaryStore(glossary_path)
        
        glossary = Glossary(
            characters=[
                GlossaryEntry(name="Test", raw="test", aliases=[], desc="A test character")
            ]
        )
        store.save(glossary)
        
        # Validate should return no errors
        errors = store.validate()
        
        # Verify no errors
        assert len(errors) == 0



class TestGlossaryStoreExport:
    """Test export functionality in GlossaryStore."""
    
    def test_export_to_json_with_sample_glossary(self, tmp_path):
        """
        Test JSON export with sample glossary.
        
        Validates: Requirements 5.7
        """
        # Create sample glossary
        glossary = Glossary(
            characters=[
                GlossaryEntry(
                    name="Chung Myung",
                    raw="청명|Chung Myung",
                    aliases=["The Divine Dragon", "Sahyung"],
                    desc="Protagonist. Former Divine Dragon, reincarnated."
                ),
                GlossaryEntry(
                    name="Baek Cheon",
                    raw="백천|Baek Cheon",
                    aliases=["Righteous Sword"],
                    desc="Senior disciple of Mount Hua Sect."
                )
            ],
            factions=[
                GlossaryEntry(
                    name="Mount Hua Sect",
                    raw="화산파|Mount Hua Sect",
                    aliases=["Plum Blossom Sect"],
                    desc="One of the Nine Great Sects."
                )
            ],
            locations=[
                GlossaryEntry(
                    name="Mount Hua",
                    raw="화산|Mount Hua",
                    aliases=["Hua Mountain"],
                    desc="Sacred mountain where Mount Hua Sect is located."
                )
            ],
            terms=[
                GlossaryEntry(
                    name="Qi",
                    raw="기|Qi",
                    aliases=["Internal Energy", "Ki"],
                    desc="Life force energy used in martial arts."
                )
            ]
        )
        
        # Create store and save glossary
        glossary_path = tmp_path / "test_glossary.yaml"
        store = GlossaryStore(glossary_path)
        store.save(glossary)
        
        # Export to JSON
        json_data = store.export_to_json()
        
        # Verify JSON structure
        assert isinstance(json_data, dict)
        assert "characters" in json_data
        assert "factions" in json_data
        assert "locations" in json_data
        assert "terms" in json_data
        
        # Verify characters
        assert len(json_data["characters"]) == 2
        assert json_data["characters"][0]["name"] == "Chung Myung"
        assert json_data["characters"][0]["raw"] == "청명|Chung Myung"
        assert "The Divine Dragon" in json_data["characters"][0]["aliases"]
        assert json_data["characters"][0]["desc"] == "Protagonist. Former Divine Dragon, reincarnated."
        
        # Verify factions
        assert len(json_data["factions"]) == 1
        assert json_data["factions"][0]["name"] == "Mount Hua Sect"
        
        # Verify locations
        assert len(json_data["locations"]) == 1
        assert json_data["locations"][0]["name"] == "Mount Hua"
        
        # Verify terms
        assert len(json_data["terms"]) == 1
        assert json_data["terms"][0]["name"] == "Qi"
    
    def test_round_trip_yaml_to_json_to_yaml(self, tmp_path):
        """
        Test round-trip YAML → JSON → YAML.
        
        Validates: Requirements 5.7
        """
        # Create sample glossary
        original_glossary = Glossary(
            characters=[
                GlossaryEntry(
                    name="Test Character",
                    raw="テスト|Test",
                    aliases=["TC", "Test"],
                    desc="A test character for round-trip testing."
                )
            ],
            factions=[
                GlossaryEntry(
                    name="Test Faction",
                    raw="テスト派|Test Faction",
                    aliases=["TF"],
                    desc="A test faction."
                )
            ],
            locations=[],
            terms=[]
        )
        
        # Save to YAML
        glossary_path = tmp_path / "test_glossary.yaml"
        store = GlossaryStore(glossary_path)
        store.save(original_glossary)
        
        # Export to JSON
        json_data = store.export_to_json()
        
        # Create new glossary from JSON data
        reconstructed_glossary = Glossary(**json_data)
        
        # Save reconstructed glossary to new YAML file
        new_glossary_path = tmp_path / "reconstructed_glossary.yaml"
        new_store = GlossaryStore(new_glossary_path)
        new_store.save(reconstructed_glossary)
        
        # Load the reconstructed glossary
        final_glossary = new_store.load()
        
        # Verify data is identical
        assert final_glossary == original_glossary
        assert final_glossary.total_entries() == original_glossary.total_entries()
        
        # Verify each category
        assert final_glossary.characters == original_glossary.characters
        assert final_glossary.factions == original_glossary.factions
        assert final_glossary.locations == original_glossary.locations
        assert final_glossary.terms == original_glossary.terms
    
    def test_export_empty_glossary(self, tmp_path):
        """
        Test JSON export with empty glossary.
        
        Validates: Requirements 5.7
        """
        # Create empty glossary
        empty_glossary = Glossary()
        
        # Create store and save glossary
        glossary_path = tmp_path / "empty_glossary.yaml"
        store = GlossaryStore(glossary_path)
        store.save(empty_glossary)
        
        # Export to JSON
        json_data = store.export_to_json()
        
        # Verify JSON structure
        assert isinstance(json_data, dict)
        assert "characters" in json_data
        assert "factions" in json_data
        assert "locations" in json_data
        assert "terms" in json_data
        
        # Verify all categories are empty
        assert len(json_data["characters"]) == 0
        assert len(json_data["factions"]) == 0
        assert len(json_data["locations"]) == 0
        assert len(json_data["terms"]) == 0
    
    def test_export_with_optional_fields(self, tmp_path):
        """
        Test JSON export with entries that have optional fields (aliases, desc).
        
        Validates: Requirements 5.7
        """
        # Create glossary with entries having different optional fields
        glossary = Glossary(
            characters=[
                # Entry with all fields
                GlossaryEntry(
                    name="Full Entry",
                    raw="完全|Full",
                    aliases=["Complete", "Full"],
                    desc="Entry with all fields."
                ),
                # Entry with no aliases
                GlossaryEntry(
                    name="No Aliases",
                    raw="別名なし|No Aliases",
                    aliases=[],
                    desc="Entry without aliases."
                ),
                # Entry with no description
                GlossaryEntry(
                    name="No Description",
                    raw="説明なし|No Description",
                    aliases=["ND"],
                    desc=None
                ),
                # Entry with only required fields
                GlossaryEntry(
                    name="Minimal Entry",
                    raw="最小|Minimal",
                    aliases=[],
                    desc=None
                )
            ]
        )
        
        # Create store and save glossary
        glossary_path = tmp_path / "test_glossary.yaml"
        store = GlossaryStore(glossary_path)
        store.save(glossary)
        
        # Export to JSON
        json_data = store.export_to_json()
        
        # Verify all entries are present
        assert len(json_data["characters"]) == 4
        
        # Verify full entry
        full_entry = json_data["characters"][0]
        assert full_entry["name"] == "Full Entry"
        assert full_entry["aliases"] == ["Complete", "Full"]
        assert full_entry["desc"] == "Entry with all fields."
        
        # Verify entry with no aliases
        no_aliases = json_data["characters"][1]
        assert no_aliases["name"] == "No Aliases"
        assert no_aliases["aliases"] == []
        assert no_aliases["desc"] == "Entry without aliases."
        
        # Verify entry with no description
        no_desc = json_data["characters"][2]
        assert no_desc["name"] == "No Description"
        assert no_desc["aliases"] == ["ND"]
        assert no_desc["desc"] is None
        
        # Verify minimal entry
        minimal = json_data["characters"][3]
        assert minimal["name"] == "Minimal Entry"
        assert minimal["aliases"] == []
        assert minimal["desc"] is None



class TestInvalidEntryHandling:
    """Test handling of invalid entries during load."""
    
    def test_skip_entries_missing_required_fields(self, tmp_path):
        """
        Test that entries missing required fields are skipped with warnings.
        
        Validates: Requirements 7.7, 7.8
        """
        import logging
        
        # Create YAML with entries missing required fields
        glossary_path = tmp_path / "test_glossary.yaml"
        yaml_content = """
characters:
  - name: "Valid Character"
    raw: "valid_raw"
    aliases: []
    desc: null
  
  - name: "Missing Raw Field"
    aliases: ["Alias"]
    desc: "Missing required 'raw' field"
  
  - raw: "missing_name_field"
    aliases: []
    desc: "Missing required 'name' field"

factions:
  - name: "Valid Faction"
    raw: "faction_raw"
    aliases: []
    desc: null
"""
        
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # Set up logging capture
        log_messages = []
        
        class ListHandler(logging.Handler):
            def emit(self, record):
                log_messages.append(record)
        
        handler = ListHandler()
        handler.setLevel(logging.WARNING)
        store_logger = logging.getLogger('babel.context.store')
        store_logger.addHandler(handler)
        
        try:
            # Load glossary
            store = GlossaryStore(glossary_path)
            glossary = store.load()
            
            # Verify only valid entries were loaded
            assert len(glossary.characters) == 1
            assert glossary.characters[0].name == "Valid Character"
            assert len(glossary.factions) == 1
            assert glossary.factions[0].name == "Valid Faction"
            
            # Verify warnings were logged
            warning_messages = [
                record.getMessage() for record in log_messages
                if record.levelno == logging.WARNING
            ]
            
            assert len(warning_messages) >= 2, (
                f"Expected at least 2 warnings, got {len(warning_messages)}"
            )
            
            # Verify warning messages mention "Skipping invalid"
            assert any("Skipping invalid" in msg for msg in warning_messages)
            
        finally:
            store_logger.removeHandler(handler)
    
    def test_skip_entries_with_invalid_field_types(self, tmp_path):
        """
        Test that entries with invalid field types are skipped with warnings.
        
        Validates: Requirements 7.7, 7.8
        """
        import logging
        
        # Create YAML with entries having invalid field types
        glossary_path = tmp_path / "test_glossary.yaml"
        yaml_content = """
characters:
  - name: "Valid Character"
    raw: "valid_raw"
    aliases: []
    desc: null
  
  - name: 123
    raw: "numeric_name"
    aliases: []
    desc: null
  
  - name: "Invalid Aliases"
    raw: "test_raw"
    aliases: "should_be_list"
    desc: null

locations:
  - name: "Valid Location"
    raw: "location_raw"
    aliases: []
    desc: null
"""
        
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # Set up logging capture
        log_messages = []
        
        class ListHandler(logging.Handler):
            def emit(self, record):
                log_messages.append(record)
        
        handler = ListHandler()
        handler.setLevel(logging.WARNING)
        store_logger = logging.getLogger('babel.context.store')
        store_logger.addHandler(handler)
        
        try:
            # Load glossary
            store = GlossaryStore(glossary_path)
            glossary = store.load()
            
            # Verify only valid entries were loaded
            assert len(glossary.characters) == 1
            assert glossary.characters[0].name == "Valid Character"
            assert len(glossary.locations) == 1
            assert glossary.locations[0].name == "Valid Location"
            
            # Verify warnings were logged
            warning_messages = [
                record.getMessage() for record in log_messages
                if record.levelno == logging.WARNING
            ]
            
            assert len(warning_messages) >= 2, (
                f"Expected at least 2 warnings, got {len(warning_messages)}"
            )
            
        finally:
            store_logger.removeHandler(handler)
    
    def test_warnings_are_logged_for_invalid_entries(self, tmp_path):
        """
        Test that warnings are logged for each invalid entry.
        
        Validates: Requirements 7.8
        """
        import logging
        
        # Create YAML with multiple invalid entries
        glossary_path = tmp_path / "test_glossary.yaml"
        yaml_content = """
characters:
  - name: "Valid"
    raw: "valid"
    aliases: []
    desc: null
  
  - name: "Invalid 1"
    aliases: []
  
  - raw: "invalid_2"
    aliases: []

factions:
  - name: "Valid Faction"
    raw: "faction"
    aliases: []
  
  - name: "Invalid Faction"
    aliases: []

locations:
  - name: "Valid Location"
    raw: "location"
    aliases: []

terms:
  - name: "Valid Term"
    raw: "term"
    aliases: []
  
  - name: "Invalid Term"
    desc: "Missing raw field"
"""
        
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # Set up logging capture
        log_messages = []
        
        class ListHandler(logging.Handler):
            def emit(self, record):
                log_messages.append(record)
        
        handler = ListHandler()
        handler.setLevel(logging.WARNING)
        store_logger = logging.getLogger('babel.context.store')
        store_logger.addHandler(handler)
        
        try:
            # Load glossary
            store = GlossaryStore(glossary_path)
            glossary = store.load()
            
            # Verify valid entries were loaded
            assert len(glossary.characters) == 1
            assert len(glossary.factions) == 1
            assert len(glossary.locations) == 1
            assert len(glossary.terms) == 1
            
            # Verify warnings were logged for each invalid entry
            warning_messages = [
                record.getMessage() for record in log_messages
                if record.levelno == logging.WARNING
            ]
            
            # Should have 4 warnings (one for each invalid entry)
            assert len(warning_messages) >= 4, (
                f"Expected at least 4 warnings, got {len(warning_messages)}"
            )
            
            # Verify each warning mentions the category
            categories_mentioned = []
            for msg in warning_messages:
                if "character" in msg.lower():
                    categories_mentioned.append("character")
                elif "faction" in msg.lower():
                    categories_mentioned.append("faction")
                elif "term" in msg.lower():
                    categories_mentioned.append("term")
            
            assert len(categories_mentioned) >= 3, (
                "Warnings should mention the category of invalid entries"
            )
            
        finally:
            store_logger.removeHandler(handler)
    
    def test_valid_entries_still_loaded_despite_invalid_ones(self, tmp_path):
        """
        Test that valid entries are loaded even when some entries are invalid.
        
        Validates: Requirements 7.8
        """
        # Create YAML with mix of valid and invalid entries
        glossary_path = tmp_path / "test_glossary.yaml"
        yaml_content = """
characters:
  - name: "Character 1"
    raw: "char1"
    aliases: ["C1"]
    desc: "First character"
  
  - name: "Invalid Character"
    aliases: []
  
  - name: "Character 2"
    raw: "char2"
    aliases: []
    desc: null

factions:
  - name: "Faction 1"
    raw: "faction1"
    aliases: []
    desc: "First faction"
  
  - raw: "invalid_faction"
    aliases: []
  
  - name: "Faction 2"
    raw: "faction2"
    aliases: ["F2"]
    desc: null
"""
        
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write(yaml_content)
        
        # Load glossary
        store = GlossaryStore(glossary_path)
        glossary = store.load()
        
        # Verify valid entries were loaded
        assert len(glossary.characters) == 2
        assert glossary.characters[0].name == "Character 1"
        assert glossary.characters[0].raw == "char1"
        assert glossary.characters[0].aliases == ["C1"]
        assert glossary.characters[0].desc == "First character"
        
        assert glossary.characters[1].name == "Character 2"
        assert glossary.characters[1].raw == "char2"
        
        assert len(glossary.factions) == 2
        assert glossary.factions[0].name == "Faction 1"
        assert glossary.factions[1].name == "Faction 2"
        assert glossary.factions[1].aliases == ["F2"]
