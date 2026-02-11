/**
 * NotFound Page Component
 * 
 * 404 error page for invalid routes.
 * This is a placeholder implementation for Task 4.1.
 */

import { Link } from 'react-router-dom';

export function NotFound() {
  return (
    <div className="min-h-screen bg-[var(--bg-primary)] text-[var(--text-main)] flex items-center justify-center p-8">
      <div className="max-w-2xl mx-auto text-center">
        {/* Error Display */}
        <div className="glass rounded-2xl p-12">
          <div className="text-8xl mb-6">🔍</div>
          <h1 className="text-6xl font-bold text-[var(--accent)] mb-4">
            404
          </h1>
          <h2 className="text-2xl font-semibold text-[var(--text-main)] mb-4">
            Page Not Found
          </h2>
          <p className="text-[var(--text-dim)] mb-8">
            The page you're looking for doesn't exist or has been moved.
          </p>
          
          {/* Action Buttons */}
          <div className="flex gap-4 justify-center">
            <Link
              to="/"
              className="px-6 py-3 rounded-xl bg-[var(--accent)] text-[var(--bg-primary)] border-2 border-[var(--accent)] hover:bg-[var(--accent-hover)] transition-all font-medium"
            >
              ← Back to Home
            </Link>
            <button
              onClick={() => window.history.back()}
              className="px-6 py-3 rounded-xl bg-[var(--bg-tertiary)] text-[var(--text-main)] border-2 border-[var(--border)] hover:border-[var(--accent)] transition-all font-medium"
            >
              Go Back
            </button>
          </div>
        </div>

        {/* Status */}
        <div className="mt-8 text-[var(--text-ghost)] text-sm">
          <p>✅ Task 4.1: React Router Configuration - 404 Page</p>
        </div>
      </div>
    </div>
  );
}
