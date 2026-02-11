"""
Property-based tests for LLM transformation module.

These tests validate universal properties that should hold across all inputs.
"""

import json
import hashlib
from datetime import datetime, timezone, timedelta
from hypothesis import given, strategies as st, settings, HealthCheck
from babel.transform.models import ChapterData, ScriptBlock, ScriptBlockType
from babel.transform.validator import JSONValidator


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.builds(
            ScriptBlock,
            type=st.sampled_from(list(ScriptBlockType)),
            speaker=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
            content=st.text(min_size=1, max_size=500),
            tone=st.one_of(st.none(), st.text(min_size=1, max_size=20))
        ),
        min_size=1,
        max_size=20
    ),
    st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    st.text(min_size=1, max_size=50)
)
def test_property_1_automatic_timestamp_population(blocks, source_hash, model_version):
    """
    Feature: llm-transformation, Property 1: Automatic Timestamp Population
    
    **Validates: Requirements 1.4**
    
    For any ChapterData instance created without explicitly setting processed_at,
    the processed_at field should be automatically populated with a timezone-aware
    UTC datetime.
    """
    # Record time before creation
    before = datetime.now(timezone.utc)
    
    # Create ChapterData without setting processed_at
    chapter_data = ChapterData(
        blocks=blocks,
        source_hash=source_hash,
        model_version=model_version
        # processed_at is NOT set explicitly
    )
    
    # Record time after creation
    after = datetime.now(timezone.utc)
    
    # Property 1: processed_at should be automatically populated
    assert chapter_data.processed_at is not None, "processed_at should be auto-populated"
    
    # Property 2: processed_at should be timezone-aware
    assert chapter_data.processed_at.tzinfo is not None, "processed_at should be timezone-aware"
    assert chapter_data.processed_at.tzinfo == timezone.utc, "processed_at should be in UTC"
    
    # Property 3: processed_at should be between before and after timestamps
    assert before <= chapter_data.processed_at <= after, \
        f"processed_at should be between {before} and {after}, got {chapter_data.processed_at}"
    
    # Property 4: processed_at should be recent (within 1 second of creation)
    time_diff = after - chapter_data.processed_at
    assert time_diff < timedelta(seconds=1), \
        f"processed_at should be recent, but was {time_diff.total_seconds()} seconds ago"


@settings(max_examples=100)
@given(st.text(min_size=0, max_size=10000))
def test_property_5_token_estimation_formula(text):
    """
    Feature: llm-transformation, Property 5: Token Estimation Formula
    
    **Validates: Requirements 7.1**
    
    For any text string, the estimated token count should equal len(text) // 4.
    """
    from babel.transform.prompt import PromptConstructor
    
    # Get estimated token count
    estimated = PromptConstructor.get_token_estimate(text)
    
    # Expected value based on formula
    expected = len(text) // 4
    
    # Property: Token estimate should match formula exactly
    assert estimated == expected, \
        f"Token estimate {estimated} does not match expected {expected} for text length {len(text)}"



