/**
 * Correction Dashboard Page
 * 
 * Displays statistics and analytics for manual block corrections.
 * Enables export of correction data for ML training.
 */

import { useEffect, useState } from 'react';
import { Download, TrendingUp, CheckCircle, AlertCircle } from 'lucide-react';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';

interface CorrectionStats {
  total_corrections: number;
  by_type: Record<string, number>;
  recent_corrections: Array<{
    chapter_id: string;
    block_index: number;
    original_type: string;
    corrected_type: string;
    correction_reason?: string;
    corrected_at: string;
  }>;
}

export function CorrectionDashboard() {
  const [stats, setStats] = useState<CorrectionStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/corrections/stats');
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load statistics');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: 'json' | 'csv' | 'jsonl') => {
    try {
      setExporting(format);
      const response = await fetch(`/api/corrections/export?format=${format}`);
      if (!response.ok) throw new Error('Export failed');

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `corrections.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setExporting(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <AlertCircle className="w-16 h-16 text-red-500" />
        <h2 className="text-2xl font-semibold text-[var(--text-main)]">Error Loading Stats</h2>
        <p className="text-[var(--text-dim)]">{error}</p>
        <button
          onClick={fetchStats}
          className="px-6 py-2 rounded-xl bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-all"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="container mx-auto p-6 space-y-6 max-w-6xl animate-fadeIn">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-[var(--text-main)]">Correction Dashboard</h1>
          <p className="text-[var(--text-dim)] mt-1">
            Track and analyze manual block corrections for quality improvement
          </p>
        </div>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Total Corrections */}
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <h3 className="text-sm font-medium text-[var(--text-dim)]">Total Corrections</h3>
          </div>
          <div className="text-4xl font-bold text-[var(--text-main)]">
            {stats.total_corrections}
          </div>
        </div>

        {/* Most Common Correction */}
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-2">
            <TrendingUp className="w-5 h-5 text-blue-500" />
            <h3 className="text-sm font-medium text-[var(--text-dim)]">Most Common</h3>
          </div>
          <div className="text-2xl font-bold text-[var(--text-main)]">
            {Object.entries(stats.by_type).length > 0
              ? Object.entries(stats.by_type).sort((a, b) => b[1] - a[1])[0][0]
              : 'N/A'}
          </div>
          <div className="text-sm text-[var(--text-dim)] mt-1">
            {Object.entries(stats.by_type).length > 0
              ? `${Object.entries(stats.by_type).sort((a, b) => b[1] - a[1])[0][1]} occurrences`
              : 'No corrections yet'}
          </div>
        </div>

        {/* Export Data */}
        <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
          <div className="flex items-center gap-3 mb-2">
            <Download className="w-5 h-5 text-purple-500" />
            <h3 className="text-sm font-medium text-[var(--text-dim)]">Export Data</h3>
          </div>
          <div className="flex flex-col gap-2 mt-3">
            <button
              onClick={() => handleExport('json')}
              disabled={exporting !== null}
              className="px-4 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-main)] border border-[var(--border)] hover:border-[var(--accent)] transition-all text-sm disabled:opacity-50"
            >
              {exporting === 'json' ? 'Exporting...' : 'JSON'}
            </button>
            <button
              onClick={() => handleExport('csv')}
              disabled={exporting !== null}
              className="px-4 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-main)] border border-[var(--border)] hover:border-[var(--accent)] transition-all text-sm disabled:opacity-50"
            >
              {exporting === 'csv' ? 'Exporting...' : 'CSV'}
            </button>
            <button
              onClick={() => handleExport('jsonl')}
              disabled={exporting !== null}
              className="px-4 py-2 rounded-lg bg-[var(--bg-tertiary)] text-[var(--text-main)] border border-[var(--border)] hover:border-[var(--accent)] transition-all text-sm disabled:opacity-50"
            >
              {exporting === 'jsonl' ? 'Exporting...' : 'JSONL'}
            </button>
          </div>
        </div>
      </div>

      {/* Correction Types Breakdown */}
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
        <h3 className="text-lg font-semibold text-[var(--text-main)] mb-4">
          Correction Type Breakdown
        </h3>
        <div className="space-y-3">
          {Object.entries(stats.by_type).length > 0 ? (
            Object.entries(stats.by_type)
              .sort((a, b) => b[1] - a[1])
              .map(([transition, count]) => (
                <div key={transition} className="flex items-center justify-between">
                  <span className="font-mono text-sm text-[var(--text-main)]">
                    {transition}
                  </span>
                  <div className="flex items-center gap-3">
                    <div className="w-32 h-2 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
                      <div
                        className="h-full bg-[var(--accent)]"
                        style={{
                          width: `${(count / stats.total_corrections) * 100}%`
                        }}
                      />
                    </div>
                    <span className="font-bold text-[var(--text-main)] w-12 text-right">
                      {count}
                    </span>
                  </div>
                </div>
              ))
          ) : (
            <p className="text-[var(--text-dim)] text-center py-8">
              No corrections yet. Start editing blocks to see statistics here.
            </p>
          )}
        </div>
      </div>

      {/* Recent Corrections */}
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl p-6">
        <h3 className="text-lg font-semibold text-[var(--text-main)] mb-4">
          Recent Corrections
        </h3>
        <div className="space-y-3">
          {stats.recent_corrections.length > 0 ? (
            stats.recent_corrections.map((correction, i) => (
              <div
                key={i}
                className="border-b border-[var(--border)] pb-3 last:border-0 last:pb-0"
              >
                <div className="flex items-center justify-between text-sm mb-1">
                  <span className="font-mono text-[var(--text-dim)]">
                    {correction.chapter_id}
                  </span>
                  <span className="text-[var(--text-dim)]">
                    {new Date(correction.corrected_at).toLocaleString()}
                  </span>
                </div>
                <div className="text-sm">
                  Block #{correction.block_index}:{' '}
                  <span className="font-bold text-[var(--text-main)]">
                    {correction.original_type}
                  </span>
                  {' → '}
                  <span className="font-bold text-green-500">
                    {correction.corrected_type}
                  </span>
                </div>
                {correction.correction_reason && (
                  <div className="text-xs text-[var(--text-dim)] italic mt-1">
                    "{correction.correction_reason}"
                  </div>
                )}
              </div>
            ))
          ) : (
            <p className="text-[var(--text-dim)] text-center py-8">
              No corrections yet. Start editing blocks to see them here.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
