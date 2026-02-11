/**
 * SettingsModal Component Tests
 * 
 * Tests modal open/close, theme toggle, and font size slider.
 * 
 * Task 9.4: Write component tests for SettingsModal
 */

import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { SettingsModal } from './SettingsModal';
import { useSettingsStore } from '@/stores/settingsStore';

describe('SettingsModal', () => {
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
        render(<SettingsModal open={false} onClose={() => { }} />);
        expect(screen.queryByTestId('settings-modal-header')).not.toBeInTheDocument();
    });

    it('should render when open', () => {
        render(<SettingsModal open={true} onClose={() => { }} />);
        expect(screen.getByTestId('settings-modal-header')).toBeInTheDocument();
        expect(screen.getByText('⚙️ Settings')).toBeInTheDocument();
    });

    it('should display theme toggle buttons', () => {
        render(<SettingsModal open={true} onClose={() => { }} />);
        expect(screen.getByTestId('theme-light-button')).toBeInTheDocument();
        expect(screen.getByTestId('theme-dark-button')).toBeInTheDocument();
    });

    it('should highlight active theme', () => {
        render(<SettingsModal open={true} onClose={() => { }} />);
        expect(screen.getByTestId('theme-dark-button')).toHaveClass('active');
        expect(screen.getByTestId('theme-light-button')).not.toHaveClass('active');
    });

    it('should switch theme when light button clicked', () => {
        render(<SettingsModal open={true} onClose={() => { }} />);
        fireEvent.click(screen.getByTestId('theme-light-button'));
        expect(useSettingsStore.getState().theme).toBe('light');
    });

    it('should display font size slider', () => {
        render(<SettingsModal open={true} onClose={() => { }} />);
        expect(screen.getByTestId('font-size-slider')).toBeInTheDocument();
    });

    it('should display current font size value', () => {
        render(<SettingsModal open={true} onClose={() => { }} />);
        expect(screen.getByText('Font Size: 16px')).toBeInTheDocument();
    });

    it('should update font size when slider changes', () => {
        render(<SettingsModal open={true} onClose={() => { }} />);
        const slider = screen.getByTestId('font-size-slider');
        fireEvent.change(slider, { target: { value: '20' } });
        expect(useSettingsStore.getState().fontSize).toBe(20);
    });

    it('should have a close button', () => {
        render(<SettingsModal open={true} onClose={() => { }} />);
        expect(screen.getByTestId('settings-close-button')).toBeInTheDocument();
    });

    it('should call onClose when close button clicked', () => {
        let closed = false;
        render(<SettingsModal open={true} onClose={() => { closed = true; }} />);
        fireEvent.click(screen.getByTestId('settings-close-button'));
        expect(closed).toBe(true);
    });
});
