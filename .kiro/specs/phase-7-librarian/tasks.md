# Implementation Plan: Phase 7 - The Librarian

## Overview

This implementation plan transforms BABEL from a single-novel processor into a multi-novel library management system. The approach follows a bottom-up strategy: database layer first, then API layer, then frontend layer, with testing integrated throughout. Each task builds incrementally, ensuring the system remains functional at every step.

## Tasks

- [x] 1. Create Database Layer Foundation
  - Create `babel/data/db.py` with DatabaseManager class
  - Implement singleton pattern with thread-local connections
  - Implement transaction context manager
  - Create database schema with novels, chapters (extended), and pipeline_state (extended) tables
  - Create indexes for performance (idx_chapters_novel, idx_pipeline_novel, idx_novels_updated)
  - _Requirements: 1.1, 1.2, 1.4, 1.5, 1.6_

- [x] 1.1 Write property test for cascade deletion
  - **Property 1: Cascade Deletion Integrity**
  - **Validates: Requirements 1.3, 3.7**

- [ ] 2. Implement Database CRUD Operations
  - [x] 2.1 Implement novel operations (create_novel, get_novel, list_novels, update_novel, delete_novel)
    - _Requirements: 1.1, 1.3_
  
  - [x] 2.2 Implement chapter operations (get_chapters_by_novel, update_chapter_novel)
    - _Requirements: 1.2, 1.3_
  
  - [x] 2.3 Implement pipeline state operations (update_pipeline_state, get_pipeline_state)
    - _Requirements: 1.6_
  
  - [x] 2.4 Write unit tests for database operations
    - Test schema creation, CRUD operations, transaction handling
    - Test NULL novel_id support for backward compatibility
    - _Requirements: 1.1, 1.2, 1.5, 1.6_

- [x] 3. Create Data Models
  - Create `babel/data/models.py` with Pydantic models
  - Implement Novel model with validation
  - Implement Chapter model (extended with novel_id)
  - Implement PipelineState model (extended with novel_id)
  - Implement ExternalMetadata and CoverUploadResponse models
  - _Requirements: 1.1, 1.2, 1.6_

- [x] 4. Implement EPUB Import Pipeline
  - [x] 4.1 Create EPUB metadata extractor
    - Extract title and author from EPUB metadata
    - Implement filename fallback for missing metadata
    - _Requirements: 2.1, 2.2_
  
  - [x] 4.2 Integrate with existing sanitization pipeline
    - Modify sanitizer to accept novel_id parameter
    - Associate extracted chapters with novel_id
    - _Requirements: 2.4, 2.5_
  
  - [x] 4.3 Implement import endpoint POST /api/library/import
    - Handle file upload
    - Create novel entry
    - Invoke sanitization pipeline
    - Return novel_id and status
    - Implement rollback on failure
    - _Requirements: 2.3, 2.6, 2.7_
  
  - [x] 4.4 Write property test for EPUB import
    - **Property 2: EPUB Import Creates Novel Entry**
    - **Property 3: EPUB Import Associates Chapters**
    - **Validates: Requirements 2.1, 2.3, 2.4, 2.5**
  
  - [x] 4.5 Write property test for import failure rollback
    - **Property 4: Import Failure Rollback**
    - **Validates: Requirements 2.7**

- [x] 5. Checkpoint - Ensure database and import tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement Library Management API Endpoints
  - [x] 6.1 Create library router in `babel/api/library.py`
    - Implement GET /api/library (list novels)
    - Implement GET /api/library/{id} (get single novel)
    - Implement GET /api/library/{id}/chapters (get novel chapters)
    - Implement DELETE /api/library/{id} (delete novel)
    - _Requirements: 3.1, 3.3, 3.4, 3.6, 3.7_
  
  - [x] 6.2 Write property test for novel list sorting
    - **Property 5: Novel List Sorting**
    - **Validates: Requirements 3.2**
  
  - [x] 6.3 Write property test for invalid novel ID handling
    - **Property 6: Invalid Novel ID Returns 404**
    - **Validates: Requirements 3.5**
  
  - [x] 6.4 Write unit tests for library API endpoints
    - Test endpoint responses, error codes, request validation
    - _Requirements: 3.1, 3.3, 3.4, 3.5, 3.6_

