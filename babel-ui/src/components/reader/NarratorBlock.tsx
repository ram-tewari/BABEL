/**
 * NarratorBlock Component
 * 
 * Renders exposition/narration with subtle left border, flat background,
 * and italic serif font. Supports keyword highlighting with tooltips.
 * 
 * Task 6.4: Implement NarratorBlock component
 * Validates: Requirements 2.6
 */

import { useMemo } from 'react';
import { cn } from '@/lib/utils';

interface NarratorBlockProps {
    /** The narration text content (may contain HTML from keyword highlighting) */
    content: string;
    mergeTop?: boolean;
    mergeBottom?: boolean;
}

/**
 * Glossary of terms for keyword highlighting in narrator blocks.
 * Keywords are highlighted with dotted underlines and show tooltips on hover.
 */
const GLOSSARY: Record<string, string> = {
    'Thunder Chopping': 'A legendary lumberjack technique.',
    'Swordsmanship': 'The art of wielding a detailed blade.',
    'magic': 'The mysterious force that powers spells.',
    'nobles': 'The ruling class with exclusive access to education.',
    'magic school': 'An elite educational institution.',
};

/**
 * Escape special regex characters in a string.
 */
function escapeRegex(str: string): string {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * NarratorBlock renders exposition/narration text.
 * 
 * Features:
 * - "Codex" styling with glassmorphism and purple accents
 * - Keyword highlighting ("Glimmer" effect)
 * - Paragraph separation with proper spacing
 * - Visual merging for consecutive blocks
 */
export function NarratorBlock({ content, mergeTop, mergeBottom }: NarratorBlockProps) {
    const paragraphs = useMemo(() => {
        if (!content) return [];
        return content.split('\n').filter(p => p.trim());
    }, [content]);

    const processParagraph = (text: string) => {
        let html = text;
        // Sort keywords by length to avoid partial matches inside longer keywords
        const keywords = Object.keys(GLOSSARY).sort((a, b) => b.length - a.length);

        keywords.forEach(keyword => {
            const regex = new RegExp(`\\b(${escapeRegex(keyword)})\\b`, 'gi');
            html = html.replace(regex, `<span class="lore-keyword" title="${GLOSSARY[keyword]}">$1</span>`);
        });
        return html;
    };

    return (
        <div
            className={cn(
                "max-w-3xl mx-auto px-8 backdrop-blur-md transition-all duration-300",
                "bg-[#111113]/80 border-x border-purple-500/20",
                "text-base leading-loose text-gray-200 font-sans",

                // Only apply shadow when NOT merging (standalone block)
                !mergeTop && !mergeBottom && "shadow-[0_4px_30px_rgba(109,40,217,0.15)]",

                // Top merging logic - increased padding
                mergeTop
                    ? "border-t-0 rounded-t-none pt-6"
                    : "rounded-t-xl border-t border-purple-500/20 pt-8",

                // Bottom merging logic - increased padding
                mergeBottom
                    ? "border-b-0 rounded-b-none pb-6"
                    : "rounded-b-xl border-b border-purple-500/20 pb-8"
            )}
            data-testid="narrator-block"
        >
            <div className="space-y-6">
                {paragraphs.map((paragraph, index) => (
                    <div key={index}>
                        {/* Larger divider between paragraphs */}
                        {index > 0 && (
                            <div className="my-8 flex items-center justify-center">
                                <div className="w-24 h-px bg-gradient-to-r from-transparent via-purple-500/30 to-transparent" />
                            </div>
                        )}
                        <p
                            className="mb-0"
                            dangerouslySetInnerHTML={{ __html: processParagraph(paragraph) }}
                        />
                    </div>
                ))}
            </div>
        </div>
    );
}
