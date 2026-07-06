import { NavLink, Outlet } from "react-router-dom";
import {
  LayoutDashboard,
  Server,
  Boxes,
  Workflow,
  PlayCircle,
  Wind,
  LogOut,
} from "lucide-react";

import { useAuth } from "@/lib/auth";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/clusters", label: "Clusters", icon: Server },
  { to: "/jobs", label: "Jobs", icon: Boxes },
  { to: "/pipelines", label: "Pipelines", icon: Workflow },
  { to: "/executions", label: "Execuções", icon: PlayCircle },
  { to: "/airflow", label: "Airflow legado", icon: Wind },
];

export default function AppLayout() {
  const { me, logout } = useAuth();

  return (
    <div className="flex min-h-screen">
      <aside className="flex w-64 flex-col border-r border-slate-200 bg-white">
        <div className="px-5 py-5">
          <div className="text-lg font-bold text-slate-900">T2C Data Ingest</div>
          <div className="text-xs text-slate-400">Ingestão · Jobs · Pipelines</div>
        </div>
        <nav className="flex-1 space-y-1 px-3">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-200 p-3">
          <div className="px-2 pb-2 text-xs text-slate-500">
            <div className="font-medium text-slate-700">{me?.name ?? me?.email}</div>
            <div>{me?.roles.join(", ")}</div>
          </div>
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100"
          >
            <LogOut size={16} /> Sair
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl px-6 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
