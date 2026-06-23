# Requirements Document

## Introduction

This document specifies requirements for migrating the BABEL CLI to use SQLite database consistently with the backend API. Currently, the CLI operates primarily on the filesystem with minimal database integration, while the backend API uses SQLite for all novel and chapter management. This migration will ensure both CLI and backend use the same database-first architecture, enabling proper multi-novel support, consistent state tracking, and unified data management across all BABEL interfaces.

## Glossary

- **CLI**: Command-line interface for BABEL operations (babel/cli.py and babel/cli_commands/)
- **Backend_API**: FastAPI-based REST API for BABEL operations
- **DatabaseManager**: Thread-safe singleton class managing SQLite operations (babel/data/db.py)
- **Novel**: A complete webnovel work with metadata stored in the novels table
- **Chapter**: An individual chapter belonging to a novel, stored in the chapters table
- **Novel_ID**: Unique integer identifier for each novel in the database
- **Pipeline_Orchestrator**: Component that processes files through sanitize, transform, and render phases
- **Phase**: A processing stage (sanitize, transform, render) tracked in pipeline_state table
- **Legacy_Chapter**: A chapter with NULL novel_id for backward compatibility
- **Ingestion**: The process of preprocessing and importing a novel file into the system

## Requirements

### Requirement 1: Novel Management Commands

**User Story:** As a CLI user, I want to list and view novels in the database, so that I can see what novels are available and select one for processing.

#### Acceptance Criteria

1. THE CLI SHALL provide a command `babel novels list` that displays all novels from the database
2. WHEN executing `babel novels list`, THE CLI SHALL query the DatabaseManager to retrieve all novels sorted by updated_at descending
3. WHEN displaying novel list, THE CLI SHALL show novel_id, title, author, status, and chapter_count in a formatted table
4. THE CLI SHALL provide a command `babel novels get <novel_id>` that displays details for a specific novel
5. WHEN executing `babel novels get`, THE CLI SHALL query the DatabaseManager and display all novel metadata including created_at and updated_at timestamps
6. WHEN a novel_id does not exist, THE CLI SHALL display an error message and exit with status code 1
7. WHEN displaying novel details, THE CLI SHALL include the count of associated chapters

### Requirement 2: Database-First Ingestion

**User Story:** As a CLI user, I want to ingest a novel file and have it automatically create a database entry, so that the novel is properly tracked in the system.

#### Acceptance Criteria

1. THE CLI SHALL provide a command `babel ingest <file>` that creates a novel entry in the database
2. WHEN executing `babel ingest`, THE CLI SHALL extract the novel title from the filename or EPUB metadata
3. WHEN a novel entry is created, THE CLI SHALL return and display the novel_id to the user
4. WHEN ingestion completes, THE CLI SHALL store all extracted chapters in the database with the novel_id foreign key
5. WHEN ingestion fails, THE CLI SHALL rollback the database transaction and display an error message
6. WHEN the input file is an EPUB, THE CLI SHALL extract Dublin Core metadata (dc:title and dc:creator) from content.opf
7. WHEN EPUB metadata extraction fails, THE CLI SHALL fall back to extracting title from the filename
8. WHEN ingestion succeeds, THE CLI SHALL display a success message with the novel_id and chapter count

### Requirement 3: Novel-Scoped Transform Commands

**User Story:** As a CLI user, I want to transform chapters for a specific novel, so that I can process novels independently without mixing data.

#### Acceptance Criteria

1. THE CLI SHALL add a `--novel-id` option to the `babel transform batch` command
2. WHEN `--novel-id` is provided, THE CLI SHALL query the database for chapters belonging to that novel
3. WHEN transforming chapters, THE CLI SHALL store output files in `data/json/novel_{id}/` directory structure
4. WHEN `--novel-id` is not provided, THE CLI SHALL process legacy chapters with NULL novel_id for backward compatibility
5. WHEN a novel_id does not exist, THE CLI SHALL display an error message and exit with status code 1
6. WHEN transformation completes, THE CLI SHALL update the pipeline_state table with the novel_id and phase status
7. WHEN transforming a single chapter, THE CLI SHALL accept a `--novel-id` option to associate the output with a novel

### Requirement 4: Novel-Scoped Render Commands

**User Story:** As a CLI user, I want to render chapters for a specific novel, so that HTML output is organized by novel.

#### Acceptance Criteria

