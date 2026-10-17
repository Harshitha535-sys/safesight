import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { ApiError, api, errMsg, isTerminal, normFrames, normJob, obj, pick } from './api';
import type { Frame, IncidentRow, JobView, Zone } from './api';

export interface Settings { zone: Zone; cooldown_s: number; process_fps: number; confidence: number }
const DEFAULTS: Settings = { zone: { x1: 0.45, y1: 0.25, x2: 0.8, y2: 0.55 }, cooldown_s: 10, process_fps: 5, confidence: 0.3 };

/** Backend has no "list jobs" endpoint, so job ids are remembered in this browser. */
export interface JobRecord {
  id: string; filename: string; createdAt: number; zone: Zone; cooldown_s: number; process_fps: number;
  cached?: unknown; doneAt?: number; seenRunning?: boolean; gone?: boolean; fetchError?: string;
}
export interface ModelInfo { state: 'loading' | 'ok' | 'error'; raw?: Record<string, unknown>; ready: boolean | null; error?: string }

function load<T>(key: string, fallback: T): T {
  try { const v = localStorage.getItem(key); return v ? (JSON.parse(v) as T) : fallback; } catch { return fallback; }
}
function save(key: string, v: unknown) { try { localStorage.setItem(key, JSON.stringify(v)); } catch { /* storage full/blocked */ } }

interface Store {
  records: JobRecord[]; views: Record<string, JobView>; incidents: IncidentRow[];
  settings: Settings; setSettings: (p: Partial<Settings>) => void;
  health: 'checking' | 'online' | 'offline'; model: ModelInfo; refreshModel: () => void;
  activeId: string | null; setActiveId: (id: string | null) => void; videoUrls: Record<string, string>;
  submit: (file: File) => Promise<void>; submitting: boolean; submitError: string | null;
  toggleAck: (key: string) => void; clearHistory: () => void;
}
const Ctx = createContext<Store | null>(null);
export const useStore = () => { const s = useContext(Ctx); if (!s) throw new Error('StoreProvider missing'); return s; };

