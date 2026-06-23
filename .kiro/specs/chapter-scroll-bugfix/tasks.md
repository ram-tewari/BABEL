# Tasks: Chapter Scroll Bugfix with Render Window

## Overview

Implement a render window for the infinite scroll chapter navigation to prevent the page from rendering from the top when switching chapters.

## Task List

### Phase 1: Core Infrastructure

- [x] 1.1 Add render window state to ChapterView component
  - Add `loadedChapters` state to store all loaded chapters
  - Add `renderedChapterIds` state to track currently rendered chapters
  - Add `renderWindow` config with size, paddingBefore, paddingAfter

- [x] 1.2 Implement `calculateRenderWindow` utility function
  - Calculate which chapters to render based on current chapter position
  - Handle edge cases (current chapter not loaded, boundaries)
  - Write unit tests for the function

- [x] 1.3 Update ChapterView render logic
  - Filter chapters to render based on `renderedChapterIds`
  - Sort chapters by their original order in `loadedChapters`
  - Ensure chapter containers have proper `data-chapter-id` attributes

### Phase 2: Window Management

- [x] 2.1 Implement window update logic
  - Create useEffect to update window when current chapter changes
  - Calculate new window centered on target chapter
  - Update `renderedChapterIds` state

- [x] 2.2 Handle current chapter not loaded
  - Detect when target chapter is not in `loadedChapters`
  - Trigger chapter load via API
  - Show loading state while loading
  - Update window after chapter loads

- [x] 2.3 Handle window at boundaries
  - Detect when window reaches start or end of loaded chapters
  - Trigger infinite scroll to load more chapters
  - Expand window if fewer chapters available than window size

### Phase 3: Infinite Scroll Integration

- [x] 3.1 Update loadNextChapter to work with render window
  - Add new chapter to `loadedChapters`
  - Update `renderedChapterIds` if needed
  - Maintain scroll position

- [x] 3.2 Update loadPrevChapter to work with render window
  - Add new chapter to `loadedChapters` (prepend)
  - Update `renderedChapterIds` if needed
  - Restore scroll position after prepending

- [x] 3.3 Update intersection observers
  - Keep existing observers for loading more chapters
  - Add observers for render window boundaries
  - Debounce window updates

### Phase 4: Scroll Position Management

- [x] 4.1 Implement scroll position tracking
  - Save scroll position before window updates
  - Restore scroll position after window updates
  - Handle smooth scrolling for navigation

- [x] 4.2 Update scrollToChapter function
  - Scroll to chapter within render window
  - Handle case where chapter needs to load first
  - Use requestAnimationFrame for smooth scrolling

- [x] 4.3 Handle rapid navigation
  - Debounce window updates
  - Cancel in-flight updates for intermediate chapters
  - Only render final target chapter's window

### Phase 5: Sidebar Integration

- [x] 5.1 Update ChapterList props
  - Add `renderedChapterIds` prop
  - Add `loadedChapterIds` prop
  - Show visual indicator for chapters in render window

- [-] 5.2 Update ChapterList rendering
  - Highlight chapters currently in render window
  - Indicate chapters that are loaded but not rendered
  - Maintain existing read status indicators

### Phase 6: Performance Optimization

- [ ] 6.1 Add React.memo to chapter components
  - Memoize individual chapter containers
  - Prevent unnecessary re-renders

- [ ] 6.2 Optimize state updates
  - Use functional state updates
  - Batch state updates where possible
  - Avoid unnecessary re-renders

- [ ] 6.3 Memory management
  - Clean up chapter data when navigating away
  - Keep chapter data in memory for quick re-rendering
  - Implement lazy loading for chapter content

### Phase 7: Testing

- [ ] 7.1 Write unit tests for calculateRenderWindow
  - Test window calculation at boundaries
  - Test window calculation for single chapter
  - Test window calculation for multiple chapters

- [ ] 7.2 Write integration tests
  - Test navigation between chapters in same window
  - Test navigation to chapters outside window
  - Test infinite scroll triggering window updates
  - Test rapid navigation handling

- [ ] 7.3 Write E2E tests
  - Test sidebar chapter click → scroll to correct position
  - Test scroll down → next chapter loads and window updates
  - Test scroll up → previous chapter loads and window updates
  - Test rapid chapter clicks → only final chapter rendered

## Dependencies

- Phase 1 must complete before Phase 2
- Phase 2 must complete before Phase 3
- Phase 3 must complete before Phase 4
- Phase 4 must complete before Phase 5
- Phase 6 can be done in parallel with Phases 2-5
- Phase 7 should be done after all implementation tasks

## Estimated Effort

- Phase 1: 2-3 hours
- Phase 2: 2-3 hours
- Phase 3: 2-3 hours
- Phase 4: 2 hours
- Phase 5: 1-2 hours
- Phase 6: 2 hours
- Phase 7: 3-4 hours

**Total: 14-20 hours