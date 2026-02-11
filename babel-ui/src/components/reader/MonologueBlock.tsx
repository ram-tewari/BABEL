/**
 * MonologueBlock Component
 * 
 * Renders monologue text with centered layout, ghost-colored text,
 * and italic styling.
 * 
 * Task 6.7: Implement MonologueBlock component
 * Validates: Requirements 2.3
 */

interface MonologueBlockProps {
    /** The monologue text content */
    content: string;
}

/**
 * MonologueBlock renders internal monologue text.
 * 
 * Features:
 * - Centered layout
 * - Ghost-colored text (lighter than dim)
 * - Italic styling
 * - Minimal padding for rhythmic spacing
 */
export function MonologueBlock({ content }: MonologueBlockProps) {
    return (
        <div className="monologue" data-testid="monologue-block">
            {content}
        </div>
    );
}
