export type BlockType = "narration" | "action" | "dialogue" | "thought" | "system" | "sfx" | "tag" | "break";
export type Tier = "rule" | "memory" | "local" | "cloud" | "user";
export type TierMode = "auto" | "rules" | "local" | "cloud";
export type EntityKind = "character" | "location" | "faction" | "term";
export const TONES = ["shout", "whisper", "angry", "sad", "laugh", "nervous", "cold"] as const;
export type Tone = (typeof TONES)[number];

export interface Job {
  id: number;
  novel_id: number;
  status: "queued" | "running" | "paused" | "done" | "failed" | "cancelled";
  first_idx: number | null;
  last_idx: number | null;
  force: number;
  tiers: TierMode;
  total: number;
  done: number;
  failed: number;
  message: string | null;
  finished_at: string | null;
  novel_title?: string;
}

export interface Novel {
  id: number;
  title: string;
  author: string | null;
  description: string | null;
  language: string | null;
  status: string | null;
  tags: string[];
  source_name: string | null;
  source_url: string | null;
  pov_character_id: number | null;
  chapter_count: number;
  done_count: number;
  read_count: number;
  last_chapter_id: number | null;
  has_cover: boolean;
  updated_at: string;
  job: Job | null;
}

export interface Usage {
  tier: "local" | "cloud";
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  questions: number;
  calls: number;
}

export interface NovelDetail extends Novel {
  progress: { chapter_id: number; position: number } | null;
  word_count: number;
  review_total: number;
  failed_count: number;
  tier_counts: Partial<Record<Tier, number>>;
  usage: Usage[];
  corrections: number;
}

export interface ChapterRow {
  id: number;
  idx: number;
  title: string;
  word_count: number;
  status: "pending" | "done" | "failed";
  review_count: number;
  tiers: Partial<Record<Tier, number>>;
  error: string | null;
  is_read: boolean;
}

export interface Entity {
  id: number;
  kind: EntityKind;
  name: string;
  note: string | null;
  gender: "m" | "f" | "n" | null;
  color: string;
  side: "left" | "right";
  lines: number;
  is_pov: boolean;
  first_idx: number | null;
  faction_id: number | null;
  has_portrait: boolean;
  aliases: string[];
  locked: string[];
}

export interface Block {
  type: BlockType;
  text: string;
  speaker: string | null;
  character_id: number | null;
  tone: Tone | null;
  conf: number;
  tier: Tier;
  para: number;
  seg: number[];
  edited: boolean;
  review: boolean;
  candidates: string[];
  why: string | null;
}

export interface GlossaryHit {
  entity_id: number;
  kind: EntityKind;
  name: string;
  note: string | null;
  terms: string[];
}

export interface ChapterView {
  id: number;
  novel_id: number;
  idx: number;
  title: string;
  status: ChapterRow["status"];
  method: "cascade" | "preview";
  tiers: Partial<Record<Tier, number>>;
  summary: string | null;
  error: string | null;
  word_count: number;
  review_count: number;
  prev_id: number | null;
  next_id: number | null;
  blocks: Block[];
  characters: Entity[];
  glossary: GlossaryHit[];
}

export interface Status {
  version: string;
  tiers: { local: string | null; cloud: { name: string; model: string }[] };
  policy: { accept: number; escalate: number; review: number; summaries: string };
  concurrency: number;
  parallel_novels: number;
}

export interface Estimate {
  chapters: number;
  words: number;
  per_tier: Partial<Record<"local" | "cloud", { prompt: number; completion: number; questions: number }>>;
  basis: string;
  local_minutes: number;
}

export interface ReviewItem {
  chapter_id: number;
  chapter_idx: number;
  chapter_title: string;
  block: Block;
  before: string[];
  after: string[];
}

export interface Correction {
  chapter_id: number;
  chapter_idx: number;
  chapter_title: string;
  seg: number;
  text: string | null;
  created_at: string;
  after: { type: BlockType; speaker: string | null };
  before: { type: BlockType; speaker: string | null; tier: Tier; conf: number } | null;
  confirmed: boolean;
}

export interface Graph {
  nodes: Entity[];
  edges: { source: number; target: number; weight: number }[];
  factions: Entity[];
}

export interface SearchHit {
  id: number;
  idx: number;
  title: string;
  snippet: string;
}

export interface MetadataResult {
  metadata: { source: string; title: string; url: string | null; author: string | null; description: string | null; cover_url: string | null; tags: string[]; status: string | null };
  notes: string[];
  applied: boolean;
}

