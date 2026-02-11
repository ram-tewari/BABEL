/**
 * ScriptBlock Component
 * 
 * Dispatcher component that renders the correct block type based on
 * the block's type field. This is the main entry point for rendering
 * chapter content blocks.
 * 
 * Supports click-to-edit functionality for manual corrections.
 * 
 * Task 6.1: Implement ScriptBlock dispatcher component
 * Validates: Requirements 2.3
 */

import { useState } from 'react';
import { DialogueBubble } from './DialogueBubble';
import { ThoughtBlock } from './ThoughtBlock';
import { NarratorBlock } from './NarratorBlock';
import { ActionBlock } from './ActionBlock';
import { SystemBlock } from './SystemBlock';
import { MonologueBlock } from './MonologueBlock';
import { BlockEditor } from '@/components/editor/BlockEditor';
import { useSettings } from '@/stores/settingsStore';
import { getCharacterLane } from '@/lib/style';
import type { ChapterBlock } from '@/lib/api';

interface ScriptBlockProps {
    /** The block data from the chapter API response */
    block: ChapterBlock;
    /** Block index in the chapter */
    blockIndex?: number;
    /** Chapter ID for editing */
    chapterId?: string;
    /** Callback when block is updated */
    onUpdate?: (updatedBlock: ChapterBlock) => void;
    /** Whether this block should visually merge with the previous one (for Narrator blocks) */
    mergeTop?: boolean;
    /** Whether this block should visually merge with the next one (for Narrator blocks) */
    mergeBottom?: boolean;
    /** List of all blocks in the chapter (for extracting character names) */
    allBlocks?: ChapterBlock[];
}

/**
 * ScriptBlock dispatches rendering to the correct block-type component.
 * 
 * Supported block types:
 * - dialogue: Character dialogue with colors, lanes, emojis
 * - thought: Internal thoughts with dashed borders
 * - narrator: Exposition with subtle styling
 * - action: Centered action descriptions
 * - system: System messages with monospace font
 * - monologue: Centered monologue text
 * - unknown: Silently ignored
 * 
 * Click any block to edit (if editing is enabled).
 */
export function ScriptBlock({ 
    block, 
    blockIndex, 
    chapterId, 
    onUpdate,
    mergeTop, 
    mergeBottom,
    allBlocks = []
}: ScriptBlockProps) {
    const [editorOpen, setEditorOpen] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    
    const canEdit = blockIndex !== undefined && chapterId && onUpdate;
    
    // Extract unique character names from all blocks
    const availableCharacters = Array.from(
        new Set(
            allBlocks
                .filter(b => b.speaker && (b.type === 'dialogue' || b.type === 'thought'))
                .map(b => b.speaker!)
        )
    ).sort();
    
    const handleClick = () => {
        if (canEdit) {
            setEditorOpen(true);
        }
    };
    
    const handleSave = (updatedBlock: ChapterBlock) => {
        if (onUpdate) {
            onUpdate(updatedBlock);
        }
    };
    
    // Extract lane for dialogue/thought blocks to apply to wrapper
    const getLaneAlignment = (): React.CSSProperties | undefined => {
        if (block.type !== 'dialogue' && block.type !== 'thought') return undefined;
        
        const { getCharacterPrefs } = useSettings.getState();
        const prefs = getCharacterPrefs(block.speaker || '');
        const lane = prefs?.lane || getCharacterLane(block.speaker || '');
        
        return {
            alignSelf: lane === 'right' ? 'flex-end' : lane === 'left' ? 'flex-start' : 'center',
            maxWidth: '70%',
        };
    };
    
    // Wrapper with edit functionality
    const wrapWithEditor = (content: React.ReactNode) => {
        if (!canEdit) return content;
        
        const laneStyle = getLaneAlignment();
        
        return (
            <>
                <div
                    className={`
                        relative cursor-pointer transition-all
                        ${isHovered ? 'ring-2 ring-[var(--accent)]/30 rounded-xl' : ''}
                    `}
                    style={laneStyle}
                    onClick={handleClick}
                    onMouseEnter={() => setIsHovered(true)}
                    onMouseLeave={() => setIsHovered(false)}
                >
                    {content}
                </div>
                
                <BlockEditor
                    open={editorOpen}
                    onClose={() => setEditorOpen(false)}
                    block={{
                        type: block.type,
                        speaker: block.speaker,
                        text: block.content,
                        corrected: block.corrected,
                        correction_id: block.correction_id
                    }}
                    blockIndex={blockIndex!}
                    chapterId={chapterId!}
                    onSave={handleSave}
                    availableCharacters={availableCharacters}
                />
            </>
        );
    };
    
    // Render appropriate block type
    let blockContent: React.ReactNode;
    
    switch (block.type) {
        case 'dialogue':
            blockContent = (
                <DialogueBubble
                    speaker={block.speaker || 'Unknown'}
                    content={block.content}
                    tone={block.tone}
                />
            );
            break;
        case 'thought':
            blockContent = (
                <ThoughtBlock
                    speaker={block.speaker || 'Unknown'}
                    content={block.content}
                />
            );
            break;
        case 'narrator':
            blockContent = <NarratorBlock content={block.content} mergeTop={mergeTop} mergeBottom={mergeBottom} />;
            break;
        case 'action':
            blockContent = <ActionBlock content={block.content} />;
            break;
        case 'system':
            blockContent = <SystemBlock content={block.content} />;
            break;
        case 'monologue':
            blockContent = <MonologueBlock content={block.content} />;
            break;
        default:
            // Unknown block types are silently ignored
            return null;
    }
    
    return wrapWithEditor(blockContent);
}
