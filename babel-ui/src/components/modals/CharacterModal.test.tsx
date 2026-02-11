/**
 * CharacterModal Component Tests
 * 
 * Tests modal open/close, field inputs, save, cancel, and reset.
 * 
 * Task 10.3: Write component tests for CharacterModal
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { CharacterModal } from './CharacterModal';
import { useSettingsStore } from '@/stores/settingsStore';

describe('CharacterModal', () => {
    const defaultProps = {
        open: true,
        onClose: () => { },
        character: 'Chung Myung',
        initialColor: '#a78bfa',
        initialLane: 'right' as const,
    };

    beforeEach(() => {
        localStorage.clear();
        useSettingsStore.setState({
            theme: 'dark',
            fontSize: 16,
            sidebarOpen: true,
            characterPrefs: {},
        });
    });

    it('should not render when closed', () => {
        render(<CharacterModal {...defaultProps} open={false} />);
        expect(screen.queryByTestId('character-modal-header')).not.toBeInTheDocument();
    });

    it('should render when open', () => {
        render(<CharacterModal {...defaultProps} />);
        expect(screen.getByTestId('character-modal-header')).toBeInTheDocument();
        expect(screen.getByText('🎨 Character Settings')).toBeInTheDocument();
    });

    it('should display character name in input', () => {
        render(<CharacterModal {...defaultProps} />);
        const input = screen.getByTestId('character-name-input') as HTMLInputElement;
        expect(input.value).toBe('Chung Myung');
    });

    it('should display color picker', () => {
        render(<CharacterModal {...defaultProps} />);
        expect(screen.getByTestId('character-color-input')).toBeInTheDocument();
    });

    it('should display lane selector', () => {
        render(<CharacterModal {...defaultProps} />);
        const select = screen.getByTestId('character-lane-select') as HTMLSelectElement;
        expect(select.value).toBe('right');
    });

    it('should save preferences on save', () => {
        let closed = false;
        render(<CharacterModal {...defaultProps} onClose={() => { closed = true; }} />);

        // Change display name
        const nameInput = screen.getByTestId('character-name-input');
        fireEvent.change(nameInput, { target: { value: 'CM' } });

        // Click save
        fireEvent.click(screen.getByTestId('character-save-button'));

        // Verify saved
        const prefs = useSettingsStore.getState().getCharacterPrefs('Chung Myung');
        expect(prefs.displayName).toBe('CM');
        expect(closed).toBe(true);
    });

    it('should call onClose on cancel', () => {
        let closed = false;
        render(<CharacterModal {...defaultProps} onClose={() => { closed = true; }} />);
        fireEvent.click(screen.getByTestId('character-cancel-button'));
        expect(closed).toBe(true);
    });

    it('should reset preferences on reset', () => {
        // First save some prefs
        useSettingsStore.getState().setCharacterPrefs('Chung Myung', {
            displayName: 'CM',
            color: '#ff0000',
        });

        let closed = false;
        render(<CharacterModal {...defaultProps} onClose={() => { closed = true; }} />);
        fireEvent.click(screen.getByTestId('character-reset-button'));

        const prefs = useSettingsStore.getState().getCharacterPrefs('Chung Myung');
        expect(prefs).toEqual({});
        expect(closed).toBe(true);
    });

    it('should load existing preferences when opened', () => {
        useSettingsStore.getState().setCharacterPrefs('Chung Myung', {
            displayName: 'Custom Name',
            lane: 'left',
        });

        render(<CharacterModal {...defaultProps} />);
        const nameInput = screen.getByTestId('character-name-input') as HTMLInputElement;
        expect(nameInput.value).toBe('Custom Name');

        const laneSelect = screen.getByTestId('character-lane-select') as HTMLSelectElement;
        expect(laneSelect.value).toBe('left');
    });

    it('should have all three action buttons', () => {
        render(<CharacterModal {...defaultProps} />);
        expect(screen.getByTestId('character-save-button')).toBeInTheDocument();
        expect(screen.getByTestId('character-cancel-button')).toBeInTheDocument();
        expect(screen.getByTestId('character-reset-button')).toBeInTheDocument();
    });
});
