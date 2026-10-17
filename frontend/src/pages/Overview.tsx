import { AlertOctagon, BellRing, CalendarClock, Users } from 'lucide-react';
import { isDone } from '../api';
import { TrendChart } from '../charts';
import { useFrames, useStore } from '../store';
import { Card, Notice, SevBadge, Stat, fmtClock, fmtDate } from '../ui';

export default function Overview() {
  const { incidents, records, views, health, settings } = useStore();
  const latest = records.find((r) => views[r.id] && isDone(views[r.id].status)) ?? null;
  const { frames, loading } = useFrames(latest?.id ?? null, !!latest, latest?.process_fps ?? 5);
  const last = frames.length ? frames[frames.length - 1] : null;
  const people = last ? last.dets.filter((d) => d.conf === null || d.conf >= settings.confidence).length : null;
  const today = new Date().toDateString();
  const todayN = incidents.filter((i) => new Date(i.runAt).toDateString() === today).length;
  const active = incidents.filter((i) => !i.acked).length;
  const recent = [...incidents].sort((a, b) => b.runAt - a.runAt || (a.videoTime ?? 0) - (b.videoTime ?? 0)).slice(0, 6);

  if (health === 'checking' && !records.length) return <Notice kind="loading" title="Connecting to backend…" />;
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Total incidents" value={incidents.length} sub={`across ${records.length} analysed video(s)`} icon={<AlertOctagon className="h-5 w-5" />} tone="red" />
        <Stat label="Incidents today" value={todayN} sub="from videos analysed today" icon={<CalendarClock className="h-5 w-5" />} tone="amber" />
        <Stat label="Active alerts" value={active} sub="unacknowledged (this browser)" icon={<BellRing className="h-5 w-5" />} tone={active ? 'red' : 'green'} />
        <Stat label="People in last frame" value={loading ? '…' : people ?? '—'} sub={latest ? `latest job: ${latest.filename}` : 'no completed analysis yet'} icon={<Users className="h-5 w-5" />} />
      </div>
      {!records.length && (
        <Notice kind="empty" title="No videos analysed yet">
          Open <a className="text-blue-400 underline" href="#/live">Live Monitoring</a> and upload a video. No camera is required.
        </Notice>
      )}
      <div className="grid gap-4 lg:grid-cols-5">
        <Card title="Incident trend (by analysis date)" className="lg:col-span-3"><TrendChart rows={incidents} /></Card>
        <Card title="Recent incidents" className="lg:col-span-2">
          {!recent.length ? <Notice kind="empty" title="No incidents recorded" /> : (
            <ul className="divide-y divide-slate-700/50">
              {recent.map((i) => (
                <li key={i.key} className="flex items-center justify-between gap-2 py-2 text-sm">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-slate-100">{i.type}</div>
                    <div className="truncate text-xs text-slate-500">{i.source} · video {fmtClock(i.videoTime)} · {fmtDate(i.runAt)}</div>
                  </div>
                  <SevBadge s={i.severity} />
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  );
}
