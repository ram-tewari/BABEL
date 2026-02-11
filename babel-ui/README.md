# BABEL UI - React Frontend

**Phase 6: The Interface** - A modern Single Page Application (SPA) for reading webnovels transformed by SYSTEM: BABEL.

## Overview

BABEL UI is the React-based frontend for SYSTEM: BABEL, providing a beautiful, fast, and customizable reading experience. It achieves 1:1 visual parity with the existing Jinja2 templates while adding the performance and interactivity benefits of a client-side framework.

### Key Features

- ✨ **Codex Style Design**: Glassmorphism, character colors, lane positioning
- ⚡ **Instant Navigation**: SPA architecture with no page refreshes
- 🎨 **Full Customization**: Theme toggle, font size, character colors/names
- 📱 **Responsive Design**: Works beautifully on mobile, tablet, and desktop
- ⌨️ **Keyboard Shortcuts**: Arrow keys for navigation, Ctrl+B for sidebar
- 💾 **Persistent Settings**: All preferences saved to localStorage
- 🚀 **Optimized Performance**: < 200KB bundle, prefetching, caching

## Tech Stack

- **Build Tool**: Vite
- **Framework**: React 18 (TypeScript)
- **Styling**: Tailwind CSS + CSS Variables
- **State Management**: Zustand
- **Data Fetching**: TanStack Query (React Query v5)
- **HTTP Client**: Axios
- **Routing**: React Router v6
- **Icons**: Lucide React
- **Testing**: Vitest + Testing Library + Playwright

## Prerequisites

- **Node.js**: v18 or higher
- **npm**: v9 or higher (comes with Node.js)
- **BABEL Backend**: FastAPI server running (see `babel_server.py`)

## Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd BABEL/babel-ui
```

### 2. Install Dependencies

```bash
npm install
```

### 3. Configure Environment Variables

Copy the example environment file and configure it:

```bash
cp .env.example .env.local
```

Edit `.env.local` and set your API base URL:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### 4. Start the Backend Server

In a separate terminal, start the BABEL FastAPI backend:

```bash
# From the BABEL root directory
python babel_server.py
```

The backend should be running at `http://localhost:8000`.

### 5. Start the Development Server

```bash
npm run dev
```

The app will be available at `http://localhost:5173`.

## Development

### Available Scripts

```bash
# Start development server with hot reload
npm run dev

# Build for production
npm run build

# Preview production build locally
npm run preview

# Run unit tests
npm run test

# Run unit tests in watch mode
npm run test:watch

# Run unit tests with coverage
npm run test:coverage

# Run E2E tests
npm run test:e2e

# Run linter
npm run lint

# Format code
npm run format
```

### Project Structure

```
babel-ui/
├── public/                 # Static assets
├── src/
│   ├── components/         # React components
│   │   ├── layout/        # MainLayout, Header, Sidebar
│   │   ├── reader/        # ScriptBlock, DialogueBubble, etc.
│   │   ├── modals/        # SettingsModal, CharacterModal
│   │   └── ui/            # Button, Modal, Slider, etc.
│   ├── lib/               # Utility functions
│   │   ├── style.ts       # Color/lane generation (ported from Python)
│   │   ├── api.ts         # Axios instance + endpoints
│   │   ├── storage.ts     # localStorage utilities
│   │   └── constants.ts   # App constants
│   ├── hooks/             # Custom React hooks
│   │   ├── useChapter.ts  # Chapter data fetching
│   │   ├── useSettings.ts # Settings store hook
│   │   └── useKeyboard.ts # Keyboard shortcuts
│   ├── stores/            # Zustand stores
│   │   └── settingsStore.ts
│   ├── types/             # TypeScript type definitions
│   │   ├── chapter.ts     # Chapter data types
│   │   ├── settings.ts    # Settings types
│   │   └── api.ts         # API response types
│   ├── pages/             # Page components
│   │   ├── ChapterView.tsx
│   │   ├── Home.tsx
│   │   └── NotFound.tsx
│   ├── App.tsx            # Root component
│   ├── main.tsx           # Entry point
│   └── index.css          # Global styles + Tailwind
├── .env.example           # Environment variables template
├── .gitignore
├── index.html
├── package.json
├── tailwind.config.js     # Tailwind configuration
├── tsconfig.json          # TypeScript configuration
├── vite.config.ts         # Vite configuration
└── README.md
```

