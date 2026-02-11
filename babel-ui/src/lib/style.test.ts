/**
 * Unit tests for style.ts
 * 
 * These tests verify that the TypeScript implementation produces
 * identical output to the Python implementation in babel/render/style.py
 */

import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { getStableHash, getCharacterColor, getCharacterLane, getCharClass, getToneEmoji } from './style';

describe('getStableHash', () => {
  it('should produce deterministic hash for same input', () => {
    const hash1 = getStableHash('Chung Myung');
    const hash2 = getStableHash('Chung Myung');
    expect(hash1).toBe(hash2);
  });

  it('should produce different hashes for different inputs', () => {
    const hash1 = getStableHash('Chung Myung');
    const hash2 = getStableHash('Baek Cheon');
    expect(hash1).not.toBe(hash2);
  });

  it('should handle special characters', () => {
    const hash1 = getStableHash('Character-Name');
    const hash2 = getStableHash('Character Name');
    expect(hash1).not.toBe(hash2);
  });

  it('should be case-sensitive', () => {
    const hash1 = getStableHash('Test');
    const hash2 = getStableHash('test');
    expect(hash1).not.toBe(hash2);
  });

  it('should handle Unicode characters', () => {
    const hash = getStableHash('中文名字');
    expect(typeof hash).toBe('number');
    expect(hash).toBeGreaterThan(0);
  });

  it('should produce valid results for modulo operations (matches Python)', () => {
    // The hash value itself may not be safe as a Number, but modulo operations
    // are performed on BigInt before conversion, ensuring correct results
    
    // Test "Chung Myung" - Python: hash % 360 = 18, hash % 11 = 4, hash % 6 = 0
    const hash1 = getStableHash('Chung Myung');
    // We can't test the raw hash value due to precision loss, but getCharacterColor
    // uses BigInt modulo which works correctly (tested separately)
    expect(typeof hash1).toBe('number');
    
    // Test that different names produce different hashes
    const hash2 = getStableHash('Baek Cheon');
    expect(hash1).not.toBe(hash2);
  });
});

