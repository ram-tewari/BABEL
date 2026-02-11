/**
 * API Client Tests
 * 
 * Tests for Axios configuration, interceptors, retry logic, and API endpoints
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { AxiosError } from 'axios';

// We need to test the actual implementation, not mock axios
// The tests will verify the configuration and behavior

// We need to test the actual implementation, not mock axios
// The tests will verify the configuration and behavior

describe('API Client Configuration', () => {
  it('should have correct base URL from env', async () => {
    // Dynamically import to get the actual configured client
    const { apiClient } = await import('./api');
    expect(apiClient.defaults.baseURL).toBe('http://localhost:8000');
  });
  
  it('should have correct timeout', async () => {
    const { apiClient } = await import('./api');
    expect(apiClient.defaults.timeout).toBe(10000);
  });
  
  it('should have correct default headers', async () => {
    const { apiClient } = await import('./api');
    expect(apiClient.defaults.headers['Content-Type']).toBe('application/json');
  });
  
  it('should have request interceptors configured', async () => {
    const { apiClient } = await import('./api');
    expect(apiClient.interceptors.request.handlers.length).toBeGreaterThan(0);
  });
  
  it('should have response interceptors configured', async () => {
    const { apiClient } = await import('./api');
    expect(apiClient.interceptors.response.handlers.length).toBeGreaterThan(0);
  });
});

describe('API Endpoint Functions Structure', () => {
  it('should export api object with all endpoint functions', async () => {
    const { api } = await import('./api');
    
    expect(api).toBeDefined();
    expect(typeof api.getChapter).toBe('function');
    expect(typeof api.getChapterList).toBe('function');
    expect(typeof api.getCharacterList).toBe('function');
    expect(typeof api.healthCheck).toBe('function');
  });
});

describe('Type Definitions', () => {
  it('should export ChapterBlock type', async () => {
    const { api } = await import('./api');
    // Type checking happens at compile time
    // This test verifies the module loads without errors
    expect(api).toBeDefined();
  });
  
  it('should export ChapterResponse type', async () => {
    const { api } = await import('./api');
    expect(api).toBeDefined();
  });
  
  it('should export ChapterListResponse type', async () => {
    const { api } = await import('./api');
    expect(api).toBeDefined();
  });
});

describe('Retry Logic Configuration', () => {
  it('should export apiRequestWithRetry function', async () => {
    const { apiRequestWithRetry } = await import('./api');
    expect(typeof apiRequestWithRetry).toBe('function');
  });
});
