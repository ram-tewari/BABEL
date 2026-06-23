/**
 * DialogueBubble Component
 * 
 * Renders character dialogue with hash-based colors, lane positioning,
 * and tone emoji indicators. Clicking a speaker name opens the character
 * customization modal.
 * 
 * Task 6.2: Implement DialogueBubble component
 * Validates: Requirements 2.4, 1.2, 1.3
 */

import { useState } from 'react';
import { Edit2 } from 'lucide-react';
import { getCharacterColor, getCharacterLane, getToneEmoji } from '@/lib/style';
import { cn } from '@/lib/utils';
import { CharacterModal } from '@/components/modals/CharacterModal';
import { useSettings } from '@/stores/settingsStore';
import { useGlossary } from '@/stores/glossaryStore';

interface DialogueBubbleProps {
    /** Character speaking the dialogue */
    speaker: string;
    /** The dialogue text content */
    content: string;
    /** Optional tone descriptor for emoji indicator */
    tone?: string;
}

/**
 * DialogueBubble renders a single dialogue block with character styling.
 * 
 * Features:
 * - Dynamic HSL color from stable hash
 * - Lane positioning (left/right) from stable hash
 * - Tone emoji indicator with pop-in animation
 * - Click speaker to customize (future: CharacterModal)
 * - Glassmorphism bubble styling
 * - Hover micro-interactions (scale + shadow)
 */
export function DialogueBubble({ speaker, content, tone }: DialogueBubbleProps) {
    const [modalOpen, setModalOpen] = useState(false);
    const { getCharacterPrefs } = useSettings();
    const prefs = getCharacterPrefs(speaker);

    const color = prefs?.color || getCharacterColor(speaker);
    const lane = prefs?.lane || getCharacterLane(speaker);
    const displayName = prefs?.displayName || speaker;
    const emoji = getToneEmoji(tone);
    const glossaryEntry = useGlossary((s) => s.getEntry(speaker));

    const handleSpeakerClick = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent block editor from opening
        setModalOpen(true);
    };

    return (
        <div className={cn('dialogue group/bubble', lane)} data-testid="dialogue-bubble">
            <div
                className="speaker group relative flex items-center gap-2"
                onClick={handleSpeakerClick}
                style={{ color }}
                data-testid="dialogue-speaker"
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                        e.stopPropagation();
                        handleSpeakerClick(e as any);
                    }
                }}
            >
                <span
                    className={cn(
                        'font-semibold text-sm tracking-wide',
                        glossaryEntry && 'underline decoration-dotted decoration-[var(--text-dim)] underline-offset-4'
                    )}
                >
                    {displayName}
                </span>
                <button
                    className="opacity-0 group-hover:opacity-100 transition-all duration-200 p-1 rounded-md hover:bg-[var(--bg-tertiary)] -ml-1 text-[var(--text-dim)]"
                    aria-label="Edit Character"
                    title="Customize Character"
                >
                    <Edit2 size={12} />
                </button>
                {glossaryEntry && (
                    <div
                        role="tooltip"
                        className="pointer-events-none absolute left-0 top-full z-20 mt-1 w-64 origin-top-left scale-95 rounded-lg border border-[var(--border)] bg-[var(--bg-secondary)] p-3 text-left opacity-0 shadow-xl transition-all duration-150 group-hover:scale-100 group-hover:opacity-100"
                        data-testid="glossary-tooltip"
                    >
                        <div className="text-sm font-semibold" style={{ color }}>
                            {glossaryEntry.name}
                        </div>
                        {glossaryEntry.faction && (
                            <div className="mt-0.5 text-xs font-medium text-[var(--text-dim)]">
                                {glossaryEntry.faction}
                            </div>
                        )}
                        {glossaryEntry.description && (
                            <p className="mt-1.5 text-xs leading-relaxed text-[var(--text-secondary)]">
                                {glossaryEntry.description}
                            </p>
                        )}
                        {glossaryEntry.aliases?.length > 0 && (
                            <div className="mt-1.5 text-[10px] uppercase tracking-wide text-[var(--text-dim)]">
                                aka {glossaryEntry.aliases.join(', ')}
                            </div>
                        )}
                    </div>
                )}
            </div>
            <div
                className="bubble"
                style={{
                    borderColor: color,
                    background: `color-mix(in srgb, ${color} 10%, transparent)`,
                }}
                data-testid="dialogue-bubble-content"
            >
                {content}
                {emoji && (
                    <span className="tone-emoji" data-testid="tone-emoji">
                        {emoji}
                    </span>
                )}
            </div>
            <CharacterModal
                open={modalOpen}
                onClose={() => setModalOpen(false)}
                character={speaker}
                initialColor={getCharacterColor(speaker)}
                initialLane={getCharacterLane(speaker)}
            />
        </div>
    );
}