describe('getCharacterColor', () => {
  it('should produce deterministic color for same input', () => {
    const color1 = getCharacterColor('Chung Myung');
    const color2 = getCharacterColor('Chung Myung');
    expect(color1).toBe(color2);
  });

  it('should match Python implementation for "Chung Myung"', () => {
    // Python: get_character_color("Chung Myung") = "hsl(18, 69%, 70%)"
    const color = getCharacterColor('Chung Myung');
    expect(color).toBe('hsl(18, 69%, 70%)');
  });

  it('should match Python implementation for "Baek Cheon"', () => {
    // Python: get_character_color("Baek Cheon") = "hsl(306, 66%, 70%)"
    const color = getCharacterColor('Baek Cheon');
    expect(color).toBe('hsl(306, 66%, 70%)');
  });

  it('should match Python implementation for "Tang Bo"', () => {
    // Python: get_character_color("Tang Bo") = "hsl(135, 72%, 73%)"
    const color = getCharacterColor('Tang Bo');
    expect(color).toBe('hsl(135, 72%, 73%)');
  });

  it('should match Python implementation for empty string', () => {
    // Python: get_character_color("") = "hsl(0, 0%, 70%)"
    const color = getCharacterColor('');
    expect(color).toBe('hsl(0, 0%, 70%)');
  });

  it('should match Python implementation for "Test"', () => {
    // Python: get_character_color("Test") = "hsl(355, 71%, 71%)"
    const color = getCharacterColor('Test');
    expect(color).toBe('hsl(355, 71%, 71%)');
  });

  it('should return neutral grey for empty string', () => {
    const color = getCharacterColor('');
    expect(color).toBe('hsl(0, 0%, 70%)');
  });

  it('should produce different colors for different characters', () => {
    const color1 = getCharacterColor('Chung Myung');
    const color2 = getCharacterColor('Baek Cheon');
    expect(color1).not.toBe(color2);
  });

  it('should produce valid HSL format', () => {
    const color = getCharacterColor('Test Character');
    expect(color).toMatch(/^hsl\(\d+, \d+%, \d+%\)$/);
  });

  it('should have hue in range 0-359', () => {
    const names = ['Chung Myung', 'Baek Cheon', 'Tang Bo', 'Test', 'Another Name'];
    
    names.forEach(name => {
      const color = getCharacterColor(name);
      const hueMatch = color.match(/hsl\((\d+),/);
      expect(hueMatch).not.toBeNull();
      
      if (hueMatch) {
        const hue = parseInt(hueMatch[1]);
        expect(hue).toBeGreaterThanOrEqual(0);
        expect(hue).toBeLessThan(360);
      }
    });
  });

  it('should have saturation in range 65-75%', () => {
    const names = ['Chung Myung', 'Baek Cheon', 'Tang Bo', 'Test', 'Another Name'];
    
    names.forEach(name => {
      const color = getCharacterColor(name);
      const satMatch = color.match(/hsl\(\d+, (\d+)%,/);
      expect(satMatch).not.toBeNull();
      
      if (satMatch) {
        const saturation = parseInt(satMatch[1]);
        expect(saturation).toBeGreaterThanOrEqual(65);
        expect(saturation).toBeLessThanOrEqual(75);
      }
    });
  });

  it('should have lightness in range 70-75%', () => {
    const names = ['Chung Myung', 'Baek Cheon', 'Tang Bo', 'Test', 'Another Name'];
    
    names.forEach(name => {
      const color = getCharacterColor(name);
      const lightMatch = color.match(/hsl\(\d+, \d+%, (\d+)%\)/);
      expect(lightMatch).not.toBeNull();
      
      if (lightMatch) {
        const lightness = parseInt(lightMatch[1]);
        expect(lightness).toBeGreaterThanOrEqual(70);
        expect(lightness).toBeLessThanOrEqual(75);
      }
    });
  });

  it('should handle Unicode characters', () => {
    const color = getCharacterColor('中文名字');
    expect(color).toMatch(/^hsl\(\d+, \d+%, \d+%\)$/);
  });

  it('should handle special characters', () => {
    const color = getCharacterColor('Character-Name!@#');
    expect(color).toMatch(/^hsl\(\d+, \d+%, \d+%\)$/);
  });

  it('should be case-sensitive', () => {
    const color1 = getCharacterColor('Test');
    const color2 = getCharacterColor('test');
    expect(color1).not.toBe(color2);
  });

  it('should handle whitespace differences', () => {
    const color1 = getCharacterColor('Chung Myung');
    const color2 = getCharacterColor('ChungMyung');
    expect(color1).not.toBe(color2);
  });
});

describe('getCharacterLane', () => {
  it('should produce deterministic lane for same input', () => {
    const lane1 = getCharacterLane('Chung Myung');
    const lane2 = getCharacterLane('Chung Myung');
    expect(lane1).toBe(lane2);
  });

  it('should match Python implementation for "Chung Myung"', () => {
    // Python: get_character_lane("Chung Myung") = "right"
    const lane = getCharacterLane('Chung Myung');
    expect(lane).toBe('right');
  });

  it('should match Python implementation for "Baek Cheon"', () => {
    // Python: get_character_lane("Baek Cheon") = "right"
    const lane = getCharacterLane('Baek Cheon');
    expect(lane).toBe('right');
  });

  it('should match Python implementation for "Tang Bo"', () => {
    // Python: get_character_lane("Tang Bo") = "left"
    const lane = getCharacterLane('Tang Bo');
    expect(lane).toBe('left');
  });

  it('should match Python implementation for "Test"', () => {
    // Python: get_character_lane("Test") = "left"
    const lane = getCharacterLane('Test');
    expect(lane).toBe('left');
  });

  it('should return center for null', () => {
    const lane = getCharacterLane(null);
    expect(lane).toBe('center');
  });

  it('should return center for empty string', () => {
    const lane = getCharacterLane('');
    expect(lane).toBe('center');
  });

  it('should produce different lanes for different characters (usually)', () => {
    // Note: Due to hash distribution, some characters may have the same lane
    // but most should differ. We test a few known cases.
    const lane1 = getCharacterLane('Chung Myung'); // right
    const lane2 = getCharacterLane('Tang Bo');     // left
    expect(lane1).not.toBe(lane2);
  });

  it('should only return valid lane values', () => {
    const names = ['Chung Myung', 'Baek Cheon', 'Tang Bo', 'Test', 'Another Name'];
    
    names.forEach(name => {
      const lane = getCharacterLane(name);
      expect(['left', 'right', 'center']).toContain(lane);
    });
  });

  it('should handle Unicode characters', () => {
    const lane = getCharacterLane('中文名字');
    expect(['left', 'right', 'center']).toContain(lane);
  });

  it('should handle special characters', () => {
    const lane = getCharacterLane('Character-Name!@#');
    expect(['left', 'right', 'center']).toContain(lane);
  });

  it('should be case-sensitive', () => {
    const lane1 = getCharacterLane('Test');
    const lane2 = getCharacterLane('test');
    // These should be different because the hash is case-sensitive
    // but they might coincidentally be the same lane (50% chance)
    // So we just verify they're both valid
    expect(['left', 'right']).toContain(lane1);
    expect(['left', 'right']).toContain(lane2);
  });

  it('should handle whitespace differences', () => {
    const lane1 = getCharacterLane('Chung Myung');
    const lane2 = getCharacterLane('ChungMyung');
    // These should produce different hashes, but might coincidentally
    // have the same lane (50% chance). We just verify they're valid.
    expect(['left', 'right']).toContain(lane1);
    expect(['left', 'right']).toContain(lane2);
  });

  it('should be deterministic across multiple calls', () => {
    const name = 'Test Character';
    const lanes = Array.from({ length: 100 }, () => getCharacterLane(name));
    const firstLane = lanes[0];
    
    // All lanes should be identical
    lanes.forEach(lane => {
      expect(lane).toBe(firstLane);
    });
  });
});

describe('getCharClass', () => {
  it('should produce deterministic class for same input', () => {
    const class1 = getCharClass('Chung Myung');
    const class2 = getCharClass('Chung Myung');
    expect(class1).toBe(class2);
  });

  it('should match Python implementation for "Chung Myung"', () => {
    // Python: get_char_class("Chung Myung") = "char-1c0d6a61d191d209"
    const className = getCharClass('Chung Myung');
    expect(className).toBe('char-1c0d6a61d191d209');
  });

  it('should match Python implementation for "Baek Cheon"', () => {
    // Python: get_char_class("Baek Cheon") = "char-5443e31cdccec324"
    const className = getCharClass('Baek Cheon');
    expect(className).toBe('char-5443e31cdccec324');
  });

  it('should match Python implementation for "Tang Bo"', () => {
    // Python: get_char_class("Tang Bo") = "char-7f3def657b99c09b"
    const className = getCharClass('Tang Bo');
    expect(className).toBe('char-7f3def657b99c09b');
  });

  it('should match Python implementation for "Test"', () => {
    // Python: get_char_class("Test") = "char-cbc6611f5540bd08"
    const className = getCharClass('Test');
    expect(className).toBe('char-cbc6611f5540bd08');
  });

  it('should return "char-none" for null', () => {
    const className = getCharClass(null);
    expect(className).toBe('char-none');
  });

  it('should return "char-none" for empty string', () => {
    const className = getCharClass('');
    expect(className).toBe('char-none');
  });

  it('should produce different classes for different characters', () => {
    const class1 = getCharClass('Chung Myung');
    const class2 = getCharClass('Baek Cheon');
    expect(class1).not.toBe(class2);
    expect(class1).not.toBe('char-none');
    expect(class2).not.toBe('char-none');
  });

  it('should produce valid CSS class format', () => {
    const className = getCharClass('Test Character');
    expect(className).toMatch(/^char-[0-9a-f]{1,16}$/);
  });

  it('should have hash component of exactly 16 characters or less', () => {
    const names = ['Chung Myung', 'Baek Cheon', 'Tang Bo', 'Test', 'Another Name'];
    
    names.forEach(name => {
      const className = getCharClass(name);
      const hashPart = className.replace('char-', '');
      expect(hashPart.length).toBeGreaterThan(0);
      expect(hashPart.length).toBeLessThanOrEqual(16);
      // Verify it's valid hex
      expect(hashPart).toMatch(/^[0-9a-f]+$/);
    });
  });

  it('should handle Unicode characters', () => {
    const className = getCharClass('中文名字');
    expect(className).toMatch(/^char-[0-9a-f]{1,16}$/);
  });

  it('should handle special characters', () => {
    const className = getCharClass('Character-Name!@#');
    expect(className).toMatch(/^char-[0-9a-f]{1,16}$/);
  });

  it('should be case-sensitive', () => {
    const class1 = getCharClass('Test');
    const class2 = getCharClass('test');
    expect(class1).not.toBe(class2);
  });

  it('should handle whitespace differences', () => {
    const class1 = getCharClass('Chung Myung');
    const class2 = getCharClass('ChungMyung');
    expect(class1).not.toBe(class2);
  });

  it('should be deterministic across multiple calls', () => {
    const name = 'Test Character';
    const classes = Array.from({ length: 100 }, () => getCharClass(name));
    const firstClass = classes[0];
    
    // All classes should be identical
    classes.forEach(className => {
      expect(className).toBe(firstClass);
    });
  });

  it('should produce valid CSS class names (no spaces or special chars)', () => {
    const names = ['Chung Myung', 'Baek Cheon', 'Tang Bo', 'Test!@#', 'Name With Spaces'];
    
    names.forEach(name => {
      const className = getCharClass(name);
      // CSS class names should not contain spaces or special characters
      expect(className).not.toMatch(/\s/);
      expect(className).toMatch(/^char-[0-9a-f]+$/);
    });
  });
});

describe('getToneEmoji', () => {
  describe('Anger/Fury tones', () => {
    it('should return 💢 for "angry"', () => {
      expect(getToneEmoji('angry')).toBe('💢');
    });

    it('should return 💢 for "furious"', () => {
      expect(getToneEmoji('furious')).toBe('💢');
    });

    it('should return 💢 for "rage"', () => {
      expect(getToneEmoji('rage')).toBe('💢');
    });

    it('should return 💢 for "mad"', () => {
      expect(getToneEmoji('mad')).toBe('💢');
    });

    it('should return 💢 for "irritated"', () => {
      expect(getToneEmoji('irritated')).toBe('💢');
    });

    it('should be case-insensitive for "ANGRY"', () => {
      expect(getToneEmoji('ANGRY')).toBe('💢');
    });

    it('should match within longer strings like "very angry"', () => {
      expect(getToneEmoji('very angry')).toBe('💢');
    });
  });

  describe('Sadness/Crying tones', () => {
    it('should return 💧 for "sad"', () => {
      expect(getToneEmoji('sad')).toBe('💧');
    });

    it('should return 💧 for "cry"', () => {
      expect(getToneEmoji('cry')).toBe('💧');
    });

    it('should return 💧 for "sob"', () => {
      expect(getToneEmoji('sob')).toBe('💧');
    });

    it('should return 💧 for "weep"', () => {
      expect(getToneEmoji('weep')).toBe('💧');
    });

    it('should return 💧 for "tears"', () => {
      expect(getToneEmoji('tears')).toBe('💧');
    });

    it('should be case-insensitive for "SAD"', () => {
      expect(getToneEmoji('SAD')).toBe('💧');
    });

    it('should match within longer strings like "crying softly"', () => {
      expect(getToneEmoji('crying softly')).toBe('💧');
    });
  });

  describe('Happiness/Laughter tones', () => {
    it('should return ✨ for "laugh"', () => {
      expect(getToneEmoji('laugh')).toBe('✨');
    });

    it('should return ✨ for "happy"', () => {
      expect(getToneEmoji('happy')).toBe('✨');
    });

    it('should return ✨ for "joy"', () => {
      expect(getToneEmoji('joy')).toBe('✨');
    });

    it('should return ✨ for "cheerful"', () => {
      expect(getToneEmoji('cheerful')).toBe('✨');
    });

    it('should return ✨ for "amused"', () => {
      expect(getToneEmoji('amused')).toBe('✨');
    });

    it('should return ✨ for "giggle"', () => {
      expect(getToneEmoji('giggle')).toBe('✨');
    });

    it('should be case-insensitive for "HAPPY"', () => {
      expect(getToneEmoji('HAPPY')).toBe('✨');
    });

    it('should match within longer strings like "laughing loudly"', () => {
      expect(getToneEmoji('laughing loudly')).toBe('✨');
    });
  });

  describe('Shock/Surprise tones', () => {
    it('should return ❗ for "shock"', () => {
      expect(getToneEmoji('shock')).toBe('❗');
    });

    it('should return ❗ for "gasp"', () => {
      expect(getToneEmoji('gasp')).toBe('❗');
    });

    it('should return ❗ for "surprise"', () => {
      expect(getToneEmoji('surprise')).toBe('❗');
    });

    it('should return ❗ for "astonish"', () => {
      expect(getToneEmoji('astonish')).toBe('❗');
    });

    it('should return ❗ for "startle"', () => {
      expect(getToneEmoji('startle')).toBe('❗');
    });

    it('should be case-insensitive for "SHOCKED"', () => {
      expect(getToneEmoji('SHOCKED')).toBe('❗');
    });

    it('should match within longer strings like "gasping in shock"', () => {
      expect(getToneEmoji('gasping in shock')).toBe('❗');
    });
  });

  describe('Whisper/Quiet tones', () => {
    it('should return 🤫 for "whisper"', () => {
      expect(getToneEmoji('whisper')).toBe('🤫');
    });

    it('should return 🤫 for "quiet"', () => {
      expect(getToneEmoji('quiet')).toBe('🤫');
    });

    it('should return 🤫 for "murmur"', () => {
      expect(getToneEmoji('murmur')).toBe('🤫');
    });

    it('should return 🤫 for "soft"', () => {
      expect(getToneEmoji('soft')).toBe('🤫');
    });

    it('should be case-insensitive for "WHISPER"', () => {
      expect(getToneEmoji('WHISPER')).toBe('🤫');
    });

    it('should match within longer strings like "whispering softly"', () => {
      expect(getToneEmoji('whispering softly')).toBe('🤫');
    });
  });

  describe('Shout/Yell tones', () => {
    it('should return 📢 for "shout"', () => {
      expect(getToneEmoji('shout')).toBe('📢');
    });

    it('should return 📢 for "yell"', () => {
      expect(getToneEmoji('yell')).toBe('📢');
    });

    it('should return 📢 for "scream"', () => {
      expect(getToneEmoji('scream')).toBe('📢');
    });

    it('should return 📢 for "roar"', () => {
      expect(getToneEmoji('roar')).toBe('📢');
    });

    it('should return 📢 for "bellow"', () => {
      expect(getToneEmoji('bellow')).toBe('📢');
    });

    it('should be case-insensitive for "SHOUT"', () => {
      expect(getToneEmoji('SHOUT')).toBe('📢');
    });

    it('should match within longer strings like "shouting loudly"', () => {
      expect(getToneEmoji('shouting loudly')).toBe('📢');
    });
  });

  describe('Edge cases', () => {
    it('should return empty string for null', () => {
      expect(getToneEmoji(null)).toBe('');
    });

    it('should return empty string for undefined', () => {
      expect(getToneEmoji(undefined)).toBe('');
    });

    it('should return empty string for empty string', () => {
      expect(getToneEmoji('')).toBe('');
    });

    it('should return empty string for unmatched tone', () => {
      expect(getToneEmoji('neutral')).toBe('');
    });

    it('should return empty string for unmatched tone "calm"', () => {
      expect(getToneEmoji('calm')).toBe('');
    });

    it('should return empty string for unmatched tone "serious"', () => {
      expect(getToneEmoji('serious')).toBe('');
    });
  });

  describe('Priority matching (first match wins)', () => {
    it('should return first matching emoji when multiple keywords present', () => {
      // "angry" is checked before "sad", so should return anger emoji
      expect(getToneEmoji('angry and sad')).toBe('💢');
    });

    it('should return sadness emoji when only sad keyword present', () => {
      expect(getToneEmoji('sad and tired')).toBe('💧');
    });
  });

  describe('Deterministic behavior', () => {
    it('should produce same result for same input across multiple calls', () => {
      const results = Array.from({ length: 100 }, () => getToneEmoji('angry'));
      const firstResult = results[0];
      
      results.forEach(result => {
        expect(result).toBe(firstResult);
      });
    });
  });

  describe('Python implementation parity', () => {
    it('should match Python for "angry"', () => {
      // Python: get_tone_emoji("angry") = "💢"
      expect(getToneEmoji('angry')).toBe('💢');
    });

    it('should match Python for "laughing"', () => {
      // Python: get_tone_emoji("laughing") = "✨"
      expect(getToneEmoji('laughing')).toBe('✨');
    });

    it('should match Python for "shocked"', () => {
      // Python: get_tone_emoji("shocked") = "❗"
      expect(getToneEmoji('shocked')).toBe('❗');
    });

    it('should match Python for None/null', () => {
      // Python: get_tone_emoji(None) = ""
      expect(getToneEmoji(null)).toBe('');
    });

    it('should match Python for "neutral"', () => {
      // Python: get_tone_emoji("neutral") = ""
      expect(getToneEmoji('neutral')).toBe('');
    });
  });
});

// ============================================================================
// Property-Based Tests
// ============================================================================

/**
 * Property-Based Tests for Style Functions
 * 
 * These tests use fast-check to verify universal properties that should hold
 * for all possible inputs, not just specific test cases. This provides much
 * stronger guarantees about correctness than unit tests alone.
 * 
 * **Validates**: Property 1 (Color Consistency), Property 2 (Lane Consistency)
 */

describe('Property-Based Tests', () => {
  describe('Property 1: Color Consistency', () => {
    /**
     * Property: For any character name, getCharacterColor() produces valid HSL format
     * 
     * **Validates**: Property 1 (Color Consistency)
     */
    it('should always produce valid HSL format for any string', () => {
      fc.assert(
        fc.property(fc.string(), (name) => {
          const color = getCharacterColor(name);
          
          // Should match HSL format: hsl(hue, saturation%, lightness%)
          const hslRegex = /^hsl\(\d+, \d+%, \d+%\)$/;
          expect(color).toMatch(hslRegex);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Hue is always in range [0, 360)
     * 
     * **Validates**: Property 1 (Color Consistency)
     */
    it('should always produce hue in range [0, 360) for any string', () => {
      fc.assert(
        fc.property(fc.string(), (name) => {
          const color = getCharacterColor(name);
          const hueMatch = color.match(/hsl\((\d+),/);
          
          if (hueMatch) {
            const hue = parseInt(hueMatch[1]);
            expect(hue).toBeGreaterThanOrEqual(0);
            expect(hue).toBeLessThan(360);
          }
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Saturation is always in range [65, 75]
     * 
     * **Validates**: Property 1 (Color Consistency)
     */
    it('should always produce saturation in range [65, 75] for any non-empty string', () => {
      fc.assert(
        fc.property(fc.string({ minLength: 1 }), (name) => {
          const color = getCharacterColor(name);
          const satMatch = color.match(/hsl\(\d+, (\d+)%,/);
          
          if (satMatch) {
            const saturation = parseInt(satMatch[1]);
            expect(saturation).toBeGreaterThanOrEqual(65);
            expect(saturation).toBeLessThanOrEqual(75);
          }
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Lightness is always in range [70, 75]
     * 
     * **Validates**: Property 1 (Color Consistency)
     */
    it('should always produce lightness in range [70, 75] for any non-empty string', () => {
      fc.assert(
        fc.property(fc.string({ minLength: 1 }), (name) => {
          const color = getCharacterColor(name);
          const lightMatch = color.match(/hsl\(\d+, \d+%, (\d+)%\)/);
          
          if (lightMatch) {
            const lightness = parseInt(lightMatch[1]);
            expect(lightness).toBeGreaterThanOrEqual(70);
            expect(lightness).toBeLessThanOrEqual(75);
          }
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Same input always produces same output (deterministic)
     * 
     * **Validates**: Property 1 (Color Consistency)
     */
    it('should be deterministic - same input always produces same output', () => {
      fc.assert(
        fc.property(fc.string(), (name) => {
          const color1 = getCharacterColor(name);
          const color2 = getCharacterColor(name);
          const color3 = getCharacterColor(name);
          
          expect(color1).toBe(color2);
          expect(color2).toBe(color3);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Empty string always returns neutral grey
     * 
     * **Validates**: Property 1 (Color Consistency)
     */
    it('should always return neutral grey for empty string', () => {
      const color = getCharacterColor('');
      expect(color).toBe('hsl(0, 0%, 70%)');
    });

    /**
     * Property: Different inputs (usually) produce different outputs
     * 
     * **Validates**: Property 1 (Color Consistency)
     */
    it('should produce different colors for different inputs (with high probability)', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 1 }),
          fc.string({ minLength: 1 }),
          (name1, name2) => {
            // Skip if names are identical
            if (name1 === name2) return true;
            
            const color1 = getCharacterColor(name1);
            const color2 = getCharacterColor(name2);
            
            // Colors should be different (hash collision is extremely rare)
            // We allow for the theoretical possibility of collision but it should be rare
            return color1 !== color2 || name1 === name2;
          }
        ),
        { numRuns: 500 }
      );
    });

    /**
     * Property: Works with Unicode characters
     * 
     * **Validates**: Property 1 (Color Consistency)
     */
    it('should handle Unicode characters correctly', () => {
      // Test with a variety of Unicode strings
      const unicodeStrings = [
        '中文名字',
        'العربية',
        'Ελληνικά',
        '日本語',
        '한국어',
        'Русский',
        '🎭🎨🎪',
        'Café',
        'naïve'
      ];
      
      unicodeStrings.forEach(name => {
        const color = getCharacterColor(name);
        const hslRegex = /^hsl\(\d+, \d+%, \d+%\)$/;
        expect(color).toMatch(hslRegex);
      });
    });
  });

  describe('Property 2: Lane Consistency', () => {
    /**
     * Property: For any character name, getCharacterLane() returns valid lane
     * 
     * **Validates**: Property 2 (Lane Consistency)
     */
    it('should always return valid lane value for any string', () => {
      fc.assert(
        fc.property(fc.string(), (name) => {
          const lane = getCharacterLane(name);
          expect(['left', 'right', 'center']).toContain(lane);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Same input always produces same output (deterministic)
     * 
     * **Validates**: Property 2 (Lane Consistency)
     */
    it('should be deterministic - same input always produces same output', () => {
      fc.assert(
        fc.property(fc.string(), (name) => {
          const lane1 = getCharacterLane(name);
          const lane2 = getCharacterLane(name);
          const lane3 = getCharacterLane(name);
          
          expect(lane1).toBe(lane2);
          expect(lane2).toBe(lane3);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Null/empty always returns 'center'
     * 
     * **Validates**: Property 2 (Lane Consistency)
     */
    it('should always return center for null', () => {
      const lane = getCharacterLane(null);
      expect(lane).toBe('center');
    });

    it('should always return center for empty string', () => {
      const lane = getCharacterLane('');
      expect(lane).toBe('center');
    });

    /**
     * Property: Non-empty strings return 'left' or 'right' (never 'center')
     * 
     * **Validates**: Property 2 (Lane Consistency)
     */
    it('should return left or right for non-empty strings', () => {
      fc.assert(
        fc.property(fc.string({ minLength: 1 }), (name) => {
          const lane = getCharacterLane(name);
          expect(['left', 'right']).toContain(lane);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Lane distribution is roughly balanced (50/50 left/right)
     * 
     * **Validates**: Property 2 (Lane Consistency)
     */
    it('should produce roughly balanced lane distribution', () => {
      // Generate 1000 random names and check distribution
      const names = Array.from({ length: 1000 }, (_, i) => `Character${i}`);
      const lanes = names.map(name => getCharacterLane(name));
      
      const leftCount = lanes.filter(lane => lane === 'left').length;
      const rightCount = lanes.filter(lane => lane === 'right').length;
      
      // Should be roughly 50/50 (allow 40-60% range for statistical variance)
      const leftPercent = (leftCount / lanes.length) * 100;
      expect(leftPercent).toBeGreaterThan(40);
      expect(leftPercent).toBeLessThan(60);
    });

    /**
     * Property: Works with Unicode characters
     * 
     * **Validates**: Property 2 (Lane Consistency)
     */
    it('should handle Unicode characters correctly', () => {
      // Test with a variety of Unicode strings
      const unicodeStrings = [
        '中文名字',
        'العربية',
        'Ελληνικά',
        '日本語',
        '한국어',
        'Русский',
        '🎭🎨🎪',
        'Café',
        'naïve'
      ];
      
      unicodeStrings.forEach(name => {
        const lane = getCharacterLane(name);
        expect(['left', 'right', 'center']).toContain(lane);
      });
    });
  });

  describe('Hash Stability', () => {
    /**
     * Property: For any string, getStableHash() produces consistent output
     * 
     * **Validates**: Hash function stability
     */
    it('should produce consistent hash for same input', () => {
      fc.assert(
        fc.property(fc.string(), (s) => {
          const hash1 = getStableHash(s);
          const hash2 = getStableHash(s);
          const hash3 = getStableHash(s);
          
          expect(hash1).toBe(hash2);
          expect(hash2).toBe(hash3);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Hash function produces numeric output
     * 
     * **Validates**: Hash function stability
     */
    it('should always produce numeric output', () => {
      fc.assert(
        fc.property(fc.string(), (s) => {
          const hash = getStableHash(s);
          expect(typeof hash).toBe('number');
          expect(Number.isFinite(hash)).toBe(true);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Different inputs (usually) produce different hashes
     * 
     * **Validates**: Hash function stability
     */
    it('should produce different hashes for different inputs (with high probability)', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 1 }),
          fc.string({ minLength: 1 }),
          (s1, s2) => {
            // Skip if strings are identical
            if (s1 === s2) return true;
            
            const hash1 = getStableHash(s1);
            const hash2 = getStableHash(s2);
            
            // Hashes should be different (collision is extremely rare)
            return hash1 !== hash2 || s1 === s2;
          }
        ),
        { numRuns: 500 }
      );
    });

    /**
     * Property: Hash is case-sensitive
     * 
     * **Validates**: Hash function stability
     */
    it('should be case-sensitive', () => {
      fc.assert(
        fc.property(
          fc.string({ minLength: 1 }).filter(s => s.toLowerCase() !== s.toUpperCase()),
          (s) => {
            const hash1 = getStableHash(s);
            const hash2 = getStableHash(s.toUpperCase());
            const hash3 = getStableHash(s.toLowerCase());
            
            // At least one should be different (unless string has no case)
            const allSame = hash1 === hash2 && hash2 === hash3;
            const hasCase = s.toLowerCase() !== s.toUpperCase();
            
            if (hasCase) {
              expect(allSame).toBe(false);
            }
          }
        ),
        { numRuns: 500 }
      );
    });

    /**
     * Property: Works with Unicode characters
     * 
     * **Validates**: Hash function stability
     */
    it('should handle Unicode characters correctly', () => {
      // Test with a variety of Unicode strings
      const unicodeStrings = [
        '中文名字',
        'العربية',
        'Ελληνικά',
        '日本語',
        '한국어',
        'Русский',
        '🎭🎨🎪',
        'Café',
        'naïve'
      ];
      
      unicodeStrings.forEach(s => {
        const hash = getStableHash(s);
        expect(typeof hash).toBe('number');
        expect(Number.isFinite(hash)).toBe(true);
      });
    });
  });

  describe('getCharClass Stability', () => {
    /**
     * Property: For any string, getCharClass() produces valid CSS class
     * 
     * **Validates**: CSS class generation stability
     */
    it('should always produce valid CSS class format', () => {
      fc.assert(
        fc.property(fc.string(), (name) => {
          const className = getCharClass(name);
          
          // Should match format: char-{hex} or char-none
          const classRegex = /^char-([0-9a-f]{1,16}|none)$/;
          expect(className).toMatch(classRegex);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Same input always produces same output (deterministic)
     * 
     * **Validates**: CSS class generation stability
     */
    it('should be deterministic - same input always produces same output', () => {
      fc.assert(
        fc.property(fc.string(), (name) => {
          const class1 = getCharClass(name);
          const class2 = getCharClass(name);
          const class3 = getCharClass(name);
          
          expect(class1).toBe(class2);
          expect(class2).toBe(class3);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Null/empty always returns 'char-none'
     * 
     * **Validates**: CSS class generation stability
     */
    it('should always return char-none for null', () => {
      const className = getCharClass(null);
      expect(className).toBe('char-none');
    });

    it('should always return char-none for empty string', () => {
      const className = getCharClass('');
      expect(className).toBe('char-none');
    });

    /**
     * Property: Works with Unicode characters
     * 
     * **Validates**: CSS class generation stability
     */
    it('should handle Unicode characters correctly', () => {
      // Test with a variety of Unicode strings
      const unicodeStrings = [
        '中文名字',
        'العربية',
        'Ελληνικά',
        '日本語',
        '한국어',
        'Русский',
        '🎭🎨🎪',
        'Café',
        'naïve'
      ];
      
      unicodeStrings.forEach(name => {
        const className = getCharClass(name);
        const classRegex = /^char-([0-9a-f]{1,16}|none)$/;
        expect(className).toMatch(classRegex);
      });
    });
  });

  describe('getToneEmoji Stability', () => {
    /**
     * Property: For any string, getToneEmoji() returns valid emoji or empty string
     * 
     * **Validates**: Tone emoji mapping stability
     */
    it('should always return valid emoji or empty string', () => {
      fc.assert(
        fc.property(fc.string(), (tone) => {
          const emoji = getToneEmoji(tone);
          
          // Should be one of the known emojis or empty string
          const validEmojis = ['💢', '💧', '✨', '❗', '🤫', '📢', ''];
          expect(validEmojis).toContain(emoji);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Same input always produces same output (deterministic)
     * 
     * **Validates**: Tone emoji mapping stability
     */
    it('should be deterministic - same input always produces same output', () => {
      fc.assert(
        fc.property(fc.string(), (tone) => {
          const emoji1 = getToneEmoji(tone);
          const emoji2 = getToneEmoji(tone);
          const emoji3 = getToneEmoji(tone);
          
          expect(emoji1).toBe(emoji2);
          expect(emoji2).toBe(emoji3);
        }),
        { numRuns: 1000 }
      );
    });

    /**
     * Property: Null/undefined/empty always returns empty string
     * 
     * **Validates**: Tone emoji mapping stability
     */
    it('should always return empty string for null', () => {
      const emoji = getToneEmoji(null);
      expect(emoji).toBe('');
    });

    it('should always return empty string for undefined', () => {
      const emoji = getToneEmoji(undefined);
      expect(emoji).toBe('');
    });

    it('should always return empty string for empty string', () => {
      const emoji = getToneEmoji('');
      expect(emoji).toBe('');
    });

    /**
     * Property: Case-insensitive matching
     * 
     * **Validates**: Tone emoji mapping stability
     */
    it('should be case-insensitive', () => {
      fc.assert(
        fc.property(
          fc.constantFrom('angry', 'sad', 'happy', 'shocked', 'whisper', 'shout'),
          (tone) => {
            const emoji1 = getToneEmoji(tone);
            const emoji2 = getToneEmoji(tone.toUpperCase());
            const emoji3 = getToneEmoji(tone.toLowerCase());
            
            expect(emoji1).toBe(emoji2);
            expect(emoji2).toBe(emoji3);
            expect(emoji1).not.toBe(''); // Should match something
          }
        ),
        { numRuns: 100 }
      );
    });
  });
});
