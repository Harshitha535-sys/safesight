import { Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { IncidentRow } from './api';
import { Notice } from './ui';

const C = { critical: '#ef4444', warning: '#f59e0b', info: '#3b82f6' };
const tick = { fill: '#94a3b8', fontSize: 12 };
const tip = { contentStyle: { background: '#0a1322', border: '1px solid #334155', borderRadius: 8, color: '#e2e8f0' }, cursor: { fill: 'rgba(59,130,246,0.08)' } };

const dayKey = (ms: number) => { const d = new Date(ms); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };

export function TrendChart({ rows }: { rows: IncidentRow[] }) {
  const m = new Map<string, { day: string; critical: number; warning: number; info: number }>();
  for (const r of rows) {
    const k = dayKey(r.runAt);
    const e = m.get(k) ?? { day: k, critical: 0, warning: 0, info: 0 };
    e[r.severity] += 1; m.set(k, e);
  }
  const data = [...m.values()].sort((a, b) => a.day.localeCompare(b.day));
  if (!data.length) return <Notice kind="empty" title="No incidents in range" />;
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data}>
        <CartesianGrid stroke="#1e293b" vertical={false} />
        <XAxis dataKey="day" tick={tick} /><YAxis allowDecimals={false} tick={tick} />
        <Tooltip {...tip} /><Legend />
        <Bar dataKey="critical" stackId="a" fill={C.critical} /><Bar dataKey="warning" stackId="a" fill={C.warning} />
        <Bar dataKey="info" stackId="a" fill={C.info} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function SeverityChart({ rows }: { rows: IncidentRow[] }) {
  const data = (['critical', 'warning', 'info'] as const).map((s) => ({ name: s, value: rows.filter((r) => r.severity === s).length })).filter((d) => d.value > 0);
  if (!data.length) return <Notice kind="empty" title="No incidents in range" />;
  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2} stroke="none">
          {data.map((d) => <Cell key={d.name} fill={C[d.name]} />)}
        </Pie>
        <Tooltip {...tip} /><Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function CategoryChart({ rows }: { rows: IncidentRow[] }) {
  const m = new Map<string, number>();
  for (const r of rows) m.set(r.type, (m.get(r.type) ?? 0) + 1);
  const data = [...m].map(([type, count]) => ({ type, count })).sort((a, b) => b.count - a.count);
  if (!data.length) return <Notice kind="empty" title="No incidents in range" />;
  return (
    <ResponsiveContainer width="100%" height={Math.max(160, data.length * 44)}>
      <BarChart data={data} layout="vertical" margin={{ left: 20 }}>
        <CartesianGrid stroke="#1e293b" horizontal={false} />
        <XAxis type="number" allowDecimals={false} tick={tick} /><YAxis type="category" dataKey="type" tick={tick} width={110} />
        <Tooltip {...tip} /><Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
