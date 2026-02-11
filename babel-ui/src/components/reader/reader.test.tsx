/**
 * Reader Component Tests
 * 
 * Tests for ScriptBlock, DialogueBubble, ThoughtBlock, NarratorBlock,
 * ActionBlock, SystemBlock, and MonologueBlock components.
 * 
 * Task 6.8: Write component tests for reader blocks
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ScriptBlock } from './ScriptBlock';
import { DialogueBubble } from './DialogueBubble';
import { ThoughtBlock } from './ThoughtBlock';
import { NarratorBlock } from './NarratorBlock';
import { ActionBlock } from './ActionBlock';
import { SystemBlock } from './SystemBlock';
import { MonologueBlock } from './MonologueBlock';
import type { ChapterBlock } from '@/lib/api';

describe('ScriptBlock', () => {
    it('should render DialogueBubble for dialogue blocks', () => {
        const block: ChapterBlock = {
            type: 'dialogue',
            speaker: 'Chung Myung',
            content: 'Hello, world!',
            tone: 'happy',
        };
        render(<ScriptBlock block={block} />);
        expect(screen.getByTestId('dialogue-bubble')).toBeInTheDocument();
    });

    it('should render ThoughtBlock for thought blocks', () => {
        const block: ChapterBlock = {
            type: 'thought',
            speaker: 'Chung Myung',
            content: 'I wonder...',
        };
        render(<ScriptBlock block={block} />);
        expect(screen.getByTestId('thought-block')).toBeInTheDocument();
    });

    it('should render NarratorBlock for narrator blocks', () => {
        const block: ChapterBlock = {
            type: 'narrator',
            content: 'The sun was setting.',
        };
        render(<ScriptBlock block={block} />);
        expect(screen.getByTestId('narrator-block')).toBeInTheDocument();
    });

    it('should render ActionBlock for action blocks', () => {
        const block: ChapterBlock = {
            type: 'action',
            content: '*draws sword*',
        };
        render(<ScriptBlock block={block} />);
        expect(screen.getByTestId('action-block')).toBeInTheDocument();
    });

    it('should render SystemBlock for system blocks', () => {
        const block: ChapterBlock = {
            type: 'system',
            content: 'Chapter loaded.',
        };
        render(<ScriptBlock block={block} />);
        expect(screen.getByTestId('system-block')).toBeInTheDocument();
    });

    it('should render MonologueBlock for monologue blocks', () => {
        const block: ChapterBlock = {
            type: 'monologue',
            content: 'A long time ago...',
        };
        render(<ScriptBlock block={block} />);
        expect(screen.getByTestId('monologue-block')).toBeInTheDocument();
    });

    it('should return null for unknown block types', () => {
        const block = {
            type: 'unknown' as any,
            content: 'test',
        };
        const { container } = render(<ScriptBlock block={block} />);
        expect(container.innerHTML).toBe('');
    });

    it('should use "Unknown" for dialogue with missing speaker', () => {
        const block: ChapterBlock = {
            type: 'dialogue',
            content: 'Test dialogue',
        };
        render(<ScriptBlock block={block} />);
        expect(screen.getByTestId('dialogue-speaker')).toHaveTextContent('Unknown');
    });
});

describe('DialogueBubble', () => {
    it('should render speaker name', () => {
        render(<DialogueBubble speaker="Chung Myung" content="Hello!" />);
        expect(screen.getByTestId('dialogue-speaker')).toHaveTextContent('Chung Myung');
    });

    it('should render content', () => {
        render(<DialogueBubble speaker="Test" content="Hello, world!" />);
        expect(screen.getByTestId('dialogue-bubble-content')).toHaveTextContent('Hello, world!');
    });

    it('should apply deterministic character color', () => {
        render(<DialogueBubble speaker="Chung Myung" content="Test" />);
        const speaker = screen.getByTestId('dialogue-speaker');
        // jsdom may convert HSL to RGB, so accept either format
        expect(speaker.style.color).toMatch(/hsl\(|rgb\(/);
    });

    it('should show tone emoji when tone is provided', () => {
        render(<DialogueBubble speaker="Test" content="I am happy!" tone="happy" />);
        expect(screen.getByTestId('tone-emoji')).toHaveTextContent('✨');
    });

    it('should not show tone emoji when tone is not provided', () => {
        render(<DialogueBubble speaker="Test" content="Normal speech." />);
        expect(screen.queryByTestId('tone-emoji')).not.toBeInTheDocument();
    });

    it('should not show tone emoji for unmatched tones', () => {
        render(<DialogueBubble speaker="Test" content="Test" tone="neutral" />);
        expect(screen.queryByTestId('tone-emoji')).not.toBeInTheDocument();
    });

    it('should have clickable speaker for customization', () => {
        render(<DialogueBubble speaker="Test" content="Test" />);
        const speaker = screen.getByTestId('dialogue-speaker');
        expect(speaker).toHaveAttribute('role', 'button');
        expect(speaker).toHaveAttribute('tabindex', '0');
    });
});

describe('ThoughtBlock', () => {
    it('should render speaker name', () => {
        render(<ThoughtBlock speaker="Baek Cheon" content="Thinking..." />);
        expect(screen.getByTestId('thought-speaker')).toHaveTextContent('Baek Cheon');
    });

    it('should render content', () => {
        render(<ThoughtBlock speaker="Test" content="Deep thoughts..." />);
        expect(screen.getByTestId('thought-content')).toHaveTextContent('Deep thoughts...');
    });

    it('should apply character color to speaker', () => {
        render(<ThoughtBlock speaker="Chung Myung" content="Test" />);
        const speaker = screen.getByTestId('thought-speaker');
        // jsdom may convert HSL to RGB, so accept either format
        expect(speaker.style.color).toMatch(/hsl\(|rgb\(/);
    });
});

describe('NarratorBlock', () => {
    it('should render content', () => {
        render(<NarratorBlock content="The wind howled through the mountains." />);
        expect(screen.getByTestId('narrator-block')).toHaveTextContent(
            'The wind howled through the mountains.'
        );
    });

    it('should highlight keywords with tooltips', () => {
        render(<NarratorBlock content="The nobles gathered." />);
        const block = screen.getByTestId('narrator-block');
        expect(block.innerHTML).toContain('class="keyword"');
        expect(block.innerHTML).toContain('keyword-tooltip');
    });

    it('should not highlight non-glossary words', () => {
        render(<NarratorBlock content="A simple sentence." />);
        const block = screen.getByTestId('narrator-block');
        expect(block.innerHTML).not.toContain('class="keyword"');
    });
});

describe('ActionBlock', () => {
    it('should render content', () => {
        render(<ActionBlock content="*draws sword*" />);
        expect(screen.getByTestId('action-block')).toHaveTextContent('*draws sword*');
    });
});

describe('SystemBlock', () => {
    it('should render content', () => {
        render(<SystemBlock content="System: Chapter loaded." />);
        expect(screen.getByTestId('system-block')).toHaveTextContent('System: Chapter loaded.');
    });
});

describe('MonologueBlock', () => {
    it('should render content', () => {
        render(<MonologueBlock content="Once upon a time..." />);
        expect(screen.getByTestId('monologue-block')).toHaveTextContent('Once upon a time...');
    });
});
