# Requirements Document

## Introduction

This document specifies requirements for implementing proper multi-novel support in BABEL's ingestion API. Currently, when users upload novels via the `/api/ingest` endpoint, no novel entry is created in the database, chapters are not associated with any novel_id, and all chapters from different novels get mixed together in the file system. This feature will enable BABEL to properly track and organize multiple novels with their associated chapters, maintaining clear separation in both the database and file system.

## Glossary

- **Novel**: A complete webnovel work with metadata (title, author, cover) and associated chapters
- **Chapter**: An individual chapter belonging to a novel, stored as cleaned text, JSON, and HTML
- **Ingestion_API**: The FastAPI `/api/ingest` endpoint that accepts file uploads
- **Pipeline_Orchestrator**: The component that processes files through sanitize, transform, and render phases
- **Novel_ID**: Unique integer identifier for each novel in the database
- **Chapter_Map**: JSON file tracking chapter metadata and navigation information
- **Phase_Directory**: File system directory for a specific processing phase (clean, json, render)

## Requirements

### Requirement 1: Novel Creation During Ingestion

**User Story:** As a user, I want a novel entry created automatically when I upload a file, so that the system can track and organize my novels.

#### Acceptance Criteria

1. WHEN a user uploads a file via `/api/ingest`, THE Ingestion_API SHALL extract the novel title from the filename
2. WHEN the novel title is extracted, THE Ingestion_API SHALL create a new novel entry in the database with the extracted title
3. WHEN a novel entry is created, THE Ingestion_API SHALL return the novel_id to the caller
4. WHEN the filename contains common separators (hyphens, underscores, dots), THE Ingestion_API SHALL normalize them to extract a clean title
5. WHEN a novel entry is created, THE Ingestion_API SHALL set the status to "active" by default

### Requirement 2: Chapter Association with Novels

**User Story:** As a user, I want all extracted chapters linked to their parent novel, so that I can distinguish between chapters from different novels.

#### Acceptance Criteria

1. WHEN chapters are extracted during ingestion, THE Pipeline_Orchestrator SHALL associate each chapter with the novel_id
2. WHEN a chapter is created in the database, THE System SHALL store the novel_id as a foreign key reference
3. WHEN querying chapters, THE System SHALL support filtering by novel_id
4. WHEN a novel is deleted, THE System SHALL cascade delete all associated chapters
5. WHEN chapters are processed, THE Pipeline_Orchestrator SHALL maintain the novel_id throughout all phases

### Requirement 3: Novel-Specific File Organization

**User Story:** As a user, I want chapters from different novels stored in separate directories, so that files don't get mixed together.

#### Acceptance Criteria

1. WHEN processing chapters for a novel, THE Pipeline_Orchestrator SHALL create a subdirectory named `novel_{id}` within each Phase_Directory
2. WHEN sanitizing chapters, THE Pipeline_Orchestrator SHALL store cleaned files in `data/clean/novel_{id}/`
3. WHEN transforming chapters, THE Pipeline_Orchestrator SHALL store JSON files in `data/json/novel_{id}/`
4. WHEN rendering chapters, THE Pipeline_Orchestrator SHALL store HTML files in `data/render/novel_{id}/`
5. WHEN a novel_id is NULL for legacy chapters, THE Pipeline_Orchestrator SHALL store files in the root Phase_Directory without a subdirectory

### Requirement 4: Novel-Specific Chapter Maps

**User Story:** As a user, I want each novel to have its own chapter map, so that navigation and metadata are properly isolated per novel.

#### Acceptance Criteria

1. WHEN processing a novel, THE Pipeline_Orchestrator SHALL create a chapter map file named `chapter_map_novel_{id}.json`
2. WHEN storing chapter map data, THE System SHALL include the novel_id in the metadata section
3. WHEN loading a chapter map, THE System SHALL verify the novel_id matches the requested novel
4. WHEN a novel has no chapters, THE System SHALL create an empty chapter map with novel_id metadata
5. WHEN legacy chapters exist with NULL novel_id, THE System SHALL maintain the original `chapter_map.json` file