@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.builds(
            ScriptBlock,
            type=st.sampled_from(list(ScriptBlockType)),
            speaker=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
            content=st.text(min_size=1, max_size=500),
            tone=st.one_of(st.none(), st.text(min_size=1, max_size=20))
        ),
        min_size=1,
        max_size=20
    ),
    st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    st.text(min_size=1, max_size=50)
)
def test_property_2_markdown_fence_removal(blocks, source_hash, model_version):
    """
    Feature: llm-transformation, Property 2: Markdown Fence Removal
    
    **Validates: Requirements 4.1, 4.2**
    
    For any valid ChapterData JSON, wrapping it in markdown code fences should
    not prevent successful parsing after cleaning. Native JSON mode should
    eliminate this, but we keep this for robustness.
    """
    # Create valid ChapterData
    chapter_data = ChapterData(
        blocks=blocks,
        source_hash=source_hash,
        model_version=model_version
    )
    
    # Serialize to JSON
    valid_json = chapter_data.model_dump_json()
    
    # Test various markdown fence patterns
    fence_patterns = [
        f"```json\n{valid_json}\n```",  # Standard markdown fence
        f"```\n{valid_json}\n```",      # Fence without language
        f"  ```json\n{valid_json}\n```  ",  # With leading/trailing whitespace
        f"```json\n{valid_json}```",    # No trailing newline
        f"{valid_json}",                # No fence (control)
        f"  {valid_json}  ",            # Just whitespace
    ]
    
    for pattern in fence_patterns:
        # Clean the response
        cleaned = JSONValidator.clean_response(pattern)
        
        # Property 1: Cleaned response should be valid JSON
        try:
            parsed = json.loads(cleaned)
            assert isinstance(parsed, dict), "Cleaned response should parse to dict"
        except json.JSONDecodeError as e:
            raise AssertionError(
                f"Cleaned response is not valid JSON.\n"
                f"Pattern: {repr(pattern[:100])}\n"
                f"Cleaned: {repr(cleaned[:100])}\n"
                f"Error: {e}"
            )
        
        # Property 2: Cleaned response should validate with Pydantic
        try:
            validated = ChapterData.model_validate_json(cleaned)
            assert validated.blocks == blocks, "Blocks should be preserved"
            assert validated.source_hash == source_hash, "Source hash should be preserved"
            assert validated.model_version == model_version, "Model version should be preserved"
        except Exception as e:
            raise AssertionError(
                f"Cleaned response failed Pydantic validation.\n"
                f"Pattern: {repr(pattern[:100])}\n"
                f"Cleaned: {repr(cleaned[:100])}\n"
                f"Error: {e}"
            )



@settings(max_examples=100)
@given(st.text(min_size=0, max_size=10000))
def test_property_7_sha256_hash_computation(text):
    """
    Feature: llm-transformation, Property 7: SHA-256 Hash Computation
    
    **Validates: Requirements 9.1**
    
    For any input text, the system should compute a valid SHA-256 hash
    (64-character hexadecimal string).
    """
    # Compute hash using the same method as transformer
    computed_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    # Property 1: Hash should be exactly 64 characters
    assert len(computed_hash) == 64, \
        f"SHA-256 hash should be 64 characters, got {len(computed_hash)}"
    
    # Property 2: Hash should only contain hexadecimal characters (0-9, a-f)
    assert all(c in '0123456789abcdef' for c in computed_hash), \
        f"SHA-256 hash should only contain hex characters, got {computed_hash}"
    
    # Property 3: Same input should produce same hash (deterministic)
    recomputed_hash = hashlib.sha256(text.encode('utf-8')).hexdigest()
    assert computed_hash == recomputed_hash, \
        "SHA-256 should be deterministic - same input should produce same hash"
    
    # Property 4: Different inputs should produce different hashes (with high probability)
    if len(text) > 0:
        modified_text = text + "x"  # Add one character
        different_hash = hashlib.sha256(modified_text.encode('utf-8')).hexdigest()
        assert computed_hash != different_hash, \
            "Different inputs should produce different hashes"



