# Requirements Document: Phase 7 - The Librarian

## Introduction

Phase 7: The Librarian transforms BABEL from a single-book processor into a comprehensive multi-novel library management system. This feature enables users to store, organize, and manage multiple webnovels within a unified interface, complete with metadata fetching, cover art display, and seamless novel switching capabilities.

The system maintains backward compatibility with existing single-novel workflows while introducing library-centric features including EPUB import, external metadata integration (NovelUpdates, RoyalRoad), and a visual bookshelf interface.

## Glossary

- **Novel**: A complete webnovel entity with metadata (title, author, cover art, status) and associated chapters
- **Library**: The collection of all novels stored in the BABEL system
- **Bookshelf**: The visual grid interface displaying novel cover art and metadata
- **Novel_Entry**: A database record representing a single novel in the novels table
- **Chapter_Association**: The foreign key relationship linking chapters to their parent novel
- **Metadata_Source**: External services (NovelUpdates, RoyalRoad) providing novel information
- **EPUB_Import**: The process of uploading and ingesting EPUB files to create novel entries
- **Context_Switcher**: UI component allowing navigation between library view and novel reading view
- **Pipeline_State**: System state tracking multiple concurrent processing jobs
- **Cover_Art**: Visual thumbnail image representing a novel in the bookshelf grid

## Requirements

### Requirement 1: Database Schema for Multi-Novel Support

**User Story:** As a system architect, I want a database schema that supports multiple novels, so that BABEL can store and manage a library of webnovels.

#### Acceptance Criteria

1. THE Database SHALL create a novels table with columns: id (primary key), title (text), author (text), cover_url (text), status (text), created_at (timestamp), updated_at (timestamp)
2. THE Database SHALL add a novel_id column to the chapters table as a foreign key referencing novels.id
3. WHEN a novel is deleted, THE Database SHALL cascade delete all associated chapters
4. THE Database SHALL create an index on chapters.novel_id for query performance
5. THE Database SHALL support NULL values for novel_id to maintain backward compatibility with existing chapters
6. THE Database SHALL update the pipeline_state table to include novel_id for tracking multiple active jobs

### Requirement 2: EPUB Import and Novel Creation

**User Story:** As a user, I want to upload EPUB files and create novel entries, so that I can add new books to my library.

#### Acceptance Criteria

1. WHEN a user uploads an EPUB file via POST /api/library/import, THE System SHALL extract the novel title and author from EPUB metadata
2. WHEN EPUB metadata is incomplete, THE System SHALL use filename as fallback for title
3. WHEN an EPUB is uploaded, THE System SHALL create a Novel_Entry in the database with extracted metadata
4. WHEN an EPUB is uploaded, THE System SHALL invoke the existing sanitization pipeline to extract chapters
5. WHEN chapters are extracted, THE System SHALL associate all chapters with the novel_id of the created Novel_Entry
6. WHEN EPUB import completes successfully, THE System SHALL return the novel_id and import status
7. IF EPUB import fails, THEN THE System SHALL return a descriptive error message and rollback database changes

### Requirement 3: Library Management API

**User Story:** As a frontend developer, I want REST API endpoints for library operations, so that I can build the bookshelf UI.

#### Acceptance Criteria

1. THE System SHALL provide GET /api/library endpoint returning a list of all novels with metadata
2. WHEN GET /api/library is called, THE System SHALL return novels sorted by updated_at descending
3. THE System SHALL provide GET /api/library/{id} endpoint returning a single novel's details
4. THE System SHALL provide GET /api/library/{id}/chapters endpoint returning all chapters for a novel
5. WHEN a novel_id does not exist, THE System SHALL return HTTP 404 with error message
6. THE System SHALL provide DELETE /api/library/{id} endpoint to remove novels
7. WHEN a novel is deleted via DELETE /api/library/{id}, THE System SHALL cascade delete all associated chapters and files

### Requirement 4: External Metadata Fetching

**User Story:** As a user, I want to fetch cover art and metadata from external sources, so that my library has rich visual information.

#### Acceptance Criteria

1. THE System SHALL provide POST /api/library/{id}/metadata endpoint accepting a source parameter (novelupdates or royalroad)
2. WHEN NovelUpdates is specified as source, THE System SHALL query NovelUpdates API with the novel title
3. WHEN RoyalRoad is specified as source, THE System SHALL query RoyalRoad API with the novel title
4. WHEN metadata is found, THE System SHALL update the Novel_Entry with cover_url, synopsis, tags, and status
5. WHEN metadata fetch fails, THE System SHALL return HTTP 404 with error message
6. THE System SHALL download cover images and store them locally in data/covers/{novel_id}.jpg
7. WHEN cover download fails, THE System SHALL log the error and continue with URL-only storage

