/**
 * API Client Configuration
 * 
 * Axios instance configured for BABEL FastAPI backend communication.
 * Includes request/response interceptors, error handling, and retry logic.
 */

import axios, { AxiosError } from 'axios';
import type { AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';

// Get API base URL from environment variable
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Configured Axios instance for API requests
 */
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000, // 10 second timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Request interceptor
 * - Logs outgoing requests in development
 * - Can add authentication headers in the future
 */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Log requests in development
    if (import.meta.env.DEV) {
      console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
    }

    // Future: Add authentication token
    // const token = localStorage.getItem('auth_token');
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }

    return config;
  },
  (error: AxiosError) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

/**
 * Response interceptor
 * - Handles common error responses
 * - Logs responses in development
 */
apiClient.interceptors.response.use(
  (response) => {
    // Log successful responses in development
    if (import.meta.env.DEV) {
      console.log(`[API Response] ${response.status} ${response.config.url}`);
    }
    return response;
  },
  (error: AxiosError) => {
    // Handle specific error status codes
    if (error.response) {
      const status = error.response.status;
      const url = error.config?.url;

      switch (status) {
        case 404:
          console.error(`[API Error] Resource not found: ${url}`);
          break;
        case 500:
          console.error(`[API Error] Server error: ${url}`);
          break;
        case 503:
          console.error(`[API Error] Service unavailable: ${url}`);
          break;
        default:
          console.error(`[API Error] ${status}: ${url}`);
      }
    } else if (error.request) {
      // Request was made but no response received (network error)
      console.error('[API Error] Network error - no response received');
    } else {
      // Something else happened
      console.error('[API Error]', error.message);
    }

    return Promise.reject(error);
  }
);

/**
 * Retry configuration for network failures
 * Implements exponential backoff strategy
 */
interface RetryConfig extends AxiosRequestConfig {
  _retry?: number;
  _retryDelay?: number;
}

/**
 * Maximum number of retry attempts
 */
const MAX_RETRIES = 3;

/**
 * Initial retry delay in milliseconds
 */
const INITIAL_RETRY_DELAY = 1000;

/**
 * Maximum retry delay in milliseconds (30 seconds)
 */
const MAX_RETRY_DELAY = 30000;

/**
 * Makes an API request with automatic retry logic
 * 
 * @param config - Axios request configuration
 * @returns Promise with the response data
 */
export async function apiRequestWithRetry<T>(config: AxiosRequestConfig): Promise<T> {
  const retryConfig = config as RetryConfig;
  retryConfig._retry = retryConfig._retry || 0;
  retryConfig._retryDelay = retryConfig._retryDelay || INITIAL_RETRY_DELAY;

  try {
    const response = await apiClient.request<T>(config);
    return response.data;
  } catch (error) {
    const axiosError = error as AxiosError;

    // Only retry on network errors or 5xx server errors
    const shouldRetry =
      !axiosError.response ||
      (axiosError.response.status >= 500 && axiosError.response.status < 600);

    if (shouldRetry && retryConfig._retry! < MAX_RETRIES) {
      retryConfig._retry!++;

      // Calculate exponential backoff delay
      const delay = Math.min(
        retryConfig._retryDelay! * Math.pow(2, retryConfig._retry! - 1),
        MAX_RETRY_DELAY
      );

      console.log(
        `[API Retry] Attempt ${retryConfig._retry}/${MAX_RETRIES} after ${delay}ms delay`
      );

      // Wait before retrying
      await new Promise(resolve => setTimeout(resolve, delay));

      // Update retry delay for next attempt
      retryConfig._retryDelay = delay;

      // Retry the request
      return apiRequestWithRetry<T>(retryConfig);
    }

    // Max retries reached or non-retryable error
    throw error;
  }
}

/**
 * Type definitions for API responses
 * These will be expanded in src/types/api.ts
 */

export interface ChapterBlock {
  type: 'dialogue' | 'thought' | 'narrator' | 'action' | 'system' | 'monologue';
  speaker?: string;
  content: string;
  tone?: string;
}

export interface ChapterMetadata {
  model_version: string;
  processed_at: string;
  source_hash: string;
}

export interface ChapterNavigation {
  prev?: number;
  next?: number;
}

export interface ChapterResponse {
  id: number;
  chapter_index: number;
  filename: string;
  title: string;
  blocks: ChapterBlock[];
  metadata?: ChapterMetadata;
  navigation?: ChapterNavigation;
}

export interface ChapterListItem {
  id: number;
  chapter_index: number;
  filename: string;
  title: string;
  status: string;
  phase: string;
}

export interface ChapterListResponse {
  chapters: ChapterListItem[];
  total: number;
  novel_id: string;
}

export interface CharacterListResponse {
  characters: string[];
  total: number;
}

export interface GraphNode {
  id: string;
  name: string;
  line_count: number;
  first_chapter: number;
  faction?: string | null;
  description?: string | null;
  aliases: string[];
  color?: string | null;
}

export interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}

export interface CharacterGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  chapters_scanned: number;
}

export interface GlossaryEntry {
  name: string;
  aliases: string[];
  faction?: string | null;
  description?: string | null;
  color?: string | null;
}