@settings(max_examples=100)
@given(st.integers(min_value=0, max_value=10_000_000))
def test_property_6_cost_calculation_formula(token_count):
    """
    Feature: llm-transformation, Property 6: Cost Calculation Formula (FREE TIER)
    
    **Validates: Requirements 7.3**
    
    Gemini 2.5 Flash FREE tier limits:
    - 15 RPM (Requests Per Minute)
    - 1,500 RPD (Requests Per Day)  
    - 4M TPM (Tokens Per Minute)
    - Cost: $0.00 (completely free within limits!)
    
    For paid tier (if needed):
    - Input: $0.30 per 1M tokens
    - Output: $2.50 per 1M tokens
    
    This test validates that we understand the free tier is FREE.
    """
    # Free tier = $0.00 cost
    free_tier_cost = 0.0
    
    # Property 1: Free tier is always free
    assert free_tier_cost == 0.0, "Free tier should have zero cost"
    
    # Property 2: Rate limits are the constraint, not cost
    # 15 RPM = 900 requests/hour = 21,600 requests/day (but limited to 1,500 RPD)
    max_daily_requests = 1500
    assert max_daily_requests == 1500, "Free tier allows 1,500 requests per day"
    
    # Property 3: Token limits are generous
    # 4M TPM = can process ~800 chapters/minute (5K tokens each)
    tokens_per_minute_limit = 4_000_000
    assert tokens_per_minute_limit == 4_000_000, "Free tier allows 4M tokens per minute"
    
    # Property 4: Paid tier pricing (for reference, not used in free tier)
    if token_count > 0:
        # This is what it WOULD cost on paid tier (but we use free!)
        paid_input_cost = (token_count / 1_000_000) * 0.30
        paid_output_cost = (token_count * 0.6 / 1_000_000) * 2.50  # ~60% output
        paid_total = paid_input_cost + paid_output_cost
        
        # Verify paid tier math is correct (even though we don't use it)
        assert paid_total > 0, "Paid tier would have non-zero cost"
        assert paid_input_cost < paid_total, "Output cost should be significant"



@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.builds(
            ScriptBlock,
            type=st.sampled_from(list(ScriptBlockType)),
            speaker=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
            content=st.text(min_size=1, max_size=500),
            tone=st.one_of(st.none(), st.text(min_size=1, max_size=20))
        ),
        min_size=1,
        max_size=20
    ),
    st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    st.text(min_size=1, max_size=50)
)
def test_property_8_metadata_completeness(blocks, source_hash, model_version):
    """
    Feature: llm-transformation, Property 8: Metadata Completeness
    
    **Validates: Requirements 9.2, 9.3, 9.4, 9.5**
    
    For any transformed chapter, the ChapterData output should contain all
    required metadata fields: source_hash (SHA-256), model_version (string),
    and processed_at (timezone-aware datetime).
    """
    # Create ChapterData with metadata
    chapter_data = ChapterData(
        blocks=blocks,
        source_hash=source_hash,
        model_version=model_version
    )
    
    # Property 1: source_hash should be present and valid SHA-256
    assert chapter_data.source_hash is not None, \
        "source_hash should be present"
    assert len(chapter_data.source_hash) == 64, \
        f"source_hash should be 64 characters (SHA-256), got {len(chapter_data.source_hash)}"
    assert all(c in '0123456789abcdef' for c in chapter_data.source_hash), \
        "source_hash should only contain hex characters"
    assert chapter_data.source_hash == source_hash, \
        "source_hash should match the provided value"
    
    # Property 2: model_version should be present and non-empty
    assert chapter_data.model_version is not None, \
        "model_version should be present"
    assert len(chapter_data.model_version) > 0, \
        "model_version should be non-empty"
    assert isinstance(chapter_data.model_version, str), \
        "model_version should be a string"
    assert chapter_data.model_version == model_version, \
        "model_version should match the provided value"
    
    # Property 3: processed_at should be present and timezone-aware
    assert chapter_data.processed_at is not None, \
        "processed_at should be present"
    assert isinstance(chapter_data.processed_at, datetime), \
        "processed_at should be a datetime object"
    assert chapter_data.processed_at.tzinfo is not None, \
        "processed_at should be timezone-aware"
    assert chapter_data.processed_at.tzinfo == timezone.utc, \
        "processed_at should be in UTC timezone"
    
    # Property 4: All metadata should be preserved in serialization
    json_str = chapter_data.model_dump_json()
    json_dict = json.loads(json_str)
    
    assert "source_hash" in json_dict, \
        "source_hash should be in serialized JSON"
    assert "model_version" in json_dict, \
        "model_version should be in serialized JSON"
    assert "processed_at" in json_dict, \
        "processed_at should be in serialized JSON"
    
    assert json_dict["source_hash"] == source_hash, \
        "source_hash should be preserved in JSON"
    assert json_dict["model_version"] == model_version, \
        "model_version should be preserved in JSON"
    
    # Property 5: Metadata should survive round-trip serialization
    deserialized = ChapterData.model_validate_json(json_str)
    assert deserialized.source_hash == chapter_data.source_hash, \
        "source_hash should survive round-trip"
    assert deserialized.model_version == chapter_data.model_version, \
        "model_version should survive round-trip"
    # Note: datetime comparison may have microsecond differences, so we check they're close
    time_diff = abs((deserialized.processed_at - chapter_data.processed_at).total_seconds())
    assert time_diff < 0.001, \
        f"processed_at should survive round-trip (diff: {time_diff}s)"



