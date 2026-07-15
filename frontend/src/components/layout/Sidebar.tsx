import { useCallback, useEffect, useMemo, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import {
  Activity,
  Bell,
  Boxes,
  Cable,
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
  Target,
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
      { to: "/connections", label: "Origens", icon: Plug, perm: "ingest:connections:read" },
      { to: "/destinations", label: "Destinos", icon: Target, perm: "ingest:destinations:read" },
      { to: "/variables", label: "Variáveis", icon: Variable, perm: "ingest:variables:read" },
      { to: "/data-lake", label: "Data Lake", icon: Boxes, perm: "ingest:data-lake:read" },
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
      { to: "/observability", label: "Observabilidade", icon: Activity, perm: "ingest:read" },
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
      { to: "/integrations", label: "Integrações (t2c_data)", icon: Cable, perm: "ingest:integrations:read" },
      { to: "/access", label: "Usuários & Acessos", icon: Users, perm: "ingest:admin" },
    ],
  },
];

// Standalone items pinned below the groups.
const FOOTER_LINKS: NavItem[] = [
  { to: "/airflow", label: "Airflow legado", icon: Wind, perm: "ingest:airflow:read" },
];

function routeActive(pathname: string, item: NavItem): boolean {
  if (item.end) return pathname === item.to;
  return pathname === item.to || pathname.startsWith(item.to + "/");
}

const COLLAPSED_W = "w-[72px]";
const EXPANDED_W = "w-[260px]";

interface SidebarProps {
  mobileOpen: boolean;
  onClose: () => void;
}

export function Sidebar({ mobileOpen, onClose }: SidebarProps) {
  const { pathname } = useLocation();
  const [hovered, setHovered] = useState(false);

  // Recolhe automaticamente ao trocar de página (mesmo comportamento do t2c_data). Como é
  // hover-driven, a rota nova recolhe; expande de novo só ao re-entrar com o mouse.
  useEffect(() => {
    setHovered(false);
  }, [pathname]);

  return (
    <>
      {/* Desktop: a rail reserva 72px no fluxo; o painel EXPANDE por cima (overlay) no hover,
          então o conteúdo não "pula" ao abrir/fechar o menu. */}
      <aside className={cn("relative hidden shrink-0 lg:block", COLLAPSED_W)}>
        <div
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
          className={cn(
            "absolute inset-y-0 left-0 flex h-full flex-col overflow-hidden bg-graphite-900 transition-[width] duration-200 ease-in-out",
            // Sidebar sempre acima da topbar/busca (que é z-20). Expandida sobe mais ainda para
            // sobrepor o conteúdo com folga.
            hovered ? cn(EXPANDED_W, "z-50 shadow-2xl") : cn(COLLAPSED_W, "z-40")
          )}
        >
          <SidebarInner expanded={hovered} onNavigate={onClose} />
        </div>
      </aside>

      {/* Mobile: drawer deslizante sobre um overlay (sempre expandido). */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col overflow-hidden bg-graphite-900 shadow-2xl">
            <SidebarInner expanded onNavigate={onClose} />
          </aside>
        </div>
      )}
    </>
  );
}

