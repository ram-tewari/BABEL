import React from 'react';
import { type Novel } from '../../lib/api';
import { Book, Clock, Layers } from 'lucide-react';
import { cn } from '../../lib/utils'; // Assuming standard cn utility exists, usually in lib/utils

interface NovelCardProps {
    novel: Novel;
    onClick: (novel: Novel) => void;
    className?: string;
}

const NovelCard: React.FC<NovelCardProps> = ({ novel, onClick, className }) => {
    const [imageError, setImageError] = React.useState(false);

    // Status badge color mapping
    const getStatusColor = (status: string) => {
        switch (status.toLowerCase()) {
            case 'active':
                return 'bg-green-500/20 text-green-400 border-green-500/30';
            case 'completed':
                return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
            case 'hiatus':
                return 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30';
            default:
                return 'bg-gray-500/20 text-gray-400 border-gray-500/30';
        }
    };

    // Format date loosely
    const formatDate = (dateString?: string) => {
        if (!dateString) return '';
        return new Date(dateString).toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    };

    return (
        <div
            className={cn(
                "group relative flex flex-col overflow-hidden rounded-xl border border-white/10 bg-black/40 transition-all hover:border-white/20 hover:bg-white/5 cursor-pointer",
                className
            )}
            onClick={() => onClick(novel)}
        >
            {/* Cover Image Area */}
            <div className="aspect-[2/3] w-full overflow-hidden bg-gray-900 relative">
                {novel.cover_url && !imageError ? (
                    <img
                        src={novel.cover_url}
                        alt={`Cover for ${novel.title}`}
                        className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                        onError={() => setImageError(true)}
                    />
                ) : (
                    <div className="flex h-full w-full flex-col items-center justify-center text-white/20 bg-gradient-to-br from-gray-800 to-gray-900">
                        <Book className="h-16 w-16 mb-2 opacity-50" />
                        <span className="text-xs font-medium uppercase tracking-wider">No Cover</span>
                    </div>
                )}

                {/* Helper overlay for text readability on hover if we had floating text, 
            but here we separate text below. However, let's add a subtle shine or overlay on hover */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />

                {/* Status Badge */}
                <div className={cn(
                    "absolute top-2 right-2 px-2 py-0.5 text-xs font-medium rounded-full border backdrop-blur-sm",
                    getStatusColor(novel.status)
                )}>
                    {novel.status}
                </div>
            </div>

            {/* Content Area */}
            <div className="flex flex-col p-4 flex-grow">
                <h3 className="line-clamp-2 text-lg font-semibold text-white group-hover:text-blue-400 transition-colors mb-1" title={novel.title}>
                    {novel.title}
                </h3>

                <p className="text-sm text-gray-400 mb-3 truncate">
                    {novel.author || 'Unknown Author'}
                </p>

                <div className="mt-auto flex items-center justify-between text-xs text-gray-500">
                    <div className="flex items-center gap-1.5" title="Chapter Count">
                        <Layers className="h-3.5 w-3.5" />
                        <span>{novel.chapter_count} Ch</span>
                    </div>

                    {novel.updated_at && (
                        <div className="flex items-center gap-1.5" title={`Updated: ${formatDate(novel.updated_at)}`}>
                            <Clock className="h-3.5 w-3.5" />
                            <span>{formatDate(novel.updated_at)}</span>
                        </div>
                    )}
                </div>

                {/* Tags (Optional - show first 2) */}
                {novel.tags && novel.tags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1.5">
                        {novel.tags.slice(0, 2).map(tag => (
                            <span key={tag} className="px-1.5 py-0.5 rounded text-[10px] bg-white/5 text-gray-400 border border-white/5">
                                {tag}
                            </span>
                        ))}
                        {novel.tags.length > 2 && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] text-gray-500">
                                +{novel.tags.length - 2}
                            </span>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default NovelCard;
