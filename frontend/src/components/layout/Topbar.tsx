import { useState } from "react";
import { LogOut, Menu, Search, Zap } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/cn";

function initials(nameOrEmail: string): string {
  const base = nameOrEmail.split("@")[0];
  const parts = base.split(/[.\s_-]+/).filter(Boolean);
  return (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "");
}

export function Topbar({ onMenuClick }: { onMenuClick?: () => void }) {
  const { me, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const label = me?.name ?? me?.email ?? "";

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-4 border-b border-gray-200 bg-white/80 px-4 backdrop-blur sm:px-6">
      {/* Abre o menu lateral no mobile */}
      <button
        type="button"
        onClick={onMenuClick}
        aria-label="Abrir menu"
        className="-ml-1 flex h-9 w-9 items-center justify-center rounded-lg text-gray-500 transition-colors hover:bg-gray-100 hover:text-gray-900 lg:hidden"
      >
        <Menu size={20} />
      </button>

      {/* Marca (aparece quando a sidebar está escondida) */}
      <div className="flex items-center gap-2 lg:hidden">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-500">
          <Zap size={16} className="text-white" fill="white" />
        </div>
        <span className="text-sm font-bold text-gray-900">T2C Data Ingest</span>
      </div>

      <div className="relative hidden max-w-md flex-1 md:block">
        <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          placeholder="Buscar jobs, pipelines, execuções…"
          className="h-9 w-full rounded-lg border border-gray-200 bg-gray-50 pl-9 pr-3 text-sm text-gray-700 placeholder:text-gray-400 focus:border-brand-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        />
      </div>

      <div className="ml-auto flex items-center gap-3">
        <div className="relative">
          <button
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-2.5 rounded-lg py-1 pl-1 pr-2 transition-colors hover:bg-gray-50"
          >
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500 text-xs font-bold uppercase text-white">
              {initials(label) || "?"}
            </span>
            <span className="hidden text-left sm:block">
              <span className="block text-sm font-medium leading-tight text-gray-900">{label}</span>
              <span className="block text-xs leading-tight text-gray-400">
                {me?.roles.join(", ")}
              </span>
            </span>
          </button>

          {open && (
            <>
              <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
              <div className="absolute right-0 z-20 mt-2 w-56 overflow-hidden rounded-xl border border-gray-200 bg-white py-1 shadow-card-hover">
                <div className="border-b border-gray-100 px-4 py-3">
                  <p className="text-sm font-medium text-gray-900">{label}</p>
                  <p className="truncate text-xs text-gray-400">{me?.email}</p>
                </div>
                <button
                  onClick={logout}
                  className={cn(
                    "flex w-full items-center gap-2 px-4 py-2.5 text-sm text-gray-600",
                    "transition-colors hover:bg-red-50 hover:text-red-600"
                  )}
                >
                  <LogOut size={16} /> Sair
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