- [x] 7. Implement External Metadata Fetching
  - [x] 7.1 Create metadata client base class
    - Create `babel/api/metadata.py` with MetadataClient abstract class
    - _Requirements: 4.1_
  
  - [x] 7.2 Implement NovelUpdates client
    - Implement search method
    - Implement cover URL fetching
    - _Requirements: 4.2_
  
  - [x] 7.3 Implement RoyalRoad client
    - Implement search method
    - Implement cover URL fetching
    - _Requirements: 4.3_
  
  - [x] 7.4 Implement metadata endpoint POST /api/library/{id}/metadata
    - Accept source parameter (novelupdates or royalroad)
    - Query external API
    - Download cover image to data/covers/{novel_id}.jpg
    - Update novel entry
    - Handle failures gracefully
    - _Requirements: 4.1, 4.4, 4.5, 4.6, 4.7_
  
  - [x] 7.5 Write property test for metadata updates
    - **Property 7: Metadata Update Completeness**
    - **Validates: Requirements 4.4**
  
  - [x] 7.6 Write property test for cover image storage
    - **Property 8: Cover Image Storage**
    - **Validates: Requirements 4.6**
  
  - [x] 7.7 Write unit tests for metadata clients
    - Mock external APIs
    - Test error handling and graceful degradation
    - _Requirements: 4.2, 4.3, 4.5, 4.7_

- [ ] 8. Implement Cover Art Upload
  - [x] 8.1 Implement cover upload endpoint POST /api/library/{id}/cover
    - Validate file type (jpg, png, webp)
    - Resize image to 400x600px maintaining aspect ratio
    - Save to data/covers/{novel_id}.jpg
    - Update novel entry
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_
  
  - [x] 8.2 Write property test for cover upload validation and processing
    - **Property 15: Cover Upload Validation and Processing**
    - **Validates: Requirements 10.2, 10.3, 10.4, 10.5**
  
  - [x] 8.3 Write unit tests for cover upload
    - Test file type validation
    - Test error handling for invalid files
    - _Requirements: 10.6_

- [x] 9. Checkpoint - Ensure all backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Update Pipeline for Multi-Novel Support
  - [x] 10.1 Modify pipeline orchestrator to accept novel_id parameter
    - Update PipelineOrchestrator to track novel_id
    - Associate transformed output with novel_id
    - Track progress separately for each novel
    - _Requirements: 9.1, 9.2, 9.3_
  
  - [x] 10.2 Implement concurrent processing prevention
    - Add locking mechanism to prevent duplicate processing
    - _Requirements: 9.5_
  
  - [x] 10.3 Write property test for pipeline novel association
    - **Property 13: Pipeline Novel Association**
    - **Validates: Requirements 9.2, 9.3**
  
  - [x] 10.4 Write property test for concurrent processing prevention
    - **Property 14: Concurrent Processing Prevention**
    - **Validates: Requirements 9.5**

- [x] 11. Implement Backward Compatibility Layer
  - [x] 11.1 Create migration script for existing chapters
    - Create default "legacy" novel
    - Associate NULL novel_id chapters with legacy novel
    - _Requirements: 8.2_
  
  - [x] 11.2 Update API to support legacy endpoints
    - Ensure /chapter/{id} continues to work
    - Support both legacy and new URL patterns
    - _Requirements: 8.3, 8.5_
  
  - [x] 11.3 Write property test for legacy chapter compatibility
    - **Property 12: Legacy Chapter Compatibility**
    - **Validates: Requirements 8.1, 8.3**
  
  - [x] 11.4 Write unit tests for migration script
    - Test chapter association
    - Test legacy endpoint compatibility
    - _Requirements: 8.2, 8.5_

- [x] 12. Integrate Library Router with FastAPI Server
  - Update `babel_server.py` to include library router
  - Add CORS configuration for new endpoints
  - Update API documentation
  - _Requirements: 3.1, 3.3, 3.4, 3.6, 4.1, 10.1_

- [x] 13. Create Frontend Library Page
  - [x] 13.1 Create Library page component
    - Create `babel-ui/src/pages/Library.tsx`
    - Implement novel grid layout
    - Fetch novels via GET /api/library
    - Display loading state
    - _Requirements: 5.1, 5.2, 5.7_
  
  - [x] 13.2 Create NovelCard component
    - Create `babel-ui/src/components/library/NovelCard.tsx`
    - Display cover art, title, author, status
    - Handle missing cover with placeholder
    - Implement click handler for navigation
    - _Requirements: 5.4, 5.5, 5.6_
  
  - [x] 13.3 Write property test for novel display completeness
    - **Property 9: Novel Display Completeness**
    - **Validates: Requirements 5.4**
  
  - [x] 13.4 Write unit tests for Library page
    - Test component rendering
    - Test API integration
    - Test loading states
    - _Requirements: 5.1, 5.2, 5.7_

