/**
 * Sidebar Component
 * 
 * Collapsible Table of Contents sidebar with chapter list navigation.
 * Connected to the Zustand settings store for open/closed state.
 * 
 * Features:
 * - Fetches chapter list from API
 * - Highlights current chapter
 * - Smooth open/close animation
 * - Glassmorphism styling
 * - Responsive: full width on mobile when open
 * 
 * Validates: Requirements 2.2, 4.2
 */

import { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useChapterList } from '@/hooks/useChapterList';
import { useSettings } from '@/stores/settingsStore';
import { useReadingProgress } from '@/stores/readingProgressStore';
import { cn } from '@/lib/utils';
import { Home, Book, Loader2, Search, Edit3 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ChapterList } from '@/components/chapter/ChapterList';

/**
 * Sidebar component for chapter navigation.
 * 
 * Displays a collapsible table of contents with all available chapters.
 * Automatically highlights the current chapter based on URL params.
 */
export function Sidebar() {
  const { data: chapterListData, isLoading, error } = useChapterList();
  const { id: chapterId } = useParams<{ id: string }>();
  const { sidebarOpen } = useSettings();
  const { currentChapterId, getProgressPercentage, setTotalChapters } = useReadingProgress();
  const [searchQuery, setSearchQuery] = useState('');

  // Convert chapterId to number for comparison
  const currentChapterIdFromUrl = chapterId ? Number(chapterId) : null;
  
  // Use currentChapterId from store, fallback to URL param
  const activeChapterId = currentChapterId || currentChapterIdFromUrl;

  // Update total chapters when chapter list loads
  useEffect(() => {
    if (chapterListData?.chapters) {
      setTotalChapters(chapterListData.chapters.length);
    }
  }, [chapterListData, setTotalChapters]);

  // Calculate progress
  const progressPercentage = getProgressPercentage();

  if (!sidebarOpen) return null;

  // Filter chapters
  const filteredChapters = chapterListData?.chapters.filter((chapter: any) =>
    chapter.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    chapter.chapter_index.toString().includes(searchQuery)
  );

  return (
    <aside
      className={cn(
        'group flex flex-col h-screen fixed inset-y-0 left-0 z-40 w-[300px] bg-[#0f0f11] border-r border-white/5 transition-transform duration-300 shadow-2xl',
        // Mobile handling could be improved, but sticking to existing logic regarding visibility
        'md:relative md:translate-x-0',
        !sidebarOpen && '-translate-x-full md:hidden'
      )}
    >
      {/* Header / Brand Area */}
      <div className="flex h-16 items-center px-6 border-b border-white/5 shrink-0 bg-[#0f0f11]/50 backdrop-blur-sm">
        <Link to="/" className="flex items-center gap-3 font-bold text-white tracking-tight">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-600 to-indigo-600 flex items-center justify-center text-xs shadow-lg shadow-purple-500/20">
            B
          </div>
          <span className="text-lg">BABEL</span>
        </Link>
      </div>

      {/* Navigation Content */}
      <div className="flex-1 overflow-y-auto py-6 px-4 space-y-8 custom-scrollbar">

        {/* Section: Platform */}
        <div className="space-y-2">
          <h4 className="px-2 text-xs uppercase tracking-widest text-gray-500 font-bold mb-3">Platform</h4>
          <Link to="/">
            <Button variant="ghost" className="w-full justify-start h-10 px-3 text-gray-400 hover:text-white hover:bg-white/5 font-medium transition-all group">
              <Home className="mr-3 h-4 w-4 text-gray-500 group-hover:text-purple-400 transition-colors" />
              Library
            </Button>
          </Link>
          <Link to="/corrections">
            <Button variant="ghost" className="w-full justify-start h-10 px-3 text-gray-400 hover:text-white hover:bg-white/5 font-medium transition-all group">
              <Edit3 className="mr-3 h-4 w-4 text-gray-500 group-hover:text-purple-400 transition-colors" />
              Corrections
            </Button>
          </Link>
          <Button variant="ghost" disabled className="w-full justify-start h-10 px-3 text-gray-500 font-medium">
            <Book className="mr-3 h-4 w-4" />
            Bookmarks
          </Button>
        </div>

        {/* Section: Chapters */}
        <div className="space-y-4">
          <div className="flex items-center justify-between px-2">
            <h4 className="text-xs uppercase tracking-widest text-gray-500 font-bold">Table of Contents</h4>
            <span className="text-[10px] text-gray-400 bg-white/5 px-2 py-0.5 rounded-full border border-white/5">
              {chapterListData?.chapters?.length || 0}
            </span>
          </div>

          {/* Progress Bar */}
          {chapterListData && chapterListData.chapters.length > 0 && (
            <div className="px-2 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-gray-400">Progress</span>
                <span className="text-purple-400 font-bold">{progressPercentage}%</span>
              </div>
              <div className="h-2 bg-[#1c1c1f] rounded-full overflow-hidden border border-white/10">
                <div
                  className="h-full bg-gradient-to-r from-purple-600 to-indigo-600 transition-all duration-500 ease-out shadow-[0_0_8px_#a855f7]"
                  style={{ width: `${progressPercentage}%` }}
                />
              </div>
            </div>
          )}

          {/* Search Input */}
          <div className="px-2 relative">
            <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
            <Input
              placeholder="Find chapter..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-9 pl-9 bg-[#1c1c1f] border-white/10 text-xs focus:ring-purple-500/50 focus:border-purple-500/50 placeholder:text-gray-600"
            />
          </div>

          {isLoading && (
            <div className="flex items-center justify-center py-8 text-gray-600">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          )}

          {error && (
            <div className="px-2 text-xs text-red-400 bg-red-500/10 p-2 rounded border border-red-500/20">
              Failed to load chapters.
            </div>
          )}

          <div className="mt-2">
            {!isLoading && !error && (
              <ChapterList
                chapters={filteredChapters || []}
                activeChapterId={activeChapterId}
                className="border-none"
              />
            )}
          </div>
        </div>

      </div>

      {/* Footer / User Area */}
      <div className="p-4 border-t border-white/5 shrink-0 bg-[#0f0f11]/50 backdrop-blur-md">
        <div className="flex items-center gap-3 px-3 py-2.5 rounded-xl bg-[#1c1c1f] border border-white/5 hover:border-white/10 transition-colors cursor-pointer group">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-purple-500 to-pink-500 ring-2 ring-[#0f0f11] group-hover:ring-purple-500/30 transition-all"></div>
          <div className="flex-1 min-w-0">
            <div className="text-xs font-bold text-gray-200 truncate group-hover:text-white">Guest User</div>
            <div className="text-[10px] text-gray-500 truncate group-hover:text-purple-400">System Access</div>
          </div>
        </div>
      </div>
    </aside>
  );
}
