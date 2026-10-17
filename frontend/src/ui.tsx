import type { ReactNode } from 'react';
import { AlertTriangle, Inbox, Loader2 } from 'lucide-react';
import type { Severity } from './api';

export const cn = (...a: (string | false | null | undefined)[]) => a.filter(Boolean).join(' ');
export const fmtClock = (s: number | null) =>
  s === null ? '—' : `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
export const fmtDate = (ms: number) => new Date(ms).toLocaleString();

export const sevStyle: Record<Severity, string> = {
  critical: 'bg-red-500/15 text-red-300 ring-red-500/40',
  warning: 'bg-amber-500/15 text-amber-300 ring-amber-500/40',
  info: 'bg-blue-500/15 text-blue-300 ring-blue-500/40',
};
export const okStyle = 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/40';
export const mutedStyle = 'bg-slate-500/15 text-slate-300 ring-slate-500/40';

export function Badge({ cls, children }: { cls: string; children: ReactNode }) {
  return <span className={cn('inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset', cls)}>{children}</span>;
}
export const SevBadge = ({ s }: { s: Severity }) => <Badge cls={sevStyle[s]}>{s[0].toUpperCase() + s.slice(1)}</Badge>;

export function Card({ title, right, children, className }: { title?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn('rounded-xl border border-slate-700/60 bg-[#0f1b30] p-4 shadow-lg shadow-black/20', className)}>
      {(title || right) && (
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-300">{title}</h2>{right}
        </div>
      )}
      {children}
    </section>
  );
}

const tones = { blue: 'text-blue-400 bg-blue-500/10', red: 'text-red-400 bg-red-500/10', amber: 'text-amber-400 bg-amber-500/10', green: 'text-emerald-400 bg-emerald-500/10' };
export function Stat({ label, value, sub, icon, tone = 'blue' }: { label: string; value: ReactNode; sub?: string; icon: ReactNode; tone?: keyof typeof tones }) {
  return (
    <div className="flex items-start gap-3 rounded-xl border border-slate-700/60 bg-[#0f1b30] p-4">
      <div className={cn('rounded-lg p-2.5', tones[tone])}>{icon}</div>
      <div className="min-w-0">
        <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
        <div className="text-2xl font-semibold text-white">{value}</div>
        {sub && <div className="truncate text-xs text-slate-500">{sub}</div>}
      </div>
    </div>
  );
}

export function Notice({ kind, title, children }: { kind: 'loading' | 'empty' | 'error'; title: string; children?: ReactNode }) {
  const Icon = kind === 'loading' ? Loader2 : kind === 'error' ? AlertTriangle : Inbox;
  const color = kind === 'error' ? 'text-red-300 border-red-500/40 bg-red-500/5' : 'text-slate-400 border-slate-700/60';
  return (
    <div className={cn('flex flex-col items-center justify-center gap-1 rounded-lg border border-dashed p-6 text-center', color)}>
      <Icon className={cn('h-6 w-6', kind === 'loading' && 'animate-spin')} />
      <div className="text-sm font-medium">{title}</div>
      {children && <div className="max-w-md text-xs opacity-80">{children}</div>}
    </div>
  );
}

export const btn = 'inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-40';
export const btnPrimary = `${btn} bg-blue-600 text-white hover:bg-blue-500`;
export const btnGhost = `${btn} border border-slate-600 text-slate-200 hover:bg-slate-700/40`;
export const input = 'rounded-lg border border-slate-600 bg-[#0a1322] px-2.5 py-1.5 text-sm text-slate-100 placeholder:text-slate-500 focus:border-blue-500 focus:outline-none';
