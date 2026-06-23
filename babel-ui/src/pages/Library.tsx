import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type Novel } from '../lib/api';
import NovelCard from '../components/library/NovelCard';
import ImportModal from '../components/modals/ImportModal';
import { Plus, Search, Loader2, Book } from 'lucide-react';

const Library: React.FC = () => {
    const navigate = useNavigate();
    const [novels, setNovels] = useState<Novel[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [searchQuery, setSearchQuery] = useState('');
    const [isImportModalOpen, setIsImportModalOpen] = useState(false);

    useEffect(() => {
        fetchNovels();
    }, []);

    const fetchNovels = async () => {
        try {
            setLoading(true);
            const data = await api.getNovels(100, 0); // Get up to 100 novels
            setNovels(data.novels);
            setError(null);
        } catch (err) {
            console.error('Failed to fetch novels:', err);
            setError('Failed to load library. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleNovelClick = (novel: Novel) => {
        // Navigate to novel context (implementation pending in router)
        // For now, let's assume the route will be /library/:id
        navigate(`/library/${novel.id}`);
    };

    const filteredNovels = novels.filter(novel =>
        novel.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (novel.author && novel.author.toLowerCase().includes(searchQuery.toLowerCase()))
    );

    return (
        <div className="flex h-screen flex-col bg-black text-white overflow-hidden">
            {/* Header */}
            <header className="flex items-center justify-between border-b border-white/10 px-6 py-4 bg-black/50 backdrop-blur-md sticky top-0 z-10 w-full mb-6">
                <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">Library</h1>

                <div className="flex items-center gap-4">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-500" />
                        <input
                            type="text"
                            placeholder="Search library..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="h-10 w-64 rounded-full border border-white/10 bg-white/5 pl-10 pr-4 text-sm text-gray-200 placeholder:text-gray-500 focus:border-blue-500/50 focus:bg-white/10 focus:outline-none focus:ring-1 focus:ring-blue-500/50 transition-all"
                        />
                    </div>

                    <button
                        onClick={() => setIsImportModalOpen(true)}
                        className="flex items-center gap-2 rounded-full bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-500 active:bg-blue-700 shadow-lg shadow-blue-500/20"
                    >
                        <Plus className="h-4 w-4" />
                        Import Novel
                    </button>
                </div>
            </header>

            {/* Main Content */}
            <main className="flex-1 overflow-y-auto px-6 pb-12 w-full max-w-[1920px] mx-auto">
                {loading ? (
                    <div className="flex h-64 w-full items-center justify-center">
                        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
                        <span className="ml-3 text-gray-400">Loading library...</span>
                    </div>
                ) : error ? (
                    <div className="flex h-64 w-full flex-col items-center justify-center text-center">
                        <div className="rounded-full bg-red-500/10 p-4 text-red-400">
                            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <h3 className="mt-4 text-lg font-medium text-white">Error Loading Library</h3>
                        <p className="mt-2 text-gray-400 max-w-md">{error}</p>
                        <button
                            onClick={fetchNovels}
                            className="mt-6 rounded-md bg-white/10 px-4 py-2 text-sm font-medium text-white hover:bg-white/20"
                        >
                            Try Again
                        </button>
                    </div>
                ) : filteredNovels.length === 0 ? (
                    <div className="flex h-64 w-full flex-col items-center justify-center text-center">
                        {searchQuery ? (
                            <>
                                <Search className="h-12 w-12 text-gray-600 mb-4" />
                                <h3 className="text-lg font-medium text-white">No matches found</h3>
                                <p className="text-gray-400">Try adjusting your search query.</p>
                            </>
                        ) : (
                            <>
                                <Book className="h-16 w-16 text-gray-700 mb-4 opacity-50" />
                                <h3 className="text-xl font-medium text-white">Your library is empty</h3>
                                <p className="mt-2 text-gray-400 max-w-md">
                                    Import an EPUB file to get started with your reading journey.
                                </p>
                                <button
                                    onClick={() => setIsImportModalOpen(true)}
                                    className="mt-6 rounded-full bg-blue-600 px-6 py-2.5 text-sm font-medium text-white hover:bg-blue-500 shadow-lg shadow-blue-500/20"
                                >
                                    Import First Novel
                                </button>
                            </>
                        )}
                    </div>
                ) : (
                    <div className="grid grid-cols-2 gap-6 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6">
                        {filteredNovels.map((novel) => (
                            <NovelCard
                                key={novel.id}
                                novel={novel}
                                onClick={handleNovelClick}
                            />
                        ))}
                    </div>
                )}
            </main>

            {/* Import Modal */}
            <ImportModal
                isOpen={isImportModalOpen}
                onClose={() => setIsImportModalOpen(false)}
                onSuccess={fetchNovels}
            />
        </div>
    );
};

export default Library;
