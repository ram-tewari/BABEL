import React, { useState, useRef } from 'react';
import { Upload, X, Loader2, CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '../../lib/api';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

type ImportStatus = 'idle' | 'uploading' | 'success' | 'error';

/**
 * ImportModal Component
 * 
 * Handles EPUB file upload and novel import.
 * Displays progress and handles errors gracefully.
 * 
 * Requirements: 2.6, 2.7
 */
const ImportModal: React.FC<ImportModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [status, setStatus] = useState<ImportStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.name.endsWith('.epub')) {
      setError('Please select a valid EPUB file');
      return;
    }

    setFileName(file.name);
    setError(null);
    setStatus('uploading');
    setProgress(0);

    try {
      // Simulate progress
      const progressInterval = setInterval(() => {
        setProgress(prev => Math.min(prev + Math.random() * 30, 90));
      }, 500);

      await api.importNovel(file);

      clearInterval(progressInterval);
      setProgress(100);
      setStatus('success');

      // Auto-close after 2 seconds
      setTimeout(() => {
        onSuccess?.();
        handleClose();
      }, 2000);
    } catch (err) {
      setStatus('error');
      setError(
        err instanceof Error
          ? err.message
          : 'Failed to import novel. Please try again.'
      );
    }
  };

  const handleClose = () => {
    setStatus('idle');
    setError(null);
    setFileName(null);
    setProgress(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-lg bg-gray-900 border border-white/10 shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 px-6 py-4">
          <h2 className="text-lg font-semibold text-white">Import Novel</h2>
          <button
            onClick={handleClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          {status === 'idle' && (
            <div className="space-y-4">
              <p className="text-sm text-gray-400">
                Select an EPUB file to import a new novel to your library.
              </p>

              <div
                onClick={() => fileInputRef.current?.click()}
                className="relative border-2 border-dashed border-white/20 rounded-lg p-8 text-center cursor-pointer hover:border-blue-500/50 hover:bg-blue-500/5 transition-all"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".epub"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <Upload className="h-8 w-8 text-gray-500 mx-auto mb-3" />
                <p className="text-sm font-medium text-white">
                  Click to select EPUB file
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  or drag and drop
                </p>
              </div>

              <p className="text-xs text-gray-500 text-center">
                Supported format: EPUB (.epub)
              </p>
            </div>
          )}

          {status === 'uploading' && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
                <div className="flex-1">
                  <p className="text-sm font-medium text-white truncate">
                    {fileName}
                  </p>
                  <p className="text-xs text-gray-500">Importing...</p>
                </div>
              </div>

              <div className="w-full bg-gray-800 rounded-full h-2 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>

              <p className="text-xs text-gray-500 text-center">
                {Math.round(progress)}%
              </p>
            </div>
          )}

          {status === 'success' && (
            <div className="space-y-4 text-center">
              <div className="flex justify-center">
                <CheckCircle className="h-12 w-12 text-green-500" />
              </div>
              <div>
                <p className="text-sm font-medium text-white">
                  Novel imported successfully!
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {fileName}
                </p>
              </div>
            </div>
          )}

          {status === 'error' && (
            <div className="space-y-4">
              <div className="flex items-start gap-3 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-red-400">
                    Import failed
                  </p>
                  <p className="text-xs text-red-300 mt-1">
                    {error}
                  </p>
                </div>
              </div>

              <button
                onClick={() => fileInputRef.current?.click()}
                className="w-full px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-500 transition-colors"
              >
                Try Again
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        {status !== 'uploading' && (
          <div className="border-t border-white/10 px-6 py-4 flex justify-end gap-3">
            <button
              onClick={handleClose}
              className="px-4 py-2 rounded-lg bg-white/5 text-gray-300 text-sm font-medium hover:bg-white/10 transition-colors"
            >
              {status === 'success' ? 'Done' : 'Cancel'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ImportModal;
