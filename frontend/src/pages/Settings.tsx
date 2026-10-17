import { Database, Download, Trash2 } from 'lucide-react';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { api, errMsg, zoneValid } from '../api';
import type { Zone } from '../api';
import { useStore } from '../store';
import { Badge, Card, Notice, btnGhost, btnPrimary, input, mutedStyle, okStyle, sevStyle } from '../ui';

export default function Settings() {
  const { settings, setSettings, model, refreshModel, health, records, views, clearHistory } = useStore();
  const [dl, setDl] = useState<{ busy: boolean; err: string | null }>({ busy: false, err: null });
  const z = settings.zone; const ok = zoneValid(z);
  const setZ = (k: keyof Zone, v: string) => setSettings({ zone: { ...z, [k]: Number(v) } });
  const latest = records[0];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Detection">
        <label className="block text-sm text-slate-300">Confidence threshold: <b className="text-white">{settings.confidence.toFixed(2)}</b>
          <input type="range" min={0} max={0.95} step={0.05} value={settings.confidence} onChange={(e) => setSettings({ confidence: Number(e.target.value) })} className="mt-2 w-full accent-blue-500" /></label>
        <p className="mt-2 text-xs text-slate-500">Display filter only: hides lower-confidence boxes in the viewer. The backend API does not accept a detection threshold, so alerts are unaffected.</p>
      </Card>

      <Card title="Restricted zone & alert cooldown">
        <div className="grid grid-cols-2 gap-3 text-sm text-slate-300">
          {(['x1', 'y1', 'x2', 'y2'] as const).map((k) => (
            <label key={k}>{k.toUpperCase()} (0–1)<input type="number" step={0.01} min={0} max={1} className={`${input} mt-1 w-full`} value={z[k]} onChange={(e) => setZ(k, e.target.value)} /></label>
          ))}
          <label>Alert cooldown (s)<input type="number" min={0} step={1} className={`${input} mt-1 w-full`} value={settings.cooldown_s} onChange={(e) => setSettings({ cooldown_s: Math.max(0, Number(e.target.value)) })} /></label>
          <label>Analysis rate (fps)<input type="number" min={1} step={1} className={`${input} mt-1 w-full`} value={settings.process_fps} onChange={(e) => setSettings({ process_fps: Math.max(1, Number(e.target.value)) })} /></label>
        </div>
        {!ok && <p className="mt-2 text-xs text-red-400">Zone must stay within 0–1 with X1 &lt; X2 and Y1 &lt; Y2. Analysis is disabled until fixed.</p>}
        <div className="relative mt-3 aspect-video w-full rounded-lg border border-slate-700 bg-[#0a1322]">
          {ok && <div className="absolute border-2 border-dashed border-red-500 bg-red-500/20" style={{ left: `${z.x1 * 100}%`, top: `${z.y1 * 100}%`, width: `${(z.x2 - z.x1) * 100}%`, height: `${(z.y2 - z.y1) * 100}%` }} />}
          <span className="absolute bottom-1 right-2 text-[10px] text-slate-500">zone preview (fraction of frame)</span>
        </div>
        <p className="mt-2 text-xs text-slate-500">Applied to the next analysis you start. Saved in this browser.</p>
      </Card>

      <Card title="System status">
        <div className="space-y-3 text-sm">
          <Line k="Backend API" v={<Badge cls={health === 'online' ? okStyle : health === 'offline' ? sevStyle.critical : mutedStyle}>{health}</Badge>} />
          <Line k="Database" v={<Badge cls={mutedStyle}><Database className="h-3 w-3" />Not available</Badge>} />
          <p className="text-xs text-slate-500">The API exposes no database endpoint; per the project README, SQLite storage is not built yet and jobs are held in backend memory. Incident history shown here is cached in this browser.</p>
          <Line k="Processing mode" v={<Badge cls={mutedStyle}>Video-file jobs · CPU</Badge>} />
          <p className="text-xs text-slate-500">YOLOX-nano on ONNX Runtime (CPU). Live camera input isn't supported by the API; use uploaded video.</p>
          <Line k="Detection model" v={model.state === 'loading' ? <Badge cls={mutedStyle}>checking…</Badge> : model.state === 'error' ? <Badge cls={sevStyle.critical}>unreachable</Badge> : <Badge cls={model.ready === null ? mutedStyle : model.ready ? okStyle : sevStyle.warning}>{model.ready === null ? 'status unknown' : model.ready ? 'weights present' : 'weights missing'}</Badge>} />
          {model.ready === false && (
            <div><button className={btnPrimary} disabled={dl.busy} onClick={async () => { setDl({ busy: true, err: null }); try { await api.downloadModel(); refreshModel(); setDl({ busy: false, err: null }); } catch (e) { setDl({ busy: false, err: errMsg(e) }); } }}><Download className="h-4 w-4" />{dl.busy ? 'Downloading…' : 'Download weights'}</button>
              {dl.err && <div className="mt-2"><Notice kind="error" title="Download failed">{dl.err}</Notice></div>}</div>
          )}
          {model.error && <Notice kind="error" title="Model status unavailable">{model.error}</Notice>}
        </div>
      </Card>

      <Card title="Local data & diagnostics">
        <button className={btnGhost} disabled={!records.length} onClick={() => { if (confirm('Forget all remembered jobs and acknowledgements in this browser? Backend data is not affected.')) clearHistory(); }}><Trash2 className="h-4 w-4" />Clear local history ({records.length})</button>
        <details className="mt-3 text-xs text-slate-400">
          <summary className="cursor-pointer">Raw API responses (for debugging field mapping)</summary>
          <pre className="mt-2 max-h-64 overflow-auto rounded bg-[#0a1322] p-2 text-[11px]">{JSON.stringify({ modelStatus: model.raw ?? null, latestJob: latest ? (views[latest.id]?.raw ?? null) : null }, null, 2)}</pre>
        </details>
      </Card>
    </div>
  );
}
const Line = ({ k, v }: { k: string; v: ReactNode }) => <div className="flex items-center justify-between"><span className="text-slate-400">{k}</span>{v}</div>;
