/* eslint-disable @typescript-eslint/no-explicit-any */
// Typed client for the SafeSight FastAPI backend (endpoints per README).
// The README does not specify JSON field names, so responses are normalised
// defensively. If a field shows as "—", adjust the key lists below
// (Settings > Diagnostics shows the raw responses).

export type Zone = { x1: number; y1: number; x2: number; y2: number };
export type Severity = 'critical' | 'warning' | 'info';
type Rec = Record<string, any>;

export interface Incident {
  key: string; jobId: string; index: number; type: string; severity: Severity;
  videoTime: number | null; track: number | null; snapshot: string | null;
}
export interface IncidentRow extends Incident { source: string; runAt: number; acked: boolean }
export interface Det { box: [number, number, number, number]; conf: number | null; track: number | null; inZone: boolean }
export interface Frame { t: number; dets: Det[]; w: number | null; h: number | null }
export interface JobView {
  id: string; status: string; progress: number | null;
  summary: Rec; incidents: Incident[]; errors: string[]; raw: unknown;
}

const BASE = ((import.meta.env.VITE_API_URL as string | undefined) ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}
export const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try { res = await fetch(BASE + path, init); }
  catch { throw new ApiError(0, 'Backend unreachable'); }
  if (!res.ok) {
    let detail = '';
    try { const j = await res.json(); detail = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail ?? j); } catch { /* no body */ }
    throw new ApiError(res.status, detail || `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export const obj = (v: unknown): Rec => (v && typeof v === 'object' && !Array.isArray(v) ? (v as Rec) : {});
export const pick = (o: Rec, ...keys: string[]): any => {
  for (const k of keys) if (o[k] !== undefined && o[k] !== null) return o[k];
  return undefined;
};
const num = (v: unknown): number | null => (typeof v === 'number' && isFinite(v) ? v : null);

export const isDone = (s: string) => /complete|done|finish|success/i.test(s);
export const isFail = (s: string) => /fail|error/i.test(s);
export const isTerminal = (s: string) => isDone(s) || isFail(s);
export const zoneValid = (z: Zone) =>
  [z.x1, z.y1, z.x2, z.y2].every((n) => n >= 0 && n <= 1) && z.x1 < z.x2 && z.y1 < z.y2;

export function normJob(raw: unknown, fallbackId: string): JobView {
  const o = obj(raw);
  const id = String(pick(o, 'id', 'job_id') ?? fallbackId);
  let progress = num(pick(o, 'progress'));
  if (progress !== null && progress > 1) progress /= 100;
  const e = pick(o, 'errors', 'error');
  const errors: string[] = Array.isArray(e)
    ? e.map((x) => (typeof x === 'string' ? x : JSON.stringify(x)))
    : e ? [typeof e === 'string' ? e : JSON.stringify(e)] : [];
  const evs: unknown[] = Array.isArray(o.events) ? o.events : [];
  return {
    id, status: String(pick(o, 'status', 'state') ?? 'unknown'), progress,
    summary: obj(o.summary), errors, raw,
    incidents: evs.map((ev, i) => normEvent(ev, id, i)),
  };
}

function normEvent(ev: unknown, jobId: string, index: number): Incident {
  const o = obj(ev);
  const type = String(pick(o, 'type', 'event_type', 'kind', 'event') ?? 'event');
  const sv = String(pick(o, 'severity', 'level') ?? '').toLowerCase();
  // The backend has no severity field per README: violations are treated as critical.
  const severity: Severity = sv === 'critical' || sv === 'warning' || sv === 'info' ? sv
    : /violation|intrusion|restricted/i.test(type) ? 'critical' : 'warning';
  const snap = pick(o, 'snapshot', 'snapshot_url', 'snapshot_path', 'snapshot_file', 'image');
  return {
    key: `${jobId}:${index}`, jobId, index, type, severity,
    videoTime: num(pick(o, 'time_s', 'video_time_s', 'timestamp_s', 't', 'time')),
    track: num(pick(o, 'track_id', 'person_id', 'id')),
    snapshot: typeof snap === 'string' ? snap : null,
  };
}

export function snapshotUrl(jobId: string, snap: string): string {
  if (/^https?:/i.test(snap)) return snap;
  if (snap.startsWith('/api/')) return BASE + snap;
  const name = snap.split(/[\\/]/).pop() ?? snap;
  return `${BASE}/api/jobs/${encodeURIComponent(jobId)}/snapshots/${encodeURIComponent(name)}`;
}

function normBox(o: Rec): [number, number, number, number] | null {
  const b = pick(o, 'bbox', 'box', 'xyxy');
  if (Array.isArray(b) && b.length >= 4 && b.slice(0, 4).every((x) => typeof x === 'number')) return [b[0], b[1], b[2], b[3]];
  if (b && typeof b === 'object' && !Array.isArray(b)) return normBox(b as Rec);
  const [x1, y1, x2, y2] = [num(o.x1), num(o.y1), num(o.x2), num(o.y2)];
  if (x1 !== null && y1 !== null && x2 !== null && y2 !== null) return [x1, y1, x2, y2];
  const [x, y, w, h] = [num(o.x), num(o.y), num(o.w ?? o.width), num(o.h ?? o.height)];
  if (x !== null && y !== null && w !== null && h !== null) return [x, y, x + w, y + h];
  return null;
}

export function normFrames(raw: unknown, fps: number): Frame[] {
  const top = obj(raw);
  const arr: unknown[] = Array.isArray(raw) ? raw : Array.isArray(top.frames) ? top.frames : [];
  const gw = num(pick(top, 'width', 'frame_width')), gh = num(pick(top, 'height', 'frame_height'));
  const frames = arr.map((f, i): Frame => {
    const o = obj(f);
    const list: unknown[] = pick(o, 'detections', 'people', 'persons', 'boxes') ?? [];
    const dets: Det[] = [];
    for (const d of Array.isArray(list) ? list : []) {
      const od = obj(d); const box = normBox(od);
      if (!box) continue;
      dets.push({
        box, conf: num(pick(od, 'confidence', 'conf', 'score')),
        track: num(pick(od, 'track_id', 'id')),
        inZone: Boolean(pick(od, 'in_zone', 'inside', 'in_restricted_zone', 'inside_zone')),
      });
    }
    const idx = num(pick(o, 'frame_index', 'frame', 'index')) ?? i;
    return {
      t: num(pick(o, 'time_s', 'video_time_s', 'timestamp_s', 't', 'time')) ?? idx / fps,
      dets, w: num(pick(o, 'width', 'frame_width')) ?? gw, h: num(pick(o, 'height', 'frame_height')) ?? gh,
    };
  });
  return frames.sort((a, b) => a.t - b.t);
}

export function frameAt(frames: Frame[], t: number): Frame | null {
  let lo = 0, hi = frames.length - 1, ans = -1;
  while (lo <= hi) { const m = (lo + hi) >> 1; if (frames[m].t <= t) { ans = m; lo = m + 1; } else hi = m - 1; }
  return ans >= 0 ? frames[ans] : null;
}

/** Normalise a box to 0-1 coordinates. Returns null if pixel size is unknown. */
export function toNorm(b: [number, number, number, number], f: Frame | null, vw: number | null, vh: number | null) {
  if (Math.max(...b) <= 1.5) return b;
  const w = f?.w ?? vw, h = f?.h ?? vh;
  return w && h ? ([b[0] / w, b[1] / h, b[2] / w, b[3] / h] as [number, number, number, number]) : null;
}

export const api = {
  health: () => request<unknown>('/api/health'),
  modelStatus: () => request<unknown>('/api/model/status'),
  downloadModel: () => request<unknown>('/api/model/download', { method: 'POST' }),
  job: (id: string) => request<unknown>(`/api/jobs/${encodeURIComponent(id)}`),
  frames: (id: string) => request<unknown>(`/api/jobs/${encodeURIComponent(id)}/frames`),
  async createJob(file: File, z: Zone, cooldown: number, fps: number): Promise<string> {
    const fd = new FormData();
    fd.append('file', file);
    (['x1', 'y1', 'x2', 'y2'] as const).forEach((k) => fd.append(`zone_${k}`, String(z[k])));
    fd.append('cooldown_s', String(cooldown));
    fd.append('process_fps', String(fps));
    const r = obj(await request<unknown>('/api/jobs', { method: 'POST', body: fd }));
    const id = pick(r, 'id', 'job_id');
    if (id === undefined) throw new ApiError(500, 'Backend response did not include a job id');
    return String(id);
  },
};
