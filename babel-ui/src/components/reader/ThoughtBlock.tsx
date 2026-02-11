/**
 * ThoughtBlock Component
 * 
 * Renders internal thoughts with dashed border styling, muted character
 * color, lane positioning, and italic serif font.
 * 
 * Task 6.3: Implement ThoughtBlock component
 * Validates: Requirements 2.5
 */

import { useState } from 'react';
import { getCharacterColor, getCharacterLane } from '@/lib/style';
import { cn } from '@/lib/utils';
import { CharacterModal } from '@/components/modals/CharacterModal';
import { useSettings } from '@/stores/settingsStore';

interface ThoughtBlockProps {
    /** Character having the thought */
    speaker: string;
    /** The thought text content */
    content: string;
}

/**
 * ThoughtBlock renders internal character thoughts.
 * 
 * Features:
 * - Dashed border styling (2px dashed)
 * - Muted character color (mixed with grey at 70%)
 * - Subtle background tint (5% character color)
 * - Lane positioning (left/right) from stable hash
 * - Italic serif font for literary feel
 * - Right-aligned text for right-lane thoughts
 */
export function ThoughtBlock({ speaker, content }: ThoughtBlockProps) {
    const [modalOpen, setModalOpen] = useState(false);
    const { getCharacterPrefs } = useSettings();
    const prefs = getCharacterPrefs(speaker);

    const lane = prefs?.lane || getCharacterLane(speaker);
    const displayName = prefs?.displayName || speaker;
    const color = prefs?.color || getCharacterColor(speaker);

    const handleSpeakerClick = (e: React.MouseEvent) => {
        e.stopPropagation(); // Prevent block editor from opening
        setModalOpen(true);
    };

    return (
        <div className={cn('thought', lane)} data-testid="thought-block">
            <div
                className="speaker"
                onClick={handleSpeakerClick}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                        e.stopPropagation();
                        handleSpeakerClick(e as any);
                    }
                }}
                style={{ color }}
                data-testid="thought-speaker"
            >
                {displayName}
            </div>
            <div
                className="content"
                style={{
                    borderColor: `color-mix(in srgb, ${color}, #808080 70%)`,
                    background: `color-mix(in srgb, ${color} 5%, transparent)`,
                }}
                data-testid="thought-content"
            >
                {content}
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
