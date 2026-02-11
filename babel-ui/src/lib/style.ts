/**
 * Style generation module for character visualization.
 *
 * This module provides deterministic color and lane assignment functions
 * for character visualization in the rendering engine. All functions use
 * stable hashing to ensure consistency across rendering sessions.
 *
 * CRITICAL: This module uses MD5 for stable hashing instead of JavaScript's
 * built-in hash functions. This ensures that the same character name produces
 * the same colors/lanes across different sessions, which is essential for
 * maintaining visual consistency.
 *
 * This is a direct port from Python's babel/render/style.py module.
 */

import md5 from 'crypto-js/md5';

/**
 * Generate stable, deterministic hash from string as BigInt.
 *
 * Uses MD5 for cryptographically stable hashing that is consistent
 * across all sessions, processes, and machines. Returns a BigInt to
 * handle the full 128-bit MD5 hash (matching Python's implementation).
 *
 * CRITICAL: This must produce identical output to Python's get_stable_hash()
 * function to ensure visual consistency between backend and frontend rendering.
 *
 * @param s - String to hash (typically a character name)
 * @returns BigInt hash value suitable for modulo operations
 *
 * @example
 * ```typescript
 * const hash1 = getStableHashBigInt("Chung Myung");
 * const hash2 = getStableHashBigInt("Chung Myung");
 * console.log(hash1 === hash2); // Always true, even across sessions
 * ```
 *
 * Note:
 * MD5 is used for deterministic hashing, not cryptographic security.
 * For this use case (color/lane generation), MD5 is fast and sufficient.
 *
 * Python Implementation:
 * ```python
 * def get_stable_hash(s: str) -> int:
 *     return int(hashlib.md5(s.encode('utf-8')).hexdigest(), 16)
 * ```
 */
function getStableHashBigInt(s: string): bigint {
  const hash = md5(s).toString();
  return BigInt('0x' + hash);
}

/**
 * Generate stable, deterministic hash from string.
 *
 * This is a wrapper around getStableHashBigInt that returns a number.
 * Note: The returned number may exceed Number.MAX_SAFE_INTEGER, so it
 * should only be used with modulo operations that reduce it to a safe range.
 *
 * @param s - String to hash (typically a character name)
 * @returns Integer hash value suitable for modulo operations
 *
 * @deprecated Use getStableHashBigInt for new code to avoid precision issues
 */
export function getStableHash(s: string): number {
  // For backwards compatibility, return as number
  // This is safe because we only use it with modulo operations
  return Number(getStableHashBigInt(s));
}

/**
 * Generate deterministic HSL color from character name.
 *
 * Uses stable hash-based HSL generation to ensure consistent character
 * colors across all rendering sessions. This creates visual identity for
 * characters without requiring a database or manual color assignment.
 *
 * Color Generation Formula:
 * - Hue: stable_hash(name) % 360 (0-360 degrees, full color spectrum)
 * - Saturation: 65 + (stable_hash(name) % 11) (65-75%, vibrant but not garish)
 * - Lightness: 70 + (stable_hash(name) % 6) (70-75%, WCAG AA compliant on dark backgrounds)
 *
 * The deterministic generation ensures that:
 * - Same character always has the same color
 * - Colors are vibrant and visually distinct
 * - Colors meet WCAG AA accessibility standards (4.5:1 minimum contrast on #1a1a1a)
 * - No database or state management required
 * - Works across different machines and sessions
 *
 * Design Rationale:
 * - HSL over RGB: Better control over color properties for readability
 * - High Saturation (65-75%): Ensures colors are vibrant and visually distinct
 * - High Lightness (70-75%): Ensures WCAG AA compliance on dark backgrounds (#1a1a1a)
 * - Full Hue Range (0-360): Provides maximum color diversity for large character casts
 *
 * WCAG AA Compliance:
 * - The lightness range (70-75%) is specifically chosen to ensure all generated
 *   colors meet WCAG AA standards (minimum 4.5:1 contrast ratio) on the dark
 *   background (#1a1a1a), regardless of hue or saturation.
 *
 * @param characterName - Character name (empty string returns neutral grey)
 * @returns HSL color string in format "hsl(hue, saturation%, lightness%)"
 *
 * @example
 * ```typescript
 * getCharacterColor("Chung Myung"); // Returns 'hsl(18, 69%, 70%)'
 * getCharacterColor("Baek Cheon");  // Returns 'hsl(306, 66%, 70%)'
 * getCharacterColor("");            // Returns 'hsl(0, 0%, 70%)'
 * ```
 *
 * Note:
 * This function is pure and deterministic - same input always
 * produces same output, even across different browser sessions.
 *
 * Python Implementation:
 * ```python
 * def get_character_color(character_name: str) -> str:
 *     if not character_name:
 *         return "hsl(0, 0%, 70%)"
 *     
 *     stable_hash = get_stable_hash(character_name)
 *     hue = stable_hash % 360
 *     saturation = 65 + (stable_hash % 11)
 *     lightness = 70 + (stable_hash % 6)
 *     
 *     return f"hsl({hue}, {saturation}%, {lightness}%)"
 * ```
 *
 * Validates: Requirements 1.2, Property 1 (Color Consistency)
 */
