# BABEL API Documentation

## Multi-Novel Ingestion Support API

This document describes the REST API endpoints for managing novels, chapters, and ingestion operations in BABEL.

---

## Base URL

```
http://localhost:8000
```

---

## Novel Management Endpoints

### POST /api/library/import

Import an EPUB file and create a novel entry.

**Request:**
- Method: `POST`
- Content-Type: `multipart/form-data`
- Body: 
  - `file`: EPUB file (required)

**Response:** `200 OK`
```json
{
  "novel_id": 1,
  "title": "Lord of Mysteries",
  "chapters_extracted": 150,
  "status": "success"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid file type or missing title
- `500 Internal Server Error`: Import failed

**Behavior:**
1. Extracts metadata (title, author) from EPUB using Dublin Core metadata
2. Falls back to filename parsing if EPUB metadata is unavailable
3. Creates novel entry in database with status "active"
4. Initializes novel-specific directories (`data/clean/novel_{id}/`, etc.)
5. Extracts chapters and associates them with the novel
6. Returns `novel_id` for tracking

**Transaction Safety:**
- If directory creation fails after database entry creation, the novel entry is automatically deleted (rollback)
- Ensures no orphaned database entries

---

### GET /api/library/

List all novels in the library.

**Request:**
- Method: `GET`
- Query Parameters:
  - `limit` (optional): Maximum number of novels to return (default: 100)
  - `offset` (optional): Number of novels to skip for pagination (default: 0)

**Response:** `200 OK`
```json
{
  "novels": [
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
  ],
  "total": 1
}
```

**Performance:**
- Uses SQL COUNT aggregation with LEFT JOIN to calculate chapter counts
- Executes exactly 2 queries regardless of the number of novels (prevents N+1 query problem)
- Sorted by `updated_at` descending (newest first)

---

### GET /api/library/{novel_id}

Get details for a specific novel.

**Request:**
- Method: `GET`
- Path Parameters:
  - `novel_id`: Novel ID (integer)

**Response:** `200 OK`
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

**Error Responses:**
- `404 Not Found`: Novel with specified ID does not exist

---

### PUT /api/library/{novel_id}

Update novel metadata.

**Request:**
- Method: `PUT`
- Path Parameters:
  - `novel_id`: Novel ID (integer)
- Body:
```json
{
  "title": "Updated Title",
  "author": "Updated Author",
  "cover_url": "/data/covers/1.jpg",
  "synopsis": "Updated synopsis",
  "tags": ["tag1", "tag2"],
  "status": "completed"
}
```

**Response:** `200 OK`
```json
{
  "id": 1,
  "title": "Updated Title",
  "author": "Updated Author",
  ...
}
```

**Error Responses:**
- `404 Not Found`: Novel with specified ID does not exist
- `500 Internal Server Error`: Update failed

---

### DELETE /api/library/{novel_id}

Delete a novel and cascade delete all associated chapters.

**Request:**
- Method: `DELETE`
- Path Parameters:
  - `novel_id`: Novel ID (integer)

**Response:** `200 OK`
```json
{
  "message": "Novel 1 deleted successfully"
}
```

**Error Responses:**
- `404 Not Found`: Novel with specified ID does not exist
- `500 Internal Server Error`: Delete failed

**Behavior:**
- Cascade deletes all chapters associated with the novel
- Cascade deletes all pipeline state records associated with the novel
- Does not affect legacy chapters with NULL novel_id

---

## Chapter Management Endpoints

### GET /api/library/{novel_id}/chapters

Get all chapters for a specific novel.

**Request:**
- Method: `GET`
- Path Parameters:
  - `novel_id`: Novel ID (integer)

**Response:** `200 OK`
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

**Error Responses:**
- `404 Not Found`: Novel with specified ID does not exist

**Behavior:**
- Returns chapters ordered by `chapter_index` ascending
- Returns empty list if novel has no chapters

---

### GET /api/library/{novel_id}/chapter/{chapter_id}

Get a specific chapter from a novel.

**Request:**
- Method: `GET`
- Path Parameters:
  - `novel_id`: Novel ID (integer)
  - `chapter_id`: Chapter ID (integer)

**Response:** `200 OK`
```json
{
  "id": 1,
  "novel_id": 1,
  "chapter_index": 1,
  "filename": "chapter_01.json",
  "title": "Chapter 1: The Beginning",
  "blocks": [
    {
      "type": "dialogue",
      "character": "Klein",
      "text": "What is this place?",
      "lane": "left"
    }
  ],
  "navigation": {
    "prev": null,
    "next": 2
  },
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Error Responses:**
- `404 Not Found`: Novel or chapter does not exist, or chapter does not belong to the novel
- `500 Internal Server Error`: Failed to load chapter content

**Behavior:**
- Loads chapter content from JSON file in `data/json/`
- Calculates navigation (prev/next chapter IDs)
- Verifies chapter belongs to the specified novel

---

### DELETE /api/library/{novel_id}/chapter/{chapter_id}

Delete a specific chapter from a novel.

**Request:**
- Method: `DELETE`
- Path Parameters:
  - `novel_id`: Novel ID (integer)
  - `chapter_id`: Chapter ID (integer)

**Response:** `200 OK`
```json
{
  "message": "Chapter 1 deleted successfully"
}
```

**Error Responses:**
- `404 Not Found`: Novel or chapter does not exist, or chapter does not belong to the novel

---

## Pipeline Status Endpoints

### GET /api/library/{novel_id}/status

Get the processing status for a novel.

**Request:**
- Method: `GET`
- Path Parameters:
  - `novel_id`: Novel ID (integer)

**Response:** `200 OK`
```json
{
  "novel_id": 1,
  "title": "Lord of Mysteries",
  "overall_status": "in_progress",
  "phases": [
    {
      "phase": "sanitize",
      "status": "completed",
      "last_chapter": 150,
      "total_chapters": 150,
      "error_message": null,
      "updated_at": "2024-01-01T00:00:00Z"
    },
    {
      "phase": "transform",
      "status": "running",
      "last_chapter": 75,
      "total_chapters": 150,
      "error_message": null,
      "updated_at": "2024-01-01T01:00:00Z"
    }
  ]
}
```

**Error Responses:**
- `404 Not Found`: Novel with specified ID does not exist

**Behavior:**
- Returns pipeline state for all phases (sanitize, transform, render)
- Computes overall status from phase states:
  - `not_started`: No pipeline state records
  - `completed`: All phases completed
  - `failed`: Any phase failed
  - `running`: Any phase running
  - `in_progress`: Otherwise

**Use Case:**
- Frontend polls this endpoint to track ingestion progress
- Uses `novel_id` as the tracking key (no separate `operation_id`)

---

## Metadata Endpoints

### GET /api/chapters/metadata

Get chapter metadata with optional novel filtering.

**Request:**
- Method: `GET`
- Query Parameters:
  - `novel_id` (optional): Filter chapters by novel ID
  - `phase` (optional): Phase directory to scan (default: "transform")

**Response:** `200 OK`
```json
{
  "chapters": [
    {
      "id": 1,
      "novel_id": 1,
      "chapter_index": 1,
      "filename": "chapter_01.json",
      "title": "Chapter 1",
      "file_path": "data/json/novel_1/chapter_01.json",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 150
}
```

**Behavior:**
- **With `novel_id`**: Returns only chapters for that novel
- **Without `novel_id`**: Returns all chapters (including legacy chapters with NULL novel_id)
- Queries database instead of scanning filesystem for performance
- Enriches chapter data with file paths based on novel_id

**Performance:**
- Database query instead of filesystem scan
- Efficient for novels with thousands of chapters

---

### POST /api/library/{novel_id}/metadata

Fetch metadata from external source (NovelUpdates or RoyalRoad).

**Request:**
- Method: `POST`
- Path Parameters:
  - `novel_id`: Novel ID (integer)
- Body:
```json
{
  "source": "novelupdates",
  "search_query": "Lord of Mysteries"
}
```

**Response:** `200 OK`
```json
{
  "message": "Metadata fetched successfully",
  "source": "novelupdates",
  "metadata": {
    "title": "Lord of Mysteries",
    "author": "Cuttlefish That Loves Diving",
    "cover_url": "/data/covers/1.jpg",
    "synopsis": "...",
    "tags": ["mystery", "fantasy"],
    "status": "completed"
  }
}
```

**Error Responses:**
- `404 Not Found`: Novel not found on external source
- `400 Bad Request`: Invalid source
- `500 Internal Server Error`: Metadata fetch failed

**Behavior:**
1. Queries external API (NovelUpdates or RoyalRoad)
2. Downloads cover image to `data/covers/{novel_id}.jpg`
3. Updates novel entry with fetched metadata

---

### POST /api/library/{novel_id}/cover

Upload custom cover art for a novel.

**Request:**
- Method: `POST`
- Path Parameters:
  - `novel_id`: Novel ID (integer)
- Content-Type: `multipart/form-data`
- Body:
  - `file`: Image file (jpg, png, webp)

**Response:** `200 OK`
```json
{
  "novel_id": 1,
  "cover_url": "/data/covers/1.jpg",
  "message": "Cover uploaded successfully"
}
```

**Error Responses:**
- `404 Not Found`: Novel with specified ID does not exist
- `400 Bad Request`: Invalid file type
- `500 Internal Server Error`: Upload failed

**Behavior:**
- Validates file type (jpg, png, webp)
- Resizes image to 400x600px maintaining aspect ratio
- Saves to `data/covers/{novel_id}.jpg`
- Updates novel entry with cover URL

---

## Backward Compatibility

### Legacy Chapters (NULL novel_id)

The API maintains backward compatibility with chapters that have NULL novel_id:

1. **GET /api/chapters/metadata** (without `novel_id` parameter):
   - Returns all chapters, including legacy chapters with NULL novel_id

2. **File Organization**:
   - Legacy chapters stored in root phase directories (`data/clean/`, `data/json/`, `data/render/`)
   - New chapters stored in novel-specific subdirectories (`data/clean/novel_{id}/`, etc.)

3. **Chapter Maps**:
   - Legacy chapters use `config/chapter_map.json`
   - New chapters use `config/chapter_map_novel_{id}.json`

4. **Cascade Deletion**:
   - Deleting a novel does NOT affect legacy chapters with NULL novel_id

---

## Error Handling

### Standard Error Response Format

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

- `200 OK`: Request succeeded
- `400 Bad Request`: Invalid request parameters or body
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server-side error

### CORS

All endpoints support CORS with the following headers:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: *`
- `Access-Control-Allow-Headers: *`

---

## Rate Limiting

No rate limiting is currently enforced on API endpoints.

---

## Authentication

No authentication is currently required for API endpoints.

---

## Examples

### Complete Ingestion Workflow

```bash
# 1. Import EPUB file
curl -X POST http://localhost:8000/api/library/import \
  -F "file=@novel.epub"

# Response: {"novel_id": 1, "title": "My Novel", "chapters_extracted": 150, "status": "success"}

# 2. Poll for status
curl http://localhost:8000/api/library/1/status

# 3. List all novels
curl http://localhost:8000/api/library/

# 4. Get novel details
curl http://localhost:8000/api/library/1

# 5. Get chapters for novel
curl http://localhost:8000/api/library/1/chapters

# 6. Get specific chapter
curl http://localhost:8000/api/library/1/chapter/1
```

### Filtering Chapters by Novel

```bash
# Get all chapters for novel 1
curl "http://localhost:8000/api/chapters/metadata?novel_id=1"

# Get all chapters (including legacy)
curl "http://localhost:8000/api/chapters/metadata"
```

---

## Database Schema

### novels Table

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

### chapters Table

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

### pipeline_state Table

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

---

## File System Structure

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

data/covers/
├── 1.jpg
└── 2.jpg
```

---

## Version History

- **v1.0.0** (2024-02-18): Initial multi-novel ingestion support
  - Novel creation during ingestion
  - Chapter association with novels
  - Novel-specific file organization
  - Novel-specific chapter maps
  - Pipeline state tracking per novel
  - Novel listing and details API
  - Chapter filtering by novel
  - Transaction safety and rollback
  - Backward compatibility for legacy chapters
