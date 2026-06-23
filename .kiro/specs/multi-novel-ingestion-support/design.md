# Design Document: Multi-Novel Ingestion Support

## Overview

This design implements proper multi-novel support in BABEL's ingestion API by ensuring that each uploaded novel creates a database entry, associates all extracted chapters with a novel_id, and organizes files in novel-specific subdirectories. The design maintains backward compatibility with existing chapters that have NULL novel_id values.

The core changes involve:
1. Modifying the `/api/ingest` endpoint to create novel entries and extract titles from filenames
2. Updating PipelineOrchestrator to accept novel_id and create novel-specific directory structures
3. Creating novel-specific chapter maps
4. Adding new API endpoints for novel listing and chapter filtering
5. Maintaining backward compatibility for legacy data

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Server                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /api/ingest                                          │  │
│  │  - Extract title from filename                        │  │
│  │  - Create novel entry                                 │  │
│  │  - Pass novel_id to pipeline                          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  /api/novels                                          │  │
│  │  - List all novels                                    │  │
│  │  - Get novel details                                  │  │
│  │  - Get chapters by novel                              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                  PipelineOrchestrator                       │
│  - Accepts novel_id parameter                               │
│  - Creates novel-specific directories                       │
│  - Tracks state per novel                                   │
│  - Generates novel-specific chapter maps                    │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    DatabaseManager                          │
│  - novels table (id, title, author, status, ...)           │
│  - chapters table (id, novel_id FK, chapter_index, ...)    │
│  - pipeline_state table (id, novel_id FK, phase, ...)      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    File System                              │
│  data/clean/novel_{id}/chapter_*.txt                        │
│  data/json/novel_{id}/chapter_*.json                        │
│  data/render/novel_{id}/chapter_*.html                      │
│  config/chapter_map_novel_{id}.json                         │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. User uploads file via `/api/ingest`
2. Ingestion API extracts title from filename
3. Ingestion API creates novel entry in database, receives novel_id
4. Ingestion API initializes PipelineOrchestrator with novel_id
5. PipelineOrchestrator creates novel-specific directories
6. PipelineOrchestrator processes chapters, storing files in novel_{id} subdirectories
7. PipelineOrchestrator creates chapter_map_novel_{id}.json
8. PipelineOrchestrator updates pipeline_state with novel_id
9. Frontend queries `/api/novels` to list novels
10. Frontend queries `/api/novels/{novel_id}/chapters` to get chapters

## Components and Interfaces

### 1. Metadata Extraction Module

**Purpose:** Extract novel metadata (title, author) from uploaded files, prioritizing internal metadata over filename parsing.

**Interface:**
```python
def extract_metadata_from_epub(file_path: Path) -> dict:
    """
    Extract metadata from EPUB file's content.opf.
    
    Reads Dublin Core metadata:
    - dc:title → novel title
    - dc:creator → author name
    
    Args:
        file_path: Path to EPUB file
        
    Returns:
        dict with 'title' and 'author' keys (None if not found)
    """

def extract_title_from_filename(filename: str) -> str:
    """
    Extract novel title from filename (fallback method).
    
    Handles common patterns:
    - "Lord of Mysteries - Book 1.epub" → "Lord of Mysteries"
    - "infinite_mage_chapter_1.txt" → "Infinite Mage Chapter 1"
    - "my-novel.epub" → "My Novel"
    
    Args:
        filename: The uploaded filename
        
    Returns:
        Cleaned title string
    """

def extract_metadata(file_path: Path, filename: str) -> dict:
    """
    Extract metadata with fallback strategy.
    
    Strategy:
    1. If EPUB, try reading internal Dublin Core metadata
    2. If metadata extraction fails or not EPUB, parse filename
    3. Return dict with 'title' and 'author'
    
    Args:
        file_path: Path to uploaded file
        filename: Original filename
        
    Returns:
        dict with 'title' and 'author' keys
    """
```

**Algorithm:**

