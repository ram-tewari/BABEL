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
    
    console.log(`DialogueBubble - Speaker: ${speaker}, Lane: ${lane}, Prefs:`, prefs);

    const handleSpeakerClick = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent block editor from opening
        setModalOpen(true);
    };

    return (
        <div className={cn('dialogue group/bubble', lane)} data-testid="dialogue-bubble">
            <div
                className="speaker group flex items-center gap-2"
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
                <span className="font-semibold text-sm tracking-wide">{displayName}</span>
                <button
                    className="opacity-0 group-hover:opacity-100 transition-all duration-200 p-1 rounded-md hover:bg-[var(--bg-tertiary)] -ml-1 text-[var(--text-dim)]"
                    aria-label="Edit Character"
                    title="Customize Character"
                >
                    <Edit2 size={12} />
                </button>
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
