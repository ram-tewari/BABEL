import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Formats a raw chapter title into a clean display format.
 * 
 * Examples:
 *   "008 Chapter 8 A Life Risking Opportunity 4" → "Chapter 8 - A Life Risking Opportunity 4"
 *   "Chapter 1 Encountering Magic 1" → "Chapter 1 - Encountering Magic 1"
 *   "000 Chapter 1" → "Chapter 1"
 */
export function formatChapterTitle(title: string): string {
  // Remove leading numeric prefix (e.g., "008 ")
  let cleaned = title.replace(/^\d+\s+/, '');

  // Insert a dash after "Chapter N" if there's more text following
  cleaned = cleaned.replace(/^(Chapter\s+\d+)\s+(?!-)(.+)$/, '$1 - $2');

  return cleaned;
}