**EPUB Metadata Extraction:**
1. Open EPUB as ZIP archive
2. Read META-INF/container.xml to find content.opf location
3. Parse content.opf XML
4. Extract dc:title and dc:creator from Dublin Core metadata
5. Return metadata dict

**Filename Extraction (Fallback):**
1. Remove file extension (.epub, .txt)
2. Check for " - Book " pattern and extract text before it
3. Replace underscores with spaces
4. Replace hyphens surrounded by spaces with spaces
5. Title-case the result
6. If result is empty, return original filename

**Combined Strategy:**
1. If file is EPUB, attempt EPUB metadata extraction
2. If EPUB extraction succeeds and has title, use it
3. Otherwise, fall back to filename extraction
4. Always use filename extraction for non-EPUB files

### 2. Modified Ingestion API Endpoint

**Endpoint:** `POST /api/ingest`

**Request:**
- file: UploadFile (EPUB or TXT)

**Response:**
```json
{
  "success": true,
  "novel_id": 42,
  "message": "File uploaded and ingestion started."
}
```

**Implementation Changes:**
```python
async def ingest_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    # 1. Validate file type
    # 2. Save to data/raw
    file_path = Path("data/raw") / file.filename
    
    # 3. Extract metadata (prioritize EPUB internal metadata)
    metadata = extract_metadata(file_path, file.filename)
    title = metadata['title']
    author = metadata.get('author')
    
    # 4. Create novel entry with transaction safety
    db = get_db()
    novel_id = None
    try:
        novel_id = db.create_novel(title=title, author=author, status="active")
        
        # 5. Initialize pipeline with novel_id
        orchestrator = PipelineOrchestrator(
            config=config,
            input_path=file_path,
            novel_id=novel_id
        )
        
        # 6. Create novel-specific directories
        orchestrator.initialize_directories()
        
    except Exception as e:
        # Rollback: Delete DB entry if directory creation fails
        if novel_id is not None:
            db.delete_novel(novel_id)
        raise HTTPException(status_code=500, detail=f"Failed to initialize novel: {str(e)}")
    
    # 7. Run pipeline in background
    background_tasks.add_task(run_ingestion_pipeline, novel_id, file_path)
    
    # 8. Return novel_id for tracking (not separate operation_id)
    return {
        "success": True,
        "novel_id": novel_id,
        "message": f"File {file.filename} uploaded and ingestion started."
    }
```

### 3. Modified PipelineOrchestrator

**Constructor Changes:**
```python
def __init__(
    self,
    config: PipelineConfig,
    input_path: Path,
    state_manager: Optional[JobStateManager] = None,
    rate_limiter: Optional[RateLimiter] = None,
    reporter: Optional[Reporter] = None,
    novel_id: Optional[int] = None  # NEW PARAMETER
):
    self.novel_id = novel_id
    # ... existing initialization

def initialize_directories(self):
    """
    Create novel-specific directories.
    
    Raises:
        OSError: If directory creation fails
    """
    for phase in ['clean', 'json', 'render']:
        phase_dir = self._get_phase_directory(phase)
        phase_dir.mkdir(parents=True, exist_ok=True)
```

**Directory Creation:**
```python
def _get_phase_directory(self, phase: str) -> Path:
    """
    Get the directory for a specific phase.
    
    If novel_id is set, returns data/{phase}/novel_{id}/
    Otherwise returns data/{phase}/ for backward compatibility
    
    Args:
        phase: Phase name (clean, json, render)
        
    Returns:
        Path to phase directory
    """
    base_dir = self.config.output_dir / phase
    
    if self.novel_id is not None:
        return base_dir / f"novel_{self.novel_id}"
    else:
        return base_dir
```

**Chapter Map Generation:**
```python
def _get_chapter_map_path(self) -> Path:
    """
    Get the path to the chapter map file.
    
    If novel_id is set, returns config/chapter_map_novel_{id}.json
    Otherwise returns config/chapter_map.json for backward compatibility
    
    Returns:
        Path to chapter map file
    """
    if self.novel_id is not None:
        return Path("config") / f"chapter_map_novel_{self.novel_id}.json"
    else:
        return Path("config") / "chapter_map.json"
```

