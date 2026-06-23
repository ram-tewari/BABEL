# Implementation Plan: CLI SQLite Migration

## Overview

This implementation plan migrates the BABEL CLI from filesystem-centric operations to database-first architecture, ensuring consistency with the backend API. The migration adds novel management commands, modifies existing commands to support novel_id parameters, and ensures all operations use the DatabaseManager for state tracking.

## Tasks

- [x] 1. Create Novel Management Commands Module
  - Create `babel/cli_commands/novels_commands.py` with Typer app
  - Implement `babel novels list` command with Rich table formatting
  - Implement `babel novels get <novel_id>` command
  - Implement `babel novels update <novel_id>` command with metadata options
  - Implement `babel novels delete <novel_id>` command with confirmation prompt
  - Register novels_commands in `babel/cli.py`
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 17.1, 17.2, 17.3, 17.4, 17.5, 17.6, 18.1, 18.2_

- [x] 1.1 Write property test for novel list ordering
  - **Property 2: Novel List Ordering**
  - **Validates: Requirements 1.2**

- [x] 1.2 Write property test for novel ID validation
  - **Property 1: Novel ID Validation Across All Commands**
  - **Validates: Requirements 1.6, 3.5, 4.6, 6.6, 9.7, 17.6**

- [x] 1.3 Write property test for status filtering
  - **Property 20: Status Filtering**
  - **Validates: Requirements 18.2**

- [x] 1.4 Write unit tests for novel commands
  - Test command existence and registration
  - Test confirmation prompts for deletion
  - Test error messages for non-existent novels
  - _Requirements: 1.1, 1.4, 9.1, 9.2, 9.6, 17.1_

- [x] 2. Create Ingestion Commands Module
  - Create `babel/cli_commands/ingest_commands.py` with Typer app
  - Implement metadata extraction from EPUB (Dublin Core dc:title, dc:creator)
  - Implement filename parsing fallback logic
  - Implement `babel ingest <file>` command with transaction safety
  - Add novel creation with directory initialization
  - Add chapter extraction and database storage with novel_id
  - Register ingest_commands in `babel/cli.py`
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 12.1, 12.2, 12.3_

- [x] 2.1 Write property test for metadata extraction from EPUB
  - **Property 7: Metadata Extraction from EPUB**
  - **Validates: Requirements 2.6**

- [x] 2.2 Write property test for metadata extraction fallback
  - **Property 8: Metadata Extraction Fallback**
  - **Validates: Requirements 2.2, 2.7**

- [x] 2.3 Write property test for chapter-novel association
  - **Property 9: Chapter-Novel Association**
  - **Validates: Requirements 2.4**

- [x] 2.4 Write property test for transaction atomicity
  - **Property 10: Transaction Atomicity for Novel Creation**
  - **Validates: Requirements 2.5, 20.1, 20.2**

- [x] 2.5 Write unit tests for ingestion
  - Test EPUB file ingestion
  - Test text file ingestion
  - Test error handling for invalid files
  - Test success message format
  - _Requirements: 2.1, 2.8_

- [x] 3. Create Chapters Management Commands Module
  - Create `babel/cli_commands/chapters_commands.py` with Typer app
  - Implement `babel chapters list` command with optional `--novel-id` filter
  - Add Rich table formatting for chapter display
  - Handle empty chapter lists gracefully
  - Register chapters_commands in `babel/cli.py`
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [x] 3.1 Write property test for chapter list ordering
  - **Property 3: Chapter List Ordering**
  - **Validates: Requirements 6.2**

- [x] 3.2 Write property test for legacy chapter inclusion
  - **Property 14: Legacy Chapter Inclusion**
  - **Validates: Requirements 10.3**

- [x] 3.3 Write unit tests for chapter commands
  - Test chapter list with novel_id filter
  - Test chapter list without filter (all chapters)
  - Test empty novel chapter list
  - _Requirements: 6.1, 6.4, 6.5_

- [x] 4. Modify Transform Commands for Novel Support
  - Add `--novel-id` option to `babel transform batch` command
  - Implement database query for chapters by novel_id
  - Update directory path logic to use novel-specific paths
  - Add pipeline_state updates with novel_id
  - Maintain backward compatibility for legacy processing
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 10.1_

- [x] 4.1 Write property test for novel-specific directory paths
  - **Property 4: Novel-Specific Directory Path Construction**
  - **Validates: Requirements 3.3, 4.2, 4.3, 8.1, 8.2, 8.3, 8.4, 12.2, 12.3**

- [x] 4.2 Write property test for chapter database filtering
  - **Property 5: Chapter Database Filtering**
  - **Validates: Requirements 3.2, 5.2**

- [x] 4.3 Write property test for pipeline state tracking
  - **Property 6: Pipeline State Tracking**
  - **Validates: Requirements 3.6, 4.5, 5.3**

- [x] 4.4 Write unit tests for transform commands
  - Test transform with novel_id
  - Test transform without novel_id (legacy)
  - Test error handling for non-existent novel_id
  - _Requirements: 3.1, 3.4, 3.7_