### Development Workflow

1. **Create a new component**: Add it to the appropriate directory under `src/components/`
2. **Add types**: Define TypeScript interfaces in `src/types/`
3. **Create hooks**: Add custom hooks to `src/hooks/`
4. **Write tests**: Co-locate tests with components using `.test.tsx` suffix
5. **Run tests**: `npm run test` to verify your changes
6. **Lint code**: `npm run lint` to check for issues
7. **Build**: `npm run build` to create production bundle

### Code Style

- **TypeScript**: Strict mode enabled, no `any` types
- **ESLint**: Enforces consistent code style
- **Prettier**: Auto-format on save (recommended)
- **Naming Conventions**:
  - Components: PascalCase (e.g., `DialogueBubble.tsx`)
  - Hooks: camelCase with `use` prefix (e.g., `useChapter.ts`)
  - Utilities: camelCase (e.g., `getCharacterColor`)
  - Types: PascalCase (e.g., `ChapterBlock`)

## Building for Production

### 1. Create Production Build

```bash
npm run build
```

This creates an optimized production build in the `dist/` directory.

### 2. Test Production Build Locally

```bash
npm run preview
```

This serves the production build locally for testing.

### 3. Deploy

The `dist/` directory can be deployed to any static hosting service:

- **Vercel**: `vercel deploy`
- **Netlify**: `netlify deploy --prod`
- **GitHub Pages**: Push `dist/` to `gh-pages` branch
- **Docker**: Use the included Dockerfile (if available)

### Environment Variables for Production

Set the following environment variables in your hosting platform:

```env
VITE_API_BASE_URL=https://your-production-api.com
```

**Important**: Make sure your backend CORS settings allow requests from your production domain.

## Configuration

### API Endpoints

The app expects the following endpoints from the backend:

- `GET /api/chapters/{id}` - Get chapter data with blocks
- `GET /api/chapters/metadata?novel_id={id}` - Get chapter list
- `GET /health` - Health check

See `src/lib/api.ts` for the complete API client implementation.

### Tailwind Configuration

Customize the theme in `tailwind.config.js`:

```js
export default {
  theme: {
    extend: {
      colors: {
        // Add custom colors
      },
      fontFamily: {
        // Add custom fonts
      }
    }
  }
}
```

### CSS Variables

Theme colors are defined using CSS variables in `src/index.css`:

```css
:root {
  --bg-primary: #0f0f0f;
  --text-main: #e0e0e0;
  /* ... more variables */
}

[data-theme="light"] {
  --bg-primary: #ffffff;
  --text-main: #1a1a1a;
  /* ... light theme overrides */
}
```

## Feature Comparison

| Feature | Old (Jinja2) | New (React) | Benefit |
|---------|--------------|-------------|---------|
| **Navigation** | Page Refresh | Instant SPA | Zero latency between chapters |
| **Search** | None | Real-time Filtering | Find chapters instantly |
| **Customization**| Server-side Config | Client-side (LocalStorage) | Immediate feedback, persistent |
| **Theme** | Static CSS | Dynamic Toggle | Dark/Light mode support |
| **Performance** | Server Rendering | Client Rendering + Caching | Faster subsequent loads |
| **Offline** | No | Partial (Cache) | Read previously loaded chapters |

## User Migration Guide

### Transitioning from Jinja2 Templates

If you are coming from the legacy Jinja2 rendering engine, welcome to the new React-based UI! Here's what you need to know:

