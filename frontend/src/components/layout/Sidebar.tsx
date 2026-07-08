import { NavLink } from "react-router-dom";
import {
  Boxes,
  CalendarClock,
  Database,
  LayoutDashboard,
  PlayCircle,
  Plug,
  Server,
  Variable,
  Wind,
  Workflow,
  Zap,
} from "lucide-react";

import { cn } from "@/lib/cn";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/connections", label: "Conexões", icon: Plug },
  { to: "/variables", label: "Variáveis", icon: Variable },
  { to: "/ingestion-control", label: "Controle de Ingestão", icon: Database },
  { to: "/clusters", label: "Clusters", icon: Server },
  { to: "/jobs", label: "Jobs", icon: Boxes },
  { to: "/pipelines", label: "Pipelines", icon: Workflow },
  { to: "/schedules", label: "Schedules", icon: CalendarClock },
  { to: "/executions", label: "Execuções", icon: PlayCircle },
  { to: "/airflow", label: "Airflow legado", icon: Wind },
];

export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col bg-graphite-900 lg:flex">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500 shadow-glow">
          <Zap size={18} className="text-white" fill="white" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-bold text-white">T2C Data Ingest</div>
          <div className="text-[11px] text-slate-400">Ingestão &amp; Orquestração</div>
        </div>
      </div>

      <div className="px-3 pb-2 pt-3">
        <p className="px-3 pb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Plataforma
        </p>
        <nav className="space-y-1">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all",
                  isActive
                    ? "bg-white/5 text-white"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                )
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && (
                    <span className="absolute inset-y-1.5 left-0 w-1 rounded-r-full bg-brand-500" />
                  )}
                  <Icon
                    size={18}
                    className={cn(isActive ? "text-brand-400" : "text-slate-500 group-hover:text-slate-300")}
                  />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="mt-auto p-4">
        <div className="rounded-xl border border-white/5 bg-white/5 p-3">
          <p className="text-xs font-medium text-slate-300">Cluster Spark local</p>
          <p className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> master + worker ativos
          </p>
        </div>
      </div>
    </aside>
  );
}