### Requirement 5: Pipeline State Tracking Per Novel

**User Story:** As a developer, I want pipeline state tracked separately for each novel, so that processing multiple novels doesn't interfere with each other.

#### Acceptance Criteria

1. WHEN updating pipeline state, THE Pipeline_Orchestrator SHALL associate the state with a novel_id
2. WHEN querying pipeline state, THE System SHALL filter by novel_id
3. WHEN multiple novels are processing concurrently, THE System SHALL maintain separate state for each novel_id
4. WHEN a pipeline phase completes, THE System SHALL update only the state for the associated novel_id
5. WHEN a novel is deleted, THE System SHALL cascade delete all associated pipeline state records

### Requirement 6: Novel Listing API

**User Story:** As a frontend developer, I want to retrieve a list of all novels, so that I can display them in the UI.

#### Acceptance Criteria

1. THE System SHALL provide a GET endpoint at `/api/novels`
2. WHEN the `/api/novels` endpoint is called, THE System SHALL return all novels sorted by updated_at descending
3. WHEN returning novel data, THE System SHALL include id, title, author, cover_url, status, and chapter_count
4. WHEN calculating chapter_count, THE System SHALL use a SQL COUNT aggregation with LEFT JOIN in a single query to avoid N+1 query problems
5. WHEN no novels exist, THE System SHALL return an empty list with total count of 0
6. THE System SHALL support pagination with limit and offset query parameters
7. WHEN listing novels, THE System SHALL NOT execute separate queries for each novel's chapter count
8. THE System SHALL use the following SQL pattern for efficient chapter counting: `SELECT n.*, COUNT(c.id) as chapter_count FROM novels n LEFT JOIN chapters c ON n.id = c.novel_id GROUP BY n.id LIMIT ? OFFSET ?`

### Requirement 7: Novel Details API

**User Story:** As a frontend developer, I want to retrieve details for a specific novel, so that I can display novel information and metadata.

#### Acceptance Criteria

1. THE System SHALL provide a GET endpoint at `/api/novels/{novel_id}`
2. WHEN a valid novel_id is provided, THE System SHALL return the complete novel record with all metadata
3. WHEN an invalid novel_id is provided, THE System SHALL return a 404 error with a descriptive message
4. WHEN returning novel details, THE System SHALL include the count of associated chapters
5. WHEN returning novel details, THE System SHALL include created_at and updated_at timestamps

### Requirement 8: Novel Chapters API

**User Story:** As a frontend developer, I want to retrieve all chapters for a specific novel, so that I can display a table of contents.

#### Acceptance Criteria

1. THE System SHALL provide a GET endpoint at `/api/novels/{novel_id}/chapters`
2. WHEN a valid novel_id is provided, THE System SHALL return all chapters for that novel ordered by chapter_index
3. WHEN an invalid novel_id is provided, THE System SHALL return a 404 error
4. WHEN a novel has no chapters, THE System SHALL return an empty list with total count of 0
5. WHEN returning chapter data, THE System SHALL include id, chapter_index, filename, title, and created_at

### Requirement 9: Updated Chapter Metadata API

**User Story:** As a frontend developer, I want the existing chapter metadata endpoint to support filtering by novel, so that I can display chapters for a specific novel.

#### Acceptance Criteria

1. WHEN the `/api/chapters/metadata` endpoint is called with a novel_id parameter, THE System SHALL return only chapters for that novel
2. WHEN the `/api/chapters/metadata` endpoint is called without a novel_id parameter, THE System SHALL return all chapters for backward compatibility
3. WHEN returning chapter metadata, THE System SHALL include the novel_id for each chapter
4. WHEN a novel_id parameter is invalid, THE System SHALL return an empty list
5. WHEN retrieving chapter metadata, THE System SHALL query the chapters table in the database instead of scanning the filesystem for performance

### Requirement 10: Ingestion API Transaction Safety

**User Story:** As a developer, I want the ingestion API to handle failures atomically, so that the system doesn't end up in an inconsistent state.

