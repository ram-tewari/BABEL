/**
 * Glossary Store (Zustand)
 *
 * Loads glossary entries (characters + factions) for a novel once and exposes
 * a case-insensitive lookup by name or alias. Powers the spoiler-safe hover
 * tooltips on speaker names in the reader.
 */

import { create } from 'zustand';
import { api } from '@/lib/api';
import type { GlossaryEntry, GlossaryResponse } from '@/lib/api';

interface GlossaryState {
  /** Loaded novel id (null = legacy/global, undefined = not loaded). */
  novelId: number | null | undefined;
  loading: boolean;
  factions: GlossaryResponse['factions'];
  /** name/alias (lowercased) -> entry */
  lookup: Record<string, GlossaryEntry>;
  loadGlossary: (novelId?: number) => Promise<void>;
  getEntry: (name: string | null | undefined) => GlossaryEntry | undefined;
}

export const useGlossary = create<GlossaryState>((set, get) => ({
  novelId: undefined,
  loading: false,
  factions: {},
  lookup: {},

  loadGlossary: async (novelId?: number) => {
    // Avoid refetching the same novel's glossary.
    const wanted = novelId ?? null;
    if (get().novelId === wanted && !get().loading) return;

    set({ loading: true, novelId: wanted });
    try {
      const res = await api.getGlossary(novelId);
      const lookup: Record<string, GlossaryEntry> = {};
      for (const entry of res.characters) {
        lookup[entry.name.toLowerCase()] = entry;
        for (const alias of entry.aliases || []) {
          lookup[alias.toLowerCase()] = entry;
        }
      }
      set({ lookup, factions: res.factions || {}, loading: false });
    } catch {
      // Glossary is optional; fail silently so the reader still works.
      set({ lookup: {}, factions: {}, loading: false });
    }
  },

  getEntry: (name) => {
    if (!name) return undefined;
    return get().lookup[name.toLowerCase()];
  },
}));