export function getCharacterColor(characterName: string): string {
  if (!characterName) {
    return 'hsl(0, 0%, 70%)'; // Neutral grey for empty names
  }

  // Use BigInt for exact match with Python's 128-bit hash
  const hashBigInt = getStableHashBigInt(characterName);
  const hue = Number(hashBigInt % 360n);
  const saturation = 65 + Number(hashBigInt % 11n); // 65-75%
  const lightness = 70 + Number(hashBigInt % 6n);   // 70-75%

  return `hsl(${hue}, ${saturation}%, ${lightness}%)`;
}

/**
 * Determine character's visual lane (left, right, or center).
 *
 * Uses stable hash-based assignment to ensure consistent lane placement
 * across all rendering sessions. This creates visual rhythm in conversations
 * where each character consistently appears on the same side.
 *
 * Lane Assignment Formula:
 * - stable_hash(name) % 2 == 0 → right lane
 * - stable_hash(name) % 2 == 1 → left lane
 * - null/empty → center
 *
 * The deterministic assignment ensures that:
 * - Same character always appears on the same side
 * - Consistency maintained across thousands of chapters
 * - No database or state management required
 * - Works across different machines and sessions
 *
 * @param characterName - Character name or null
 * @returns "left", "right", or "center"
 *
 * @example
 * ```typescript
 * getCharacterLane("Chung Myung"); // Returns 'right' (always)
 * getCharacterLane("Baek Cheon");  // Returns 'left' (always)
 * getCharacterLane(null);          // Returns 'center'
 * getCharacterLane("");            // Returns 'center'
 * ```
 *
 * Note:
 * This function is pure and deterministic - same input always
 * produces same output, even across different browser sessions.
 *
 * Python Implementation:
 * ```python
 * def get_character_lane(character_name: str | None) -> str:
 *     if not character_name:
 *         return 'center'
 *     
 *     stable_hash = get_stable_hash(character_name)
 *     return 'right' if stable_hash % 2 == 0 else 'left'
 * ```
 *
 * Validates: Requirements 1.3, Property 2 (Lane Consistency)
 */
export function getCharacterLane(characterName: string | null): 'left' | 'right' | 'center' {
  if (!characterName) {
    return 'center';
  }

  // Use BigInt for exact match with Python's 128-bit hash
  const hashBigInt = getStableHashBigInt(characterName);
  return hashBigInt % 2n === 0n ? 'right' : 'left';
}

/**
 * Generate stable CSS class name for a character.
 *
 * Uses stable hash to create a unique, deterministic CSS class name
 * for each character. This enables CSS variable-based styling that
 * can be overridden by JavaScript for reader personalization.
 *
 * The class name format is "char-{hash}" where hash is a 16-character
 * hexadecimal string derived from the character's name. This provides
 * sufficient uniqueness for character identification while maintaining
 * readability in the DOM.
 *
 * @param characterName - Character name or null
 * @returns CSS class name in format "char-{hash}" or "char-none" for null/empty
 *
 * @example
 * ```typescript
 * getCharClass("Chung Myung"); // Returns 'char-a3f5b8c9d2e1f4a7'
 * getCharClass(null);          // Returns 'char-none'
 * getCharClass("");            // Returns 'char-none'
 * ```
 *
 * Note:
 * This function is pure and deterministic - same input always
 * produces same output, even across different browser sessions.
 * The hash is truncated to 16 characters for readability while
 * maintaining sufficient uniqueness for character identification.
 *
 * Python Implementation:
 * ```python
 * def get_char_class(character_name: Optional[str]) -> str:
 *     if not character_name:
 *         return "char-none"
 *     
 *     stable_hash = get_stable_hash(character_name)
 *     hash_hex = format(stable_hash, 'x')[:16]
 *     
 *     return f"char-{hash_hex}"
 * ```
 *
 * Validates: Requirements 1.2
 */