1. THE CLI SHALL add a `--novel-id` option to the `babel render batch` command
2. WHEN `--novel-id` is provided, THE CLI SHALL read JSON files from `data/json/novel_{id}/` directory
3. WHEN rendering chapters, THE CLI SHALL store HTML output in `data/render/novel_{id}/` directory structure
4. WHEN `--novel-id` is not provided, THE CLI SHALL process legacy files from root directories for backward compatibility
5. WHEN rendering completes, THE CLI SHALL update the pipeline_state table with the novel_id and phase status
6. WHEN a novel_id does not exist, THE CLI SHALL display an error message and exit with status code 1

### Requirement 5: Novel-Scoped Pipeline Commands

**User Story:** As a CLI user, I want to run the full pipeline for a specific novel, so that I can process a complete novel from ingestion to rendering.

#### Acceptance Criteria

1. THE CLI SHALL add a `--novel-id` option to the `babel pipeline run` command
2. WHEN `--novel-id` is provided, THE CLI SHALL process only chapters belonging to that novel through all phases
3. WHEN running the pipeline, THE CLI SHALL update pipeline_state table with novel_id for each phase
4. WHEN the pipeline fails at any phase, THE CLI SHALL record the error in pipeline_state with the novel_id
5. WHEN `--novel-id` is not provided, THE CLI SHALL display an error message requiring novel_id to be specified
6. WHEN the pipeline completes successfully, THE CLI SHALL display a summary showing novel_id, title, and chapters processed
7. WHEN querying pipeline status, THE CLI SHALL filter by novel_id to show status for a specific novel

### Requirement 6: Chapter Listing by Novel

**User Story:** As a CLI user, I want to list all chapters for a specific novel, so that I can see what chapters have been ingested and their processing status.

#### Acceptance Criteria

1. THE CLI SHALL provide a command `babel chapters list --novel-id <id>` that displays chapters for a novel
2. WHEN executing `babel chapters list`, THE CLI SHALL query the DatabaseManager to retrieve chapters ordered by chapter_index
3. WHEN displaying chapter list, THE CLI SHALL show chapter_id, chapter_index, filename, and title in a formatted table
4. WHEN `--novel-id` is not provided, THE CLI SHALL list all chapters including legacy chapters with NULL novel_id
5. WHEN a novel has no chapters, THE CLI SHALL display a message indicating the novel is empty
6. WHEN a novel_id does not exist, THE CLI SHALL display an error message and exit with status code 1

### Requirement 7: Pipeline State Tracking Per Novel

**User Story:** As a CLI user, I want to check the processing status of a specific novel, so that I can monitor progress and identify failures.

#### Acceptance Criteria

1. THE CLI SHALL provide a command `babel pipeline status --novel-id <id>` that displays pipeline state for a novel
2. WHEN executing `babel pipeline status`, THE CLI SHALL query the pipeline_state table filtered by novel_id
3. WHEN displaying pipeline status, THE CLI SHALL show phase, status, last_chapter, total_chapters, and error_message in a formatted table
4. WHEN a phase has not started, THE CLI SHALL display status as "pending"
5. WHEN a phase is in progress, THE CLI SHALL display status as "running" with progress information
6. WHEN a phase has completed, THE CLI SHALL display status as "complete"
7. WHEN a phase has failed, THE CLI SHALL display status as "failed" with the error_message
8. WHEN `--novel-id` is not provided, THE CLI SHALL display an error message requiring novel_id to be specified

### Requirement 8: File Organization by Novel

**User Story:** As a system administrator, I want all processed files organized by novel_id, so that files from different novels are clearly separated.

#### Acceptance Criteria

1. WHEN processing chapters for a novel, THE CLI SHALL create directory structure `data/clean/novel_{id}/`
2. WHEN transforming chapters for a novel, THE CLI SHALL create directory structure `data/json/novel_{id}/`
3. WHEN rendering chapters for a novel, THE CLI SHALL create directory structure `data/render/novel_{id}/`
4. WHEN creating directories, THE CLI SHALL use the novel_id from the database to construct paths
5. WHEN processing legacy chapters with NULL novel_id, THE CLI SHALL store files in root phase directories without novel_id subdirectory
6. WHEN a novel is deleted, THE CLI SHALL provide a command to clean up associated directories

### Requirement 9: Novel Deletion with Cleanup