1.  **No More Re-rendering**: Previously, changing themes or character names required re-running the Python script. Now, changes happen instantly in the browser.
2.  **Settings Persistence**: Your improved settings (font size, theme) are saved in your browser. They won't be lost if you restart the server.
3.  **New URL Structure**:
    *   Old: `/render/chapter_001.html`
    *   New: `/chapter/1`
4.  **Shortcuts**:
    *   `ArrowLeft` / `ArrowRight`: Navigate chapters
    *   `Ctrl+B`: Toggle sidebar
    *   `Esc`: Close modals

### Data Migration

No automatic data migration is needed for user preferences, as the old system didn't store client-side preferences. Just set up your preferred theme and font size once, and you're good to go!

## Troubleshooting

### Backend Connection Issues

**Problem**: "Failed to fetch chapter data"

**Solution**:
1. Verify the backend is running: `curl http://localhost:8000/health`
2. Check `.env.local` has the correct `VITE_API_BASE_URL`
3. Check browser console for CORS errors
4. Verify backend CORS settings allow your frontend origin

### Build Errors

**Problem**: "Module not found" errors

**Solution**:
1. Delete `node_modules/` and `package-lock.json`
2. Run `npm install` again
3. Clear Vite cache: `rm -rf node_modules/.vite`

### Performance Issues

**Problem**: Slow loading or navigation

**Solution**:
1. Check Network tab in browser DevTools
2. Verify API responses are fast (< 500ms)
3. Clear browser cache and localStorage
4. Check bundle size: `npm run build` and inspect `dist/`

### TypeScript Errors

**Problem**: Type errors during development

**Solution**:
1. Run `npm run type-check` to see all errors
2. Update type definitions in `src/types/`
3. Restart TypeScript server in your IDE

## Testing

### Unit Tests

```bash
# Run all unit tests
npm run test

# Run tests in watch mode
npm run test:watch

# Run tests with coverage
npm run test:coverage
```

### E2E Tests

```bash
# Run Playwright E2E tests
npm run test:e2e

# Run E2E tests in UI mode
npm run test:e2e:ui
```

### Visual Regression Tests

Visual regression testing ensures pixel-perfect parity with the Jinja2 version:

```bash
# Take baseline screenshots
npm run test:visual:baseline

# Run visual comparison
npm run test:visual
```

## Performance Metrics

Target metrics for production:

- **Bundle Size**: < 200KB (gzipped)
- **First Contentful Paint**: < 1.5s
- **Time to Interactive**: < 3s
- **Lighthouse Performance**: > 90
- **Chapter Navigation**: < 100ms (cached)

Run Lighthouse audit:

```bash
npm run lighthouse
```

## Browser Support

- Chrome/Edge (last 2 versions)
- Firefox (last 2 versions)
- Safari (last 2 versions)
- iOS Safari (last 2 versions)
- Chrome Android (last 2 versions)

## Contributing

### Development Guidelines

1. **Write tests**: All new features should have tests
2. **Type safety**: No `any` types, use proper TypeScript
3. **Accessibility**: Maintain WCAG AA compliance
4. **Performance**: Keep bundle size under budget
5. **Documentation**: Update README for new features

### Commit Messages

Use conventional commits format:

```
feat: add character search functionality
fix: resolve sidebar animation glitch
docs: update API endpoint documentation
test: add E2E test for chapter navigation
```

## License

[Your License Here]

## Related Documentation

- **Requirements**: `.kiro/specs/rendering-engine/requirements.md`
- **Design**: `.kiro/specs/rendering-engine/design.md`
- **Tasks**: `.kiro/specs/rendering-engine/tasks.md`
- **Backend API**: `babel_server.py`
- **Python Style Module**: `babel/render/style.py`
- **Codex Style Guide**: `docs/CODEX_STYLE_REFINED.md`

## Support

For issues, questions, or contributions, please refer to the main BABEL project documentation.

---

**Built with ❤️ for hardcore webnovel readers**