export function StoreProvider({ children }: { children: ReactNode }) {
  const [records, setRecords] = useState<JobRecord[]>(() =>
    load<JobRecord[]>('safesight.jobs', []).map((r) => (r.cached && !isTerminal(normJob(r.cached, r.id).status) ? { ...r, seenRunning: false } : r)));
  const [acks, setAcks] = useState<Record<string, true>>(() => load('safesight.acks', {}));
  const [settings, setSettingsState] = useState<Settings>(() => ({ ...DEFAULTS, ...load<Partial<Settings>>('safesight.settings', {}) }));
  const [health, setHealth] = useState<Store['health']>('checking');
  const [model, setModel] = useState<ModelInfo>({ state: 'loading', ready: null });
  const [activeId, setActiveId] = useState<string | null>(() => load<JobRecord[]>('safesight.jobs', [])[0]?.id ?? null);
  const [videoUrls, setVideoUrls] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => save('safesight.jobs', records), [records]);
  useEffect(() => save('safesight.acks', acks), [acks]);
  useEffect(() => save('safesight.settings', settings), [settings]);

  useEffect(() => {
    let alive = true;
    const ping = () => api.health().then(() => alive && setHealth('online')).catch(() => alive && setHealth('offline'));
    ping(); const h = setInterval(ping, 8000);
    return () => { alive = false; clearInterval(h); };
  }, []);

  const refreshModel = useCallback(() => {
    api.modelStatus().then((raw) => {
      const o = obj(raw);
      const r = pick(o, 'present', 'available', 'ready', 'exists', 'valid', 'ok', 'loaded');
      setModel({ state: 'ok', raw: o, ready: typeof r === 'boolean' ? r : null });
    }).catch((e) => setModel({ state: 'error', ready: null, error: errMsg(e) }));
  }, []);
  useEffect(() => { refreshModel(); const h = setInterval(refreshModel, 30000); return () => clearInterval(h); }, [refreshModel]);

  const refreshJob = useCallback(async (id: string) => {
    try {
      const raw = await api.job(id);
      const term = isTerminal(normJob(raw, id).status);
      setRecords((rs) => rs.map((r) => r.id !== id ? r : {
        ...r, cached: raw, gone: false, fetchError: undefined,
        seenRunning: r.seenRunning || !term, doneAt: term ? (r.doneAt ?? Date.now()) : undefined,
      }));
    } catch (e) {
      const gone = e instanceof ApiError && e.status === 404;
      setRecords((rs) => rs.map((r) => r.id !== id ? r : gone ? { ...r, gone: true } : { ...r, fetchError: errMsg(e) }));
    }
  }, []);

  const recRef = useRef(records); recRef.current = records;
  const busy = useRef(false);
  useEffect(() => {
    const tick = async () => {
      if (busy.current) return;
      busy.current = true;
      for (const r of [...recRef.current]) {
        if (r.gone) continue;
        if (r.cached && isTerminal(normJob(r.cached, r.id).status)) continue;
        await refreshJob(r.id);
      }
      busy.current = false;
    };
    tick(); const h = setInterval(tick, 1500);
    return () => clearInterval(h);
  }, [refreshJob]);

  const views = useMemo(() => {
    const m: Record<string, JobView> = {};
    for (const r of records) if (r.cached) m[r.id] = normJob(r.cached, r.id);
    return m;
  }, [records]);

  const incidents = useMemo<IncidentRow[]>(() =>
    records.flatMap((r) => (views[r.id]?.incidents ?? []).map((i) => ({ ...i, source: r.filename, runAt: r.createdAt, acked: !!acks[i.key] }))),
  [records, views, acks]);

  const submit = useCallback(async (file: File) => {
    setSubmitting(true); setSubmitError(null);
    try {
      const id = await api.createJob(file, settings.zone, settings.cooldown_s, settings.process_fps);
      setVideoUrls((v) => ({ ...v, [id]: URL.createObjectURL(file) }));
      setRecords((rs) => [{ id, filename: file.name, createdAt: Date.now(), zone: settings.zone, cooldown_s: settings.cooldown_s, process_fps: settings.process_fps, seenRunning: true }, ...rs]);
      setActiveId(id);
      refreshJob(id);
    } catch (e) { setSubmitError(errMsg(e)); }
    finally { setSubmitting(false); }
  }, [settings, refreshJob]);

  const value: Store = {
    records, views, incidents, settings, health, model, refreshModel, activeId, setActiveId, videoUrls, submit, submitting, submitError,
    setSettings: (p) => setSettingsState((s) => ({ ...s, ...p })),
    toggleAck: (k) => setAcks((a) => { const n = { ...a }; if (n[k]) delete n[k]; else n[k] = true; return n; }),
    clearHistory: () => { setRecords([]); setAcks({}); setActiveId(null); },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

const frameCache = new Map<string, Frame[]>();
/** Loads per-frame detections for a finished job (GET /api/jobs/{id}/frames). */
export function useFrames(id: string | null, ready: boolean, fps: number) {
  const [st, setSt] = useState<{ frames: Frame[]; loading: boolean; error: string | null }>({ frames: [], loading: false, error: null });
  useEffect(() => {
    let cancel = false;
    const hit = id ? frameCache.get(id) : undefined;
    if (!id || !ready) setSt({ frames: [], loading: false, error: null });
    else if (hit) setSt({ frames: hit, loading: false, error: null });
    else {
      setSt({ frames: [], loading: true, error: null });
      api.frames(id)
        .then((raw) => { const f = normFrames(raw, fps); frameCache.set(id, f); if (!cancel) setSt({ frames: f, loading: false, error: null }); })
        .catch((e) => { if (!cancel) setSt({ frames: [], loading: false, error: errMsg(e) }); });
    }
    return () => { cancel = true; };
  }, [id, ready, fps]);
  return st;
}
