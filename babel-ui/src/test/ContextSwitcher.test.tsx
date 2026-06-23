import { describe, it, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import { render, screen, fireEvent } from '@testing-library/react';
import { ContextSwitcher } from '../components/layout/ContextSwitcher';
import { MemoryRouter, useNavigate } from 'react-router-dom';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

describe('ContextSwitcher', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders correctly', () => {
        render(
            <MemoryRouter>
                <ContextSwitcher />
            </MemoryRouter>
        );
        expect(screen.getByText('Back to Library')).toBeInTheDocument();
        expect(screen.getByRole('button')).toBeInTheDocument();
    });

    it('navigates to library on click', () => {
        render(
            <MemoryRouter>
                <ContextSwitcher />
            </MemoryRouter>
        );

        fireEvent.click(screen.getByText('Back to Library'));

        expect(mockNavigate).toHaveBeenCalledWith('/library');
    });
});
