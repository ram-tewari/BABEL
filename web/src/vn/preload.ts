import { useEffect, useState } from "react";
import type { StageView } from "../lib/api";

/**
 * Chapter preloading: every background and every expression a chapter uses is fetched *and decoded*
 * before its curtain rises, so faces and sets change instantly instead of popping in mid-scene.
 *
 * Decoded images are kept (bounded) so the browser doesn't throw them away between lines.
 */

const pending = new Map<string, Promise<void>>();
const kept: HTMLImageElement[] = [];
const KEEP = 90; // ~ this chapter and the next

export function preloadImage(url: string): Promise<void> {
  let p = pending.get(url);
  if (!p) {
    p = new Promise<void>((resolve) => {
      const img = new Image();
      img.decoding = "async";
      img.src = url;
      const done = () => {
        kept.push(img);
        if (kept.length > KEEP) kept.splice(0, kept.length - KEEP);
        resolve();
      };
      img.decode().then(done, () => {
        pending.delete(url); // a failed load can be retried later (art may still be painting)
        resolve();
      });
    });
    pending.set(url, p);
  }
  return p;
}

/** Every image a chapter will show: its scenes' backgrounds and all the expressions its lines use. */
export function chapterAssets(s: StageView): string[] {
  const out = new Set<string>();
  for (const sc of s.scenes) if (sc.background) out.add(sc.background);
  for (const b of s.blocks) if (b.sprite) out.add(b.sprite);
  return [...out];
}

/** Preload a whole chapter, a few at a time; ``progress`` is (loaded, total). */
export async function preloadChapter(s: StageView, progress?: (done: number, total: number) => void) {
  const urls = chapterAssets(s);
  let done = 0;
  progress?.(0, urls.length);
  const queue = [...urls];
  const worker = async () => {
    for (let u = queue.shift(); u; u = queue.shift()) {
      await preloadImage(u);
      progress?.(++done, urls.length);
    }
  };
  await Promise.all(Array.from({ length: 4 }, worker));
}

/** Preload state for the chapter on stage: ready when everything is decoded (or after ``maxWait`` ms). */
export function useChapterPreload(s: StageView | undefined, maxWait = 12000) {
  const [state, setState] = useState<{ id?: number; done: number; total: number; ready: boolean }>({ done: 0, total: 0, ready: false });
  const key = s ? `${s.chapter.id}:${chapterAssets(s).join("|")}` : "";
  useEffect(() => {
    if (!s) return;
    let live = true;
    const id = s.chapter.id;
    setState((x) => (x.id === id ? x : { id, done: 0, total: 0, ready: false }));
    const timer = setTimeout(() => live && setState((x) => (x.id === id ? { ...x, ready: true } : x)), maxWait);
    void preloadChapter(s, (done, total) => live && setState((x) => ({ id, done, total, ready: x.id === id && x.ready ? true : done >= total }))).then(
      () => live && setState((x) => ({ ...x, id, ready: true })),
    );
    return () => {
      live = false;
      clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, maxWait]);
  return s && state.id === s.chapter.id ? state : { done: 0, total: 0, ready: false };
}
