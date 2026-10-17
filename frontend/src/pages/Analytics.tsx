import { useMemo, useState } from 'react';
import { CategoryChart, SeverityChart, TrendChart } from '../charts';
import { useStore } from '../store';
import { Card, Notice, input } from '../ui';

export default function Analytics() {
  const { incidents } = useStore();
  const [from, setFrom] = useState(''); const [to, setTo] = useState('');
  const rows = useMemo(() => incidents.filter((i) => {
    const d = new Date(i.runAt); const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return (!from || k >= from) && (!to || k <= to);
  }), [incidents, from, to]);

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-300">
          <span>Analysis date</span>
          <input type="date" className={input} value={from} onChange={(e) => setFrom(e.target.value)} />
          <span>to</span>
          <input type="date" className={input} value={to} onChange={(e) => setTo(e.target.value)} />
          {(from || to) && <button className="text-blue-400 hover:underline" onClick={() => { setFrom(''); setTo(''); }}>Clear</button>}
          <span className="ml-auto text-xs text-slate-500">{rows.length} incident(s) in range</span>
        </div>
      </Card>
      {!incidents.length ? <Notice kind="empty" title="No data to analyse yet">Analyse a video on Live Monitoring first.</Notice> : (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Incident trend" className="lg:col-span-2"><TrendChart rows={rows} /></Card>
          <Card title="Severity distribution"><SeverityChart rows={rows} /></Card>
          <Card title="Event categories"><CategoryChart rows={rows} /></Card>
        </div>
      )}
      <p className="text-xs text-slate-500">Dates are when each video was analysed (event timestamps are video time). Severity is derived from event type; the backend does not assign one.</p>
    </div>
  );
}
