import { useCallback, useEffect, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bell,
  Boxes,
  CalendarClock,
  ChevronRight,
  Cpu,
  Database,
  DownloadCloud,
  History,
  LayoutDashboard,
  Package,
  PlayCircle,
  Plug,
  Rocket,
  Scale,
  Server,
  ServerCog,
  ShieldAlert,
  ShieldCheck,
  Tags as TagsIcon,
  Users,
  Variable,
  Wind,
  Workflow,
  Zap,
} from "lucide-react";

import { cn } from "@/lib/cn";
import { useAuth } from "@/lib/auth";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  /** Read permission required to see this item. Undefined -> always visible. */
  perm?: string;
  /** Match the route exactly (used for "/"). */
  end?: boolean;
}

interface NavGroup {
  key: string;
  label: string;
  icon: LucideIcon;
  items: NavItem[];
}

// Standalone item pinned above the groups.
const HOME: NavItem = { to: "/", label: "Visão geral", icon: LayoutDashboard, end: true };

// Only routes that actually exist today are listed. The structure is grouped by subject so new
// areas (Metadados, Linhagem, Observabilidade, etc.) can slot into the right group later.
const GROUPS: NavGroup[] = [
  {
    key: "operacao",
    label: "Operação",
    icon: Rocket,
    items: [
      { to: "/jobs", label: "Jobs", icon: Boxes },
      { to: "/pipelines", label: "Pipelines", icon: Workflow, perm: "ingest:pipelines:read" },
      { to: "/executions", label: "Execuções", icon: PlayCircle },
      { to: "/schedules", label: "Schedules", icon: CalendarClock, perm: "ingest:schedules:read" },
      { to: "/backfills", label: "Reprocessamentos", icon: History },
    ],
  },
  {
    key: "ingestao",
    label: "Ingestão",
    icon: DownloadCloud,
    items: [
      { to: "/ingestion-control", label: "Controle de Ingestão", icon: Database, perm: "ingest:control:read" },
      { to: "/connections", label: "Conexões", icon: Plug, perm: "ingest:connections:read" },
      { to: "/variables", label: "Variáveis", icon: Variable, perm: "ingest:variables:read" },
      { to: "/tags", label: "Tags", icon: TagsIcon, perm: "ingest:tags:read" },
    ],
  },
  {
    key: "infra",
    label: "Infraestrutura",
    icon: Cpu,
    items: [
      { to: "/clusters", label: "Clusters", icon: Server, perm: "ingest:clusters:read" },
      { to: "/runtime", label: "Ambiente de Execução", icon: ServerCog, perm: "ingest:runtime:read" },
      { to: "/libraries", label: "Bibliotecas", icon: Package, perm: "ingest:libraries:read" },
    ],
  },
  {
    key: "monitoramento",
    label: "Monitoramento",
    icon: Activity,
    items: [
      { to: "/alerts", label: "Alertas", icon: Bell, perm: "ingest:alerts:read" },
    ],
  },
  {
    key: "governanca",
    label: "Governança",
    icon: Scale,
    items: [
      { to: "/data-quality", label: "Data Quality", icon: ShieldAlert, perm: "ingest:quality:read" },
      { to: "/audit", label: "Auditoria", icon: ShieldCheck, perm: "ingest:admin" },
    ],
  },
  {
    key: "administracao",
    label: "Administração",
    icon: Users,
    items: [
      { to: "/access", label: "Usuários & Acessos", icon: Users, perm: "ingest:admin" },
    ],
  },
];

// Standalone items pinned below the groups.
const FOOTER_LINKS: NavItem[] = [
  { to: "/airflow", label: "Airflow legado", icon: Wind, perm: "ingest:airflow:read" },
];

const STORAGE_KEY = "t2c-ingest:sidebar-groups";