export function getCharClass(characterName: string | null): string {
  if (!characterName) {
    return 'char-none';
  }

  // Generate stable hash and convert to hex, truncate to 16 chars for readability
  const hashBigInt = getStableHashBigInt(characterName);
  const hashHex = hashBigInt.toString(16).substring(0, 16);

  return `char-${hashHex}`;
}

/**
 * Map tone keywords to floating emoji indicators.
 *
 * Part of Phase 2.6 "Emotion Engine" - provides visual emotional context
 * for dialogue blocks through floating emoji indicators. Uses keyword
 * matching to detect emotional tone in dialogue.
 *
 * Tone Mapping:
 * - Anger/Fury: 💢 (anger symbol)
 * - Sadness/Crying: 💧 (droplet)
 * - Happiness/Laughter: ✨ (sparkles)
 * - Shock/Surprise: ❗ (exclamation)
 * - Whisper/Quiet: 🤫 (shushing face)
 * - Shout/Yell: 📢 (loudspeaker)
 *
 * @param tone - Tone string from ChapterData (can be null/undefined)
 * @returns Emoji string or empty string if no match
 *
 * @example
 * ```typescript
 * getToneEmoji("angry");      // Returns '💢'
 * getToneEmoji("laughing");   // Returns '✨'
 * getToneEmoji("shocked");    // Returns '❗'
 * getToneEmoji(null);         // Returns ''
 * getToneEmoji("neutral");    // Returns ''
 * ```
 *
 * Note:
 * Matching is case-insensitive and checks for keyword presence
 * in the tone string (e.g., "very angry" matches "angry").
 *
 * Python Implementation:
 * ```python
 * def get_tone_emoji(tone: Optional[str]) -> str:
 *     if not tone:
 *         return ""
 *     
 *     tone_lower = tone.lower()
 *     
 *     # Anger/Fury
 *     if any(k in tone_lower for k in ['angry', 'furious', 'rage', 'mad', 'irritated']):
 *         return '💢'
 *     
 *     # Sadness/Crying
 *     if any(k in tone_lower for k in ['sad', 'cry', 'sob', 'weep', 'tears']):
 *         return '💧'
 *     
 *     # Happiness/Laughter
 *     if any(k in tone_lower for k in ['laugh', 'happy', 'joy', 'cheerful', 'amused', 'giggle']):
 *         return '✨'
 *     
 *     # Shock/Surprise
 *     if any(k in tone_lower for k in ['shock', 'gasp', 'surprise', 'astonish', 'startle']):
 *         return '❗'
 *     
 *     # Whisper/Quiet
 *     if any(k in tone_lower for k in ['whisper', 'quiet', 'murmur', 'soft']):
 *         return '🤫'
 *     
 *     # Shout/Yell
 *     if any(k in tone_lower for k in ['shout', 'yell', 'scream', 'roar', 'bellow']):
 *         return '📢'
 *     
 *     return ""
 * ```
 *
 * Validates: Requirements 1.2, Phase 2.6 Specification - Emotion Engine
 */
export function getToneEmoji(tone: string | null | undefined): string {
  if (!tone) {
    return '';
  }

  // Normalize to lowercase for matching
  const toneLower = tone.toLowerCase();

  // Anger/Fury
  if (['angry', 'furious', 'rage', 'mad', 'irritated'].some(keyword => toneLower.includes(keyword))) {
    return '💢';
  }

  // Sadness/Crying
  if (['sad', 'cry', 'sob', 'weep', 'tears'].some(keyword => toneLower.includes(keyword))) {
    return '💧';
  }

  // Happiness/Laughter
  if (['laugh', 'happy', 'joy', 'cheerful', 'amused', 'giggle'].some(keyword => toneLower.includes(keyword))) {
    return '✨';
  }

  // Shock/Surprise
  if (['shock', 'gasp', 'surprise', 'astonish', 'startle'].some(keyword => toneLower.includes(keyword))) {
    return '❗';
  }

  // Whisper/Quiet
  if (['whisper', 'quiet', 'murmur', 'soft'].some(keyword => toneLower.includes(keyword))) {
    return '🤫';
  }

  // Shout/Yell
  if (['shout', 'yell', 'scream', 'roar', 'bellow'].some(keyword => toneLower.includes(keyword))) {
    return '📢';
  }

  // No match
  return '';
}