**User Story:** As a CLI user, I want to delete a novel and all its associated data, so that I can remove unwanted novels from the system.

#### Acceptance Criteria

1. THE CLI SHALL provide a command `babel novels delete <novel_id>` that removes a novel from the database
2. WHEN executing `babel novels delete`, THE CLI SHALL prompt for confirmation before deletion
3. WHEN deletion is confirmed, THE CLI SHALL delete the novel entry which cascades to chapters and pipeline_state
4. WHEN deletion is confirmed, THE CLI SHALL delete the file system directories `data/*/novel_{id}/`
5. WHEN file system deletion fails, THE CLI SHALL display a warning but complete the database deletion
6. WHEN deletion is cancelled, THE CLI SHALL display a message and exit without changes
7. WHEN a novel_id does not exist, THE CLI SHALL display an error message and exit with status code 1

### Requirement 10: Backward Compatibility for Legacy Operations

**User Story:** As a CLI user, I want existing commands to continue working for legacy chapters, so that the migration doesn't break existing workflows.

#### Acceptance Criteria

1. WHEN executing `babel transform batch` without `--novel-id`, THE CLI SHALL process files from `data/clean/` root directory
2. WHEN executing `babel render batch` without `--novel-id`, THE CLI SHALL process files from `data/json/` root directory
3. WHEN querying chapters without `--novel-id`, THE CLI SHALL include chapters with NULL novel_id
4. WHEN displaying pipeline status without `--novel-id`, THE CLI SHALL show status for legacy pipeline state with NULL novel_id
5. WHEN processing legacy chapters, THE CLI SHALL maintain existing file paths and naming conventions

### Requirement 11: Database Initialization and Migration

**User Story:** As a system administrator, I want the CLI to automatically initialize the database schema, so that the system is ready to use without manual setup.

#### Acceptance Criteria

1. WHEN the CLI is first executed, THE DatabaseManager SHALL create the database file at `data/babel.db` if it does not exist
2. WHEN the database is created, THE DatabaseManager SHALL execute schema creation for novels, chapters, and pipeline_state tables
3. WHEN the database already exists, THE DatabaseManager SHALL verify the schema and create missing tables if needed
4. WHEN the database schema is incompatible, THE CLI SHALL display an error message with migration instructions
5. THE DatabaseManager SHALL enable foreign key constraints with `PRAGMA foreign_keys = ON`

### Requirement 12: Context Commands Integration

**User Story:** As a CLI user, I want context and glossary commands to work with novel-specific data, so that context is properly scoped to each novel.

#### Acceptance Criteria

1. THE CLI SHALL add a `--novel-id` option to `babel context build` command
2. WHEN building context with `--novel-id`, THE CLI SHALL read chapters from `data/json/novel_{id}/` directory
3. WHEN building context, THE CLI SHALL store the context file in `data/context/novel_{id}/` directory
4. WHEN `--novel-id` is not provided, THE CLI SHALL build context from root `data/json/` directory for legacy support
5. WHEN loading context for transformation, THE CLI SHALL use the novel_id to locate the correct context file

### Requirement 13: Utility Commands for Database Operations

**User Story:** As a developer, I want utility commands to inspect and manage the database, so that I can troubleshoot issues and verify data integrity.

#### Acceptance Criteria

1. THE CLI SHALL provide a command `babel util db-info` that displays database statistics
2. WHEN executing `babel util db-info`, THE CLI SHALL display total novels, total chapters, and database file size
3. THE CLI SHALL provide a command `babel util db-check` that verifies database integrity
4. WHEN executing `babel util db-check`, THE CLI SHALL check for orphaned chapters, missing files, and inconsistent pipeline state
5. WHEN integrity issues are found, THE CLI SHALL display a detailed report with recommendations
6. THE CLI SHALL provide a command `babel util db-vacuum` that optimizes the database file

### Requirement 14: Consistent Error Handling

**User Story:** As a CLI user, I want clear error messages when database operations fail, so that I can understand and resolve issues.

#### Acceptance Criteria

1. WHEN a database query fails, THE CLI SHALL display an error message with the specific database error
2. WHEN a novel_id is not found, THE CLI SHALL display "Novel with ID {id} not found"
3. WHEN a database connection fails, THE CLI SHALL display "Failed to connect to database at {path}"
4. WHEN a foreign key constraint is violated, THE CLI SHALL display a message explaining the relationship constraint
5. WHEN a transaction fails, THE CLI SHALL rollback changes and display the error without leaving partial state

