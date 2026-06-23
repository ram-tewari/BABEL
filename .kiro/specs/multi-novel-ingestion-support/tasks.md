# Implementation Tasks: Multi-Novel Ingestion Support

## Phase 1: Database Schema and Core Infrastructure

### Task 1: Update Database Schema
- [x] 1.1 Add `novels` table with columns: id, title, author, cover_url, synopsis, tags, status, created_at, updated_at
- [x] 1.2 Add `novel_id` column to `chapters` table (nullable for backward compatibility)
- [x] 1.3 Add `novel_id` column to `pipeline_state` table (nullable for backward compatibility)
- [x] 1.4 Add foreign key constraint from `chapters.novel_id` to `novels.id` with CASCADE DELETE
- [x] 1.5 Add foreign key constraint from `pipeline_state.novel_id` to `novels.id` with CASCADE DELETE
- [x] 1.6 Add unique constraint on `pipeline_state(novel_id, phase)`
- [x] 1.7 Create database migration script
- [x] 1.8 Write unit tests for schema validation

### Task 2: Implement Database Manager Methods
- [x] 2.1 Implement `create_novel(title, author, status)` method
- [x] 2.2 Implement `get_novel(novel_id)` method
- [x] 2.3 Implement `list_novels(limit, offset)` method with SQL COUNT aggregation to avoid N+1 queries
- [x] 2.4 Implement `delete_novel(novel_id)` method
- [x] 2.5 Implement `count_novels()` method
- [x] 2.6 Implement `get_chapters_by_novel(novel_id)` method
- [x] 2.7 Implement `get_all_chapters()` method
- [x] 2.8 Implement `get_pipeline_states_by_novel(novel_id)` method
- [x] 2.9 Write unit tests for all database methods
- [x] 2.10 Write property-based test for Property 2: Novel Creation Returns ID
- [x] 2.11 Write property-based test for Property 4: Chapter Query Filtering
- [x] 2.12 Write property-based test for Property 5: Cascade Deletion Integrity

## Phase 2: Metadata Extraction

### Task 3: Implement EPUB Metadata Extraction
- [x] 3.1 Implement `extract_metadata_from_epub(file_path)` to read Dublin Core metadata from content.opf
- [x] 3.2 Parse dc:title from EPUB metadata
- [x] 3.3 Parse dc:creator from EPUB metadata
- [x] 3.4 Handle missing or malformed content.opf gracefully
- [x] 3.5 Write unit tests for EPUB metadata extraction with valid metadata
- [x] 3.6 Write unit tests for EPUB metadata extraction with missing metadata
- [x] 3.7 Write unit tests for EPUB metadata extraction with malformed XML

### Task 4: Implement Filename-Based Title Extraction
- [x] 4.1 Implement `extract_title_from_filename(filename)` function
- [x] 4.2 Handle " - Book " pattern extraction
- [x] 4.3 Replace underscores with spaces
- [x] 4.4 Handle hyphens surrounded by spaces
- [x] 4.5 Remove file extensions
- [x] 4.6 Implement fallback to full filename for empty results
- [x] 4.7 Write unit tests for various filename patterns
- [x] 4.8 Write unit tests for edge cases (empty, special characters)

### Task 5: Implement Combined Metadata Extraction Strategy
- [x] 5.1 Implement `extract_metadata(file_path, filename)` with fallback logic
- [x] 5.2 Prioritize EPUB internal metadata over filename parsing
- [x] 5.3 Fall back to filename extraction for non-EPUB files
- [x] 5.4 Fall back to filename extraction when EPUB metadata fails
- [x] 5.5 Write unit tests for combined extraction strategy
- [ ] 5.6 Write property-based test for Property 1: Metadata Extraction with Fallback

## Phase 3: Pipeline Orchestrator Modifications

### Task 6: Update PipelineOrchestrator Constructor
- [x] 6.1 Add `novel_id` parameter to `__init__` method
- [x] 6.2 Store `novel_id` as instance variable
- [x] 6.3 Implement `initialize_directories()` method to create novel-specific directories
- [x] 6.4 Write unit tests for constructor with novel_id
- [x] 6.5 Write unit tests for constructor without novel_id (backward compatibility)

