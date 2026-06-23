# Design Document: Chapter Scroll Bugfix with Render Window

## Overview

This document specifies the technical design for implementing a render window for the infinite scroll chapter navigation. The render window will limit the number of chapters rendered in the DOM at any time, preventing performance issues and scroll position problems when navigating between chapters.

## Architecture

### Component Structure

```
ChapterView (Main Component)
├── RenderWindowManager (Logic for managing which chapters to render)
├── ChapterContainer (Renders individual chapter with data-chapter-id)
└── ScrollManager (Handles scroll position and navigation)
```

### State Management

```typescript
interface ChapterViewState {
  // All loaded chapters (from API)
  loadedChapters: ChapterResponse[];
  
  // Currently rendered chapters (subset of loadedChapters)
  renderedChapterIds: number[];
  
  // Current chapter ID (from URL)
  currentChapterId: number | null;
  
  // Render window configuration
  windowConfig: {
    size: number;        // Number of chapters to render (default: 5)
    paddingBefore: number; // Extra chapters to render before current (default: 2)
    paddingAfter: number;  // Extra chapters to render after current (default: 2)
  };
}
```

## Implementation Details

### 1. Render Window Manager

The RenderWindowManager will be responsible for:

1. **Calculating which chapters to render** based on the current chapter position
2. **Updating the rendered set** when the current chapter changes
3. **Coordinating with infinite scroll** to load additional chapters as needed

```typescript
function calculateRenderWindow(
  loadedChapters: ChapterResponse[],
  currentChapterId: number,
  windowSize: number = 5
): number[] {
  // Find current chapter index
  const currentIndex = loadedChapters.findIndex(ch => ch.id === currentChapterId);
  if (currentIndex === -1) {
    // Current chapter not loaded yet, return empty or partial window
    return [];
  }
  
  // Calculate window bounds
  const halfWindow = Math.floor(windowSize / 2);
  const startIndex = Math.max(0, currentIndex - halfWindow);
  const endIndex = Math.min(loadedChapters.length, startIndex + windowSize);
  
  // Adjust start if we're at the end
  const actualStart = Math.max(0, endIndex - windowSize);
  
  // Return chapter IDs in the window
  return loadedChapters
    .slice(actualStart, endIndex)
    .map(ch => ch.id);
}
```

### 2. ChapterView Component Changes

#### State Updates

```typescript
// Replace the simple chapters state with:
const [loadedChapters, setLoadedChapters] = useState<ChapterResponse[]>([]);
const [renderedChapterIds, setRenderedChapterIds] = useState<number[]>([]);

// New state for render window configuration
const [renderWindow] = useState({
  size: 5,
  paddingBefore: 2,
  paddingAfter: 2
});
```

#### Render Logic

```typescript
// Filter chapters to render based on the window
const chaptersToRender = loadedChapters.filter(ch => 
  renderedChapterIds.includes(ch.id)
);

// Sort by chapter order
chaptersToRender.sort((a, b) => {
  const aIndex = loadedChapters.findIndex(ch => ch.id === a.id);
  const bIndex = loadedChapters.findIndex(ch => ch.id === b.id);
  return aIndex - bIndex;
});
```

### 3. Window Update Logic

When the current chapter changes (via URL or navigation):

```typescript
useEffect(() => {
  if (!id) return;
  
  const targetId = Number(id);
  
  // Check if target chapter is in the render window
  const needsWindowUpdate = !renderedChapterIds.includes(targetId);
  
  if (needsWindowUpdate) {
    // Calculate new window centered on target chapter
    const newWindow = calculateRenderWindow(
      loadedChapters,
      targetId,
      renderWindow.size
    );
    
    setRenderedChapterIds(newWindow);
  }
  
  // Scroll to the chapter
  scrollToChapter(targetId);
}, [id, loadedChapters, renderWindow]);
```

### 4. Infinite Scroll Integration

The infinite scroll needs to be updated to:

1. **Load chapters** as before, adding them to `loadedChapters`
2. **Trigger window update** when new chapters are loaded
3. **Maintain the render window** around the current chapter