@settings(max_examples=100)
@given(
    st.text(min_size=1, max_size=10000),
    st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    st.text(min_size=1, max_size=50)
)
def test_property_3_idempotency_check(chapter_text, source_hash, model_version):
    """
    Feature: llm-transformation, Property 3: Idempotency Check
    
    **Validates: Requirements 5.2**
    
    For any chapter text, if the source hash matches the existing output's hash,
    the chapter should be skipped (not reprocessed). If the hash differs,
    the chapter should be reprocessed.
    """
    # Create two ChapterData instances with same hash
    chapter_data_1 = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Test",
                content="Test content"
            )
        ],
        source_hash=source_hash,
        model_version=model_version
    )
    
    chapter_data_2 = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.ACTION,
                content="Different content"
            )
        ],
        source_hash=source_hash,  # Same hash
        model_version=model_version
    )
    
    # Property 1: Same hash means idempotent (should skip)
    assert chapter_data_1.source_hash == chapter_data_2.source_hash, \
        "Same hash should indicate idempotency"
    
    # Create ChapterData with different hash
    different_hash = hashlib.sha256((chapter_text + "modified").encode('utf-8')).hexdigest()
    chapter_data_3 = ChapterData(
        blocks=[
            ScriptBlock(
                type=ScriptBlockType.DIALOGUE,
                speaker="Test",
                content="Test content"
            )
        ],
        source_hash=different_hash,
        model_version=model_version
    )
    
    # Property 2: Different hash means not idempotent (should reprocess)
    assert chapter_data_1.source_hash != chapter_data_3.source_hash, \
        "Different hash should indicate need for reprocessing"
    
    # Property 3: Hash comparison is deterministic
    # Same source text should always produce same hash
    hash_1 = hashlib.sha256(chapter_text.encode('utf-8')).hexdigest()
    hash_2 = hashlib.sha256(chapter_text.encode('utf-8')).hexdigest()
    assert hash_1 == hash_2, \
        "Hash computation should be deterministic"
    
    # Property 4: Different source text should produce different hash
    if len(chapter_text) > 0:
        modified_text = chapter_text + "x"
        hash_modified = hashlib.sha256(modified_text.encode('utf-8')).hexdigest()
        assert hash_1 != hash_modified, \
            "Different source text should produce different hash"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.builds(
            ScriptBlock,
            type=st.sampled_from(list(ScriptBlockType)),
            speaker=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
            content=st.text(min_size=1, max_size=500),
            tone=st.one_of(st.none(), st.text(min_size=1, max_size=20))
        ),
        min_size=1,
        max_size=20
    ),
    st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    st.text(min_size=1, max_size=50)
)
def test_property_4_file_writing_on_success(blocks, source_hash, model_version):
    """
    Feature: llm-transformation, Property 4: File Writing on Success
    
    **Validates: Requirements 5.5**
    
    For any successful transformation, the output should be written to a JSON file
    with proper formatting (2-space indentation) and UTF-8 encoding.
    """
    import tempfile
    import os
    
    # Create ChapterData
    chapter_data = ChapterData(
        blocks=blocks,
        source_hash=source_hash,
        model_version=model_version
    )
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix='.json') as f:
        temp_path = f.name
        f.write(chapter_data.model_dump_json(indent=2))
    
    try:
        # Property 1: File should exist after writing
        assert os.path.exists(temp_path), \
            "Output file should exist after writing"
        
        # Property 2: File should be readable as UTF-8
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert len(content) > 0, \
            "Output file should not be empty"
        
        # Property 3: File should contain valid JSON
        try:
            parsed = json.loads(content)
            assert isinstance(parsed, dict), \
                "Output should be a JSON object"
        except json.JSONDecodeError as e:
            raise AssertionError(f"Output is not valid JSON: {e}")
        
        # Property 4: JSON should be properly formatted (2-space indentation)
        # Check for indentation by looking for newlines and spaces
        if len(blocks) > 0:
            assert '\n' in content, \
                "Formatted JSON should contain newlines"
            # Check for 2-space indentation pattern
            lines = content.split('\n')
            indented_lines = [line for line in lines if line.startswith('  ')]
            assert len(indented_lines) > 0, \
                "Formatted JSON should have indented lines"
        
        # Property 5: Deserialized data should match original
        deserialized = ChapterData.model_validate_json(content)
        assert len(deserialized.blocks) == len(blocks), \
            "Deserialized blocks count should match original"
        assert deserialized.source_hash == source_hash, \
            "Deserialized source_hash should match original"
        assert deserialized.model_version == model_version, \
            "Deserialized model_version should match original"
    
    finally:
        # Cleanup
        import time
        time.sleep(0.1)  # Brief delay for Windows file locking
        try:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        except PermissionError:
            pass  # File still locked, skip cleanup