### Task 7: Implement Novel-Specific Directory Management
- [x] 7.1 Implement `_get_phase_directory(phase)` method
- [x] 7.2 Return `data/{phase}/novel_{id}/` when novel_id is set
- [x] 7.3 Return `data/{phase}/` when novel_id is NULL (backward compatibility)
- [ ] 7.4 Update all phase processors to use `_get_phase_directory()`
- [x] 7.5 Write unit tests for directory path generation
- [ ] 7.6 Write property-based test for Property 6: Novel-Specific Directory Structure

### Task 8: Implement Novel-Specific Chapter Map Management
- [x] 8.1 Implement `_get_chapter_map_path()` method
- [x] 8.2 Return `config/chapter_map_novel_{id}.json` when novel_id is set
- [x] 8.3 Return `config/chapter_map.json` when novel_id is NULL
- [ ] 8.4 Update chapter map generation to include novel_id in metadata
- [ ] 8.5 Update chapter map loading to support both formats
- [x] 8.6 Write unit tests for chapter map path generation
- [ ] 8.7 Write property-based test for Property 7: Chapter Map Novel Association
- [ ] 8.8 Write property-based test for Property 18: Chapter Map Format Support

### Task 9: Update Pipeline State Tracking
- [x] 9.1 Update `_update_pipeline_state()` to include novel_id
- [x] 9.2 Ensure pipeline state updates are isolated per novel
- [x] 9.3 Write unit tests for pipeline state updates with novel_id
- [x] 9.4 Write property-based test for Property 8: Pipeline State Isolation

## Phase 4: Ingestion API Modifications

### Task 10: Update Ingestion Endpoint with Transaction Safety
- [x] 10.1 Update `/api/ingest` to call `extract_metadata()` instead of filename-only extraction
- [x] 10.2 Create novel entry with extracted title and author
- [x] 10.3 Wrap novel creation and directory initialization in try/except block
- [x] 10.4 Implement rollback: delete novel entry if directory creation fails
- [x] 10.5 Pass novel_id to PipelineOrchestrator constructor
- [x] 10.6 Call `orchestrator.initialize_directories()` before starting pipeline
- [x] 10.7 Update response to return novel_id (remove operation_id)
- [x] 10.8 Write unit tests for successful ingestion flow
- [x] 10.9 Write unit tests for rollback on directory creation failure
- [ ] 10.10 Write property-based test for Property 3: Novel_ID Preservation Throughout Pipeline

### Task 11: Update Background Pipeline Execution
- [x] 11.1 Update `run_ingestion_pipeline()` to accept novel_id parameter
- [x] 11.2 Remove operation_id parameter (use novel_id for tracking)
- [x] 11.3 Ensure all chapter database inserts include novel_id
- [ ] 11.4 Write integration tests for complete ingestion flow

## Phase 5: Novel Management API Endpoints

### Task 12: Implement GET /api/novels Endpoint
- [x] 12.1 Create `NovelListResponse` Pydantic model
- [x] 12.2 Implement endpoint handler with pagination support
- [x] 12.3 Use SQL COUNT aggregation with LEFT JOIN for chapter_count
- [x] 12.4 Sort results by updated_at descending
- [x] 12.5 Write unit tests for novel listing
- [x] 12.6 Write unit tests for pagination
- [x] 12.7 Write unit tests for empty novel list
- [ ] 12.8 Write property-based test for Property 9: Novel List Ordering
- [ ] 12.9 Write property-based test for Property 10: Novel Response Completeness
- [ ] 12.10 Write property-based test for Property 11: Pagination Correctness

### Task 13: Implement GET /api/novels/{novel_id} Endpoint
- [x] 13.1 Create `NovelDetailResponse` Pydantic model
- [x] 13.2 Implement endpoint handler
- [x] 13.3 Return 404 for invalid novel_id
- [x] 13.4 Include chapter_count in response
- [x] 13.5 Write unit tests for valid novel_id
- [x] 13.6 Write unit tests for invalid novel_id
- [ ] 13.7 Write property-based test for Property 12: Invalid Novel ID Error Handling

### Task 14: Implement GET /api/novels/{novel_id}/chapters Endpoint
- [x] 14.1 Create `ChapterListResponse` Pydantic model
- [x] 14.2 Implement endpoint handler
- [x] 14.3 Return chapters ordered by chapter_index ascending
- [x] 14.4 Return 404 for invalid novel_id
- [x] 14.5 Handle empty chapter list
- [x] 14.6 Write unit tests for valid novel_id
- [x] 14.7 Write unit tests for invalid novel_id
- [x] 14.8 Write unit tests for empty chapter list
- [ ] 14.9 Write property-based test for Property 13: Chapter List Ordering
- [ ] 14.10 Write property-based test for Property 14: Chapter Response Completeness

