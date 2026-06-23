# Design Document: Phase 7 - The Librarian

## Overview

Phase 7: The Librarian transforms BABEL from a single-novel processor into a comprehensive multi-novel library management system. This design introduces a database-backed library architecture that enables users to manage multiple webnovels, fetch external metadata, and navigate between books through a visual bookshelf interface.

The system maintains strict backward compatibility with existing single-novel workflows while introducing new library-centric capabilities. The architecture follows a three-tier design: database layer (SQLite with novel/chapter relationships), API layer (FastAPI REST endpoints), and presentation layer (React SPA with bookshelf UI).

Key design principles:
- Backward compatibility: Existing chapters with NULL novel_id continue to work
- Idempotent operations: Safe re-runs and concurrent processing
- Separation of concerns: Clear boundaries between library management, pipeline processing, and UI
- Progressive enhancement: Single-novel users see no library UI, multi-novel users get full bookshelf

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     React Frontend (babel-ui)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Library    │  │    Reader    │  │   Settings   │      │
│  │   /library   │  │  /chapter/N  │  │    Modal     │      │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘      │
└─────────┼──────────────────┼──────────────────────────────────┘
          │                  │
          │ HTTP/REST        │ HTTP/REST
          │                  │
┌─────────▼──────────────────▼──────────────────────────────────┐
│              FastAPI Server (babel_server.py)                  │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │  Library Router  │  │  Chapter Router  │                  │
│  │  /api/library/*  │  │  /api/chapter/*  │                  │
│  └────────┬─────────┘  └────────┬─────────┘                  │
│           │                     │                             │
│  ┌────────▼─────────────────────▼─────────┐                  │
│  │       DatabaseManager (Singleton)       │                  │
│  │     Thread-safe SQLite connections      │                  │
│  └────────┬─────────────────────┬─────────┘                  │
└───────────┼─────────────────────┼────────────────────────────┘
            │                     │
            │                     │
┌───────────▼─────────────────────▼────────────────────────────┐
│                   SQLite Database (babel.db)                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐               │
│  │  novels  │  │ chapters │  │ pipeline_state│               │
│  │  table   │  │  table   │  │     table     │               │
│  └──────────┘  └──────────┘  └──────────────┘               │
└───────────────────────────────────────────────────────────────┘
```

### Data Flow

**Novel Import Flow:**
1. User uploads EPUB via POST /api/library/import
2. Server extracts metadata (title, author) from EPUB
3. Server creates Novel_Entry in database
4. Server invokes sanitization pipeline with novel_id
5. Sanitizer extracts chapters and associates with novel_id
6. Server returns novel_id and status to frontend

**Metadata Fetching Flow:**
1. User triggers metadata fetch via POST /api/library/{id}/metadata
2. Server queries external API (NovelUpdates or RoyalRoad)
3. Server downloads cover image to data/covers/{novel_id}.jpg
4. Server updates Novel_Entry with cover_url, synopsis, tags
5. Server returns updated metadata to frontend

**Novel Selection Flow:**
1. User clicks novel card in bookshelf
2. Frontend fetches chapters via GET /api/library/{id}/chapters
3. Frontend updates sidebar with novel's chapter list
4. Frontend navigates to first chapter
5. Frontend stores novel_id in reading progress

### Component Interactions

**DatabaseManager (Singleton):**
- Thread-local connections for concurrent access
- Context manager for automatic transaction handling
- CRUD operations for novels, chapters, pipeline state
- Foreign key enforcement with cascade deletes

**Library Router (FastAPI):**
- Novel CRUD endpoints (create, read, list, delete)
- Metadata fetching with external API integration
- Cover art upload and storage
- Chapter association queries

**Bookshelf Component (React):**
- Responsive grid layout (3-5 columns)
- Novel cards with cover art, title, author, status
- Placeholder images for missing covers
- Navigation to reader on card click

**Context Switcher:**
- "Back to Library" button in sidebar
- Reading position persistence
- Novel-specific chapter list filtering
- URL-based navigation (/library vs /chapter/{id})

## Components and Interfaces

### Database Layer

#### DatabaseManager Class

```python
class DatabaseManager:
    """
    Thread-safe singleton database manager for BABEL.
    
    Provides CRUD operations for novels, chapters, and pipeline state.
    Uses thread-local connections for concurrent access.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __init__(self, db_path: Path = Path("data/babel.db")):
        """Initialize database and create schema if needed."""
        self.db_path = db_path
        self._local = threading.local()
        self._create_tables()
    
    @property
    def connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self.connection
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    
    # Novel operations
    def create_novel(self, title: str, author: str = None, 
                    cover_url: str = None, status: str = "active") -> int:
        """Create a new novel entry and return novel_id."""
        pass
    
    def get_novel(self, novel_id: int) -> Optional[Dict]:
        """Get novel by ID."""
        pass
    
    def list_novels(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """List all novels sorted by updated_at descending."""
        pass
    
    def update_novel(self, novel_id: int, **kwargs) -> bool:
        """Update novel metadata."""
        pass
    
    def delete_novel(self, novel_id: int) -> bool:
        """Delete novel and cascade delete chapters."""
        pass
    
    # Chapter operations
    def get_chapters_by_novel(self, novel_id: int) -> List[Dict]:
        """Get all chapters for a novel."""
        pass
    
    def update_chapter_novel(self, chapter_id: int, novel_id: int) -> bool:
        """Associate a chapter with a novel."""
        pass
```

#### Database Schema

```sql
-- Novels table
CREATE TABLE IF NOT EXISTS novels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT,
    cover_url TEXT,
    synopsis TEXT,
    tags TEXT,  -- JSON array
    status TEXT DEFAULT 'active',  -- active, completed, dropped
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chapters table (extended)
CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER,  -- NULL for backward compatibility
    chapter_index INTEGER NOT NULL,
    filename TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE
);

-- Pipeline state table (extended)
CREATE TABLE IF NOT EXISTS pipeline_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER,  -- NULL for legacy single-novel
    phase TEXT NOT NULL,  -- sanitize, transform, render
    status TEXT NOT NULL,  -- pending, running, complete, failed
    last_chapter INTEGER,
    total_chapters INTEGER,
    error_message TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (novel_id) REFERENCES novels(id) ON DELETE CASCADE,
    UNIQUE(novel_id, phase)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_chapters_novel ON chapters(novel_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_novel ON pipeline_state(novel_id);
CREATE INDEX IF NOT EXISTS idx_novels_updated ON novels(updated_at DESC);
```

### API Layer

#### Library Router

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/library", tags=["library"])

class NovelResponse(BaseModel):
    id: int
    title: str
    author: Optional[str]
    cover_url: Optional[str]
    synopsis: Optional[str]
    tags: List[str]
    status: str
    chapter_count: int
    created_at: str
    updated_at: str

class NovelListResponse(BaseModel):
    novels: List[NovelResponse]
    total: int

class ImportResponse(BaseModel):
    novel_id: int
    title: str
    chapters_extracted: int
    status: str

class MetadataRequest(BaseModel):
    source: str  # "novelupdates" or "royalroad"
    search_query: Optional[str]  # Override title for search

@router.post("/import", response_model=ImportResponse)
async def import_epub(file: UploadFile = File(...)):
    """
    Import EPUB file and create novel entry.
    
    Steps:
    1. Save uploaded file to temp location
    2. Extract metadata (title, author) from EPUB
    3. Create novel entry in database
    4. Run sanitization pipeline with novel_id
    5. Return novel_id and status
    """
    pass

@router.get("/", response_model=NovelListResponse)
async def list_novels(limit: int = 100, offset: int = 0):
    """List all novels sorted by updated_at descending."""
    pass

@router.get("/{novel_id}", response_model=NovelResponse)
async def get_novel(novel_id: int):
    """Get single novel by ID."""
    pass

@router.delete("/{novel_id}")
async def delete_novel(novel_id: int):
    """Delete novel and cascade delete chapters."""
    pass

@router.post("/{novel_id}/metadata")
async def fetch_metadata(novel_id: int, request: MetadataRequest):
    """
    Fetch metadata from external source.
    
    Steps:
    1. Query external API (NovelUpdates or RoyalRoad)
    2. Download cover image
    3. Update novel entry
    4. Return updated metadata
    """
    pass

@router.post("/{novel_id}/cover")
async def upload_cover(novel_id: int, file: UploadFile = File(...)):
    """
    Upload custom cover art.
    
    Steps:
    1. Validate file type (jpg, png, webp)
    2. Resize to 400x600px
    3. Save to data/covers/{novel_id}.jpg
    4. Update novel entry
    """
    pass

@router.get("/{novel_id}/chapters")
async def get_novel_chapters(novel_id: int):
    """Get all chapters for a novel."""
    pass
```

#### External Metadata Clients

```python
class MetadataClient(ABC):
    """Abstract base class for metadata fetching."""
    
    @abstractmethod
    async def search(self, title: str) -> Optional[Dict]:
        """Search for novel by title."""
        pass
    
    @abstractmethod
    async def get_cover_url(self, novel_id: str) -> Optional[str]:
        """Get cover image URL."""
        pass

class NovelUpdatesClient(MetadataClient):
    """Client for NovelUpdates API."""
    
    BASE_URL = "https://www.novelupdates.com/api"
    
    async def search(self, title: str) -> Optional[Dict]:
        """
        Search NovelUpdates for novel.
        
        Returns:
            {
                "title": str,
                "author": str,
                "cover_url": str,
                "synopsis": str,
                "tags": List[str],
                "status": str
            }
        """
        pass

class RoyalRoadClient(MetadataClient):
    """Client for RoyalRoad API."""
    
    BASE_URL = "https://www.royalroad.com/api"
    
    async def search(self, title: str) -> Optional[Dict]:
        """Search RoyalRoad for novel."""
        pass
```

### Frontend Layer

#### Library Page Component

```typescript
// pages/Library.tsx
interface Novel {
  id: number;
  title: string;
  author?: string;
  cover_url?: string;
  synopsis?: string;
  tags: string[];
  status: string;
  chapter_count: number;
}

export function Library() {
  const { data: novels, isLoading } = useQuery({
    queryKey: ['novels'],
    queryFn: () => api.get<NovelListResponse>('/api/library')
  });
  
  const navigate = useNavigate();
  
  const handleNovelClick = (novel: Novel) => {
    // Fetch first chapter for this novel
    api.get(`/api/library/${novel.id}/chapters`)
      .then(chapters => {
        if (chapters.length > 0) {
          navigate(`/chapter/${chapters[0].id}`);
        }
      });
  };
  
  return (
    <div className="library-container">
      <h1>Your Library</h1>
      <div className="novel-grid">
        {novels?.novels.map(novel => (
          <NovelCard 
            key={novel.id}
            novel={novel}
            onClick={() => handleNovelClick(novel)}
          />
        ))}
      </div>
    </div>
  );
}
```

#### Novel Card Component

```typescript
// components/library/NovelCard.tsx
interface NovelCardProps {
  novel: Novel;
  onClick: () => void;
}

export function NovelCard({ novel, onClick }: NovelCardProps) {
  const coverUrl = novel.cover_url || '/placeholder-cover.png';
  
  return (
    <div className="novel-card" onClick={onClick}>
      <img 
        src={coverUrl} 
        alt={novel.title}
        className="novel-cover"
      />
      <div className="novel-info">
        <h3>{novel.title}</h3>
        {novel.author && <p className="author">{novel.author}</p>}
        <span className="status">{novel.status}</span>
        <span className="chapter-count">{novel.chapter_count} chapters</span>
      </div>
    </div>
  );
}
```

#### Context Switcher Component

```typescript
// components/layout/ContextSwitcher.tsx
export function ContextSwitcher() {
  const location = useLocation();
  const navigate = useNavigate();
  const { currentNovelId } = useReadingProgress();
  
  const isInReader = location.pathname.startsWith('/chapter');
  
  if (!isInReader) return null;
  
  return (
    <button 
      className="back-to-library"
      onClick={() => navigate('/library')}
    >
      ← Back to Library
    </button>
  );
}
```

#### Import Modal Component

```typescript
// components/modals/ImportModal.tsx
export function ImportModal({ isOpen, onClose }: ModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  
  const handleImport = async () => {
    if (!file) return;
    
    setImporting(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await api.post('/api/library/import', formData);
      toast.success(`Imported: ${response.title}`);
      onClose();
    } catch (error) {
      toast.error('Import failed');
    } finally {
      setImporting(false);
    }
  };
  
  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <h2>Import EPUB</h2>
      <input 
        type="file" 
        accept=".epub"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
      />
      <button onClick={handleImport} disabled={!file || importing}>
        {importing ? 'Importing...' : 'Import'}
      </button>
    </Modal>
  );
}
```

## Data Models

### Novel Model

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class Novel(BaseModel):
    """Novel entity with metadata."""
    
    id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=500)
    author: Optional[str] = Field(None, max_length=200)
    cover_url: Optional[str] = Field(None, max_length=1000)
    synopsis: Optional[str] = Field(None, max_length=5000)
    tags: List[str] = Field(default_factory=list)
    status: str = Field(default="active", pattern="^(active|completed|dropped)$")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Return of the Mount Hua Sect",
                "author": "Biga",
                "status": "active",
                "tags": ["martial arts", "regression", "action"]
            }
        }
```

### Chapter Model (Extended)

```python
class Chapter(BaseModel):
    """Chapter entity with novel association."""
    
    id: Optional[int] = None
    novel_id: Optional[int] = None  # NULL for backward compatibility
    chapter_index: int = Field(..., ge=1)
    filename: str = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=500)
    created_at: Optional[datetime] = None
```

### Pipeline State Model (Extended)

```python
class PipelineState(BaseModel):
    """Pipeline processing state for a novel."""
    
    id: Optional[int] = None
    novel_id: Optional[int] = None  # NULL for legacy
    phase: str = Field(..., pattern="^(sanitize|transform|render)$")
    status: str = Field(..., pattern="^(pending|running|complete|failed)$")
    last_chapter: Optional[int] = None
    total_chapters: Optional[int] = None
    error_message: Optional[str] = None
    updated_at: Optional[datetime] = None
```

### Metadata Response Models

```python
class ExternalMetadata(BaseModel):
    """Metadata fetched from external source."""
    
    title: str
    author: Optional[str]
    cover_url: Optional[str]
    synopsis: Optional[str]
    tags: List[str]
    status: str
    source: str  # "novelupdates" or "royalroad"

class CoverUploadResponse(BaseModel):
    """Response for cover upload."""
    
    novel_id: int
    cover_url: str
    message: str
```


## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system - essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Cascade Deletion Integrity

*For any* novel with associated chapters, when the novel is deleted from the database, all associated chapters and files should be automatically deleted, leaving no orphaned records.

**Validates: Requirements 1.3, 3.7**

### Property 2: EPUB Import Creates Novel Entry

*For any* valid EPUB file with metadata, when imported via the API, the system should create a novel entry in the database with the extracted title and author.

**Validates: Requirements 2.1, 2.3**

### Property 3: EPUB Import Associates Chapters

*For any* EPUB file that is successfully imported, all extracted chapters should be associated with the created novel's ID in the database.

**Validates: Requirements 2.4, 2.5**

### Property 4: Import Failure Rollback

*For any* EPUB import that fails during processing, the system should rollback all database changes, leaving no partial novel or chapter entries.

**Validates: Requirements 2.7**

### Property 5: Novel List Sorting

*For any* set of novels in the database, when retrieved via GET /api/library, the results should be sorted by updated_at timestamp in descending order (newest first).

**Validates: Requirements 3.2**

### Property 6: Invalid Novel ID Returns 404

*For any* novel ID that does not exist in the database, API requests to GET /api/library/{id} or GET /api/library/{id}/chapters should return HTTP 404 status.

**Validates: Requirements 3.5**

### Property 7: Metadata Update Completeness

*For any* successful metadata fetch from external sources, the novel entry should be updated with all available fields (cover_url, synopsis, tags, status).

**Validates: Requirements 4.4**

### Property 8: Cover Image Storage

*For any* successful cover image download, the file should be stored locally at data/covers/{novel_id}.jpg and the novel's cover_url field should be updated.

**Validates: Requirements 4.6**

### Property 9: Novel Display Completeness

*For any* novel rendered in the frontend, the display should include all core fields: cover art (or placeholder), title, author (if present), and status.

**Validates: Requirements 5.4**

### Property 10: Reading Position Persistence

*For any* navigation between library and reader views, the system should persist the current reading position and restore it when returning to the same novel.

**Validates: Requirements 6.3, 6.4**

### Property 11: Chapter List Isolation

*For any* novel selection from the bookshelf, the sidebar chapter list should update to show only that novel's chapters, clearing any previous novel's chapter cache.

**Validates: Requirements 7.2, 7.4**

### Property 12: Legacy Chapter Compatibility

*For any* chapter with NULL novel_id, the system should treat it as belonging to a default legacy novel and allow access through both legacy (/chapter/{id}) and new URL patterns.

**Validates: Requirements 8.1, 8.3**

### Property 13: Pipeline Novel Association

*For any* chapter processed through the transformation pipeline, the output should be correctly associated with the specified novel_id, and pipeline state should track progress separately for each novel.

**Validates: Requirements 9.2, 9.3**

### Property 14: Concurrent Processing Prevention

*For any* novel currently being processed, attempts to start another processing job for the same novel should be rejected until the first job completes.

**Validates: Requirements 9.5**

### Property 15: Cover Upload Validation and Processing

*For any* valid image file (jpg, png, webp) uploaded as cover art, the system should validate the file type, resize it to 400x600px maintaining aspect ratio, save it to data/covers/{novel_id}.jpg, and update the novel's cover_url field.

**Validates: Requirements 10.2, 10.3, 10.4, 10.5**

## Error Handling

### Database Errors

**Connection Failures:**
- Retry with exponential backoff (3 attempts)
- Log error with full context
- Return HTTP 503 Service Unavailable to client

**Constraint Violations:**
- Foreign key violations: Return HTTP 400 with descriptive message
- Unique constraint violations: Return HTTP 409 Conflict
- Rollback transaction automatically

**Transaction Deadlocks:**
- Automatic retry with jitter (up to 3 attempts)
- Log deadlock occurrence for monitoring
- If all retries fail, return HTTP 503

### API Errors

**Invalid Input:**
- Validate all request bodies with Pydantic
- Return HTTP 422 with detailed validation errors
- Include field-level error messages

**Resource Not Found:**
- Return HTTP 404 with clear error message
- Include resource type and ID in message
- Example: "Novel with ID 123 not found"

**External API Failures:**
- Timeout after 10 seconds
- Return HTTP 504 Gateway Timeout
- Log external API errors for debugging
- Graceful degradation: Continue without metadata

**File Upload Errors:**
- Validate file size (max 10MB)
- Validate file type before processing
- Return HTTP 413 for oversized files
- Return HTTP 415 for unsupported media types
- Clean up temporary files on error

### Frontend Errors

**Network Errors:**
- Display toast notification with retry option
- Implement exponential backoff for retries
- Show offline indicator if persistent

**Loading States:**
- Display skeleton loaders during data fetch
- Show progress indicators for long operations
- Timeout after 30 seconds with error message

**Navigation Errors:**
- Redirect to 404 page for invalid routes
- Preserve navigation history for back button
- Log navigation errors for debugging

## Testing Strategy

### Dual Testing Approach

The testing strategy employs both unit tests and property-based tests to ensure comprehensive coverage:

**Unit Tests:**
- Specific examples demonstrating correct behavior
- Edge cases (empty lists, NULL values, boundary conditions)
- Error conditions (invalid inputs, missing resources)
- Integration points between components
- API endpoint contracts

**Property-Based Tests:**
- Universal properties across all inputs
- Randomized test data generation (novels, chapters, metadata)
- Minimum 100 iterations per property test
- Each test tagged with: **Feature: phase-7-librarian, Property {N}: {property_text}**

### Test Coverage by Component

**Database Layer (babel/data/db.py):**
- Unit tests: Schema creation, CRUD operations, transaction handling
- Property tests: Cascade deletion, concurrent access, data integrity
- Target: 95%+ code coverage

**API Layer (babel_server.py):**
- Unit tests: Endpoint responses, error codes, request validation
- Property tests: Novel sorting, ID validation, metadata updates
- Integration tests: Full import flow, metadata fetching
- Target: 90%+ code coverage

**Frontend Layer (babel-ui/src):**
- Unit tests: Component rendering, event handlers, API calls
- Property tests: Display completeness, state persistence
- E2E tests: User flows (import, browse, read, switch novels)
- Target: 85%+ code coverage

### Property-Based Testing Configuration

**Library:** Hypothesis (Python), fast-check (TypeScript)

**Configuration:**
```python
# pytest.ini
[pytest]
hypothesis_profile = default

[hypothesis]
max_examples = 100
deadline = 5000  # 5 seconds per test
```

**Example Property Test:**
```python
from hypothesis import given, strategies as st
from babel.data.db import DatabaseManager

@given(
    novel_title=st.text(min_size=1, max_size=500),
    chapter_count=st.integers(min_value=1, max_value=100)
)
def test_cascade_deletion_property(novel_title, chapter_count):
    """
    Feature: phase-7-librarian, Property 1: Cascade Deletion Integrity
    
    For any novel with associated chapters, when the novel is deleted,
    all associated chapters should be automatically deleted.
    """
    db = DatabaseManager()
    
    # Create novel
    novel_id = db.create_novel(title=novel_title)
    
    # Create chapters
    for i in range(chapter_count):
        db.create_chapter(
            novel_id=novel_id,
            chapter_index=i + 1,
            filename=f"Ch_{i+1:03d}.txt"
        )
    
    # Verify chapters exist
    chapters_before = db.get_chapters_by_novel(novel_id)
    assert len(chapters_before) == chapter_count
    
    # Delete novel
    db.delete_novel(novel_id)
    
    # Verify all chapters deleted
    chapters_after = db.get_chapters_by_novel(novel_id)
    assert len(chapters_after) == 0
```

### Testing Priorities

**Critical Path (Must Test):**
1. Database schema creation and migrations
2. EPUB import and novel creation
3. Cascade deletion integrity
4. API endpoint contracts
5. Frontend navigation flows

**Important (Should Test):**
1. Metadata fetching and storage
2. Cover art upload and processing
3. Reading position persistence
4. Concurrent processing prevention
5. Error handling and rollback

**Nice to Have (Can Test):**
1. Performance under load
2. UI responsiveness
3. Accessibility compliance
4. Browser compatibility