export type ArtTier = "main" | "supporting" | "minor" | "extra";
export type DesignStatus = "new" | "profiled" | "candidates" | "choose" | "sheet" | "approved" | "failed";

export interface ProfileField {
  value: string;
  guessed: boolean;
  chapter: number | null;
  quote: string;
}
export type Profile = Record<string, ProfileField> & { tags?: string[] };

export interface ArtImage {
  id: number;
  kind: "candidate" | "expression";
  emotion: string | null;
  status: "queued" | "running" | "done" | "failed" | "rejected";
  seed: number;
  model: string;
  error: string | null;
  secs: number | null;
  url: string | null;
  thumb: string | null;
  attempt: number;
  qc_status: "pending" | "pass" | "fail" | "skipped" | null;
  qc_score: number | null;
  qc_issues: string[];
}

export interface DesignView {
  entity_id: number;
  name: string;
  status: DesignStatus;
  message: string | null;
  tier: ArtTier;
  tier_locked: boolean;
  first_idx: number | null;
  lines: number;
  profile: Profile | null;
  profile_locked: string[];
  base_image_id: number | null;
  candidates: ArtImage[];
  rejected: ArtImage[];
  sheet: Record<string, ArtImage | null>;
}

export interface ArtCharacter {
  id: number;
  name: string;
  gender: string | null;
  lines: number;
  chapters: number;
  first_idx: number | null;
  tier: ArtTier;
  tier_locked: boolean;
  design_id: number | null;
  status: DesignStatus;
  message: string | null;
}

export interface SchedulerStatus {
  status: "idle" | "waiting" | "paused" | "profiling" | "staging" | "drawing" | "checking" | "unavailable";
  detail: string | null;
  error: string | null;
  images: boolean;
  worker_running: boolean;
  queued: number;
  failed: number;
  checker: string | null;
  checked: number;
  caught: number;
}

export interface SystemPolicy {
  headroom_gb: number;
  idle_after_s: number;
  background_when: "idle" | "always";
  pause_on_battery: boolean;
}

export interface SystemStatus {
  available_gb: number | null;
  total_gb: number | null;
  pressure: number | null;
  on_battery: boolean | null;
  idle_seconds: number | null;
  policy: SystemPolicy;
  ollama_loaded: Record<string, number>;
  background_ok: boolean;
  background_reason: string | null;
}

export interface NovelArt {
  settings: { style: string; setting: string; era: string; auto: boolean };
  scheduler: SchedulerStatus;
  tiers: Record<ArtTier, number>;
  designed: number;
  needed: number;
  queue: ArtCharacter[];
  characters: ArtCharacter[];
  readiness: {
    ready: number;
    transformed: number;
    total: number;
    ready_through: number | null;
    ready_ids: number[];
    blocked: { chapter_id: number; idx: number; missing: string[] }[];
  };
}

export interface ArtMeta extends SchedulerStatus {
  emotions: string[];
  fields: { key: string; label: string }[];
}

export interface StageBlock {
  type: BlockType;
  text: string;
  speaker: string | null;
  character_id: number | null;
  tone: Tone | null;
  para: number;
  scene: number;
  emotion?: string;
  sprite?: string | null;
}

export interface StageView {
  chapter: {
    id: number;
    novel_id: number;
    idx: number;
    title: string;
    prev_id: number | null;
    next_id: number | null;
    novel_title: string;
    chapter_count: number;
    transformed: boolean;
  };
  ready: boolean;
  missing: string[];
  refined: boolean;
  scenes: { start: number; end: number; place: string; night: boolean; background: string | null; weather: string | null; indoor: boolean; category: string }[];
  blocks: StageBlock[];
  cast: Record<string, { name: string; color: string | null; side: "left" | "right"; extra: boolean; has_art: boolean; aliases?: string[] }>;
  queued?: number;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {};
  if (init?.body && typeof init.body === "string" && !(init.headers as Record<string, string>)?.["Content-Type"]) headers["Content-Type"] = "application/json";
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
  const type = res.headers.get("content-type") ?? "";
  return (type.includes("json") ? res.json() : res.text()) as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({ method, body: body === undefined ? undefined : JSON.stringify(body) });

function upload(file: File, extra?: Record<string, string>): RequestInit {
  const fd = new FormData();
  fd.append("file", file);
  Object.entries(extra ?? {}).forEach(([k, v]) => v && fd.append(k, v));
  return { method: "POST", body: fd };
}

const qs = (o: Record<string, unknown>) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => v !== null && v !== undefined && p.set(k, String(v)));
  const s = p.toString();
  return s ? `?${s}` : "";
};

