import { useEffect, useRef, useState } from 'react';
import { Loader2, Pause, Play, RotateCcw, Square, Upload } from 'lucide-react';
import { frameAt, isDone, isFail, snapshotUrl, toNorm, zoneValid } from '../api';
import { useFrames, useStore } from '../store';
import { Badge, Card, Notice, SevBadge, btnGhost, btnPrimary, cn, fmtClock, input, mutedStyle, okStyle, sevStyle } from '../ui';

export default function Live() {
  const s = useStore();
  const rec = s.records.find((r) => r.id === s.activeId) ?? null;
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  useEffect(() => {
    if (!file) { setPreview(null); return; }
    const u = URL.createObjectURL(file); setPreview(u);
    return () => URL.revokeObjectURL(u);
  }, [file]);

  const viewRec = file ? null : rec;
  const view = viewRec ? s.views[viewRec.id] : undefined;
  const ready = !!view && isDone(view.status);
  const { frames, loading, error } = useFrames(viewRec?.id ?? null, ready, viewRec?.process_fps ?? 5);
  const src = file ? preview : viewRec ? s.videoUrls[viewRec.id] : undefined;
  const zone = viewRec?.zone ?? s.settings.zone;

  const vref = useRef<HTMLVideoElement>(null);
  const [t, setT] = useState(0); const [playing, setPlaying] = useState(false);
  const [dims, setDims] = useState<{ w: number; h: number } | null>(null);
  const [dur, setDur] = useState(0);
  const maxT = src ? dur : frames.length ? frames[frames.length - 1].t : 0;

  useEffect(() => { setT(0); setPlaying(false); setDims(null); setDur(0); }, [src, viewRec?.id]);
  useEffect(() => {
    if (!playing) return;
    let raf = 0, last = performance.now();
    const loop = (now: number) => {
      const v = vref.current;
      if (v) setT(v.currentTime);
      else { setT((p) => Math.min(maxT, p + (now - last) / 1000)); }
      last = now; raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
  }, [playing, maxT]);
  useEffect(() => { if (playing && !src && t >= maxT) setPlaying(false); }, [t, playing, src, maxT]);

  const play = () => { vref.current?.play(); setPlaying(true); };
  const pause = () => { vref.current?.pause(); setPlaying(false); };
  const seek = (x: number) => { if (vref.current) vref.current.currentTime = x; setT(x); };
  const stop = () => { pause(); seek(0); };

  const frame = frameAt(frames, t);
  const shown = frame ? frame.dets.filter((d) => d.conf === null || d.conf >= s.settings.confidence) : [];
  const hidden = frame ? frame.dets.length - shown.length : 0;
  const boxes = shown.map((d) => ({ d, n: toNorm(d.box, frame, dims?.w ?? null, dims?.h ?? null) }));
  const unplaceable = boxes.some((b) => !b.n);
  const aspect = dims ? `${dims.w} / ${dims.h}` : frame?.w && frame.h ? `${frame.w} / ${frame.h}` : '16 / 9';

  const incidents = view?.incidents ?? [];
  const isActive = (k: string, vt: number | null) => !s.incidents.find((i) => i.key === k)?.acked && (vt === null ? ready : vt <= t);
  const activeN = incidents.filter((i) => isActive(i.key, i.videoTime)).length;
  const measured = viewRec?.doneAt && viewRec.seenRunning && frames.length ? frames.length / ((viewRec.doneAt - viewRec.createdAt) / 1000) : null;
  const zOk = zoneValid(s.settings.zone);
  const offline = s.health === 'offline';

  return (
    <div className="grid gap-4 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card title="Processed-frame viewer" right={view && <Badge cls={isDone(view.status) ? okStyle : isFail(view.status) ? sevStyle.critical : sevStyle.warning}>{view.status}</Badge>}>
          <div className="relative w-full overflow-hidden rounded-lg border border-slate-700 bg-black" style={{ aspectRatio: aspect }}>
            {src && <video ref={vref} src={src} muted playsInline preload="auto" className="absolute inset-0 h-full w-full"
              onLoadedMetadata={(e) => { setDims({ w: e.currentTarget.videoWidth, h: e.currentTarget.videoHeight }); setDur(e.currentTarget.duration); }}
              onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onSeeked={(e) => setT(e.currentTarget.currentTime)} onEnded={() => setPlaying(false)} />}
            {!src && !viewRec && <div className="absolute inset-0 grid place-items-center p-4"><Notice kind="empty" title="No video loaded">Choose a video file below. Live camera input is not supported by the current API.</Notice></div>}
            {!src && viewRec && <div className="absolute inset-0 grid place-items-center text-xs text-slate-500">Source video not available in this session (detections only)</div>}
            <div className="pointer-events-none absolute border-2 border-dashed border-red-500 bg-red-500/15"
              style={{ left: `${zone.x1 * 100}%`, top: `${zone.y1 * 100}%`, width: `${(zone.x2 - zone.x1) * 100}%`, height: `${(zone.y2 - zone.y1) * 100}%` }}>
              <span className="absolute -top-5 left-0 rounded bg-red-600 px-1.5 text-[10px] font-semibold text-white">RESTRICTED ZONE</span>
            </div>
            {boxes.map(({ d, n }, i) => n && (
              <div key={i} className={cn('pointer-events-none absolute border-2', d.inZone ? 'border-red-400' : 'border-emerald-400')}
                style={{ left: `${n[0] * 100}%`, top: `${n[1] * 100}%`, width: `${(n[2] - n[0]) * 100}%`, height: `${(n[3] - n[1]) * 100}%` }}>
                <span className={cn('absolute -top-4 left-0 whitespace-nowrap rounded px-1 text-[10px] font-medium text-white', d.inZone ? 'bg-red-600' : 'bg-emerald-600')}>
                  {d.track !== null ? `#${d.track} ` : ''}{d.conf !== null ? `${Math.round(d.conf * 100)}%` : 'person'}
                </span>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button className={btnGhost} disabled={!(src || frames.length)} onClick={playing ? pause : play}>{playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}{playing ? 'Pause' : 'Play'}</button>
            <button className={btnGhost} disabled={!(src || frames.length)} onClick={stop}><Square className="h-4 w-4" />Stop</button>
            <button className={btnGhost} disabled={!(src || frames.length)} onClick={() => { seek(0); play(); }}><RotateCcw className="h-4 w-4" />Restart</button>
            <input type="range" className="min-w-[120px] flex-1 accent-blue-500" min={0} max={maxT || 1} step={0.05} value={Math.min(t, maxT || 1)} disabled={!maxT} onChange={(e) => seek(Number(e.target.value))} />
            <span className="w-24 text-right text-xs tabular-nums text-slate-400">{fmtClock(t)} / {fmtClock(maxT || null)}</span>
          </div>
          <p className="mt-2 text-xs text-slate-500">Playback controls drive this viewer only. The API cannot pause or cancel a running backend job.</p>
          {unplaceable && <p className="mt-1 text-xs text-amber-400">Detections use pixel coordinates but the frame size is unknown, so boxes can't be drawn.</p>}
        </Card>

        <Card title="Analyse a video">
          <div className="flex flex-wrap items-center gap-3">
            <label className={`${btnGhost} cursor-pointer`}><Upload className="h-4 w-4" />{file ? file.name : 'Choose video file'}
              <input type="file" accept="video/*" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
            <button className={btnPrimary} disabled={!file || s.submitting || offline || !zOk} onClick={async () => { if (file) { await s.submit(file); setFile(null); } }}>
              {s.submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}Start analysis
            </button>
            {file && <button className="text-sm text-slate-400 hover:underline" onClick={() => setFile(null)}>Cancel</button>}
          </div>
          <p className="mt-2 text-xs text-slate-500">Uses the zone, cooldown ({s.settings.cooldown_s}s) and analysis rate ({s.settings.process_fps} fps) from Settings. Previewing the zone on your file before upload.</p>
          {offline && <p className="mt-1 text-xs text-red-400">Backend unreachable. Start it to analyse videos.</p>}
          {!zOk && <p className="mt-1 text-xs text-red-400">The restricted zone in Settings is invalid.</p>}
          {s.submitError && <div className="mt-2"><Notice kind="error" title="Upload failed">{s.submitError}</Notice></div>}
          {s.records.length > 0 && (
            <div className="mt-3 flex items-center gap-2 text-sm text-slate-300">Job
              <select className={`${input} max-w-xs`} value={s.activeId ?? ''} onChange={(e) => { setFile(null); s.setActiveId(e.target.value); }}>
                {s.records.map((r) => <option key={r.id} value={r.id}>{r.filename} · {new Date(r.createdAt).toLocaleTimeString()}</option>)}
              </select>
            </div>
          )}
        </Card>
      </div>

      <div className="space-y-4">
        <Card title="Processing status">
          {!viewRec ? <Notice kind="empty" title="No job selected" /> : viewRec.gone ? (
            <Notice kind="error" title="Job no longer on backend">The backend forgot this job (jobs are in memory and lost on restart).</Notice>
          ) : !view ? <Notice kind={viewRec.fetchError ? 'error' : 'loading'} title={viewRec.fetchError ?? 'Waiting for job status…'} /> : (
            <div className="space-y-2 text-sm">
              {view.progress !== null && (
                <div><div className="mb-1 flex justify-between text-xs text-slate-400"><span>Progress</span><span>{Math.round(view.progress * 100)}%</span></div>
                  <div className="h-2 rounded bg-slate-700"><div className="h-2 rounded bg-blue-500 transition-all" style={{ width: `${view.progress * 100}%` }} /></div></div>
              )}
              <Row k="Analysis rate (configured)" v={`${viewRec.process_fps} fps`} />
              <Row k="Measured throughput" v={measured ? `${measured.toFixed(1)} frames/s` : '—'} hint="Analysed frames ÷ wall-clock time from upload until completion was observed (includes upload/poll latency)." />
              <Row k="Frames analysed" v={ready ? (loading ? '…' : frames.length || '—') : '—'} />
              <Row k="Detected in view" v={ready ? `${shown.length}${hidden ? ` (+${hidden} below threshold)` : ''}` : '—'} />
              {Object.entries(view.summary).filter(([, v]) => typeof v !== 'object').map(([k, v]) => <Row key={k} k={k.replace(/_/g, ' ')} v={String(v)} />)}
              {view.errors.map((e, i) => <Notice key={i} kind="error" title="Job error">{e}</Notice>)}
              {error && <Notice kind="error" title="Could not load frame detections">{error}</Notice>}
            </div>
          )}
        </Card>

        <Card title="Active safety alerts" right={<Badge cls={activeN ? sevStyle.critical : okStyle}>{activeN ? `${activeN} active` : 'Safe'}</Badge>}>
          {!view ? <Notice kind="empty" title="No alerts" /> : !incidents.length ? (
            <Notice kind={ready ? 'empty' : 'loading'} title={ready ? 'No violations detected' : 'Analysis in progress…'} />
          ) : (
            <ul className="max-h-80 space-y-2 overflow-y-auto">
              {incidents.map((i) => {
                const acked = s.incidents.find((x) => x.key === i.key)?.acked;
                const active = isActive(i.key, i.videoTime);
                return (
                  <li key={i.key} className={cn('rounded-lg border p-2 text-sm', active ? 'border-red-500/50 bg-red-500/10' : 'border-slate-700/60 opacity-70')}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium text-slate-100">{i.type}{i.track !== null && <span className="text-xs text-slate-400"> · #{i.track}</span>}</span>
                      <SevBadge s={i.severity} />
                    </div>
                    <div className="mt-1 flex items-center justify-between text-xs text-slate-400">
                      <button className="hover:text-blue-300" onClick={() => i.videoTime !== null && seek(i.videoTime)}>at {fmtClock(i.videoTime)}</button>
                      <span className="flex items-center gap-2">
                        {i.snapshot && <a className="text-blue-400 hover:underline" href={snapshotUrl(i.jobId, i.snapshot)} target="_blank" rel="noreferrer">Snapshot</a>}
                        <button className="text-blue-400 hover:underline" onClick={() => s.toggleAck(i.key)}>{acked ? 'Reopen' : 'Acknowledge'}</button>
                        {acked && <Badge cls={mutedStyle}>Ack</Badge>}
                      </span>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}

function Row({ k, v, hint }: { k: string; v: string | number; hint?: string }) {
  return <div className="flex justify-between gap-3 border-b border-slate-700/40 pb-1" title={hint}><span className="capitalize text-slate-400">{k}</span><span className="text-right text-slate-100">{v}</span></div>;
}
