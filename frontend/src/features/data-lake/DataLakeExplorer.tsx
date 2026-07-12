import { useState } from "react";
import { ChevronDown, ChevronRight, Cloud, Database, Loader2, Table2 } from "lucide-react";

import { SecondaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { DlTreeCatalog } from "@/features/data-lake/types";

export function DataLakeExplorer({
  catalog,
  loading,
  filter,
  selectedTableId,
  onSelectTable,
  scanned,
  canScan,
  onScan,
}: {
  catalog: DlTreeCatalog | null;
  loading?: boolean;
  filter: string;
  selectedTableId: number | null;
  onSelectTable: (id: number) => void;
  scanned: boolean;
  canScan: boolean;
  onScan: () => void;
}) {
  const [collapsed, setCollapsed] = useState<Record<number, boolean>>({});
  const f = filter.trim().toLowerCase();

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-2">
      <div className="flex items-center gap-2 px-2 py-2 text-xs font-semibold uppercase tracking-wide text-gray-400">
        <Cloud size={14} /> Explorer
      </div>

      {loading ? (
        <div className="flex items-center gap-2 px-3 py-6 text-sm text-gray-400">
          <Loader2 size={15} className="animate-spin" /> Carregando catálogo…
        </div>
      ) : !catalog || catalog.schemas.length === 0 ? (
        <div className="px-3 py-6 text-center">
          <p className="text-sm text-gray-500">
            {scanned ? "Catálogo vazio." : "O catálogo ainda não foi atualizado."}
          </p>
          <p className="mt-1 text-xs text-gray-400">
            Execute uma varredura para identificar schemas, tabelas, arquivos e colunas.
          </p>
          {canScan && (
            <SecondaryButton className="mt-3" onClick={onScan}>Atualizar catálogo</SecondaryButton>
          )}
        </div>
      ) : (
        <div className="max-h-[70vh] overflow-auto pb-2 text-sm">
          <div className="flex items-center gap-1.5 px-2 py-1 font-medium text-gray-700">
            <Cloud size={14} className="text-brand-500" /> {catalog.connection_name ?? catalog.name}
          </div>
          {catalog.schemas.map((s) => {
            const isCollapsed = collapsed[s.id];
            const tables = s.tables.filter((t) => !f || t.name.toLowerCase().includes(f));
            if (f && tables.length === 0) return null;
            return (
              <div key={s.id} className="ml-2">
                <button
                  onClick={() => setCollapsed((p) => ({ ...p, [s.id]: !p[s.id] }))}
                  className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-gray-700 hover:bg-gray-50"
                >
                  {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                  <Database size={14} className="text-sky-500" />
                  <span className="font-medium">{s.name}</span>
                  <span className="ml-auto text-xs text-gray-400">{tables.length}</span>
                </button>
                {!isCollapsed && (
                  <div className="ml-4 border-l border-gray-100">
                    {tables.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => onSelectTable(t.id)}
                        className={cn(
                          "flex w-full items-center gap-1.5 rounded-md py-1 pl-3 pr-2 text-left",
                          selectedTableId === t.id
                            ? "bg-brand-50 font-medium text-brand-700"
                            : "text-gray-600 hover:bg-gray-50",
                        )}
                      >
                        <Table2 size={14} className={selectedTableId === t.id ? "text-brand-500" : "text-gray-400"} />
                        <span className="truncate">{t.name}</span>
                      </button>
                    ))}
                    {tables.length === 0 && (
                      <p className="py-1 pl-3 text-xs text-gray-400">Sem tabelas.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