- [x] 5. Modify Render Commands for Novel Support
  - Add `--novel-id` option to `babel render batch` command
  - Update input directory path logic for novel-specific paths
  - Update output directory path logic for novel-specific paths
  - Implement novel-specific chapter map generation
  - Add pipeline_state updates with novel_id
  - Maintain backward compatibility for legacy processing
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 10.2, 19.1, 19.2, 19.3, 19.4, 19.5_

- [x] 5.1 Write property test for chapter map novel ID inclusion
  - **Property 22: Chapter Map Novel ID Inclusion**
  - **Validates: Requirements 19.2**

- [x] 5.2 Write property test for chapter map verification
  - **Property 23: Chapter Map Novel ID Verification**
  - **Validates: Requirements 19.3**

- [x] 5.3 Write unit tests for render commands
  - Test render with novel_id
  - Test render without novel_id (legacy)
  - Test chapter map generation
  - Test empty novel chapter map
  - _Requirements: 4.1, 4.4, 19.4, 19.5_

- [x] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Modify Pipeline Commands for Novel Support
  - Make `--novel-id` required for `babel pipeline run` command
  - Add `--novel-id` option to `babel pipeline status` command
  - Implement `babel pipeline run-all` command for batch processing
  - Add novel verification before pipeline execution
  - Update PipelineOrchestrator initialization with novel_id
  - Add progress display with novel information
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8, 18.3, 18.4, 18.5, 18.6_

- [x] 7.1 Write property test for pipeline state filtering
  - **Property 25: Pipeline State Filtering**
  - **Validates: Requirements 5.7, 7.2**

- [x] 7.2 Write property test for batch processing resilience
  - **Property 21: Batch Processing Resilience**
  - **Validates: Requirements 18.5**

- [x] 7.3 Write unit tests for pipeline commands
  - Test pipeline run with novel_id
  - Test pipeline run without novel_id (error)
  - Test pipeline status display
  - Test pipeline run-all batch processing
  - Test status display for different phases
  - _Requirements: 5.1, 5.5, 7.1, 7.4, 7.5, 7.6, 7.7, 7.8, 18.3_

- [x] 8. Modify Context Commands for Novel Support
  - Add `--novel-id` option to `babel context build` command
  - Update input directory path logic for novel-specific paths
  - Update output file path logic for novel-specific paths
  - Maintain backward compatibility for legacy processing
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [x] 8.1 Write unit tests for context commands
  - Test context build with novel_id
  - Test context build without novel_id (legacy)
  - _Requirements: 12.1, 12.4_

- [x] 9. Extend Utility Commands with Database Operations
  - Implement `babel util db-info` command with database statistics
  - Implement `babel util db-check` command with integrity verification
  - Implement `babel util db-vacuum` command for optimization
  - Add orphaned chapter detection
  - Add missing file detection
  - Add stuck pipeline state detection
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

- [x] 9.1 Write property test for database integrity check
  - **Property 30: Database Integrity Check Detection**
  - **Validates: Requirements 13.4, 13.5**

- [x] 9.2 Write unit tests for utility commands
  - Test db-info command output
  - Test db-check with clean database
  - Test db-check with integrity issues
  - Test db-vacuum command
  - _Requirements: 13.1, 13.3, 13.6_

- [x] 10. Update CLI Entry Point
  - Add global `--db-path` option to main CLI
  - Add environment variable support for `BABEL_DB_PATH`
  - Register all new command modules (novels, ingest, chapters)
  - Add verbose mode for database path display
  - Initialize DatabaseManager with custom path if provided
  - _Requirements: 16.1, 16.2, 16.3, 16.4, 16.5_

- [x] 10.1 Write property test for database path configuration
  - **Property 17: Database Path Configuration Precedence**
  - **Validates: Requirements 16.3**

- [x] 10.2 Write property test for automatic directory creation
  - **Property 18: Automatic Directory Creation**
  - **Validates: Requirements 16.5**

- [x] 10.3 Write unit tests for CLI entry point
  - Test global --db-path option
  - Test BABEL_DB_PATH environment variable
  - Test option precedence over environment variable
  - Test verbose mode output
  - _Requirements: 16.1, 16.2, 16.4_

- [x] 11. Update Pipeline Orchestrator Integration
  - Verify novel_id parameter is properly used in all methods
  - Ensure `_get_phase_directory()` is called for all directory operations
  - Ensure `_get_chapter_map_path()` is called for chapter map operations
  - Add DatabaseManager integration for pipeline_state updates
  - Update all phase execution methods to use DatabaseManager
  - _Requirements: 5.3, 5.4, 8.1, 8.2, 8.3, 8.4_

- [x] 11.1 Write integration tests for pipeline orchestrator
  - Test end-to-end pipeline with novel_id
  - Test directory creation for all phases
  - Test pipeline state updates
  - Test error recording in pipeline_state
  - _Requirements: 5.3, 5.4_

