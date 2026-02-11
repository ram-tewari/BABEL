import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useChapterList } from '@/hooks/useChapterList';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ChapterList } from '@/components/chapter/ChapterList';
import { Search, BookOpen } from 'lucide-react';

export function Home() {
  const { data: chapterListData, isLoading } = useChapterList();
  const [searchQuery, setSearchQuery] = useState('');

  // Filter chapters based on search query
  const filteredChapters = chapterListData?.chapters.filter((chapter) =>
    chapter.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    chapter.chapter_index.toString().includes(searchQuery)
  );

  return (
    <div className="animate-fadeIn pb-20 pt-8">
      {/* "Manga Site" Style Series Header */}
      <div className="bg-[#111] rounded-xl overflow-hidden shadow-2xl border border-white/5 mx-auto max-w-6xl">

        {/* Backdrop / Blur Effect (Optional) */}
        <div className="h-48 bg-gradient-to-b from-purple-900/40 to-[#111] relative">
          <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1519638399535-1b036603ac77?q=80&w=1000&auto=format&fit=crop')] bg-cover bg-center opacity-20 mix-blend-overlay"></div>
        </div>

        <div className="px-8 pb-8 -mt-24 relative flex flex-col md:flex-row gap-8">
          {/* Poster Image */}
          <div className="flex-shrink-0 mx-auto md:mx-0">
            <div className="w-52 h-72 bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg shadow-2xl border-4 border-[#1c1c1f] relative overflow-hidden group">
              {/* Placeholder Cover */}
              <div className="absolute inset-0 flex flex-col items-center justify-center text-center p-4">
                <span className="text-4xl mb-2">🗼</span>
                <span className="font-bold text-gray-500 tracking-widest uppercase text-sm">Babel</span>
                <span className="text-xs text-gray-600 mt-1">System Architecture</span>
              </div>
            </div>
          </div>

          {/* Series Info */}
          <div className="flex-1 pt-6 text-center md:text-left space-y-4">
            <div className="space-y-2">
              <h1 className="text-4xl md:text-5xl font-bold text-white tracking-tight drop-shadow-md">
                BABEL SYSTEM
              </h1>
              <div className="flex flex-wrap justify-center md:justify-start gap-2">
                <Badge className="bg-purple-600 hover:bg-purple-700 text-white border-0">System</Badge>
                <Badge variant="secondary">Visual Novel</Badge>
                <Badge variant="secondary">AI Generated</Badge>
                <Badge variant="outline" className="text-muted-foreground">Ongoing</Badge>
              </div>
            </div>

            <p className="text-gray-400 text-sm md:text-base leading-relaxed max-w-2xl">
              The Babel System processes raw text into immersive visual scenarios.
              Experience the narrative through an adaptive, AI-driven interface that brings
              characters and dialogue to life.
            </p>

            {/* Metadata Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 py-4 text-sm border-y border-white/5">
              <div>
                <div className="text-gray-500 text-xs uppercase font-bold">Status</div>
                <div className="text-white">Active</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs uppercase font-bold">chapters</div>
                <div className="text-white">{chapterListData?.chapters.length || 0}</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs uppercase font-bold">Author</div>
                <div className="text-white">System</div>
              </div>
              <div>
                <div className="text-gray-500 text-xs uppercase font-bold">Updated</div>
                <div className="text-white">Today</div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex flex-col sm:flex-row gap-4 pt-2">
              <Link to={chapterListData?.chapters[0] ? `/chapter/${chapterListData.chapters[0].id}` : '#'}>
                <Button className="w-full sm:w-auto bg-purple-600 hover:bg-purple-700 text-white font-bold py-6 px-8 rounded-lg shadow-[0_4px_14px_0_rgba(124,58,237,0.39)] transition-transform active:scale-95">
                  READ FIRST CHAPTER
                </Button>
              </Link>
              <Link to={chapterListData?.chapters.length ? `/chapter/${chapterListData.chapters[chapterListData.chapters.length - 1].id}` : '#'}>
                <Button variant="secondary" className="w-full sm:w-auto font-bold py-6 px-8 rounded-lg bg-[#2c2c31] hover:bg-[#3f3f46] text-white">
                  LATEST CHAPTER
                </Button>
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content Areas */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-8 mt-8 max-w-6xl mx-auto">

        {/* Left Column: Chapter List */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold flex items-center gap-2">
              <BookOpen className="text-purple-500" />
              Chapter List
            </h3>
            <div className="relative w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input
                type="text"
                placeholder="Search Chapter..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-[#111] border border-white/10 rounded-lg py-2 pl-10 pr-4 text-sm focus:outline-none focus:border-purple-500 transition-colors"
              />
            </div>
          </div>

          <div className="bg-[#111] rounded-xl border border-white/5 overflow-hidden min-h-[500px]">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center p-20 text-muted-foreground gap-2">
                <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
                <span className="text-xs uppercase tracking-widest">Loading Records...</span>
              </div>
            ) : (
              <ChapterList chapters={filteredChapters || []} />
            )}
          </div>
        </div>

        {/* Right Column: Sidebar / Stats */}
        <div className="space-y-6">
          <div className="bg-[#111] rounded-xl border border-white/5 p-6">
            <h3 className="text-lg font-bold mb-4 border-b border-white/5 pb-2">Weekly Top</h3>
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="flex gap-3 items-center group cursor-pointer">
                  <div className={`w-8 h-8 rounded flex items-center justify-center font-bold text-sm ${i === 1 ? 'bg-purple-600 text-white' : 'bg-white/5 text-gray-500'}`}>
                    {i}
                  </div>
                  <div className="bg-white/5 w-10 h-12 rounded overflow-hidden">
                    {/* Placeholder Thumb */}
                  </div>
                  <div className="flex-1">
                    <div className="text-sm font-medium text-gray-300 group-hover:text-purple-400 transition-colors">Popular Scenario {i}</div>
                    <div className="text-xs text-gray-600">Views: 8.5K</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
