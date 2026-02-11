/**
 * LoadingSpinner Component
 * 
 * Animated loading spinner with size variants.
 * 
 * Task 7.4: Implement LoadingSpinner component
 * Validates: Requirements 4.4
 */

import { cn } from '@/lib/utils';

interface LoadingSpinnerProps {
    /** Size variant */
    size?: 'sm' | 'md' | 'lg';
    /** Optional className */
    className?: string;
    /** Optional label for accessibility */
    label?: string;
}

const sizeClasses = {
    sm: 'w-4 h-4 border-2',
    md: 'w-8 h-8 border-4',
    lg: 'w-12 h-12 border-4',
};

/**
 * LoadingSpinner renders an animated circular spinner.
 * 
 * Features:
 * - CSS animation (1s linear infinite rotation)
 * - Border-top colored with accent
 * - Three size variants (sm, md, lg)
 * - Accessible via role="status" and sr-only label
 */
export function LoadingSpinner({
    size = 'md',
    className,
    label = 'Loading...',
}: LoadingSpinnerProps) {
    return (
        <div
            className={cn(
                'loading-spinner',
                sizeClasses[size],
                className
            )}
            role="status"
            aria-label={label}
            data-testid="loading-spinner"
        >
            <span className="sr-only">{label}</span>
        </div>
    );
}
