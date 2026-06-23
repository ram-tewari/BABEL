
import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import { useReadingProgress } from '@/stores/readingProgressStore';

// 1. Hoist the mock function
const { mockHook } = vi.hoisted(() => ({
    mockHook: vi.fn(),
}));

// 2. Mock the module
vi.mock('@/stores/readingProgressStore', () => ({
    useReadingProgress: mockHook,
}));

// 3. Component that uses the store
function TestComponent() {
    const state = useReadingProgress();
    return <div>{state.currentNovelId || 'default'}</div>;
}

describe('Mock Check', () => {
    it('should return mocked value', () => {
        mockHook.mockReturnValue({ currentNovelId: 'novel-123' });

        const { getByText } = render(<TestComponent />);

        expect(getByText('novel-123')).toBeDefined();
    });

    it('should return default value', () => {
        mockHook.mockReturnValue({ currentNovelId: null });

        const { getByText } = render(<TestComponent />);

        expect(getByText('default')).toBeDefined();
    });
});
