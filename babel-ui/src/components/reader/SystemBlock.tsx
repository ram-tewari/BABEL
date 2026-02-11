/**
 * SystemBlock Component
 * 
 * Renders system messages with monospace font, centered layout,
 * and distinct accent-colored border styling.
 * 
 * Task 6.6: Implement SystemBlock component
 * Validates: Requirements 2.3
 */

interface SystemBlockProps {
    /** The system message text */
    content: string;
}

/**
 * SystemBlock renders system-level messages.
 * 
 * Features:
 * - Monospace font (Courier New / Consolas)
 * - Centered layout
 * - Accent-colored 2px border
 * - 10% accent background tint
 * - 16px border radius
 * - 0.9em font size
 */
export function SystemBlock({ content }: SystemBlockProps) {
    return (
        <div className="system" data-testid="system-block">
            {content}
        </div>
    );
}