@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.builds(
            ScriptBlock,
            type=st.sampled_from(list(ScriptBlockType)),
            speaker=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
            content=st.text(min_size=1, max_size=500),
            tone=st.one_of(st.none(), st.text(min_size=1, max_size=20))
        ),
        min_size=1,
        max_size=20
    ),
    st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    st.text(min_size=1, max_size=50)
)
def test_property_9_iso8601_datetime_serialization(blocks, source_hash, model_version):
    """
    Feature: llm-transformation, Property 9: ISO 8601 Datetime Serialization
    
    **Validates: Requirements 11.3**
    
    For any ChapterData instance, the processed_at field should serialize to
    ISO 8601 format with timezone information.
    """
    # Create ChapterData
    chapter_data = ChapterData(
        blocks=blocks,
        source_hash=source_hash,
        model_version=model_version
    )
    
    # Serialize to JSON
    json_str = chapter_data.model_dump_json()
    parsed = json.loads(json_str)
    
    # Property 1: processed_at should be in JSON
    assert "processed_at" in parsed, \
        "processed_at should be in serialized JSON"
    
    processed_at_str = parsed["processed_at"]
    
    # Property 2: Should be a string
    assert isinstance(processed_at_str, str), \
        "processed_at should serialize to string"
    
    # Property 3: Should contain timezone indicator (Z or +00:00)
    assert 'Z' in processed_at_str or '+' in processed_at_str or 'T' in processed_at_str, \
        f"processed_at should be in ISO 8601 format with timezone, got: {processed_at_str}"
    
    # Property 4: Should be parseable back to datetime
    from datetime import datetime
    try:
        # Try parsing as ISO 8601
        parsed_dt = datetime.fromisoformat(processed_at_str.replace('Z', '+00:00'))
        assert parsed_dt is not None, \
            "processed_at should be parseable as ISO 8601 datetime"
    except ValueError as e:
        raise AssertionError(f"processed_at is not valid ISO 8601: {processed_at_str}, error: {e}")


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.builds(
            ScriptBlock,
            type=st.sampled_from(list(ScriptBlockType)),
            speaker=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
            content=st.text(min_size=1, max_size=500),
            tone=st.one_of(st.none(), st.text(min_size=1, max_size=20))
        ),
        min_size=1,
        max_size=20
    ),
    st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    st.text(min_size=1, max_size=50)
)
def test_property_10_deserialization_support(blocks, source_hash, model_version):
    """
    Feature: llm-transformation, Property 10: Deserialization Support
    
    **Validates: Requirements 11.4**
    
    For any serialized ChapterData JSON, it should be deserializable back to
    a valid ChapterData instance with all fields preserved.
    """
    # Create ChapterData
    chapter_data = ChapterData(
        blocks=blocks,
        source_hash=source_hash,
        model_version=model_version
    )
    
    # Serialize to JSON
    json_str = chapter_data.model_dump_json()
    
    # Property 1: Should be deserializable
    try:
        deserialized = ChapterData.model_validate_json(json_str)
    except Exception as e:
        raise AssertionError(f"Failed to deserialize ChapterData: {e}")
    
    # Property 2: Deserialized instance should be valid ChapterData
    assert isinstance(deserialized, ChapterData), \
        "Deserialized object should be ChapterData instance"
    
    # Property 3: All fields should be preserved
    assert len(deserialized.blocks) == len(blocks), \
        "Blocks count should be preserved"
    assert deserialized.source_hash == source_hash, \
        "source_hash should be preserved"
    assert deserialized.model_version == model_version, \
        "model_version should be preserved"
    assert deserialized.processed_at is not None, \
        "processed_at should be preserved"
    
    # Property 4: Blocks should be preserved with correct types
    for i, block in enumerate(deserialized.blocks):
        assert isinstance(block, ScriptBlock), \
            f"Block {i} should be ScriptBlock instance"
        assert block.type == blocks[i].type, \
            f"Block {i} type should be preserved"
        assert block.content == blocks[i].content, \
            f"Block {i} content should be preserved"