#### Acceptance Criteria

1. WHEN the `/api/ingest` endpoint creates a novel entry, THE Ingestion_API SHALL pass the novel_id to the Pipeline_Orchestrator
2. WHEN initializing the Pipeline_Orchestrator, THE System SHALL accept and store the novel_id parameter
3. WHEN the pipeline processes chapters, THE Pipeline_Orchestrator SHALL use the stored novel_id for all database operations
4. WHEN the pipeline creates output directories, THE Pipeline_Orchestrator SHALL use the novel_id in directory paths
5. WHEN directory creation fails after database entry creation, THE System SHALL delete the database entry to maintain consistency
6. WHEN the pipeline completes successfully, THE Ingestion_API SHALL return the novel_id in the operation status

### Requirement 11: Backward Compatibility for Legacy Chapters

**User Story:** As a system administrator, I want existing chapters without novel_id to continue working, so that the system doesn't break for existing data.

#### Acceptance Criteria

1. WHEN querying chapters with NULL novel_id, THE System SHALL return those chapters
2. WHEN processing chapters with NULL novel_id, THE Pipeline_Orchestrator SHALL store files in root Phase_Directory paths
3. WHEN loading chapter maps, THE System SHALL support both `chapter_map.json` and `chapter_map_novel_{id}.json` formats
4. WHEN the `/api/chapters/metadata` endpoint is called without novel_id, THE System SHALL include legacy chapters with NULL novel_id
5. WHEN displaying chapters in the UI, THE System SHALL handle both novel-associated and legacy chapters

### Requirement 12: Novel Title and Metadata Extraction

**User Story:** As a user, I want the system to intelligently extract novel titles and metadata from uploaded files, so that I don't have to manually enter metadata.

#### Acceptance Criteria

1. WHEN an EPUB file is uploaded, THE System SHALL prioritize reading the Dublin Core metadata (dc:title and dc:creator) from the content.opf file
2. WHEN EPUB metadata extraction fails or the file is not EPUB, THE System SHALL fall back to extracting the title from the filename
3. WHEN a filename contains " - Book ", THE System SHALL extract the text before " - Book " as the title
4. WHEN a filename contains underscores, THE System SHALL replace them with spaces in the extracted title
5. WHEN a filename contains hyphens surrounded by spaces, THE System SHALL preserve them in the title
6. WHEN a filename has a file extension, THE System SHALL remove the extension before extracting the title
7. WHEN the extracted title is empty or only whitespace, THE System SHALL use the full filename as the title
8. WHEN EPUB metadata contains dc:creator, THE System SHALL store it as the author field in the novel entry

### Requirement 13: Transaction Atomicity for Novel Creation

**User Story:** As a system administrator, I want novel creation and directory initialization to be atomic, so that the system doesn't have orphaned database entries.

#### Acceptance Criteria

1. WHEN creating a novel entry in the database, THE System SHALL wrap the database operation and directory creation in a try/except block
2. WHEN directory creation fails after database entry creation, THE System SHALL delete the just-created database entry
3. WHEN directory creation fails, THE System SHALL return a 500 error with a descriptive message about the filesystem failure
4. WHEN both database and directory creation succeed, THE System SHALL commit the transaction and return success
5. WHEN any part of the atomic operation fails, THE System SHALL ensure no partial state remains (no ghost entries)

### Requirement 14: Operation Tracking and Status Polling

**User Story:** As a frontend developer, I want to track the progress of ingestion operations, so that I can show users real-time status updates.

#### Acceptance Criteria

1. WHEN the `/api/ingest` endpoint starts processing, THE System SHALL return a novel_id that can be used for tracking
2. WHEN the frontend polls for status, THE System SHALL use the novel_id to query the pipeline_state table
3. WHEN multiple operations run on the same novel, THE System SHALL track the most recent operation status
4. WHEN querying operation status, THE System SHALL return phase, status, progress, and any error messages
5. WHEN an operation completes, THE System SHALL update the pipeline_state with a final status (completed or failed)
