import { Cloud, Database, Globe, Loader2 } from "lucide-react";

import { cn } from "@/lib/cn";
import { CATEGORY_LABEL } from "@/features/connections/types";
import type { ConnectionCategory, ConnectorMeta } from "@/features/connections/types";
import { useConnectors } from "@/features/connections/useConnectors";

const CATEGORY_ORDER: ConnectionCategory[] = ["database", "storage", "api"];
const CATEGORY_ICON: Record<ConnectionCategory, typeof Database> = {
  database: Database,
  storage: Cloud,
  api: Globe,
};

export function ConnectionTypePicker({ onPick }: { onPick: (type: ConnectorMeta) => void }) {
  const connectors = useConnectors();

  if (connectors.isLoading) {
    return (
      <div className="flex items-center gap-2 py-10 text-sm text-gray-400">
        <Loader2 size={16} className="animate-spin" /> Carregando tipos de conexão…
      </div>
    );
  }
  const byCat = (cat: ConnectionCategory) => (connectors.data ?? []).filter((c) => c.category === cat);

  return (
    <div className="space-y-5">
      <p className="text-sm text-gray-500">Escolha o tipo de conexão que deseja cadastrar.</p>
      {CATEGORY_ORDER.map((cat) => {
        const items = byCat(cat);
        if (!items.length) return null;
        const CatIcon = CATEGORY_ICON[cat];
        return (
          <div key={cat}>
            <div className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-gray-400">
              <CatIcon size={14} /> {CATEGORY_LABEL[cat]}
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {items.map((c) => (
                <button
                  key={c.type}
                  onClick={() => onPick(c)}
                  className={cn(
                    "flex flex-col items-start gap-0.5 rounded-xl border border-gray-200 bg-white p-3 text-left",
                    "transition-colors hover:border-brand-300 hover:bg-brand-50/40"
                  )}
                >
                  <span className="text-sm font-medium text-gray-900">{c.label}</span>
                  <span className="line-clamp-2 text-xs text-gray-400">{c.description}</span>
                </button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
