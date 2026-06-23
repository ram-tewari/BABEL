import { describe, it, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import fc from 'fast-check';
import Library from '../pages/Library';
import { api, type Novel } from '../lib/api';
import { BrowserRouter } from 'react-router-dom';

// Mock the API
vi.mock('../lib/api', () => ({
    api: {
        getNovels: vi.fn(),
    },
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

describe('Library Page', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders loading state initially', () => {
        // Return a promise that never resolves immediately to keep loading state
        vi.mocked(api.getNovels).mockReturnValue(new Promise(() => { }));

        render(
            <BrowserRouter>
                <Library />
            </BrowserRouter>
        );

        expect(screen.getByText('Loading library...')).toBeInTheDocument();
    });

    it('renders novels after fetching', async () => {
        const mockNovels: Novel[] = [
            { id: 1, title: 'Test Novel 1', status: 'active', chapter_count: 10 },
            { id: 2, title: 'Test Novel 2', status: 'completed', chapter_count: 20 },
        ];

        vi.mocked(api.getNovels).mockResolvedValue({ novels: mockNovels, total: 2 });

        render(
            <BrowserRouter>
                <Library />
            </BrowserRouter>
        );

        await waitFor(() => {
            expect(screen.getByText('Test Novel 1')).toBeInTheDocument();
            expect(screen.getByText('Test Novel 2')).toBeInTheDocument();
        });
    });

    it('handles API errors gracefully', async () => {
        vi.mocked(api.getNovels).mockRejectedValue(new Error('Network error'));

        render(
            <BrowserRouter>
                <Library />
            </BrowserRouter>
        );

        await waitFor(() => {
            expect(screen.getByText('Error Loading Library')).toBeInTheDocument();
            expect(screen.getByText('Failed to load library. Please try again.')).toBeInTheDocument();
        });
    });

    it('filters novels based on search query', async () => {
        const mockNovels: Novel[] = [
            { id: 1, title: 'Apple Book', status: 'active', chapter_count: 10 },
            { id: 2, title: 'Banana Book', status: 'completed', chapter_count: 20 },
        ];

        vi.mocked(api.getNovels).mockResolvedValue({ novels: mockNovels, total: 2 });

        render(
            <BrowserRouter>
                <Library />
            </BrowserRouter>
        );

        await waitFor(() => {
            expect(screen.getByText('Apple Book')).toBeInTheDocument();
        });

        const searchInput = screen.getByPlaceholderText('Search library...');
        fireEvent.change(searchInput, { target: { value: 'Banana' } });

        expect(screen.queryByText('Apple Book')).not.toBeInTheDocument();
        expect(screen.getByText('Banana Book')).toBeInTheDocument();
    });

    it('navigates to novel detail on click', async () => {
        const mockNovels: Novel[] = [
            { id: 1, title: 'Clickable Novel', status: 'active', chapter_count: 10 },
        ];

        vi.mocked(api.getNovels).mockResolvedValue({ novels: mockNovels, total: 1 });

        render(
            <BrowserRouter>
                <Library />
            </BrowserRouter>
        );

        await waitFor(() => {
            expect(screen.getByText('Clickable Novel')).toBeInTheDocument();
        });

        fireEvent.click(screen.getByText('Clickable Novel'));

        expect(mockNavigate).toHaveBeenCalledWith('/library/1');
    });

    // Property Test: Novel Display Completeness
    it.skip('Property 9: Novel Display Completeness - correctly renders any valid novel data', async () => {
        await fc.assert(
            fc.asyncProperty(
                fc.record({
                    id: fc.integer({ min: 1 }),
                    title: fc.string({ minLength: 1 }),
                    author: fc.option(fc.string(), { nil: undefined }),
                    cover_url: fc.option(fc.webUrl(), { nil: undefined }),
                    synopsis: fc.option(fc.string(), { nil: undefined }),
                    tags: fc.option(fc.array(fc.string()), { nil: undefined }),
                    status: fc.constantFrom('active', 'completed', 'hiatus', 'dropped'),
                    chapter_count: fc.integer({ min: 0 }),
                    created_at: fc.option(fc.date().map(d => d.toISOString()), { nil: undefined }),
                    updated_at: fc.option(fc.date().map(d => d.toISOString()), { nil: undefined })
                }),
                async (novel) => {
                    // Cleanup previous run
                    cleanup();

                    // Setup
                    vi.mocked(api.getNovels).mockResolvedValue({ novels: [novel], total: 1 });

                    // Render
                    const { unmount } = render(
                        <BrowserRouter>
                            <Library />
                        </BrowserRouter>
                    );

                    // Verify
                    await waitFor(() => {
                        // Title might match author or other text, so use getAllByText
                        const titles = screen.getAllByText(novel.title);
                        expect(titles.length).toBeGreaterThan(0);
                        expect(titles[0]).toBeInTheDocument();

                        if (novel.author) {
                            const authors = screen.getAllByText(novel.author);
                            expect(authors.length).toBeGreaterThan(0);
                            expect(authors[0]).toBeInTheDocument();
                        } else {
                            const placeholders = screen.getAllByText('Unknown Author');
                            expect(placeholders.length).toBeGreaterThan(0);
                            expect(placeholders[0]).toBeInTheDocument();
                        }

                        // Chapter count
                        const chapterCounts = screen.getAllByText(`${novel.chapter_count} Ch`);
                        expect(chapterCounts.length).toBeGreaterThan(0);

                        // Status
                        const statuses = screen.getAllByText(novel.status);
                        expect(statuses.length).toBeGreaterThan(0);
                    });

                    // Cleanup
                    unmount();
                }
            ),
            { numRuns: 20 } // Reduced runs for component testing speed
        );
    });
});
