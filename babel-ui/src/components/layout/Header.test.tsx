import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Header } from './Header';

describe('Header Component', () => {
  describe('Rendering', () => {
    it('should render the header element', () => {
      render(<Header />);
      const header = screen.getByRole('banner');
      expect(header).toBeInTheDocument();
    });

    it('should display default title when no chapterTitle provided', () => {
      render(<Header />);
      expect(screen.getByText('SYSTEM: BABEL')).toBeInTheDocument();
    });

    it('should display provided chapter title', () => {
      render(<Header chapterTitle="Chapter 1: Encountering Magic" />);
      expect(screen.getByText('Chapter 1: Encountering Magic')).toBeInTheDocument();
    });

    it('should render menu toggle button', () => {
      render(<Header />);
      const menuButton = screen.getByLabelText('Toggle sidebar');
      expect(menuButton).toBeInTheDocument();
    });

    it('should render settings button', () => {
      render(<Header />);
      const settingsButton = screen.getByLabelText('Open settings');
      expect(settingsButton).toBeInTheDocument();
    });
  });

  describe('Interactions', () => {
    it('should call onToggleSidebar when menu button is clicked', () => {
      const handleToggle = vi.fn();
      render(<Header onToggleSidebar={handleToggle} />);

      const menuButton = screen.getByLabelText('Toggle sidebar');
      fireEvent.click(menuButton);

      expect(handleToggle).toHaveBeenCalledTimes(1);
    });

    it('should not throw error when menu button clicked without callback', () => {
      render(<Header />);

      const menuButton = screen.getByLabelText('Toggle sidebar');
      expect(() => fireEvent.click(menuButton)).not.toThrow();
    });

    it('should open settings modal when settings button is clicked', () => {
      render(<Header />);

      const settingsButton = screen.getByLabelText('Open settings');
      fireEvent.click(settingsButton);

      // SettingsModal should now be visible
      expect(screen.getByTestId('settings-modal-header')).toBeInTheDocument();
      expect(screen.getByText('⚙️ Settings')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('should have sticky positioning', () => {
      render(<Header />);
      const header = screen.getByRole('banner');
      expect(header).toHaveClass('sticky');
    });

    it('should have glassmorphism effect', () => {
      render(<Header />);
      const header = screen.getByRole('banner');
      expect(header).toHaveClass('glass');
    });

    it('should have proper z-index for stacking', () => {
      render(<Header />);
      const header = screen.getByRole('banner');
      expect(header).toHaveClass('z-10');
    });

    it('should have border at bottom', () => {
      render(<Header />);
      const header = screen.getByRole('banner');
      expect(header).toHaveClass('border-b');
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels on buttons', () => {
      render(<Header />);

      expect(screen.getByLabelText('Toggle sidebar')).toBeInTheDocument();
      expect(screen.getByLabelText('Open settings')).toBeInTheDocument();
    });

    it('should have title attributes for tooltips', () => {
      render(<Header />);

      const menuButton = screen.getByLabelText('Toggle sidebar');
      expect(menuButton).toHaveAttribute('title', 'Toggle sidebar (Ctrl+B)');

      const settingsButton = screen.getByLabelText('Open settings');
      expect(settingsButton).toHaveAttribute('title', 'Settings');
    });

    it('should be keyboard accessible', () => {
      const handleToggle = vi.fn();
      render(<Header onToggleSidebar={handleToggle} />);

      const menuButton = screen.getByLabelText('Toggle sidebar');
      menuButton.focus();
      expect(menuButton).toHaveFocus();
    });
  });

  describe('Responsive Design', () => {
    it('should truncate long chapter titles', () => {
      const longTitle = 'Chapter 1: This is a very long chapter title that should be truncated to prevent layout issues';
      render(<Header chapterTitle={longTitle} />);

      const titleElement = screen.getByText(longTitle);
      expect(titleElement).toHaveClass('truncate');
    });

    it('should have responsive max-width for chapter title', () => {
      render(<Header chapterTitle="Chapter 1" />);

      const titleElement = screen.getByText('Chapter 1');
      expect(titleElement).toHaveClass('max-w-[300px]');
      expect(titleElement).toHaveClass('md:max-w-[500px]');
    });
  });

  describe('Button Hover Effects', () => {
    it('should have hover styles on menu button', () => {
      render(<Header />);
      const menuButton = screen.getByLabelText('Toggle sidebar');

      expect(menuButton).toHaveClass('hover:bg-[var(--bg-tertiary)]');
      expect(menuButton).toHaveClass('hover:scale-105');
    });

    it('should have hover styles on settings button', () => {
      render(<Header />);
      const settingsButton = screen.getByLabelText('Open settings');

      expect(settingsButton).toHaveClass('hover:bg-[var(--bg-tertiary)]');
      expect(settingsButton).toHaveClass('hover:scale-105');
    });

    it('should have active (pressed) styles on buttons', () => {
      render(<Header />);
      const menuButton = screen.getByLabelText('Toggle sidebar');

      expect(menuButton).toHaveClass('active:scale-95');
    });
  });

  describe('Integration', () => {
    it('should work with MainLayout integration', () => {
      const handleToggle = vi.fn();
      render(
        <Header
          chapterTitle="Test Chapter"
          onToggleSidebar={handleToggle}
        />
      );

      // Verify all elements are present
      expect(screen.getByText('Test Chapter')).toBeInTheDocument();
      expect(screen.getByLabelText('Toggle sidebar')).toBeInTheDocument();
      expect(screen.getByLabelText('Open settings')).toBeInTheDocument();

      // Verify interaction works
      fireEvent.click(screen.getByLabelText('Toggle sidebar'));
      expect(handleToggle).toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    it('should handle empty string chapter title', () => {
      render(<Header chapterTitle="" />);
      expect(screen.getByText('SYSTEM: BABEL')).toBeInTheDocument();
    });

    it('should handle undefined chapter title', () => {
      render(<Header chapterTitle={undefined} />);
      expect(screen.getByText('SYSTEM: BABEL')).toBeInTheDocument();
    });

    it('should handle multiple rapid clicks on menu button', () => {
      const handleToggle = vi.fn();
      render(<Header onToggleSidebar={handleToggle} />);

      const menuButton = screen.getByLabelText('Toggle sidebar');
      fireEvent.click(menuButton);
      fireEvent.click(menuButton);
      fireEvent.click(menuButton);

      expect(handleToggle).toHaveBeenCalledTimes(3);
    });

    it('should handle special characters in chapter title', () => {
      const specialTitle = 'Chapter 1: "The Beginning" & <The End>';
      render(<Header chapterTitle={specialTitle} />);
      expect(screen.getByText(specialTitle)).toBeInTheDocument();
    });
  });
});
