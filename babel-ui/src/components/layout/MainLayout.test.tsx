/**
 * MainLayout Component Tests
 * 
 * Tests for the root layout component including:
 * - Layout structure rendering
 * - Sidebar toggle functionality
 * - Children rendering
 * - Responsive layout classes
 * - Accessibility
 * 
 * Updated to work with real Header/Sidebar components and mocked providers.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MainLayout } from './MainLayout';

// Mock the useChapterList hook for Sidebar
vi.mock('@/hooks/useChapterList', () => ({
  useChapterList: () => ({
    data: { chapters: [], total: 0, novel_id: 'default' },
    isLoading: false,
    error: null,
  }),
}));

const renderWithProviders = (ui: React.ReactElement) => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    </QueryClientProvider>
  );
};

describe('MainLayout', () => {
  it('should render the layout structure', () => {
    renderWithProviders(<MainLayout />);

    // Check for main structural elements
    expect(screen.getByRole('complementary')).toBeInTheDocument(); // aside (Sidebar)
    expect(screen.getByRole('banner')).toBeInTheDocument(); // header (Header)
    expect(screen.getByRole('main')).toBeInTheDocument(); // main
  });

  it('should render children content', () => {
    renderWithProviders(
      <MainLayout>
        <div>Test Content</div>
      </MainLayout>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('should have sidebar component', () => {
    renderWithProviders(<MainLayout />);

    // Sidebar should show Table of Contents
    expect(screen.getByText('Table of Contents')).toBeInTheDocument();
  });

  it('should have header with BABEL title', () => {
    renderWithProviders(<MainLayout />);

    expect(screen.getByText(/SYSTEM: BABEL/i)).toBeInTheDocument();
  });

  it('should render toggle sidebar button', () => {
    renderWithProviders(<MainLayout />);

    const toggleButton = screen.getByLabelText('Toggle sidebar');
    expect(toggleButton).toBeInTheDocument();
  });

  it('should have sticky header', () => {
    renderWithProviders(<MainLayout />);

    const header = screen.getByRole('banner');
    expect(header).toHaveClass('sticky');
    expect(header).toHaveClass('top-0');
  });

  it('should have proper z-index for header', () => {
    renderWithProviders(<MainLayout />);

    const header = screen.getByRole('banner');
    expect(header).toHaveClass('z-10');
  });

  it('should have accessible toggle button', () => {
    renderWithProviders(<MainLayout />);

    const toggleButton = screen.getByLabelText('Toggle sidebar');
    expect(toggleButton).toBeInTheDocument();
    expect(toggleButton).toHaveAttribute('aria-label', 'Toggle sidebar');
  });

  it('should apply theme colors from CSS variables', () => {
    const { container } = renderWithProviders(<MainLayout />);

    const appContainer = container.querySelector('.app-container');
    expect(appContainer).toHaveClass('bg-bg-primary');
    expect(appContainer).toHaveClass('text-text-main');
  });

  it('should have grid layout container', () => {
    const { container } = renderWithProviders(<MainLayout />);

    const gridContainer = container.querySelector('.app-container > div');
    expect(gridContainer).toHaveClass('grid');
  });

  it('should have responsive classes for mobile', () => {
    const { container } = renderWithProviders(<MainLayout />);

    const gridContainer = container.querySelector('.app-container > div');
    expect(gridContainer).toHaveClass('max-md:grid-cols-1');
  });

  it('should render main content area', () => {
    renderWithProviders(<MainLayout />);

    const main = screen.getByRole('main');
    expect(main).toHaveClass('overflow-y-auto');
    expect(main).toHaveClass('p-6');
  });

  it('should render settings button in header', () => {
    renderWithProviders(<MainLayout />);

    expect(screen.getByLabelText('Open settings')).toBeInTheDocument();
  });
});