**Pipeline State Updates:**
```python
def _update_pipeline_state(self, phase: str, status: str, **kwargs):
    """
    Update pipeline state with novel_id.
    
    Args:
        phase: Pipeline phase
        status: Phase status
        **kwargs: Additional state fields
    """
    db = get_db()
    db.update_pipeline_state(
        phase=phase,
        status=status,
        novel_id=self.novel_id,
        **kwargs
    )
```

### 4. Operation Tracking and Status Polling

**Purpose:** Track ingestion progress using novel_id instead of separate operation_id.

**Status Endpoint:**
```python
@app.get("/api/novels/{novel_id}/status")
async def get_novel_status(novel_id: int):
    """
    Get current processing status for a novel.
    
    Returns pipeline_state for the novel across all phases.
    """
    db = get_db()
    
    # Verify novel exists
    novel = db.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail=f"Novel {novel_id} not found")
    
    # Get pipeline state for all phases
    states = db.get_pipeline_states_by_novel(novel_id)
    
    return {
        "novel_id": novel_id,
        "title": novel['title'],
        "phases": states,
        "overall_status": _compute_overall_status(states)
    }
```

**Key Design Decision:**
- Use `novel_id` as the tracking identifier instead of a separate `operation_id`
- The `pipeline_state` table tracks status by `novel_id` and `phase`
- Multiple operations on the same novel update the same state records
- Frontend polls `/api/novels/{novel_id}/status` for progress updates

### 5. New API Endpoints

#### GET /api/novels

**Purpose:** List all novels with efficient chapter counting

**Query Parameters:**
- limit: Optional integer for pagination (default: 50)
- offset: Optional integer for pagination (default: 0)

**Response:**
```json
{
  "novels": [
    {
      "id": 1,
      "title": "Lord of Mysteries",
      "author": "Cuttlefish That Loves Diving",
      "cover_url": "/data/covers/1.jpg",
      "status": "active",
      "chapter_count": 150,
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-15T00:00:00Z"
    }
  ],
  "total": 1
}
```

**Implementation:**
```python
@app.get("/api/novels")
async def list_novels(limit: int = 50, offset: int = 0):
    db = get_db()
    
    # Single query with COUNT aggregation to avoid N+1 problem
    query = """
        SELECT n.*, COUNT(c.id) as chapter_count 
        FROM novels n 
        LEFT JOIN chapters c ON n.id = c.novel_id 
        GROUP BY n.id 
        ORDER BY n.updated_at DESC
        LIMIT ? OFFSET ?
    """
    
    novels = db.execute(query, (limit, offset)).fetchall()
    total = db.execute("SELECT COUNT(*) FROM novels").fetchone()[0]
    
    return {
        "novels": [dict(novel) for novel in novels],
        "total": total
    }
```

**Performance Note:** This implementation executes exactly 2 queries regardless of the number of novels, preventing the N+1 query problem that would occur if chapter counts were fetched individually.

#### GET /api/novels/{novel_id}

**Purpose:** Get novel details

**Response:**
```json
{
  "id": 1,
  "title": "Lord of Mysteries",
  "author": "Cuttlefish That Loves Diving",
  "cover_url": "/data/covers/1.jpg",
  "synopsis": "...",
  "tags": ["mystery", "fantasy"],
  "status": "active",
  "chapter_count": 150,
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-15T00:00:00Z"
}
```

#### GET /api/novels/{novel_id}/chapters

**Purpose:** Get all chapters for a novel

**Response:**
```json
{
  "chapters": [
    {
      "id": 1,
      "chapter_index": 1,
      "filename": "chapter_01.txt",
      "title": "Chapter 1: The Beginning",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 150,
  "novel_id": 1
}
```

#### GET /api/chapters/metadata (Modified)

