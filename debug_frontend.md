# Frontend Chapter Display Debugging Guide

## Current Status
- Backend API is working correctly (returns 200 OK for chapters 2028, 2029)
- JSON files exist and are properly formatted
- Frontend code looks correct

## Debugging Steps

### 1. Open Browser Developer Tools
Press `F12` or right-click and select "Inspect"

### 2. Check Console Tab
Look for any JavaScript errors:
- Red error messages
- Failed API calls
- React component errors

### 3. Check Network Tab
1. Refresh the page
2. Look for the API call to `/api/library/3/chapter/2028`
3. Click on it and check:
   - Status: Should be 200 OK
   - Response tab: Should show JSON with blocks array
   - Preview tab: Should show formatted JSON

### 4. Check React DevTools (if installed)
1. Look for `ChapterView` component
2. Check its state:
   - `loadedChapters`: Should contain chapter data
   - `renderedChapterIds`: Should contain [2028] or similar
   - `isLoading`: Should be false

### 5. Common Issues to Check

#### Issue A: Chapter not in render window
- Check if `renderedChapterIds` includes the current chapter ID
- The render window only shows 5 chapters at a time

#### Issue B: CSS hiding content
- Check if elements have `display: none` or `opacity: 0`
- Look for `visibility: hidden`

#### Issue C: Empty blocks array
- Check if the API response has a `blocks` array
- Verify blocks array is not empty

#### Issue D: React rendering error
- Look for error boundaries catching errors
- Check if ScriptBlock components are rendering

### 6. Quick Console Tests

Open the Console tab and run these commands:

```javascript
// Check if chapter data is loaded
document.querySelector('[data-chapter-id="2028"]')

// Check if blocks are rendered
document.querySelectorAll('.chapter-container .content > *').length

// Check render window state (if React DevTools available)
// Look for ChapterView component state
```

### 7. Possible Solutions

#### If chapter is not in render window:
The render window logic might be filtering it out. Try navigating directly to:
`http://localhost:5173/library/3/chapter/2028`

#### If CSS is hiding content:
Check the theme/styling in Settings

#### If blocks array is empty:
Check the JSON file structure matches the expected format

#### If React error:
Check browser console for the specific error message

## Next Steps
Please check the above and report back:
1. Any console errors (copy the exact error message)
2. Network tab status for the chapter API call
3. Whether you can see the chapter container element in the Elements tab
4. The value of `renderedChapterIds` from React DevTools
