export type BlockType = "narration" | "dialogue" | "thought" | "system" | "sfx" | "tag" | "break";

export interface Job {
  id: number;
  novel_id: number;
  status: "queued" | "running" | "paused" | "done" | "failed" | "cancelled";
  first_idx: number | null;
  last_idx: number | null;
  force: number;
  mode: "auto" | "llm" | "heuristic";
  total: number;
  done: number;
  failed: number;
  message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  novel_title?: string;
}

export interface Novel {
  id: number;
  title: string;
  author: string | null;
  description: string | null;
  language: string | null;
  source_name: string | null;
  pov_character_id: number | null;
  chapter_count: number;
  done_count: number;
  last_chapter_id: number | null;
  has_cover: boolean;
  updated_at: string;
  job: Job | null;
}

export interface NovelDetail extends Novel {
  progress: { chapter_id: number; position: number } | null;
  methods: Record<string, number>;
  failed_count: number;
  word_count: number;
}

export interface ChapterRow {
  id: number;
  idx: number;
  title: string;
  word_count: number;
  status: "pending" | "done" | "failed";
  method: string | null;
  model: string | null;
  error: string | null;
}

export interface Character {
  id: number;
  name: string;
  note: string | null;
  color: string;
  side: "left" | "right";
  lines: number;
  is_pov: boolean;
  first_idx: number | null;
  aliases?: string[];
  custom_color?: boolean;
  custom_side?: boolean;
}

export interface Block {
  type: BlockType;
  text: string;
  speaker: string | null;
  character_id: number | null;
  para: number;
  seg: number[];
  edited: boolean;
}

export interface ChapterView {
  id: number;
  novel_id: number;
  idx: number;
  title: string;
  status: ChapterRow["status"];
  method: "llm" | "heuristic" | "mixed" | "preview";
  model: string | null;
  summary: string | null;
  error: string | null;
  word_count: number;
  prev_id: number | null;
  next_id: number | null;
  blocks: Block[];
  characters: Character[];
}

export interface Status {
  version: string;
  llm: string | null;
  providers: { name: string; model: string }[];
  concurrency: number;
}

export interface SearchHit {
  id: number;
  idx: number;
  title: string;
  snippet: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  if (init?.body && !(init.body instanceof FormData)) headers["Content-Type"] = "application/json";
  const res = await fetch(`/api${path}`, { ...init, headers: { ...headers, ...(init?.headers as object) } });
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* not json */
    }
    throw new ApiError(res.status, msg);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

function upload(file: File): RequestInit {
  const fd = new FormData();
  fd.append("file", file);
  return { method: "POST", body: fd };
}

export const api = {
  status: () => req<Status>("/status"),
  novels: () => req<Novel[]>("/novels"),
  novel: (id: number) => req<NovelDetail>(`/novels/${id}`),
  importNovel: (file: File) => req<{ id: number; title: string; chapters: number; warnings: string[] }>("/novels/import", upload(file)),
  appendChapters: (id: number, file: File) => req<{ added: number }>(`/novels/${id}/append`, upload(file)),
  patchNovel: (id: number, body: Partial<Pick<Novel, "title" | "author" | "description" | "pov_character_id">>) =>
    req<NovelDetail>(`/novels/${id}`, json("PATCH", body)),
  deleteNovel: (id: number) => req<void>(`/novels/${id}`, { method: "DELETE" }),
  uploadCover: (id: number, file: File) => req<{ ok: true }>(`/novels/${id}/cover`, upload(file)),
  coverUrl: (id: number, bust?: string) => `/api/novels/${id}/cover${bust ? `?v=${encodeURIComponent(bust)}` : ""}`,
  chapters: (id: number) => req<ChapterRow[]>(`/novels/${id}/chapters`),
  search: (id: number, q: string) => req<SearchHit[]>(`/novels/${id}/search?q=${encodeURIComponent(q)}`),
  progress: (id: number, chapter_id: number, position: number) =>
    req<{ ok: true }>(`/novels/${id}/progress`, json("PUT", { chapter_id, position })),
  chapter: (id: number) => req<ChapterView>(`/chapters/${id}`),
  source: (id: number) => req<{ id: number; title: string; text: string }>(`/chapters/${id}/source`),
  edit: (id: number, segs: number[], type: BlockType, speaker: string | null) =>
    req<ChapterView>(`/chapters/${id}/edit`, json("POST", { segs, type, speaker })),
  clearEdits: (id: number, segs?: number[]) => req<ChapterView>(`/chapters/${id}/edit/clear`, json("POST", { segs: segs ?? null })),
  retransform: (id: number, mode: Job["mode"] = "auto") => req<Job>(`/chapters/${id}/transform`, json("POST", { mode, force: true })),
  characters: (novelId: number) => req<Character[]>(`/novels/${novelId}/characters`),
  patchCharacter: (id: number, body: { name?: string; note?: string | null; color?: string | null; side?: string | null }) =>
    req<{ ok: true }>(`/characters/${id}`, json("PATCH", body)),
  mergeCharacter: (id: number, into: number) => req<{ ok: true }>(`/characters/${id}/merge`, json("POST", { into })),
  addAlias: (id: number, alias: string) => req<{ ok: true }>(`/characters/${id}/aliases`, json("POST", { alias })),
  removeAlias: (id: number, alias: string) => req<{ ok: true }>(`/characters/${id}/aliases/${encodeURIComponent(alias)}`, { method: "DELETE" }),
  startJob: (novelId: number, body: { first?: number | null; last?: number | null; force?: boolean; mode?: Job["mode"] }) =>
    req<Job>(`/novels/${novelId}/jobs`, json("POST", body)),
  jobAction: (jobId: number, action: "pause" | "resume" | "cancel") => req<Job>(`/jobs/${jobId}/${action}`, json("POST")),
  exportUrl: (novelId: number, kind: "epub" | "html" | "corrections", first?: number | null, last?: number | null) => {
    const p = new URLSearchParams();
    if (first != null) p.set("first", String(first));
    if (last != null) p.set("last", String(last));
    const q = p.toString();
    return `/api/novels/${novelId}/export/${kind}${q ? `?${q}` : ""}`;
  },
};

export const isActive = (j: Job | null | undefined) => !!j && (j.status === "queued" || j.status === "running");
