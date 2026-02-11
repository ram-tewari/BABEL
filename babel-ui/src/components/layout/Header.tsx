/**
 * Header Component
 * 
 * Sticky header with menu toggle, settings button, and chapter title.
 * Opens SettingsModal for theme/font configuration.
 * 
 * Features:
 * - Menu button toggles sidebar (via callback prop)
 * - Settings button opens SettingsModal
 * - Displays current chapter title
 * - Sticky positioning with glassmorphism styling
 * - Responsive design
 * 
 * Validates: Requirements 2.1
 */

import { Link } from 'react-router-dom';
import { useState } from 'react';
import { Menu, Settings, UploadCloud, Home } from 'lucide-react';
import { SettingsModal } from '@/components/modals/SettingsModal';
import { IngestModal } from '@/components/modals/IngestModal';

interface HeaderProps {
  /** Current chapter title to display */
  chapterTitle?: string;
  /** Callback to toggle sidebar */
  onToggleSidebar?: () => void;
}

export function Header({ chapterTitle, onToggleSidebar }: HeaderProps) {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [ingestOpen, setIngestOpen] = useState(false);

  return (
    <header
      className="sticky top-0 z-50 flex items-center justify-between h-16 px-4 bg-[var(--bg-primary)]/80 backdrop-blur-md border-b border-[var(--border)] w-full"
    >
      {/* Left Section: Menu Button + Home + Chapter Title */}
      <div className="flex items-center gap-2 md:gap-4">
        {/* Menu Toggle Button */}
        <button
          onClick={onToggleSidebar}
          className="
              p-2 
              hover:bg-[var(--bg-tertiary)] 
              rounded-lg 
              transition-all 
              duration-200
              hover:scale-105
              active:scale-95
            "
          aria-label="Toggle sidebar"
          title="Toggle sidebar (Ctrl+B)"
        >
          <Menu size={20} className="text-[var(--text-main)]" />
        </button>

        {/* Home Button */}
        <Link
          to="/"
          className="
              p-2 
              hover:bg-[var(--bg-tertiary)] 
              rounded-lg 
              transition-all 
              duration-200
              hover:scale-105
              active:scale-95
              flex items-center justify-center
            "
          aria-label="Go to Home"
          title="Home / Library"
        >
          <Home size={20} className="text-[var(--text-main)]" />
        </Link>

        {/* Divider */}
        <div className="h-6 w-px bg-[var(--border)] mx-1 hidden md:block" />

        {/* Chapter Title */}
        <span className="text-sm md:text-lg font-semibold text-[var(--text-main)] truncate max-w-[200px] md:max-w-[500px]">
          {chapterTitle || 'SYSTEM: BABEL'}
        </span>
      </div>

      {/* Right Section: Settings Button */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setIngestOpen(true)}
          className="
            p-2 
            hover:bg-[var(--bg-tertiary)] 
            rounded-lg 
            transition-all 
            duration-200
            hover:scale-105
            active:scale-95
          "
          aria-label="Upload content"
          title="Ingest Chapter"
        >
          <UploadCloud size={24} className="text-[var(--text-main)]" />
        </button>

        <button
          onClick={() => setSettingsOpen(true)}
          className="
            p-2 
            hover:bg-[var(--bg-tertiary)] 
            rounded-lg 
            transition-all 
            duration-200
            hover:scale-105
            active:scale-95
          "
          aria-label="Open settings"
          title="Settings"
        >
          <Settings size={24} className="text-[var(--text-main)]" />
        </button>
      </div>

      {/* Settings Modal */}
      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
      />

      {/* Ingest Modal */}
      <IngestModal
        open={ingestOpen}
        onClose={() => setIngestOpen(false)}
      />
    </header>
  );
}
