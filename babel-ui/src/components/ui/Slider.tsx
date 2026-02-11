/**
 * Slider Component
 * 
 * Range input wrapper with value display and styling that matches
 * the Jinja2 template's font size slider.
 * 
 * Task 7.3: Implement Slider component
 * Validates: System Design
 */

interface SliderProps {
    /** Current value */
    value: number;
    /** Minimum value */
    min: number;
    /** Maximum value */
    max: number;
    /** Step increment */
    step?: number;
    /** Label text */
    label?: string;
    /** Unit suffix for display (e.g., "px") */
    unit?: string;
    /** Change handler */
    onChange: (value: number) => void;
    /** Optional className */
    className?: string;
}

/**
 * Slider renders a range input with value display.
 * 
 * Features:
 * - Custom-styled range input (accent thumb, tertiary track)
 * - Value display with optional unit suffix
 * - Label showing current value
 * - Full-width track
 */
export function Slider({
    value,
    min,
    max,
    step = 1,
    label,
    unit = '',
    onChange,
    className,
}: SliderProps) {
    return (
        <div className={`modal-field ${className || ''}`} data-testid="slider">
            {label && (
                <label data-testid="slider-label">
                    {label}: {value}{unit}
                </label>
            )}
            <input
                type="range"
                min={min}
                max={max}
                step={step}
                value={value}
                onChange={(e) => onChange(Number(e.target.value))}
                data-testid="slider-input"
            />
        </div>
    );
}
