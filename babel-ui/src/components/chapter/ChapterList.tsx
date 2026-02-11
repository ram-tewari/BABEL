import { Link } from 'react-router-dom';
import { cn, formatChapterTitle } from '@/lib/utils';
import { ChevronRight, Check } from 'lucide-react';
import { useReadingProgress } from '@/stores/readingProgressStore';

interface Chapter {
    id: number;
    chapter_index: number;
    title: string;
    status: string;
}

interface ChapterListProps {
    chapters: Chapter[];
    activeChapterId?: number | null;
    className?: string;
}

export function ChapterList({ chapters, activeChapterId, className }: ChapterListProps) {
    const { isChapterRead } = useReadingProgress();

    if (chapters.length === 0) {
        return (
            <div className="p-8 text-center text-muted-foreground text-sm italic border-t border-white/5">
                No chapters found.
            </div>
        );
    }

    const handleChapterClick = (e: React.MouseEvent, chapter: Chapter) => {
        // Find the chapter container on the page using data-chapter-id
        const targetElement = document.querySelector(`.chapter-container[data-chapter-id="${chapter.id}"]`);

        if (targetElement) {
            e.preventDefault();
            targetElement.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        // If not found on page, let the <Link> navigate normally
    };

    return (
        <div className={cn("divide-y divide-white/5 border-t border-white/5", className)}>
            {chapters.map((chapter) => {
                const isActive = activeChapterId === chapter.id;
                const isRead = isChapterRead(chapter.id);
                
                return (
                    <Link
                        key={chapter.id}
                        to={`/chapter/${chapter.id}`}
                        onClick={(e) => handleChapterClick(e, chapter)}
                        className={cn(
                            "group flex items-center justify-between p-3.5 transition-all outline-none",
                            isActive
                                ? "bg-purple-600/10 hover:bg-purple-600/15"
                                : "hover:bg-white/5 hover:pl-4"
                        )}
                    >
                        <div className="flex items-center gap-3 min-w-0 overflow-hidden">
                            {/* Active Indicator Line */}
                            {isActive && (
                                <div className="absolute left-0 w-1 h-8 bg-purple-500 rounded-r-full shadow-[0_0_8px_#a855f7]" />
                            )}

                            <span className={cn(
                                "text-xs font-mono shrink-0 transition-colors",
                                isActive ? "text-purple-400 font-bold" : "text-muted-foreground group-hover:text-purple-400/80"
                            )}>
                                #{chapter.chapter_index.toString().padStart(3, '0')}
                            </span>

                            <span className={cn(
                                "text-sm truncate transition-colors",
                                isActive 
                                    ? "text-white font-medium" 
                                    : isRead 
                                        ? "text-gray-400 group-hover:text-white" 
                                        : "text-gray-300 group-hover:text-white"
                            )}>
                                {formatChapterTitle(chapter.title)}
                            </span>
                        </div>

                        <div className="flex items-center gap-3 shrink-0 pl-2">
                            {/* Read indicator */}
                            {isRead && !isActive && (
                                <Check className="w-3.5 h-3.5 text-emerald-500/70 group-hover:text-emerald-400" />
                            )}
                            
                            <span className={cn(
                                "text-[10px] uppercase tracking-wider transition-colors hidden sm:inline-block",
                                chapter.status === 'complete'
                                    ? "text-emerald-500/70 group-hover:text-emerald-400"
                                    : "text-amber-500/70"
                            )}>
                                {chapter.status === 'complete' ? 'Ready' : 'WIP'}
                            </span>

                            {isActive && <ChevronRight className="w-4 h-4 text-purple-500 animate-in fade-in slide-in-from-left-1" />}
                        </div>
                    </Link>
                );
            })}
        </div>
    );
}