function SidebarInner({ expanded, onNavigate }: { expanded: boolean; onNavigate: () => void }) {
  const { can } = useAuth();
  const { pathname } = useLocation();
  const [open, setOpen] = useState<Record<string, boolean>>({});

  const visible = (perm?: string) => !perm || can(perm);
  const groups = useMemo(
    () =>
      GROUPS.map((g) => ({ ...g, items: g.items.filter((it) => visible(it.perm)) })).filter(
        (g) => g.items.length > 0
      ),
    [can]
  );

  const isOpen = useCallback((key: string) => open[key] ?? true, [open]);

  // Abre automaticamente o grupo que contém a rota ativa (aparece aberto ao expandir).
  useEffect(() => {
    const active = GROUPS.find((g) => g.items.some((it) => routeActive(pathname, it)));
    if (active) {
      setOpen((prev) => (prev[active.key] === false ? { ...prev, [active.key]: true } : prev));
    }
  }, [pathname]);

  const toggle = (key: string) => setOpen((prev) => ({ ...prev, [key]: !(prev[key] ?? true) }));

  // Texto que só aparece expandido: sempre no DOM (acessível + animação só de largura),
  // recortado pelo overflow-hidden do painel quando recolhido.
  const labelCls = cn(
    "whitespace-nowrap transition-opacity duration-150",
    expanded ? "opacity-100" : "opacity-0"
  );

  const itemClass = ({ isActive }: { isActive: boolean }) =>
    cn(
      "group relative flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all",
      isActive ? "bg-white/5 text-white" : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
    );

  const renderItem = (item: NavItem, opts?: { indent?: boolean }) => {
    const Icon = item.icon;
    return (
      <NavLink
        key={item.to}
        to={item.to}
        end={item.end}
        onClick={onNavigate}
        title={!expanded ? item.label : undefined}
        className={itemClass}
      >
        {({ isActive }) => (
          <>
            {isActive && <span className="absolute inset-y-1.5 left-0 w-1 rounded-r-full bg-brand-500" />}
            <Icon
              size={18}
              className={cn(
                "shrink-0",
                opts?.indent && expanded && "ml-1",
                isActive ? "text-brand-400" : "text-slate-500 group-hover:text-slate-300"
              )}
            />
            <span className={labelCls}>{item.label}</span>
          </>
        )}
      </NavLink>
    );
  };

  const footerLinks = FOOTER_LINKS.filter((it) => visible(it.perm));

  return (
    <>
      {/* Header fixo */}
      <div className="flex shrink-0 items-center gap-3 px-[18px] py-5">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-500 shadow-glow">
          <Zap size={18} className="text-white" fill="white" />
        </div>
        <div className={cn("leading-tight", labelCls)}>
          <div className="text-sm font-bold text-white">T2C Data Ingest</div>
          <div className="whitespace-nowrap text-[11px] text-slate-400">Ingestão &amp; Orquestração</div>
        </div>
      </div>

      {/* Área central com rolagem própria */}
      <nav className="flex-1 space-y-1 overflow-y-auto overflow-x-hidden px-3 pb-3">
        {renderItem(HOME)}

        {groups.map((group) => {
          const GroupIcon = group.icon;
          const groupOpen = isOpen(group.key);
          const groupActive = group.items.some((it) => routeActive(pathname, it));
          // Recolhido: itens sempre visíveis (o item ativo precisa aparecer). Expandido: respeita
          // o estado do grupo (com o grupo da rota ativa aberto automaticamente).
          const showItems = !expanded || groupOpen;
          return (
            <div key={group.key} className="pt-2">
              <button
                type="button"
                onClick={() => expanded && toggle(group.key)}
                title={!expanded ? group.label : undefined}
                className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-slate-500 transition-colors hover:text-slate-300"
              >
                <GroupIcon size={14} className={cn("shrink-0", groupActive ? "text-brand-400" : "text-slate-500")} />
                <span className={cn(labelCls, groupActive ? "text-slate-200" : "text-slate-400")}>{group.label}</span>
                <ChevronRight
                  size={14}
                  className={cn("ml-auto text-slate-500 transition-transform", labelCls, groupOpen && "rotate-90")}
                />
              </button>
              {showItems && (
                <div className={cn("mt-1 space-y-1", expanded && "border-l border-white/5 pl-2")}>
                  {group.items.map((it) => renderItem(it, { indent: true }))}
                </div>
              )}
            </div>
          );
        })}

        {footerLinks.length > 0 && <div className="pt-2">{footerLinks.map((it) => renderItem(it))}</div>}
      </nav>

      {/* Rodapé fixo */}
      <div className="shrink-0 p-3">
        {expanded ? (
          <div className="rounded-xl border border-white/5 bg-white/5 p-3">
            <p className="whitespace-nowrap text-xs font-medium text-slate-300">Cluster Spark local</p>
            <p className="mt-1 flex items-center gap-1.5 whitespace-nowrap text-[11px] text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> master + workers ativos
            </p>
          </div>
        ) : (
          <div className="flex justify-center py-2" title="Cluster Spark local ativo">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
          </div>
        )}
      </div>
    </>
  );
}
