import { describe, it, expect, vi, beforeEach } from 'vitest'; // Import vitest methods
import '@testing-library/jest-dom'; // Import jest-dom matchers
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { ImportModal } from '../components/modals/ImportModal';
import { api } from '../lib/api';

// Mock the API
vi.mock('../lib/api', () => ({
    api: {
        importNovel: vi.fn(),
    },
}));

describe('ImportModal', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders correctly when open', () => {
        render(
            <ImportModal open={true} onClose={() => { }} />
        );
        expect(screen.getByText('Import Novel')).toBeInTheDocument();
        expect(screen.getByText('Click to upload EPUB')).toBeInTheDocument();
    });

    it('does not render when closed', () => {
        render(
            <ImportModal open={false} onClose={() => { }} />
        );
        expect(screen.queryByText('Import Novel')).not.toBeInTheDocument();
    });

    it('validates file extension', () => {
        render(
            <ImportModal open={true} onClose={() => { }} />
        );

        // Check if input element exists
        const fileInput = screen.getByTestId('file-input');

        // Create a dummy txt file
        const file = new File(['dummy content'], 'test.txt', { type: 'text/plain' });

        fireEvent.change(fileInput, { target: { files: [file] } });

        expect(screen.getByText('Only .epub files are supported.')).toBeInTheDocument();
    });

    it('handles file selection successfully', () => {
        render(
            <ImportModal open={true} onClose={() => { }} />
        );

        const fileInput = screen.getByTestId('file-input');
        const file = new File(['dummy content'], 'novel.epub', { type: 'application/epub+zip' });

        fireEvent.change(fileInput, { target: { files: [file] } });

        expect(screen.getByText('novel.epub')).toBeInTheDocument();
        expect(screen.queryByText('Only .epub files are supported.')).not.toBeInTheDocument();
    });

    it('handles successful import flow', async () => {
        const mockOnSuccess = vi.fn();
        const mockOnClose = vi.fn();

        vi.mocked(api.importNovel).mockResolvedValue({
            novel_id: 123,
            title: 'Imported Novel',
            chapters_extracted: 10,
            status: 'success'
        });

        render(
            <ImportModal open={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
        );

        // Select file
        const fileInput = screen.getByTestId('file-input');
        const file = new File(['dummy content'], 'novel.epub', { type: 'application/epub+zip' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        // Click import
        const importButton = screen.getByText('Start Import');
        fireEvent.click(importButton);

        // Verify loading state
        expect(screen.getByText(/Importing.../i)).toBeInTheDocument();

        // Verify success
        await waitFor(() => {
            expect(screen.getByText(/Successfully imported "Imported Novel"/i)).toBeInTheDocument();
        });

        // Wait for auto-close timeout
        // We can't easily wait for setTimeout without fake timers, but we can verify success message appears.
        // To verify onClose is called, we can wait for it.
        await waitFor(() => {
            expect(mockOnSuccess).toHaveBeenCalledWith(123);
            expect(mockOnClose).toHaveBeenCalled();
        }, { timeout: 3000 });
    });

    it('handles import error', async () => {
        vi.mocked(api.importNovel).mockRejectedValue(new Error('Upload failed'));

        render(
            <ImportModal open={true} onClose={() => { }} />
        );

        // Select file
        const fileInput = screen.getByTestId('file-input');
        const file = new File(['dummy content'], 'novel.epub', { type: 'application/epub+zip' });
        fireEvent.change(fileInput, { target: { files: [file] } });

        // Click import
        fireEvent.click(screen.getByText('Start Import'));

        // Verify error
        await waitFor(() => {
            expect(screen.getByText(/Import failed/i)).toBeInTheDocument();
        });
    });
});