### Requirement 5: Bookshelf UI - Library View

**User Story:** As a user, I want a visual bookshelf displaying my novels, so that I can browse and select books to read.

#### Acceptance Criteria

1. THE Frontend SHALL create a /library route displaying the bookshelf interface
2. WHEN /library is accessed, THE Frontend SHALL fetch all novels via GET /api/library
3. THE Frontend SHALL display novels in a responsive grid layout with 3-5 columns depending on screen width
4. WHEN displaying a novel, THE Frontend SHALL show cover art, title, author, and status
5. WHEN a novel has no cover_url, THE Frontend SHALL display a placeholder image with the novel title
6. WHEN a user clicks a novel card, THE Frontend SHALL navigate to /chapter/{first_chapter_id} for that novel
7. THE Frontend SHALL display a loading state while fetching library data

### Requirement 6: Context Switching Between Library and Reader

**User Story:** As a user, I want to navigate between the library and individual novels, so that I can switch between books seamlessly.

#### Acceptance Criteria

1. WHEN reading a chapter, THE Frontend SHALL display a "Back to Library" button in the sidebar
2. WHEN "Back to Library" is clicked, THE Frontend SHALL navigate to /library
3. THE Frontend SHALL persist the current reading position before navigating to library
4. WHEN returning to a novel from library, THE Frontend SHALL restore the last read chapter
5. THE Frontend SHALL update the browser URL to reflect current context (/library or /chapter/{id})

### Requirement 7: Novel Selection and Chapter Loading

**User Story:** As a user, I want to select a novel and load its chapters, so that I can read different books in my library.

#### Acceptance Criteria

1. WHEN a novel is selected from the bookshelf, THE Frontend SHALL fetch chapters via GET /api/library/{id}/chapters
2. WHEN chapters are loaded, THE Frontend SHALL update the sidebar chapter list to show only that novel's chapters
3. THE Frontend SHALL display the novel title in the reader header
4. WHEN switching novels, THE Frontend SHALL clear the previous novel's chapter cache
5. THE Frontend SHALL load the first chapter of the selected novel by default

### Requirement 8: Backward Compatibility with Single-Novel Workflow

**User Story:** As an existing user, I want my current single-novel workflow to continue working, so that the upgrade doesn't break my existing setup.

#### Acceptance Criteria

1. WHEN chapters exist with NULL novel_id, THE System SHALL treat them as belonging to a default "legacy" novel
2. THE System SHALL provide a migration script to associate existing chapters with a default novel
3. WHEN the legacy single-novel endpoints are called, THE System SHALL continue to function without requiring novel_id
4. THE Frontend SHALL detect if only one novel exists and skip the library view, navigating directly to the reader
5. THE System SHALL support both /chapter/{id} (legacy) and /library/{novel_id}/chapter/{id} (new) URL patterns

### Requirement 9: Pipeline Integration for Multi-Novel Processing

**User Story:** As a user, I want to process multiple novels concurrently, so that I can transform several books simultaneously.

#### Acceptance Criteria

1. THE Pipeline SHALL accept a novel_id parameter for all transformation operations
2. WHEN processing chapters, THE Pipeline SHALL associate transformed output with the correct novel_id
3. THE Pipeline_State SHALL track progress separately for each novel_id
4. WHEN multiple novels are processing, THE System SHALL display progress for each novel independently
5. THE System SHALL prevent duplicate processing of the same novel concurrently

### Requirement 10: Cover Art Management

**User Story:** As a user, I want to upload custom cover art, so that I can personalize my library appearance.

#### Acceptance Criteria

1. THE System SHALL provide POST /api/library/{id}/cover endpoint accepting image file uploads
2. WHEN a cover image is uploaded, THE System SHALL validate file type (jpg, png, webp)
3. WHEN a cover image is uploaded, THE System SHALL resize it to 400x600px maintaining aspect ratio
4. WHEN a cover image is uploaded, THE System SHALL save it to data/covers/{novel_id}.jpg
5. WHEN a cover upload succeeds, THE System SHALL update the Novel_Entry cover_url field
6. IF cover upload fails validation, THEN THE System SHALL return HTTP 400 with error message