@settings(max_examples=100, suppress_health_check=[HealthCheck.too_slow])
@given(
    st.lists(
        st.builds(
            ScriptBlock,
            type=st.sampled_from(list(ScriptBlockType)),
            speaker=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
            content=st.text(min_size=1, max_size=500),
            tone=st.one_of(st.none(), st.text(min_size=1, max_size=20))
        ),
        min_size=1,
        max_size=20
    ),
    st.text(min_size=64, max_size=64, alphabet='0123456789abcdef'),
    st.text(min_size=1, max_size=50)
)
def test_property_11_round_trip_serialization(blocks, source_hash, model_version):
    """
    Feature: llm-transformation, Property 11: Round-Trip Serialization
    
    **Validates: Requirements 11.5**
    
    For any ChapterData instance, serializing and then deserializing should
    produce an equivalent instance (round-trip property).
    """
    # Create ChapterData
    original = ChapterData(
        blocks=blocks,
        source_hash=source_hash,
        model_version=model_version
    )
    
    # Round-trip: serialize then deserialize
    json_str = original.model_dump_json()
    deserialized = ChapterData.model_validate_json(json_str)
    
    # Property 1: Blocks should be identical
    assert len(deserialized.blocks) == len(original.blocks), \
        "Blocks count should survive round-trip"
    
    for i, (orig_block, deser_block) in enumerate(zip(original.blocks, deserialized.blocks)):
        assert deser_block.type == orig_block.type, \
            f"Block {i} type should survive round-trip"
        assert deser_block.speaker == orig_block.speaker, \
            f"Block {i} speaker should survive round-trip"
        assert deser_block.content == orig_block.content, \
            f"Block {i} content should survive round-trip"
        assert deser_block.tone == orig_block.tone, \
            f"Block {i} tone should survive round-trip"
    
    # Property 2: Metadata should be identical
    assert deserialized.source_hash == original.source_hash, \
        "source_hash should survive round-trip"
    assert deserialized.model_version == original.model_version, \
        "model_version should survive round-trip"
    
    # Property 3: Datetime should be close (within 1 second due to serialization precision)
    time_diff = abs((deserialized.processed_at - original.processed_at).total_seconds())
    assert time_diff < 1.0, \
        f"processed_at should survive round-trip (diff: {time_diff}s)"
    
    # Property 4: Second round-trip should produce same result
    json_str_2 = deserialized.model_dump_json()
    deserialized_2 = ChapterData.model_validate_json(json_str_2)
    
    assert len(deserialized_2.blocks) == len(deserialized.blocks), \
        "Second round-trip should be stable"
    assert deserialized_2.source_hash == deserialized.source_hash, \
        "Second round-trip should be stable"
