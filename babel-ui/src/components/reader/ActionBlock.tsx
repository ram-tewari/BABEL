/**
 * ActionBlock Component
 * 
 * Renders action descriptions with center alignment, subtle styling,
 * and sans-serif font.
 * 
 * Task 6.5: Implement ActionBlock component
 * Validates: Requirements 2.3
 */

interface ActionBlockProps {
    /** The action description text */
    content: string;
}

/**
 * ActionBlock renders centered action descriptions.
 * 
 * Features:
 * - Center alignment
 * - Subtle dim color
 * - Italic serif font
 * - Minimal padding for rhythmic spacing
 */
export function ActionBlock({ content }: ActionBlockProps) {
    return (
        <div className="action" data-testid="action-block">
            {content}
        </div>
    );
}
