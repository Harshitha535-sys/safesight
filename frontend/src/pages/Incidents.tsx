import { useMemo, useState } from 'react';
import { CheckCircle2, Download, Search } from 'lucide-react';
import { snapshotUrl } from '../api';
import { useStore } from '../store';
import { Badge, Card, Notice, SevBadge, btnGhost, fmtClock, fmtDate, input, mutedStyle, okStyle } from '../ui';

// Prefix formula-trigger characters so spreadsheets treat file-name-derived text as text (mirrors backend _csv_safe).
const esc = (v: unknown) => { const t = String(v ?? ''); return `"${(/^[=+\-@\t\r]/.test(t) ? "'" + t : t).replace(/"/g, '""')}"`; };

export default function Incidents() {
  const { incidents, toggleAck, health } = useStore();
  const [q, setQ] = useState(''); const [sev, setSev] = useState('all'); const [type, setType] = useState('all'); const [ack, setAck] = useState('all');
  const types = useMemo(() => [...new Set(incidents.map((i) => i.type))], [incidents]);
  const rows = useMemo(() => incidents.filter((i) =>
    (sev === 'all' || i.severity === sev) && (type === 'all' || i.type === type) &&
    (ack === 'all' || (ack === 'ack') === i.acked) &&
    (!q || `${i.type} ${i.source} ${i.jobId} ${i.track ?? ''}`.toLowerCase().includes(q.toLowerCase()))
  ).sort((a, b) => b.runAt - a.runAt || (a.videoTime ?? 0) - (b.videoTime ?? 0)), [incidents, q, sev, type, ack]);

  const exportCsv = () => {
    const head = ['job_id', 'source', 'analysed_at', 'video_time_s', 'event_type', 'severity', 'track_id', 'acknowledged_local'];
    const body = rows.map((r) => [r.jobId, r.source, new Date(r.runAt).toISOString(), r.videoTime ?? '', r.type, r.severity, r.track ?? '', r.acked].map(esc).join(','));
    const url = URL.createObjectURL(new Blob([[head.join(','), ...body].join('\n')], { type: 'text/csv' }));
    const a = document.createElement('a'); a.href = url; a.download = `safesight-incidents-${Date.now()}.csv`; a.click(); URL.revokeObjectURL(url);
  };

  return (
    <Card title="Incident log" right={<button className={btnGhost} disabled={!rows.length} onClick={exportCsv}><Download className="h-4 w-4" />Export CSV</button>}>
      <div className="mb-3 flex flex-wrap gap-2">
        <div className="relative min-w-[200px] flex-1">
          <Search className="absolute left-2.5 top-2 h-4 w-4 text-slate-500" />
          <input className={`${input} w-full pl-8`} placeholder="Search event, source, job, track…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select className={input} value={sev} onChange={(e) => setSev(e.target.value)}>
          <option value="all">All severities</option><option value="critical">Critical</option><option value="warning">Warning</option><option value="info">Info</option>
        </select>
        <select className={input} value={type} onChange={(e) => setType(e.target.value)}>
          <option value="all">All event types</option>{types.map((t) => <option key={t}>{t}</option>)}
        </select>
        <select className={input} value={ack} onChange={(e) => setAck(e.target.value)}>
          <option value="all">Any status</option><option value="open">Unacknowledged</option><option value="ack">Acknowledged</option>
        </select>
      </div>
      {!incidents.length ? (
        <Notice kind={health === 'offline' ? 'error' : 'empty'} title={health === 'offline' ? 'Backend unreachable' : 'No incidents yet'}>
          Incidents appear after a video has been analysed on Live Monitoring.
        </Notice>
      ) : !rows.length ? <Notice kind="empty" title="No incidents match these filters" /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-slate-400">
              <tr><th className="py-2 pr-3">Timestamp</th><th className="pr-3">Event</th><th className="pr-3">Severity</th><th className="pr-3">Source</th><th className="pr-3">Snapshot</th><th className="pr-3">Status</th><th /></tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {rows.map((r) => (
                <tr key={r.key} className="hover:bg-slate-800/30">
                  <td className="py-2 pr-3"><div className="text-slate-100">video {fmtClock(r.videoTime)}</div><div className="text-xs text-slate-500">analysed {fmtDate(r.runAt)}</div></td>
                  <td className="pr-3 text-slate-200">{r.type}{r.track !== null && <span className="text-xs text-slate-500"> · track {r.track}</span>}</td>
                  <td className="pr-3"><SevBadge s={r.severity} /></td>
                  <td className="max-w-[180px] truncate pr-3 text-slate-300" title={r.source}>{r.source}</td>
                  <td className="pr-3">{r.snapshot ? <a className="text-blue-400 hover:underline" href={snapshotUrl(r.jobId, r.snapshot)} target="_blank" rel="noreferrer">View</a> : <span className="text-slate-600">—</span>}</td>
                  <td className="pr-3"><Badge cls={r.acked ? okStyle : mutedStyle}>{r.acked ? 'Acknowledged' : 'Open'}</Badge></td>
                  <td className="text-right"><button className={btnGhost} onClick={() => toggleAck(r.key)}><CheckCircle2 className="h-4 w-4" />{r.acked ? 'Reopen' : 'Acknowledge'}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-xs text-slate-500">Event times are video time (backend limitation). Acknowledgement is stored in this browser only; the API has no acknowledgement endpoint. Showing {rows.length} of {incidents.length}.</p>
    </Card>
  );
}