### Requirement 15: Progress Reporting for Long Operations

**User Story:** As a CLI user, I want to see progress updates during long-running operations, so that I know the system is working and can estimate completion time.

#### Acceptance Criteria

1. WHEN ingesting a large novel, THE CLI SHALL display a progress bar showing chapters processed
2. WHEN transforming chapters in batch, THE CLI SHALL display progress with current chapter number and total
3. WHEN rendering chapters in batch, THE CLI SHALL display progress with current chapter number and total
4. WHEN running the full pipeline, THE CLI SHALL display progress for each phase with chapter counts
5. WHEN an operation completes, THE CLI SHALL display total time elapsed and chapters processed per second

### Requirement 16: Configuration for Database Path

**User Story:** As a system administrator, I want to configure the database path, so that I can use different databases for testing and production.

#### Acceptance Criteria

1. THE CLI SHALL read database path from environment variable `BABEL_DB_PATH` if set
2. WHEN `BABEL_DB_PATH` is not set, THE CLI SHALL use default path `data/babel.db`
3. THE CLI SHALL provide a `--db-path` global option that overrides the environment variable
4. WHEN a custom database path is used, THE CLI SHALL display the path in verbose mode
5. WHEN the database path directory does not exist, THE CLI SHALL create it automatically

### Requirement 17: Novel Update Commands

**User Story:** As a CLI user, I want to update novel metadata, so that I can correct titles, authors, and other information.

#### Acceptance Criteria

1. THE CLI SHALL provide a command `babel novels update <novel_id>` with options for metadata fields
2. WHEN executing `babel novels update`, THE CLI SHALL accept `--title`, `--author`, `--cover-url`, and `--status` options
3. WHEN updating a novel, THE CLI SHALL call DatabaseManager.update_novel with the provided fields
4. WHEN an update succeeds, THE CLI SHALL display the updated novel information
5. WHEN no update fields are provided, THE CLI SHALL display an error message listing available options
6. WHEN a novel_id does not exist, THE CLI SHALL display an error message and exit with status code 1

### Requirement 18: Batch Operations with Novel Context

**User Story:** As a CLI user, I want to perform batch operations on multiple novels, so that I can efficiently manage large libraries.

#### Acceptance Criteria

1. THE CLI SHALL provide a command `babel novels list --status <status>` that filters novels by status
2. WHEN filtering by status, THE CLI SHALL query the database with a WHERE clause on the status field
3. THE CLI SHALL provide a command `babel pipeline run-all` that processes all novels with status "active"
4. WHEN executing `babel pipeline run-all`, THE CLI SHALL iterate through active novels and run the pipeline for each
5. WHEN a novel fails during batch processing, THE CLI SHALL continue with remaining novels and report failures at the end
6. WHEN batch processing completes, THE CLI SHALL display a summary with success count, failure count, and total time

### Requirement 19: Chapter Map Generation Per Novel

**User Story:** As a CLI user, I want chapter maps generated per novel, so that navigation metadata is properly isolated.

#### Acceptance Criteria

1. WHEN rendering chapters for a novel, THE CLI SHALL generate a chapter map file named `chapter_map_novel_{id}.json`
2. WHEN generating a chapter map, THE CLI SHALL include novel_id in the metadata section
3. WHEN a chapter map is loaded, THE CLI SHALL verify the novel_id matches the requested novel
4. WHEN legacy chapters are rendered, THE CLI SHALL generate the original `chapter_map.json` file for backward compatibility
5. WHEN a novel has no chapters, THE CLI SHALL create an empty chapter map with novel_id metadata

### Requirement 20: Transaction Safety for All Database Operations

**User Story:** As a developer, I want all database operations to be transaction-safe, so that the system maintains consistency even when operations fail.

#### Acceptance Criteria

1. WHEN creating a novel, THE CLI SHALL wrap the database insert and directory creation in a transaction
2. WHEN directory creation fails after database insert, THE CLI SHALL rollback the transaction and delete the database entry
3. WHEN updating pipeline state, THE CLI SHALL use the DatabaseManager transaction context manager
4. WHEN deleting a novel, THE CLI SHALL wrap database deletion and file system cleanup in a try/except block
5. WHEN any database operation fails, THE CLI SHALL ensure no partial state remains in the database