```typescript
// When loading next chapter
const loadNextChapter = useCallback(async () => {
  // ... existing load logic ...
  
  const nextChapter = // ... loaded from API ...
  
  setLoadedChapters(prev => {
    const newChapters = [...prev, nextChapter];
    
    // Update render window if current chapter is in the new set
    if (renderedChapterIds.includes(nextChapter.id) || 
        renderedChapterIds.length === 0) {
      const newWindow = calculateRenderWindow(
        newChapters,
        currentChapterId,
        renderWindow.size
      );
      setRenderedChapterIds(newWindow);
    }
    
    return newChapters;
  });
}, [loadedChapters, renderedChapterIds, currentChapterId, renderWindow]);
```

### 5. Scroll Position Restoration

When the render window shifts (chapters are added/removed):

```typescript
// Use a ref to track the last known scroll position
const scrollPositionRef = useRef<number>(0);

useEffect(() => {
  // Save scroll position before window update
  scrollPositionRef.current = window.scrollY;
}, [renderedChapterIds]);

useEffect(() => {
  // Restore scroll position after window update
  // The chapter container should be in the same position
  const targetElement = document.querySelector(
    `.chapter-container[data-chapter-id="${currentChapterId}"]`
  );
  
  if (targetElement) {
    targetElement.scrollIntoView({ behavior: 'auto', block: 'start' });
  }
}, [renderedChapterIds, currentChapterId]);
```

### 6. ChapterList Sidebar Integration

The ChapterList component needs to be aware of the render window to:

1. **Highlight chapters** that are currently in the render window
2. **Indicate chapters** that are loaded but not rendered

```typescript
// In ChapterListProps
interface ChapterListProps {
  chapters: Chapter[];           // All chapters from API
  activeChapterId?: number | null;
  renderedChapterIds?: number[]; // Chapters currently in render window
  loadedChapterIds?: number[];   // All loaded chapters
  className?: string;
}
```

## Performance Considerations

### Memory Management

1. **Unload chapters** outside the render window from the DOM
2. **Keep chapter data** in memory for quick re-rendering
3. **Use React.memo** for chapter components to prevent unnecessary re-renders

### Scroll Performance

1. **Debounce scroll events** for window updates
2. **Use IntersectionObserver** for detecting when to load more chapters
3. **Pre-load chapters** near the window boundaries

## Edge Cases

### 1. Current Chapter Not Loaded

When navigating to a chapter that hasn't been loaded yet:

1. Trigger the chapter to load via API
2. Show a loading state
3. Once loaded, add to `loadedChapters` and update render window
4. Scroll to the chapter

### 2. Window at Boundaries

When the render window reaches the start or end of available chapters:

1. Infinite scroll triggers to load more chapters
2. Window expands if fewer chapters are available than window size
3. Show loading indicators at boundaries

### 3. Rapid Navigation

When user rapidly clicks different chapters:

1. Debounce window updates
2. Only render the final target chapter's window
3. Cancel in-flight updates for intermediate chapters

## Testing Strategy

### Unit Tests

1. `calculateRenderWindow` function tests
2. Window update logic tests
3. Scroll position restoration tests

### Integration Tests

1. Navigation between chapters in the same window
2. Navigation to chapters outside the window
3. Infinite scroll triggering window updates
4. Rapid navigation handling

### E2E Tests

1. Click chapter in sidebar → verify scroll to correct position
2. Scroll down → verify next chapter loads and window updates
3. Scroll up → verify previous chapter loads and window updates
4. Rapid chapter clicks → verify only final chapter is rendered

## Implementation Tasks

1. Update ChapterView state management for render window
2. Implement `calculateRenderWindow` utility function
3. Update render logic to filter chapters based on window
4. Modify infinite scroll to work with render window
5. Update scroll position restoration for window changes
6. Update ChapterList to show render window status
7. Add performance optimizations (React.memo, etc.)
8. Write unit tests for render window logic
9. Write integration tests for navigation flow