export const api = {
  status: () => req<Status>("/status"),
  novels: () => req<Novel[]>("/novels"),
  novel: (id: number) => req<NovelDetail>(`/novels/${id}`),
  importNovel: (file: File, chapterPattern?: string) =>
    req<{ id: number; title: string; chapters: number; words: number; warnings: string[] }>("/novels/import", upload(file, { chapter_pattern: chapterPattern ?? "" })),
  appendChapters: (id: number, file: File) => req<{ added: number }>(`/novels/${id}/append`, upload(file)),
  patchNovel: (id: number, body: Partial<Pick<Novel, "title" | "author" | "description" | "pov_character_id" | "status" | "tags">>) =>
    req<NovelDetail>(`/novels/${id}`, json("PATCH", body)),
  deleteNovel: (id: number) => req<void>(`/novels/${id}`, { method: "DELETE" }),
  uploadCover: (id: number, file: File) => req<{ ok: true }>(`/novels/${id}/cover`, upload(file)),
  coverUrl: (id: number, bust?: string) => `/api/novels/${id}/cover${bust ? `?v=${encodeURIComponent(bust)}` : ""}`,
  fetchMetadata: (id: number, apply: boolean, sources?: string[]) => req<MetadataResult>(`/novels/${id}/metadata`, json("POST", { apply, sources })),
  chapters: (id: number) => req<ChapterRow[]>(`/novels/${id}/chapters`),
  search: (id: number, q: string) => req<SearchHit[]>(`/novels/${id}/search${qs({ q })}`),
  estimate: (id: number, first?: number | null, last?: number | null) => req<Estimate>(`/novels/${id}/estimate${qs({ first, last })}`),
  progress: (id: number, chapter_id: number, position: number) => req<{ ok: true }>(`/novels/${id}/progress`, json("PUT", { chapter_id, position })),
  chapter: (id: number) => req<ChapterView>(`/chapters/${id}`),
  source: (id: number) => req<{ id: number; title: string; text: string }>(`/chapters/${id}/source`),
  edit: (id: number, segs: number[], type: BlockType, speaker: string | null, tone: Tone | null) =>
    req<ChapterView>(`/chapters/${id}/edit`, json("POST", { segs, type, speaker, tone })),
  accept: (id: number, segs: number[]) => req<ChapterView>(`/chapters/${id}/accept`, json("POST", { segs })),
  clearEdits: (id: number, segs?: number[]) => req<ChapterView>(`/chapters/${id}/edit/clear`, json("POST", { segs: segs ?? null })),
  retransform: (id: number, tiers: TierMode = "auto") => req<Job>(`/chapters/${id}/transform`, json("POST", { tiers, force: true })),
  review: (novelId: number) => req<ReviewItem[]>(`/novels/${novelId}/review`),
  corrections: (novelId: number) => req<Correction[]>(`/novels/${novelId}/corrections`),
  entities: (novelId: number, kind?: EntityKind) => req<Entity[]>(`/novels/${novelId}/entities${qs({ kind })}`),
  createEntity: (novelId: number, body: { name: string; kind: EntityKind; note?: string | null }) => req<Entity>(`/novels/${novelId}/entities`, json("POST", body)),
  patchEntity: (id: number, body: Partial<Pick<Entity, "name" | "note" | "gender" | "color" | "side" | "faction_id" | "kind">>) =>
    req<Entity>(`/entities/${id}`, json("PATCH", body)),
  deleteEntity: (id: number) => req<void>(`/entities/${id}`, { method: "DELETE" }),
  mergeEntity: (id: number, into: number) => req<{ ok: true }>(`/entities/${id}/merge`, json("POST", { into })),
  addAlias: (id: number, alias: string) => req<{ ok: true }>(`/entities/${id}/aliases`, json("POST", { alias })),
  removeAlias: (id: number, alias: string) => req<{ ok: true }>(`/entities/${id}/aliases/${encodeURIComponent(alias)}`, { method: "DELETE" }),
  uploadPortrait: (id: number, file: File) => req<{ ok: true }>(`/entities/${id}/portrait`, upload(file)),
  portraitUrl: (id: number, bust?: string | number) => `/api/entities/${id}/portrait${bust ? `?v=${bust}` : ""}`,
  glossaryYaml: (novelId: number) => req<string>(`/novels/${novelId}/glossary.yaml`),
  importGlossary: (novelId: number, text: string, dryRun = false) =>
    req<{ created?: number; updated?: number; valid?: boolean }>(`/novels/${novelId}/glossary${qs({ dry_run: dryRun || null })}`, {
      method: "POST",
      body: text,
      headers: { "Content-Type": "text/plain" },
    }),
  graph: (novelId: number, minWeight = 2) => req<Graph>(`/novels/${novelId}/graph${qs({ min_weight: minWeight })}`),
  startJob: (novelId: number, body: { first?: number | null; last?: number | null; force?: boolean; tiers?: TierMode }) =>
    req<Job>(`/novels/${novelId}/jobs`, json("POST", body)),
  jobAction: (jobId: number, action: "pause" | "resume" | "cancel") => req<Job>(`/jobs/${jobId}/${action}`, json("POST")),
  exportUrl: (novelId: number, kind: "epub" | "html" | "json" | "corrections", first?: number | null, last?: number | null) =>
    `/api/novels/${novelId}/export/${kind}${qs({ first, last })}`,
  glossaryUrl: (novelId: number) => `/api/novels/${novelId}/glossary.yaml`,
  artMeta: () => req<ArtMeta>("/art/status"),
  stage: (chapterId: number) => req<StageView>(`/chapters/${chapterId}/stage`),
  library: (novelId: number) =>
    req<{ items: { entity_id: number; kind: "extra" | "background"; label: string; status: DesignStatus; thumb: string | null; users: string[] }[]; first_ready_chapter: number | null }>(
      `/novels/${novelId}/library`,
    ),
  redrawLibrary: (entityId: number) => req<{ ok: true }>(`/library/${entityId}/redraw`, json("POST")),
  restyle: (novelId: number, backgrounds = false) => req<{ characters: number; extras: number; backgrounds: number }>(`/novels/${novelId}/art/restyle?backgrounds=${backgrounds}`, json("POST")),
  paintDefaults: (novelId: number) => req<{ queued: number; era: string }>(`/novels/${novelId}/library/defaults`, json("POST")),
  prepareStage: (chapterId: number) => req<StageView>(`/chapters/${chapterId}/stage/prepare`, json("POST")),
  play: (novelId: number) =>
    req<{ title: string; author: string | null; has_cover: boolean; first: { id: number; idx: number; title: string } | null; continue: { id: number; idx: number; title: string } | null; ready: number; transformed: number; total: number }>(
      `/novels/${novelId}/play`,
    ),
  system: () => req<SystemStatus>("/system"),
  setSystemPrefs: (body: Partial<Pick<SystemPolicy, "background_when" | "pause_on_battery" | "idle_after_s">>) =>
    req<SystemPolicy>("/system/prefs", json("PUT", body)),
  novelArt: (novelId: number) => req<NovelArt>(`/novels/${novelId}/art`),
  setNovelArt: (novelId: number, body: Partial<NovelArt["settings"]>) => req<NovelArt["settings"]>(`/novels/${novelId}/art`, json("PUT", body)),
  design: (entityId: number) => req<DesignView>(`/entities/${entityId}/design`),
  saveProfile: (entityId: number, profile: Profile) => req<DesignView>(`/entities/${entityId}/design/profile`, json("PUT", { profile })),
  draftProfile: (entityId: number) => req<DesignView>(`/entities/${entityId}/design/draft`, json("POST")),
  drawCandidates: (entityId: number) => req<DesignView>(`/entities/${entityId}/design/candidates`, json("POST")),
  resetDesign: (entityId: number) => req<DesignView>(`/entities/${entityId}/design/reset`, json("POST")),
  setArtTier: (entityId: number, tier: ArtTier | null) => req<DesignView>(`/entities/${entityId}/design/tier`, json("PUT", { tier })),
  approveImage: (imageId: number) => req<DesignView>(`/art/images/${imageId}/approve`, json("POST")),
  rerollImage: (imageId: number) => req<DesignView>(`/art/images/${imageId}/reroll`, json("POST")),
};

export const isActive = (j: Job | null | undefined) => !!j && (j.status === "queued" || j.status === "running");

export const TIER_LABEL: Record<Tier, string> = {
  rule: "rules",
  memory: "memory",
  local: "local model",
  cloud: "cloud model",
  user: "you",
};