function loadOpenState(): Record<string, boolean> {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function routeActive(pathname: string, item: NavItem): boolean {
  if (item.end) return pathname === item.to;
  return pathname === item.to || pathname.startsWith(item.to + "/");
}

interface SidebarProps {
  mobileOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  return (
    <>
      {/* Desktop: coluna fixa de altura total com rolagem interna. */}
      <aside className="hidden h-full w-64 shrink-0 flex-col bg-graphite-900 lg:flex">
        <SidebarInner onNavigate={onClose} />
      </aside>

      {/* Mobile: drawer deslizante sobre um overlay. */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-graphite-900 shadow-2xl">
            <SidebarInner onNavigate={onClose} />
          </aside>
        </div>
      )}
    </>
  );
}

function SidebarInner({ onNavigate }: { onNavigate: () => void }) {
  const { can } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState<Record<string, boolean>>(loadOpenState);

  const visible = (perm?: string) => !perm || can(perm);
  const groups = GROUPS.map((g) => ({ ...g, items: g.items.filter((it) => visible(it.perm)) })).filter(
    (g) => g.items.length > 0
  );

  const isOpen = useCallback((key: string) => open[key] ?? true, [open]);

  // Abre automaticamente o grupo que contém a rota ativa.
  useEffect(() => {
    const active = GROUPS.find((g) => g.items.some((it) => routeActive(pathname, it)));
    if (active) {
      setOpen((prev) => (prev[active.key] === false ? { ...prev, [active.key]: true } : prev));
    }
  }, [pathname]);

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(open));
  }, [open]);

  const toggle = (key: string) => setOpen((prev) => ({ ...prev, [key]: !(prev[key] ?? true) }));

  const itemClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all",
      isActive ? "bg-white/5 text-white" : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
    );

  const renderItem = (item: NavItem, opts?: { indent?: boolean }) => {
    const Icon = item.icon;
    return (
      <NavLink key={item.to} to={item.to} end={item.end} onClick={onNavigate} className={itemClass}>
        {({ isActive }) => (
          <>
            {isActive && <span className="absolute inset-y-1.5 left-0 w-1 rounded-r-full bg-brand-500" />}
            <Icon
              size={18}
              className={cn(
                opts?.indent && "ml-1",
                isActive ? "text-brand-400" : "text-slate-500 group-hover:text-slate-300"
              )}
            />
            {item.label}
          </>
        )}
      </NavLink>
    );
  };

  return (
    <>
      {/* Header fixo */}
      <div className="flex shrink-0 items-center gap-3 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500 shadow-glow">
          <Zap size={18} className="text-white" fill="white" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-bold text-white">T2C Data Ingest</div>
          <div className="text-[11px] text-slate-400">Ingestão &amp; Orquestração</div>
        </div>
      </div>

      {/* Área central com rolagem própria */}
      <nav className="flex-1 space-y-1 overflow-y-auto overflow-x-hidden px-3 pb-3">
        {renderItem(HOME)}

        {groups.map((group) => {
          const GroupIcon = group.icon;
          const expanded = isOpen(group.key);
          const groupActive = group.items.some((it) => routeActive(pathname, it));
          return (
            <div key={group.key} className="pt-2">
              <button
                type="button"
                onClick={() => toggle(group.key)}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500 transition-colors hover:text-slate-300"
              >
                <GroupIcon size={14} className={cn(groupActive ? "text-brand-400" : "text-slate-500")} />
                <span className={cn(groupActive ? "text-slate-200" : "text-slate-400")}>{group.label}</span>
                <ChevronRight
                  size={14}
                  className={cn("ml-auto text-slate-500 transition-transform", expanded && "rotate-90")}
                />
              </button>
              {expanded && (
                <div className="mt-1 space-y-1 border-l border-white/5 pl-2">
                  {group.items.map((it) => renderItem(it, { indent: true }))}
                </div>
              )}
            </div>
          );
        })}

        {FOOTER_LINKS.filter((it) => visible(it.perm)).length > 0 && (
          <div className="pt-2">{FOOTER_LINKS.filter((it) => visible(it.perm)).map((it) => renderItem(it))}</div>
        )}
      </nav>

      {/* Rodapé fixo */}
      <div className="shrink-0 p-4">
        <div className="rounded-xl border border-white/5 bg-white/5 p-3">
          <p className="text-xs font-medium text-slate-300">Cluster Spark local</p>
          <p className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> master + workers ativos
          </p>
        </div>
      </div>
    </>
  );
}
