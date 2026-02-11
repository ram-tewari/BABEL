/**
 * Main Entry Point
 * 
 * Sets up React root, wraps app with BrowserRouter and QueryClientProvider.
 * Task 4.1: Configure React Router
 * Task 11.1: Configure QueryClient
 */

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.tsx'

/**
 * TanStack Query client configuration
 * - staleTime: 5 minutes (data is considered fresh)
 * - gcTime: 30 minutes (cache retention)
 * - retry: 3 attempts with exponential backoff
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 30 * 60 * 1000,
      retry: 3,
      retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000),
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
