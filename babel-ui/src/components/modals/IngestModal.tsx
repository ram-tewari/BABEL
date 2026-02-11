/**
 * IngestModal Component
 * 
 * Allows users to upload .txt or .epub files for ingestion.
 * Handles file selection, upload to API, and displays progress.
 */

import React, { useState } from 'react';
import { X, Upload, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import axios from 'axios';

interface IngestModalProps {
    open: boolean;
    onClose: () => void;
}

export function IngestModal({ open, onClose }: IngestModalProps) {
    const [file, setFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [message, setMessage] = useState('');

    if (!open) return null;

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            setFile(e.target.files[0]);
            setStatus('idle');
            setMessage('');
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        setUploading(true);
        setStatus('idle');

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await axios.post(`${import.meta.env.VITE_API_BASE_URL}/api/ingest`, formData, {
                headers: {
                    'Content-Type': 'multipart/form-data',
                },
            });

            setStatus('success');
            setMessage(response.data.message || 'File uploaded successfully!');
            setTimeout(() => {
                onClose();
                setFile(null);
                setStatus('idle');
                setMessage('');
            }, 2000);
        } catch (error: any) {
            console.error('Upload failed:', error);
            setStatus('error');
            setMessage(error.response?.data?.detail || 'Upload failed. Please try again.');
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <div className="bg-[var(--bg-secondary)] border border-[var(--glass-border)] shadow-2xl max-w-md w-full max-h-[90vh] overflow-y-auto p-6 rounded-2xl animate-fade-in relative">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 p-2 rounded-full hover:bg-[var(--bg-tertiary)] transition-colors text-[var(--text-dim)]"
                >
                    <X size={20} />
                </button>

                <h2 className="text-2xl font-bold mb-6 text-[var(--text-main)] font-serif">
                    Ingest Content
                </h2>

                <div className="space-y-6">
                    {/* File Drop Area (Simplified as click input for now) */}
                    <div className={`
            border-2 border-dashed rounded-xl p-8 text-center transition-all
            ${file ? 'border-[var(--accent)] bg-[var(--accent)]/5' : 'border-[var(--border)] hover:border-[var(--text-dim)]'}
          `}>
                        <input
                            type="file"
                            id="file-upload"
                            className="hidden"
                            accept=".txt,.epub"
                            onChange={handleFileChange}
                        />

                        <label htmlFor="file-upload" className="cursor-pointer block">
                            {file ? (
                                <div className="flex flex-col items-center gap-3">
                                    <FileText size={48} className="text-[var(--accent)]" />
                                    <div>
                                        <p className="font-medium text-[var(--text-main)] truncate max-w-[200px]">{file.name}</p>
                                        <p className="text-sm text-[var(--text-dim)]">{(file.size / 1024).toFixed(1)} KB</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex flex-col items-center gap-3">
                                    <Upload size={48} className="text-[var(--text-dim)]" />
                                    <div>
                                        <p className="font-medium text-[var(--text-main)]">Click to upload file</p>
                                        <p className="text-sm text-[var(--text-dim)]">Supports .txt, .epub</p>
                                    </div>
                                </div>
                            )}
                        </label>
                    </div>

                    {/* Status Messages */}
                    {status === 'success' && (
                        <div className="flex items-center gap-3 text-green-400 bg-green-400/10 p-4 rounded-xl border border-green-400/20">
                            <CheckCircle size={20} />
                            <p className="text-sm">{message}</p>
                        </div>
                    )}

                    {status === 'error' && (
                        <div className="flex items-center gap-3 text-red-400 bg-red-400/10 p-4 rounded-xl border border-red-400/20">
                            <AlertCircle size={20} />
                            <p className="text-sm">{message}</p>
                        </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-3 pt-2">
                        <button
                            onClick={onClose}
                            className="flex-1 px-4 py-3 rounded-xl border border-[var(--border)] text-[var(--text-dim)] hover:bg-[var(--bg-tertiary)] hover:text-[var(--text-main)] transition-colors font-medium"
                            disabled={uploading}
                        >
                            Cancel
                        </button>
                        <button
                            onClick={handleUpload}
                            disabled={!file || uploading}
                            className={`
                flex-1 px-4 py-3 rounded-xl font-medium transition-all shadow-lg
                ${!file || uploading
                                    ? 'bg-[var(--bg-tertiary)] text-[var(--text-dim)] cursor-not-allowed'
                                    : 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] hover:scale-[1.02] shadow-[var(--accent)]/25'}
              `}
                        >
                            {uploading ? 'Uploading...' : 'Start Ingestion'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