**Purpose:** Get chapter metadata with optional novel filtering

**Query Parameters:**
- novel_id: Optional integer to filter by novel

**Implementation Changes:**
```python
@app.get("/api/chapters/metadata", response_model=ChapterMetadataListResponse)
async def get_chapters_metadata(
    novel_id: Optional[int] = None,
    phase: str = "transform"
):
    db = get_db()
    
    # Query database instead of scanning filesystem for performance
    if novel_id is not None:
        chapters = db.get_chapters_by_novel(novel_id)
    else:
        # Include all chapters (including legacy NULL novel_id)
        chapters = db.get_all_chapters()
    
    # Enrich with file paths
    for chapter in chapters:
        if chapter['novel_id'] is not None:
            base_path = Path(f"data/{phase}/novel_{chapter['novel_id']}")
        else:
            base_path = Path(f"data/{phase}")
        
        chapter['file_path'] = str(base_path / chapter['filename'])
    
    return ChapterMetadataListResponse(chapters=chapters, total=len(chapters))
```

## Data Models

### Novel Table Schema

```sql
CREATE TABLE novels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    cover_url TEXT,
    synopsis TEXT,
    tags TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Chapters Table Schema (Extended)

```sql
CREATE TABLE chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER,  -- NULL for backward compatibility
    chapter_index INTEGER NOT NULL,
    filename TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
)
```

### Pipeline State Table Schema (Extended)

```sql
CREATE TABLE pipeline_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER,  -- NULL for backward compatibility
    phase TEXT NOT NULL,
    status TEXT NOT NULL,
    last_chapter INTEGER,
    total_chapters INTEGER,
    error_message TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE,
    UNIQUE(novel_id, phase)
)
```

### Chapter Map JSON Structure

**Novel-Specific Format:** `config/chapter_map_novel_{id}.json`

```json
{
  "novel_id": 1,
  "title": "Lord of Mysteries",
  "chapters": [
    {
      "chapter_index": 1,
      "filename": "chapter_01.txt",
      "title": "Chapter 1: The Beginning",
      "clean_path": "data/clean/novel_1/chapter_01.txt",
      "json_path": "data/json/novel_1/chapter_01.json",
      "html_path": "data/render/novel_1/chapter_01.html"
    }
  ]
}
```

**Legacy Format:** `config/chapter_map.json` (for NULL novel_id)

```json
{
  "chapters": [
    {
      "chapter_index": 1,
      "filename": "chapter_01.txt",
      "title": "Chapter 1",
      "clean_path": "data/clean/chapter_01.txt",
      "json_path": "data/json/chapter_01.json",
      "html_path": "data/render/chapter_01.html"
    }
  ]
}
```

### File System Structure

```
data/
├── clean/
│   ├── novel_1/
│   │   ├── chapter_01.txt
│   │   └── chapter_02.txt
│   ├── novel_2/
│   │   └── chapter_01.txt
│   └── legacy_chapter.txt  # NULL novel_id
├── json/
│   ├── novel_1/
│   │   ├── chapter_01.json
│   │   └── chapter_02.json
│   ├── novel_2/
│   │   └── chapter_01.json
│   └── legacy_chapter.json  # NULL novel_id
└── render/
    ├── novel_1/
    │   ├── chapter_01.html
    │   └── chapter_02.html
    ├── novel_2/
    │   └── chapter_01.html
    └── legacy_chapter.html  # NULL novel_id