- [x] 12. Implement Cascade Deletion and Cleanup
  - Implement filesystem cleanup in `babel novels delete` command
  - Add graceful error handling for filesystem cleanup failures
  - Verify database cascade deletion works correctly
  - Add warning messages for partial cleanup failures
  - _Requirements: 9.3, 9.4, 9.5, 8.6_

- [x] 12.1 Write property test for cascade deletion
  - **Property 11: Cascade Deletion**
  - **Validates: Requirements 9.3**

- [x] 12.2 Write property test for filesystem cleanup
  - **Property 12: Filesystem Cleanup on Deletion**
  - **Validates: Requirements 9.4**

- [x] 12.3 Write property test for graceful cleanup failure
  - **Property 13: Graceful Filesystem Cleanup Failure**
  - **Validates: Requirements 9.5**

- [x] 13. Implement Database Schema Initialization
  - Verify DatabaseManager creates all tables on first run
  - Add schema verification logic
  - Implement foreign key constraint enforcement
  - Add error handling for schema incompatibility
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 13.1 Write property test for schema initialization
  - **Property 15: Database Schema Initialization**
  - **Validates: Requirements 11.2**

- [x] 13.2 Write property test for foreign key enforcement
  - **Property 16: Foreign Key Enforcement**
  - **Validates: Requirements 11.5**

- [x] 13.3 Write unit tests for database initialization
  - Test first-time database creation
  - Test schema verification on existing database
  - Test error handling for incompatible schema
  - _Requirements: 11.1, 11.3, 11.4_

- [x] 14. Implement Error Handling Patterns
  - Add transaction wrapper pattern for atomic operations
  - Add graceful degradation pattern for cleanup operations
  - Add validation pattern for novel existence checks
  - Implement consistent error message formatting
  - Add proper exit codes for all error conditions
  - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 20.3, 20.4, 20.5_

- [x] 14.1 Write property test for transaction rollback
  - **Property 24: Transaction Rollback on Failure**
  - **Validates: Requirements 14.5, 20.5**

- [x] 14.2 Write property test for error message format
  - **Property 29: Novel Not Found Error Format**
  - **Validates: Requirements 14.2**

- [x] 14.3 Write property test for database error messages
  - **Property 28: Database Error Message Clarity**
  - **Validates: Requirements 14.1**

- [x] 14.4 Write unit tests for error handling
  - Test transaction rollback on failure
  - Test error message formats
  - Test exit codes
  - Test foreign key constraint error messages
  - _Requirements: 14.3, 14.4_

- [x] 15. Implement Backward Compatibility Support
  - Verify legacy chapter processing works without novel_id
  - Test legacy file path handling
  - Test legacy chapter map generation
  - Verify NULL novel_id handling in all queries
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

- [x] 15.1 Write property test for legacy chapter processing
  - **Property 14: Legacy Chapter Inclusion**
  - **Validates: Requirements 10.3**

- [x] 15.2 Write unit tests for backward compatibility
  - Test transform without novel_id
  - Test render without novel_id
  - Test pipeline status without novel_id
  - Test legacy file paths
  - _Requirements: 10.1, 10.2, 10.4, 10.5_

- [x] 16. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 17. Integration Testing and Documentation
  - Run end-to-end integration tests for complete workflows
  - Test multi-novel isolation (processing one doesn't affect others)
  - Verify database-filesystem consistency
  - Update CLI help text and command documentation
  - Create migration guide for existing users
  - _Requirements: All requirements_

- [x] 18. Update Main Documentation Files
  - Update `README.md` with new CLI commands and workflow
  - Update `docs/CLI_GUIDE.md` with novel management commands
  - Update `docs/ARCHITECTURE.md` with database-first design
  - Update `docs/API_DOCUMENTATION.md` to reflect CLI-backend consistency
  - Add examples for common workflows (ingest → transform → render)
  - Document database schema and relationships
  - Add troubleshooting section for common issues
  - _Requirements: All requirements_

- [x] 18.1 Write documentation validation tests
  - Test that all CLI commands mentioned in docs exist
  - Test that all code examples in docs are valid
  - Test that all file paths in docs are correct

- [x] 19. Update Steering Files
  - Update `.kiro/steering/tech.md` with database-first patterns
  - Update `.kiro/steering/structure.md` with new CLI structure
  - Update `.kiro/steering/product.md` with multi-novel workflow
  - Create `.kiro/steering/cli-patterns.md` for CLI development guidelines
  - Document transaction safety patterns
  - Document error handling patterns
  - Document backward compatibility requirements
  - _Requirements: All requirements_

- [x] 20. Update Issue Tracking
  - Update `docs/ISSUES.md` with CLI migration completion
  - Document any known limitations or edge cases
  - Add migration notes for existing users
  - Document breaking changes (if any)
  - Add performance benchmarks for database operations
  - _Requirements: All requirements_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- All code examples use Python with Typer, Rich, and Hypothesis libraries
- DatabaseManager singleton pattern ensures thread-safe database access
- Transaction safety is critical for all database operations
