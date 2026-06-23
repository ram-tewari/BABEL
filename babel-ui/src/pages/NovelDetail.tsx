import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, type Novel, type ChapterListItem } from '../lib/api';
import { Loader2, ChevronRight, ArrowLeft } from 'lucide-react';
import { useReadingProgress } from '../stores/readingProgressStore';

/**
 * NovelDetail Page Component
 * 
 * Displays novel information and chapter list.
 * Allows user to select a chapter to read.
 * Implements novel selection flow.
 * 
 * Requirements: 7.1, 7.2, 7.3, 7.4, 7.5
 */
const NovelDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { setCurrentNovel, initNovel, getCurrentChapter } = useReadingProgress();

  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapters, setChapters] = useState<ChapterListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const novelId = id ? parseInt(id) : null;

  useEffect(() => {
    if (!novelId) {
      setError('Invalid novel ID');
      setLoading(false);
      return;
    }

    fetchNovelData();
  }, [novelId]);

  const fetchNovelData = async () => {
    if (!novelId) return;

    try {
      setLoading(true);
      setError(null);

      // Fetch novel details
      const novelData = await api.getNovel(novelId);
      setNovel(novelData);

      // Set current novel context
      setCurrentNovel(novelId.toString());
      initNovel(novelId.toString(), novelData.chapter_count);

      // Fetch chapters for this novel
      const chaptersData = await api.getNovelChapters(novelId);
      setChapters(chaptersData.chapters);
    } catch (err) {
      console.error('Failed to fetch novel data:', err);
      setError('Failed to load novel. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleChapterClick = (chapterId: number) => {
    if (novelId) {
      navigate(`/library/${novelId}/chapter/${chapterId}`);
    }
  };

  const handleContinueReading = () => {
    if (!novelId) return;

    const currentChapterId = getCurrentChapter(novelId.toString());
    if (currentChapterId) {
      navigate(`/library/${novelId}/chapter/${currentChapterId}`);
    } else if (chapters.length > 0) {
      // Start from first chapter
      navigate(`/library/${novelId}/chapter/${chapters[0].id}`);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
        <p className="text-gray-400">Loading novel...</p>
      </div>
    );
  }

  if (error || !novel) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="text-6xl mb-4">📖</div>
        <h2 className="text-2xl font-semibold text-white">Novel Not Found</h2>
        <p className="text-gray-400 text-center max-w-md">{error}</p>
        <button
          onClick={() => navigate('/library')}
          className="mt-6 flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Library
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-6 py-8">
      {/* Header */}
      <button
        onClick={() => navigate('/library')}
        className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Library
      </button>

      {/* Novel Info */}
      <div className="flex gap-6 mb-12">
        {novel.cover_url && (
          <img
            src={novel.cover_url}
            alt={novel.title}
            className="w-32 h-48 rounded-lg object-cover shadow-lg"
          />
        )}

        <div className="flex-1">
          <h1 className="text-4xl font-bold text-white mb-2">{novel.title}</h1>
          {novel.author && (
            <p className="text-lg text-gray-400 mb-4">by {novel.author}</p>
          )}

          {novel.synopsis && (
            <p className="text-gray-300 mb-6 leading-relaxed max-w-2xl">
              {novel.synopsis}
            </p>
          )}

          <div className="flex items-center gap-4 mb-6">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Status:</span>
              <span className="px-3 py-1 rounded-full bg-blue-500/20 text-blue-300 text-sm font-medium">
                {novel.status}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-400">Chapters:</span>
              <span className="text-white font-medium">{novel.chapter_count}</span>
            </div>
          </div>

          {novel.tags && novel.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {novel.tags.map(tag => (
                <span
                  key={tag}
                  className="px-3 py-1 rounded-full bg-white/5 text-gray-300 text-xs border border-white/10"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}

          <button
            onClick={handleContinueReading}
            className="mt-8 px-6 py-3 rounded-lg bg-blue-600 text-white font-medium hover:bg-blue-500 transition-colors"
          >
            Continue Reading
          </button>
        </div>
      </div>

      {/* Chapters List */}
      <div>
        <h2 className="text-2xl font-bold text-white mb-4">Chapters</h2>

        {chapters.length === 0 ? (
          <p className="text-gray-400 text-center py-8">No chapters available</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {chapters.map(chapter => (
              <button
                key={chapter.id}
                onClick={() => handleChapterClick(chapter.id)}
                className="flex items-center justify-between p-4 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 hover:border-blue-500/50 transition-all text-left group"
              >
                <div className="flex-1">
                  <p className="text-sm font-medium text-white group-hover:text-blue-400 transition-colors">
                    {chapter.title}
                  </p>
                  <p className="text-xs text-gray-500">
                    Chapter {chapter.chapter_index}
                  </p>
                </div>
                <ChevronRight className="h-4 w-4 text-gray-500 group-hover:text-blue-400 transition-colors" />
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default NovelDetail;