config/
├── chapter_map_novel_1.json
├── chapter_map_novel_2.json
└── chapter_map.json  # Legacy
```

## Backward Compatibility Strategy

### Database Compatibility

1. **NULL novel_id Support:** The chapters and pipeline_state tables allow NULL novel_id values
2. **Query Handling:** All queries support filtering by NULL novel_id
3. **Legacy Data Access:** Existing chapters with NULL novel_id remain accessible

### File System Compatibility

1. **Root Directory Fallback:** When novel_id is NULL, files are stored in root phase directories
2. **Chapter Map Fallback:** When novel_id is NULL, use `chapter_map.json`
3. **Directory Scanning:** The `/api/chapters/metadata` endpoint scans both root and novel-specific directories

### API Compatibility

1. **Optional Parameters:** The novel_id parameter is optional in `/api/chapters/metadata`
2. **Default Behavior:** Without novel_id, endpoints return all chapters (including legacy)
3. **Graceful Degradation:** Legacy chapters display correctly in the UI with "Unknown Novel" label


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Metadata Extraction with Fallback

*For any* uploaded file, the metadata extraction should prioritize EPUB internal Dublin Core metadata (dc:title, dc:creator) when available, fall back to filename parsing for non-EPUB files or when EPUB metadata is missing, normalize separators to spaces, remove extensions, handle " - Book " patterns, and return non-empty title and optional author.

**Validates: Requirements 1.1, 1.4, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8**

### Property 2: Novel Creation Returns ID

*For any* novel creation request with a valid title, the API should create a database entry with status "active" and return the novel_id in the response.

**Validates: Requirements 1.2, 1.3, 1.5**

### Property 3: Novel_ID Preservation Throughout Pipeline

*For any* chapter processed with a novel_id, that novel_id should be preserved in the database record, maintained through all pipeline phases (sanitize, transform, render), used in all database operations, included in the final operation status, and if directory creation fails, the novel database entry should be rolled back.

**Validates: Requirements 2.1, 2.2, 2.5, 10.1, 10.2, 10.3, 10.5, 10.6**

### Property 4: Chapter Query Filtering

*For any* novel_id, querying chapters by that novel_id should return only chapters where the chapter's novel_id matches the query parameter, and no chapters from other novels.

**Validates: Requirements 2.3, 5.2, 9.1**

### Property 5: Cascade Deletion Integrity

*For any* novel with associated chapters and pipeline state records, deleting the novel should result in all associated chapters and pipeline state records being deleted from the database.

**Validates: Requirements 2.4, 5.5**

### Property 6: Novel-Specific Directory Structure

*For any* chapter with a non-NULL novel_id, processing through all phases should store files in novel-specific subdirectories: `data/clean/novel_{id}/`, `data/json/novel_{id}/`, and `data/render/novel_{id}/`.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 10.4**

### Property 7: Chapter Map Novel Association

*For any* novel_id, processing should create a chapter map file named `chapter_map_novel_{id}.json` that includes the novel_id in its metadata section, and loading that chapter map should verify the novel_id matches the requested novel.

**Validates: Requirements 4.1, 4.2, 4.3**

### Property 8: Pipeline State Isolation

*For any* two different novel_ids processing concurrently, updating pipeline state for one novel should not affect the pipeline state of the other novel, and querying state by novel_id should return only that novel's state.

**Validates: Requirements 5.1, 5.3, 5.4**

### Property 9: Novel List Ordering

*For any* set of novels with different updated_at timestamps, the `/api/novels` endpoint should return them sorted by updated_at in descending order (newest first).

**Validates: Requirements 6.2**

### Property 10: Novel Response Completeness

*For any* novel returned by `/api/novels` or `/api/novels/{novel_id}`, the response should include all required fields: id, title, author, cover_url, status, chapter_count (calculated via SQL aggregation), created_at, and updated_at.

**Validates: Requirements 6.3, 6.4, 7.2, 7.4, 7.5**

### Property 11: Pagination Correctness

*For any* limit and offset values, the `/api/novels` endpoint should return exactly `limit` novels starting from position `offset` in the sorted list, or fewer if there aren't enough novels remaining.

**Validates: Requirements 6.5**

### Property 12: Invalid Novel ID Error Handling

*For any* invalid or non-existent novel_id, the endpoints `/api/novels/{novel_id}` and `/api/novels/{novel_id}/chapters` should return a 404 HTTP status code with a descriptive error message.

**Validates: Requirements 7.3, 8.3, 9.4**

### Property 13: Chapter List Ordering

*For any* novel with multiple chapters, the `/api/novels/{novel_id}/chapters` endpoint should return chapters ordered by chapter_index in ascending order.

**Validates: Requirements 8.2**

### Property 14: Chapter Response Completeness

*For any* chapter returned by `/api/novels/{novel_id}/chapters` or `/api/chapters/metadata`, the response should include all required fields: id, chapter_index, filename, title, novel_id, and created_at.

**Validates: Requirements 8.5, 9.3**

### Property 15: Metadata Endpoint Database Querying

*For any* call to `/api/chapters/metadata` with a novel_id parameter, the system should query the chapters table in the database (not scan filesystem) and return only chapters belonging to that novel; without a novel_id parameter, all chapters (including legacy chapters with NULL novel_id) should be returned from the database.

**Validates: Requirements 9.1, 9.2, 9.5, 11.4**

### Property 16: Operation Status Tracking

*For any* novel being processed, querying `/api/novels/{novel_id}/status` should return the current pipeline state including phase, status, progress, and error messages, using the novel_id as the tracking key.

**Validates: Requirements 13.1, 13.2, 13.3, 13.4, 13.5**

### Property 17: Backward Compatibility for NULL Novel_ID

*For any* chapter with NULL novel_id, the system should store files in root phase directories (without novel_{id} subdirectories), support loading from `chapter_map.json`, return those chapters in unfiltered queries, and allow querying specifically for NULL novel_id chapters.

**Validates: Requirements 3.5, 11.1, 11.2, 11.3**

### Property 18: Chapter Map Format Support

*For any* chapter map load operation, the system should successfully load both the legacy format (`chapter_map.json` without novel_id metadata) and the novel-specific format (`chapter_map_novel_{id}.json` with novel_id metadata).

**Validates: Requirements 4.5, 11.3**

## Error Handling

### Technical Considerations

#### 1. Metadata Extraction Strategy
The design prioritizes EPUB internal metadata (Dublin Core) over filename parsing to handle messy filenames like `684151.epub` or `temp_print_export.epub`. This significantly reduces manual renaming needs.

#### 2. N+1 Query Prevention
The `/api/novels` endpoint uses SQL COUNT aggregation with LEFT JOIN to calculate chapter counts in a single query, preventing performance degradation as the library grows.

#### 3. Transaction Atomicity
The ingestion flow wraps database creation and directory initialization in try/except blocks. If directory creation fails after the DB entry is created, the entry is explicitly deleted to prevent "ghost" novels.

#### 4. Operation Tracking
The design uses `novel_id` as the tracking key instead of a separate `operation_id`. The `pipeline_state` table tracks status by `(novel_id, phase)`, supporting status polling via `/api/novels/{novel_id}/status`.

#### 5. Database-First Metadata Retrieval
The `/api/chapters/metadata` endpoint queries the `chapters` table instead of scanning the filesystem, providing better performance for novels with thousands of chapters.

### Title Extraction Errors

- **Empty Filename:** If the filename is empty or NULL, use "Untitled Novel" as the default title
- **Invalid Characters:** Strip or replace invalid filesystem characters from extracted titles
- **Encoding Issues:** Handle UTF-8 encoding errors gracefully, falling back to ASCII-safe titles

### Database Errors

- **Duplicate Titles:** Allow duplicate novel titles (novels are identified by ID, not title)
- **Foreign Key Violations:** Prevent chapter creation if novel_id doesn't exist (return 400 error)
- **Transaction Failures:** Roll back all changes if novel or chapter creation fails during ingestion
- **Cascade Delete Failures:** Log errors but complete deletion if cascade fails for some records

### File System Errors

- **Directory Creation Failures:** Return 500 error if novel-specific directories cannot be created
- **Permission Errors:** Log permission errors and return 500 error with descriptive message
- **Disk Space Errors:** Check available disk space before processing, fail early if insufficient
- **File Not Found:** Handle missing chapter files gracefully in metadata endpoints (skip or mark as missing)

### API Errors

- **Invalid Novel ID:** Return 404 with message "Novel with ID {id} not found"
- **Invalid File Type:** Return 400 with message "Only .txt and .epub files are supported"
- **Missing Parameters:** Return 400 with message describing required parameters
- **Concurrent Processing:** Return 409 if novel is already being processed (lock conflict)

### Pipeline Errors

- **Chapter Extraction Failures:** Log error, continue with other chapters, report failed count
- **Phase Processing Failures:** Update pipeline state to "failed" with error message
- **Rate Limit Errors:** Respect rate limiter, retry with exponential backoff
- **Timeout Errors:** Set reasonable timeouts for each phase, fail gracefully on timeout

## Testing Strategy

### Unit Tests

Unit tests should focus on specific examples, edge cases, and error conditions:

1. **Metadata Extraction Examples:**
   - EPUB with valid Dublin Core metadata → extract title and author
   - EPUB with missing dc:title → fall back to filename
   - EPUB with malformed content.opf → fall back to filename
   - TXT file → use filename extraction
   - "Lord of Mysteries - Book 1.epub" → "Lord of Mysteries"
   - "infinite_mage_chapter_1.txt" → "Infinite Mage Chapter 1"
   - "my-novel.epub" → "My Novel"
   - "___test___.txt" → "Test"
   - ".epub" → "Untitled Novel" (fallback)

2. **Database Edge Cases:**
   - Creating novel with NULL author
   - Creating novel with empty string title (should fail)
   - Deleting novel with no chapters
   - Querying chapters for non-existent novel_id
   - N+1 query prevention: verify single query for novel list with chapter counts
   - Transaction rollback: verify novel deletion when directory creation fails

3. **File System Edge Cases:**
   - Creating directories when parent doesn't exist
   - Handling NULL novel_id (backward compatibility)
   - Scanning empty directories
   - Loading non-existent chapter maps

4. **API Error Conditions:**
   - POST /api/ingest with invalid file type
   - POST /api/ingest with directory creation failure (verify rollback)
   - GET /api/novels/{novel_id} with negative ID
   - GET /api/novels/{novel_id}/chapters with ID 0
   - GET /api/chapters/metadata with invalid novel_id
   - GET /api/novels/{novel_id}/status for non-existent novel

### Property-Based Tests

Property-based tests should verify universal properties across all inputs. Each test should run a minimum of 100 iterations with randomized inputs.

1. **Property 1: Metadata Extraction with Fallback**
   - Generate random EPUB files with/without Dublin Core metadata and various filenames
   - Verify extracted titles and authors are correct with proper fallback behavior
   - Tag: **Feature: multi-novel-ingestion-support, Property 1: Metadata Extraction with Fallback**

2. **Property 2: Novel Creation Returns ID**
   - Generate random valid titles
   - Create novels and verify novel_id is returned and status is "active"
   - Tag: **Feature: multi-novel-ingestion-support, Property 2: Novel Creation Returns ID**

3. **Property 3: Novel_ID Preservation Throughout Pipeline**
   - Generate random novel_ids and chapters
   - Process through pipeline and verify novel_id is preserved
   - Tag: **Feature: multi-novel-ingestion-support, Property 3: Novel_ID Preservation Throughout Pipeline**

4. **Property 4: Chapter Query Filtering**
   - Generate random novels with chapters
   - Query by novel_id and verify only matching chapters returned
   - Tag: **Feature: multi-novel-ingestion-support, Property 4: Chapter Query Filtering**

5. **Property 5: Cascade Deletion Integrity**
   - Generate random novels with chapters and pipeline state
   - Delete novel and verify all associated records deleted
   - Tag: **Feature: multi-novel-ingestion-support, Property 5: Cascade Deletion Integrity**

6. **Property 6: Novel-Specific Directory Structure**
   - Generate random novel_ids and chapters
   - Process and verify files in correct novel-specific directories
   - Tag: **Feature: multi-novel-ingestion-support, Property 6: Novel-Specific Directory Structure**

7. **Property 7: Chapter Map Novel Association**
   - Generate random novel_ids
   - Create chapter maps and verify novel_id in metadata
   - Tag: **Feature: multi-novel-ingestion-support, Property 7: Chapter Map Novel Association**

8. **Property 8: Pipeline State Isolation**
   - Generate two random novel_ids
   - Process concurrently and verify states don't interfere
   - Tag: **Feature: multi-novel-ingestion-support, Property 8: Pipeline State Isolation**

9. **Property 9: Novel List Ordering**
   - Generate random novels with different updated_at timestamps
   - Query and verify descending order
   - Tag: **Feature: multi-novel-ingestion-support, Property 9: Novel List Ordering**

10. **Property 10: Novel Response Completeness**
    - Generate random novels
    - Query and verify all required fields present
    - Tag: **Feature: multi-novel-ingestion-support, Property 10: Novel Response Completeness**

11. **Property 11: Pagination Correctness**
    - Generate random novels and pagination parameters
    - Verify correct subset returned
    - Tag: **Feature: multi-novel-ingestion-support, Property 11: Pagination Correctness**

12. **Property 12: Invalid Novel ID Error Handling**
    - Generate random invalid novel_ids
    - Verify 404 responses
    - Tag: **Feature: multi-novel-ingestion-support, Property 12: Invalid Novel ID Error Handling**

13. **Property 13: Chapter List Ordering**
    - Generate random chapters with different indices
    - Query and verify ascending order
    - Tag: **Feature: multi-novel-ingestion-support, Property 13: Chapter List Ordering**

14. **Property 14: Chapter Response Completeness**
    - Generate random chapters
    - Query and verify all required fields present
    - Tag: **Feature: multi-novel-ingestion-support, Property 14: Chapter Response Completeness**

15. **Property 15: Metadata Endpoint Filtering**
    - Generate random novels and chapters
    - Test with and without novel_id parameter
    - Tag: **Feature: multi-novel-ingestion-support, Property 15: Metadata Endpoint Filtering**

16. **Property 16: Operation Status Tracking**
    - Generate random novel_ids and pipeline states
    - Verify status endpoint returns correct tracking information
    - Tag: **Feature: multi-novel-ingestion-support, Property 16: Operation Status Tracking**

17. **Property 17: Backward Compatibility for NULL Novel_ID**
    - Generate chapters with NULL novel_id
    - Verify root directory storage and query inclusion
    - Tag: **Feature: multi-novel-ingestion-support, Property 17: Backward Compatibility for NULL Novel_ID**

18. **Property 18: Chapter Map Format Support**
    - Generate both legacy and novel-specific chapter maps
    - Verify both formats load successfully
    - Tag: **Feature: multi-novel-ingestion-support, Property 18: Chapter Map Format Support**

### Integration Tests

Integration tests should verify end-to-end workflows:

1. **Complete Ingestion Flow:**
   - Upload EPUB file
   - Verify novel created
   - Verify chapters extracted and associated
   - Verify files in correct directories
   - Verify chapter map created
   - Verify pipeline state updated

2. **Multi-Novel Workflow:**
   - Upload two different novels
   - Verify both have separate directories
   - Verify chapters don't mix
   - Verify independent pipeline states

3. **Backward Compatibility:**
   - Create legacy chapters with NULL novel_id
   - Upload new novel
   - Verify both accessible
   - Verify queries work for both

4. **API Workflow:**
   - List novels
   - Get novel details
   - Get novel chapters
   - Filter chapter metadata by novel
   - Verify all data consistent

### Test Configuration

- **Property Test Iterations:** Minimum 100 per test
- **Test Database:** Use separate test database (data/babel_test.db)
- **Test Directories:** Use separate test directories (data_test/)
- **Cleanup:** Clean up test data after each test
- **Isolation:** Each test should be independent and not rely on other tests
