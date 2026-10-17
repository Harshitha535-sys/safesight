import { useEffect, useState } from 'react';
import { BarChart3, LayoutDashboard, Settings as Cog, ShieldAlert, ShieldCheck, Video } from 'lucide-react';
import Analytics from './pages/Analytics';
import Incidents from './pages/Incidents';
import Live from './pages/Live';
import Overview from './pages/Overview';
import Settings from './pages/Settings';
import { StoreProvider, useStore } from './store';
import { cn } from './ui';

const NAV = [
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, page: Overview },
  { id: 'live', label: 'Live Monitoring', icon: Video, page: Live },
  { id: 'incidents', label: 'Incidents', icon: ShieldAlert, page: Incidents },
  { id: 'analytics', label: 'Analytics', icon: BarChart3, page: Analytics },
  { id: 'settings', label: 'Settings', icon: Cog, page: Settings },
] as const;

function Shell() {
  const [route, setRoute] = useState(() => location.hash.replace('#/', '') || 'overview');
  useEffect(() => { const f = () => setRoute(location.hash.replace('#/', '') || 'overview'); window.addEventListener('hashchange', f); return () => window.removeEventListener('hashchange', f); }, []);
  const { health, model, incidents } = useStore();
  const cur = NAV.find((n) => n.id === route) ?? NAV[0];
  const Page = cur.page;
  const open = incidents.filter((i) => !i.acked).length;
  const dot = health === 'online' ? 'bg-emerald-400' : health === 'offline' ? 'bg-red-500' : 'bg-amber-400 animate-pulse';

  return (
    <div className="min-h-screen bg-[#0a1322] text-slate-200 lg:flex">
      <aside className="border-b border-slate-700/60 bg-[#0c1829] lg:sticky lg:top-0 lg:h-screen lg:w-60 lg:shrink-0 lg:border-b-0 lg:border-r">
        <div className="flex items-center gap-2 px-4 py-3 lg:py-5">
          <ShieldCheck className="h-7 w-7 text-blue-500" /><div><div className="font-bold leading-tight text-white">SafeSight AI</div><div className="text-[10px] uppercase tracking-widest text-slate-500">Industrial safety</div></div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-2 pb-2 lg:flex-col lg:pb-0">
          {NAV.map((n) => (
            <a key={n.id} href={`#/${n.id}`} className={cn('flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition', n.id === cur.id ? 'bg-blue-600/20 text-blue-300' : 'text-slate-400 hover:bg-slate-700/30 hover:text-slate-200')}>
              <n.icon className="h-4 w-4" />{n.label}
              {n.id === 'incidents' && open > 0 && <span className="ml-auto rounded-full bg-red-500 px-1.5 text-[10px] text-white">{open}</span>}
            </a>
          ))}
        </nav>
      </aside>
      <main className="min-w-0 flex-1">
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-700/60 px-4 py-3 sm:px-6">
          <h1 className="text-lg font-semibold text-white">{cur.label}</h1>
          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span className="flex items-center gap-1.5"><span className={cn('h-2 w-2 rounded-full', dot)} />{health === 'online' ? 'Backend connected' : health === 'offline' ? 'Backend unreachable' : 'Connecting…'}</span>
            <span className="hidden sm:inline">Model: {model.state === 'ok' ? (model.ready === null ? 'unknown' : model.ready ? 'ready' : 'missing') : model.state === 'error' ? 'unreachable' : '…'}</span>
          </div>
        </header>
        <div className="p-4 sm:p-6">
          {health === 'offline' && <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">Backend unreachable. Start it with <code>uvicorn app.main:app --port 8000</code>. Previously saved results below come from this browser's cache.</div>}
          <Page />
        </div>
      </main>
    </div>
  );
}

export default function App() { return <StoreProvider><Shell /></StoreProvider>; }