export interface GlossaryResponse {
  characters: GlossaryEntry[];
  factions: Record<string, { color?: string; description?: string }>;
}

export interface Novel {
  id: number;
  title: string;
  author?: string;
  cover_url?: string;
  synopsis?: string;
  tags?: string[];
  status: string;
  chapter_count: number;
  created_at?: string;
  updated_at?: string;
}

export interface NovelListResponse {
  novels: Novel[];
  total: number;
}

export interface ImportResponse {
  novel_id: number;
  title: string;
  chapters_extracted: number;
  status: string;
}

export interface NovelUpdate {
  title?: string;
  author?: string;
  cover_url?: string;
  synopsis?: string;
  tags?: string[];
  status?: string;
}

export interface HealthResponse {
  status: string;
  version: string;
  timestamp: string;
}

/**
 * API endpoint functions
 * These provide a clean interface for making API calls
 */
export const api = {
  /**
   * Get chapter data by ID
   * @param id - Chapter ID
   * @returns Promise with chapter data
   */
  getChapter: (id: number) =>
    apiRequestWithRetry<ChapterResponse>({
      method: 'GET',
      url: `/api/chapters/${id}`,
    }),

  /**
   * Get chapter list (metadata only)
   * @param novelId - Novel ID (default: 'default')
   * @returns Promise with chapter list
   */
  getChapterList: (novelId: string = 'default') =>
    apiRequestWithRetry<ChapterListResponse>({
      method: 'GET',
      url: '/api/chapters/metadata',
      params: { novel_id: novelId },
    }),

  getNovelChapters: (novelId: number | string) =>
    apiRequestWithRetry<ChapterListResponse>({
      method: 'GET',
      url: `/api/library/${novelId}/chapters`,
    }),

  /**
   * Get a single chapter from a novel (Library API)
   * @param novelId - Novel ID
   * @param chapterId - Chapter ID
   * @returns Promise with chapter detail
   */
  getNovelChapter: (novelId: number, chapterId: number) =>
    apiRequestWithRetry<ChapterResponse>({
      method: 'GET',
      url: `/api/library/${novelId}/chapter/${chapterId}`,
    }),

  /**
   * Get character list
   * @returns Promise with character list
   */
  getCharacterList: () =>
    apiRequestWithRetry<CharacterListResponse>({
      method: 'GET',
      url: '/api/characters/list',
    }),

  /**
   * Get the character relationship graph.
   * @param novelId - Optional novel ID (omit for legacy data/json)
   * @param upToChapter - Spoiler-safe limit: only scan chapters before this index
   */
  getCharacterGraph: (novelId?: number, upToChapter?: number) =>
    apiRequestWithRetry<CharacterGraphResponse>({
      method: 'GET',
      url: '/api/characters/graph',
      params: {
        ...(novelId != null ? { novel_id: novelId } : {}),
        ...(upToChapter != null ? { up_to_chapter: upToChapter } : {}),
      },
    }),

  /**
   * Get glossary entries (characters + factions) for tooltips.
   * @param novelId - Optional novel ID
   */
  getGlossary: (novelId?: number) =>
    apiRequestWithRetry<GlossaryResponse>({
      method: 'GET',
      url: '/api/glossary',
      params: novelId != null ? { novel_id: novelId } : {},
    }),

  /**
   * Health check endpoint
   * @returns Promise with health status
   */
  healthCheck: () =>
    apiRequestWithRetry<HealthResponse>({
      method: 'GET',
      url: '/health',
    }),

  /**
   * Get all novels
   * @param limit - Max number of novels (default: 100)
   * @param offset - Offset for pagination (default: 0)
   * @returns Promise with novel list
   */
  getNovels: (limit: number = 100, offset: number = 0) =>
    apiRequestWithRetry<NovelListResponse>({
      method: 'GET',
      url: '/api/library',
      params: { limit, offset },
    }),

  /**
   * Get a single novel by ID
   * @param id - Novel ID
   * @returns Promise with novel data
   */
  getNovel: (id: number) =>
    apiRequestWithRetry<Novel>({
      method: 'GET',
      url: `/api/library/${id}`,
    }),

  /**
   * Import an EPUB file
   * @param file - EPUB file
   * @returns Promise with import result
   */
  importNovel: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiRequestWithRetry<ImportResponse>({
      method: 'POST',
      url: '/api/library/import',
      data: formData,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      timeout: 60000, // Longer timeout for imports
    });
  },

  /**
   * Delete a novel
   * @param id - Novel ID
   * @returns Promise with success message
   */
  deleteNovel: (id: number) =>
    apiRequestWithRetry<{ message: string }>({
      method: 'DELETE',
      url: `/api/library/${id}`,
    }),

  /**
   * Update novel metadata
   * @param id - Novel ID
   * @param data - Update data
   * @returns Promise with updated novel
   */
  updateNovel: (id: number, data: NovelUpdate) =>
    apiRequestWithRetry<Novel>({
      method: 'PUT',
      url: `/api/library/${id}`,
      data,
    }),
};

/**
 * Export the configured client for direct use if needed
 */
export default apiClient;

export const getChapter = api.getChapter;
