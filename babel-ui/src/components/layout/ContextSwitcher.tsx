import React from 'react';
import { useNavigate } from 'react-router-dom';
import { BookOpen, Library } from 'lucide-react';
import { useReadingProgress } from '../../stores/readingProgressStore';

interface ContextSwitcherProps {
  novelId?: number;
  novelTitle?: string;
}

/**
 * ContextSwitcher Component
 * 
 * Displays navigation controls to switch between library and reader views.
 * Shows "Back to Library" button when reading a novel.
 * Persists reading position before navigation.
 * 
 * Requirements: 6.1, 6.2, 6.3
 */
const ContextSwitcher: React.FC<ContextSwitcherProps> = ({ novelId, novelTitle }) => {
  const navigate = useNavigate();
  const { currentNovelId } = useReadingProgress();

  const handleBackToLibrary = () => {
    // Reading position is automatically persisted by the store
    navigate('/library');
  };

  const handleBackToReader = () => {
    if (novelId) {
      navigate(`/library/${novelId}`);
    }
  };

  // Only show context switcher if we have a novel context
  if (!novelId && !currentNovelId) {
    return null;
  }

  return (
    <div className="flex items-center gap-2">
      {novelId && novelTitle && (
        <>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10">
            <BookOpen className="h-4 w-4 text-blue-400" />
            <span className="text-sm text-gray-300 truncate max-w-[200px]">
              {novelTitle}
            </span>
          </div>
          <button
            onClick={handleBackToLibrary}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:bg-white/10 hover:border-white/20 transition-all text-sm"
            title="Return to library"
          >
            <Library className="h-4 w-4" />
            <span className="hidden sm:inline">Library</span>
          </button>
        </>
      )}
    </div>
  );
};

export default ContextSwitcher;