- [x] 14. Create Frontend Import Modal
  - [x] 14.1 Create ImportModal component
    - Create `babel-ui/src/components/modals/ImportModal.tsx`
    - Implement file upload UI
    - Call POST /api/library/import
    - Display import progress
    - Handle errors with toast notifications
    - _Requirements: 2.6, 2.7_
  
  - [x] 14.2 Write unit tests for ImportModal
    - Test file upload
    - Test error handling
    - _Requirements: 2.6, 2.7_

- [x] 15. Implement Context Switcher
  - [x] 15.1 Create ContextSwitcher component
    - Create `babel-ui/src/components/layout/ContextSwitcher.tsx`
    - Display "Back to Library" button in reader
    - Handle navigation to /library
    - Persist reading position before navigation
    - _Requirements: 6.1, 6.2, 6.3_
  
  - [x] 15.2 Update reading progress store
    - Extend `babel-ui/src/stores/readingProgressStore.ts`
    - Add novel_id tracking
    - Implement position persistence
    - Implement position restoration
    - _Requirements: 6.3, 6.4_
  
  - [x] 15.3 Write property test for reading position persistence
    - **Property 10: Reading Position Persistence**
    - **Validates: Requirements 6.3, 6.4**
  
  - [x] 15.4 Write unit tests for ContextSwitcher
    - Test button rendering
    - Test navigation
    - Test persistence
    - _Requirements: 6.1, 6.2, 6.3_

- [ ] 16. Implement Novel Selection Flow
  - [ ] 16.1 Update ChapterView to support novel context
    - Fetch chapters via GET /api/library/{id}/chapters
    - Update sidebar to show only selected novel's chapters
    - Display novel title in header
    - Clear previous novel's chapter cache on switch
    - Load first chapter by default
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_
  
  - [ ] 16.2 Write property test for chapter list isolation
    - **Property 11: Chapter List Isolation**
    - **Validates: Requirements 7.2, 7.4**
  
  - [ ] 16.3 Write unit tests for novel selection
    - Test chapter fetching
    - Test sidebar updates
    - Test cache clearing
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

- [ ] 17. Implement Single-Novel Detection
  - Update Library page to detect single novel
  - Skip library view and navigate directly to reader
  - _Requirements: 8.4_

- [ ] 18. Add Library Route to React Router
  - Update `babel-ui/src/App.tsx` with /library route
  - Update navigation to support both /chapter/{id} and /library/{novel_id}/chapter/{id}
  - _Requirements: 5.1, 8.5_

- [ ] 19. Update API Client
  - Extend `babel-ui/src/lib/api.ts` with library endpoints
  - Add type definitions for Novel, NovelListResponse, ImportResponse
  - _Requirements: 3.1, 3.3, 3.4, 3.6, 4.1, 10.1_

- [ ] 20. Checkpoint - Ensure all frontend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 21. Create E2E Tests for User Flows
  - [ ] 21.1 Write E2E test for import flow
    - Upload EPUB
    - Verify novel appears in library
    - Navigate to novel
    - Verify chapters load
  
  - [ ] 21.2 Write E2E test for library browsing
    - Navigate to library
    - Click novel card
    - Verify reader loads
    - Click "Back to Library"
    - Verify library loads
  
  - [ ] 21.3 Write E2E test for novel switching
    - Read chapter from Novel A
    - Navigate to library
    - Select Novel B
    - Verify Novel B chapters load
    - Return to Novel A
    - Verify reading position restored

- [ ] 22. Create Database Migration Script
  - Create `babel/data/migrations/001_add_novels_table.py`
  - Implement migration for existing databases
  - Create default "legacy" novel for existing chapters
  - _Requirements: 8.2_

- [ ] 23. Update Documentation
  - Update README.md with Phase 7 features
  - Add library management guide to docs/
  - Document API endpoints in OpenAPI spec
  - Add migration guide for existing users
  - _Requirements: All_

- [ ] 24. Final Integration Testing
  - [ ] 24.1 Test complete import-to-read flow
    - Import multiple EPUBs
    - Verify library display
    - Read chapters from different novels
    - Verify metadata fetching
    - Verify cover uploads
  
  - [ ] 24.2 Test backward compatibility
    - Verify existing single-novel workflow
    - Verify legacy URL patterns
    - Verify migration script
  
  - [ ] 24.3 Test concurrent operations
    - Process multiple novels simultaneously
    - Verify independent progress tracking
    - Verify no race conditions

- [ ] 25. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties (minimum 100 iterations each)
- Unit tests validate specific examples and edge cases
- E2E tests validate complete user workflows
- The implementation follows a bottom-up approach: database → API → frontend
- Backward compatibility is maintained throughout to avoid breaking existing workflows
