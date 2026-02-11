/**
 * BlockEditor Modal Component
 * 
 * Provides inline editing interface for correcting block classifications.
 * 
 * Features:
 * - Block type selector
 * - Conditional speaker input
 * - Text editing
 * - Correction reason tracking
 * - Keyboard shortcuts (Esc to close, Ctrl+S to save)
 */

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';

interface Block {
  type: string;
  speaker?: string;
  text: string;
  corrected?: boolean;
  correction_id?: number;
}

interface BlockEditorProps {
  open: boolean;
  onClose: () => void;
  block: Block;
  blockIndex: number;
  chapterId: string;
  onSave: (updatedBlock: Block) => void;
  availableCharacters?: string[]; // List of characters in the chapter
}

const BLOCK_TYPES = [
  { value: 'DIALOGUE', label: '🗣️ Dialogue', needsSpeaker: true },
  { value: 'THOUGHT', label: '💭 Thought', needsSpeaker: true },
  { value: 'NARRATION', label: '📖 Narration', needsSpeaker: false },
  { value: 'ACTION', label: '⚡ Action', needsSpeaker: false },
  { value: 'SCENE_BREAK', label: '🎬 Scene Break', needsSpeaker: false },
];

export function BlockEditor({
  open,
  onClose,
  block,
  blockIndex,
  chapterId,
  onSave,
  availableCharacters = []
}: BlockEditorProps) {
  const [type, setType] = useState(block.type.toUpperCase());
  const [speaker, setSpeaker] = useState(block.speaker || '');
  const [text, setText] = useState(block.text);
  const [reason, setReason] = useState('');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedType = BLOCK_TYPES.find(t => t.value === type);
  const needsSpeaker = selectedType?.needsSpeaker || false;

  // Reset form when block changes
  useEffect(() => {
    setType(block.type.toUpperCase());
    setSpeaker(block.speaker || '');
    setText(block.text);
    setReason('');
    setError(null);
  }, [block]);

  // Keyboard shortcuts
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Esc to close
      if (e.key === 'Escape') {
        onClose();
      }
      // Ctrl+S to save
      if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        handleSave();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, type, speaker, text, reason]);

  const handleSave = async () => {
    setError(null);
    setSaving(true);

    try {
      const response = await fetch(
        `/api/chapters/${chapterId}/blocks/${blockIndex}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            type,
            speaker: needsSpeaker ? speaker : null,
            text,
            correction_reason: reason || null
          })
        }
      );

      if (!response.ok) {
        // Try to parse error response
        let errorMessage = `Failed to save correction (${response.status})`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch (parseErr) {
          // If JSON parsing fails, try to get text
          try {
            const errorText = await response.text();
            if (errorText) {
              errorMessage = `${errorMessage}: ${errorText.substring(0, 200)}`;
            }
          } catch {
            // Use status text as fallback
            errorMessage = `${errorMessage}: ${response.statusText}`;
          }
        }
        throw new Error(errorMessage);
      }

      // Parse successful response
      let data;
      try {
        data = await response.json();
      } catch (parseErr) {
        console.error('Failed to parse success response:', parseErr);
        throw new Error('Server returned invalid JSON response');
      }

      if (!data.updated_block) {
        throw new Error('Server response missing updated_block field');
      }

      onSave(data.updated_block);
      onClose();
    } catch (err) {
      console.error('Error saving correction:', err);
      setError(err instanceof Error ? err.message : 'Failed to save correction');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this block? This action cannot be undone.')) {
      return;
    }

    setError(null);
    setDeleting(true);

    try {
      const response = await fetch(
        `/api/chapters/${chapterId}/blocks/${blockIndex}`,
        {
          method: 'DELETE'
        }
      );

      if (!response.ok) {
        // Try to parse error if there's content
        let errorMessage = 'Failed to delete block';
        try {
          const errorData = await response.json();
          errorMessage = errorData.detail || errorMessage;
        } catch {
          // No JSON body, use status text
          errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
      }

      // 204 No Content - successful deletion
      // Signal deletion by passing null
      onSave(null as any);
      onClose();
    } catch (err) {
      console.error('Error deleting block:', err);
      setError(err instanceof Error ? err.message : 'Failed to delete block');
    } finally {
      setDeleting(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-fadeIn">
      <div className="bg-[var(--bg-secondary)] border border-[var(--border)] rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-[var(--border)]">
          <h2 className="text-xl font-semibold text-[var(--text-main)]">
            Edit Block #{blockIndex}
          </h2>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-[var(--text-dim)]" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {/* Error Message */}
          {error && (
            <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Block Type */}
          <div>
            <label htmlFor="type" className="block text-sm font-medium text-[var(--text-main)] mb-2">
              Block Type
            </label>
            <select
              id="type"
              value={type}
              onChange={(e) => setType(e.target.value)}
              className="w-full px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-xl text-[var(--text-main)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
            >
              {BLOCK_TYPES.map(({ value, label }) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          {/* Speaker (conditional) */}
          {needsSpeaker && (
            <div>
              <label htmlFor="speaker" className="block text-sm font-medium text-[var(--text-main)] mb-2">
                Speaker
              </label>
              {availableCharacters.length > 0 ? (
                <div className="flex gap-2">
                  <select
                    id="speaker"
                    value={speaker}
                    onChange={(e) => setSpeaker(e.target.value)}
                    className="flex-1 px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-xl text-[var(--text-main)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
                  >
                    <option value="">Select character...</option>
                    {availableCharacters.map((char) => (
                      <option key={char} value={char}>
                        {char}
                      </option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={speaker}
                    onChange={(e) => setSpeaker(e.target.value)}
                    placeholder="Or type custom name"
                    className="flex-1 px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-xl text-[var(--text-main)] placeholder:text-[var(--text-dim)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
                  />
                </div>
              ) : (
                <input
                  id="speaker"
                  type="text"
                  value={speaker}
                  onChange={(e) => setSpeaker(e.target.value)}
                  placeholder="Character name"
                  className="w-full px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-xl text-[var(--text-main)] placeholder:text-[var(--text-dim)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
                />
              )}
            </div>
          )}

          {/* Text */}
          <div>
            <label htmlFor="text" className="block text-sm font-medium text-[var(--text-main)] mb-2">
              Text
            </label>
            <textarea
              id="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={6}
              className="w-full px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-xl text-[var(--text-main)] font-mono text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all resize-none"
            />
          </div>

          {/* Correction Reason */}
          <div>
            <label htmlFor="reason" className="block text-sm font-medium text-[var(--text-main)] mb-2">
              Correction Reason <span className="text-[var(--text-dim)]">(Optional)</span>
            </label>
            <input
              id="reason"
              type="text"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why did you make this change?"
              className="w-full px-4 py-3 bg-[var(--bg-tertiary)] border border-[var(--border)] rounded-xl text-[var(--text-main)] placeholder:text-[var(--text-dim)] focus:outline-none focus:ring-2 focus:ring-[var(--accent)] transition-all"
            />
          </div>

          {/* Keyboard Shortcuts Hint */}
          <div className="text-xs text-[var(--text-dim)] flex items-center gap-4">
            <span>💡 Tip:</span>
            <span><kbd className="px-2 py-1 bg-[var(--bg-tertiary)] rounded">Esc</kbd> to cancel</span>
            <span><kbd className="px-2 py-1 bg-[var(--bg-tertiary)] rounded">Ctrl+S</kbd> to save</span>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between gap-3 p-6 border-t border-[var(--border)]">
          {/* Delete Button (Left) */}
          <button
            onClick={handleDelete}
            disabled={saving || deleting}
            className="px-6 py-2.5 rounded-xl bg-red-500/10 text-red-500 border border-red-500/30 hover:bg-red-500/20 hover:border-red-500/50 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {deleting ? (
              <>
                <div className="w-4 h-4 border-2 border-red-500/30 border-t-red-500 rounded-full animate-spin" />
                Deleting...
              </>
            ) : (
              <>
                🗑️ Delete Block
              </>
            )}
          </button>

          {/* Save/Cancel Buttons (Right) */}
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              disabled={saving || deleting}
              className="px-6 py-2.5 rounded-xl bg-[var(--bg-tertiary)] text-[var(--text-main)] border border-[var(--border)] hover:border-[var(--accent)] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || deleting || !text.trim()}
              className="px-6 py-2.5 rounded-xl bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              {saving ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Correction'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