### Task 15: Implement GET /api/novels/{novel_id}/status Endpoint
- [x] 15.1 Create `NovelStatusResponse` Pydantic model
- [x] 15.2 Implement endpoint handler
- [x] 15.3 Query pipeline_state by novel_id
- [x] 15.4 Compute overall status from phase states
- [x] 15.5 Return 404 for invalid novel_id
- [x] 15.6 Write unit tests for status tracking
- [ ] 15.7 Write property-based test for Property 16: Operation Status Tracking

## Phase 6: Chapter Metadata API Updates

### Task 16: Update GET /api/chapters/metadata Endpoint
- [x] 16.1 Add optional `novel_id` query parameter
- [x] 16.2 Query database instead of scanning filesystem
- [x] 16.3 Filter by novel_id when parameter is provided
- [x] 16.4 Return all chapters (including NULL novel_id) when parameter is omitted
- [x] 16.5 Enrich chapter data with file paths based on novel_id
- [x] 16.6 Write unit tests for filtering by novel_id
- [x] 16.7 Write unit tests for unfiltered query
- [x] 16.8 Write unit tests for invalid novel_id
- [ ] 16.9 Write property-based test for Property 15: Metadata Endpoint Database Querying

## Phase 7: Backward Compatibility

### Task 17: Implement Backward Compatibility for Legacy Chapters
- [x] 17.1 Ensure NULL novel_id chapters are stored in root directories
- [x] 17.2 Ensure NULL novel_id chapters use `chapter_map.json`
- [x] 17.3 Ensure NULL novel_id chapters are included in unfiltered queries
- [x] 17.4 Write unit tests for NULL novel_id handling
- [ ] 17.5 Write property-based test for Property 17: Backward Compatibility for NULL Novel_ID

### Task 18: Test Legacy Data Migration
- [x] 18.1 Create test database with legacy chapters (NULL novel_id)
- [x] 18.2 Verify legacy chapters remain accessible after schema update
- [x] 18.3 Verify new novels work alongside legacy chapters
- [x] 18.4 Write integration tests for mixed legacy and new data

## Phase 8: Integration Testing

### Task 19: Write End-to-End Integration Tests
- [x] 19.1 Test complete ingestion flow: upload → novel creation → chapter extraction → file organization
- [x] 19.2 Test multi-novel workflow: upload two novels, verify separation
- [x] 19.3 Test backward compatibility: legacy chapters + new novel
- [x] 19.4 Test API workflow: list novels → get details → get chapters → filter metadata
- [x] 19.5 Test concurrent processing of multiple novels
- [x] 19.6 Test transaction rollback on failures

### Task 20: Performance Testing
- [x] 20.1 Test `/api/novels` performance with 1000+ novels (verify no N+1 queries)
- [x] 20.2 Test `/api/chapters/metadata` performance with 5000+ chapters (verify database query, not filesystem scan)
- [x] 20.3 Profile database queries and optimize if needed
- [x] 20.4 Test concurrent ingestion of multiple novels

## Phase 9: Documentation and Deployment

### Task 21: Update API Documentation
- [x] 21.1 Document new `/api/novels` endpoint
- [x] 21.2 Document new `/api/novels/{novel_id}` endpoint
- [x] 21.3 Document new `/api/novels/{novel_id}/chapters` endpoint
- [x] 21.4 Document new `/api/novels/{novel_id}/status` endpoint
- [x] 21.5 Document updated `/api/ingest` endpoint response format
- [x] 21.6 Document updated `/api/chapters/metadata` endpoint with novel_id parameter

### Task 22: Create Migration Guide
- [ ] 22.1 Document database migration steps
- [ ] 22.2 Document backward compatibility considerations
- [ ] 22.3 Document how to handle existing data
- [ ] 22.4 Create rollback plan

### Task 23: Final Validation
- [ ] 23.1 Run all unit tests
- [ ] 23.2 Run all property-based tests (minimum 100 iterations each)
- [ ] 23.3 Run all integration tests
- [ ] 23.4 Verify all 18 correctness properties pass
- [ ] 23.5 Perform manual testing of complete workflows
- [ ] 23.6 Review code for security issues
- [ ] 23.7 Review code for performance issues
