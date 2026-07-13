import { useMemo, useState } from "react";
import {
  ChevronDown, ChevronRight, Cloud, Database, Loader2, Pin, PinOff, Search, Table2,
} from "lucide-react";

import { SecondaryButton } from "@/components/ui";
import { cn } from "@/lib/cn";
import type { DlTreeCatalog } from "@/features/data-lake/types";

interface Props {
  expanded: boolean;
  catalog: DlTreeCatalog | null;
  loading?: boolean;
  filter: string;
  onFilterChange: (v: string) => void;
  selectedTableId: number | null;
  onSelectTable: (id: number) => void;
  scanned: boolean;
  canScan: boolean;
  onScan: () => void;
  pinned: boolean;
  onTogglePin: () => void;
}

export function DataLakeExplorer(props: Props) {
  const { expanded, catalog, selectedTableId } = props;

  // Localiza a tabela/camada ativa (para o indicador no modo recolhido).
  const active = useMemo(() => {
    for (const s of catalog?.schemas ?? []) {
      const t = s.tables.find((x) => x.id === selectedTableId);
      if (t) return { schema: s, table: t };
    }
    return null;
  }, [catalog, selectedTableId]);

  return (
    <div className="overflow-hidden rounded-2xl border border-gray-100 bg-white">
      {expanded ? <Expanded {...props} /> : <Collapsed active={active} />}
    </div>
  );
}

/** Rail compacto: nuvem (conexão), inicial da camada ativa e ícone da tabela ativa (tooltip). */
function Collapsed({
  active,
}: {
  active: { schema: { name: string }; table: { name: string } } | null;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-4">
      <span title="Data Lake (passe o mouse para expandir)" className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-50 text-sky-600">
        <Cloud size={18} />
      </span>
      {active && (
        <>
          <span
            title={`Camada: ${active.schema.name}`}
            className="flex h-7 w-7 items-center justify-center rounded-lg bg-gray-100 text-xs font-bold uppercase text-gray-500"
          >
            {active.schema.name[0] ?? "?"}
          </span>
          <span className="relative flex h-9 w-9 items-center justify-center" title={`${active.schema.name}.${active.table.name}`}>
            <span className="absolute left-0 top-1.5 h-6 w-1 rounded-r-full bg-brand-500" />
            <Table2 size={18} className="text-brand-500" />
          </span>
        </>
      )}
      <span className="mt-1 text-[10px] font-medium uppercase tracking-wide text-gray-300">Explorer</span>
    </div>
  );
}

function Expanded({
  catalog, loading, filter, onFilterChange, selectedTableId, onSelectTable, scanned, canScan,
  onScan, pinned, onTogglePin,
}: Props) {
  const [collapsedSchemas, setCollapsedSchemas] = useState<Record<number, boolean>>({});
  const f = filter.trim().toLowerCase();

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 px-3 py-2.5">
        <Cloud size={14} className="text-gray-400" />
        <span className="text-xs font-semibold uppercase tracking-wide text-gray-400">Explorer</span>
        <button
          onClick={onTogglePin}
          title={pinned ? "Desafixar (recolher após selecionar)" : "Fixar Explorer aberto"}
          className={cn(
            "ml-auto rounded-md p-1 transition-colors hover:bg-gray-100",
            pinned ? "text-brand-500" : "text-gray-400"
          )}
        >
          {pinned ? <Pin size={14} /> : <PinOff size={14} />}
        </button>
      </div>

      {/* Busca (só no modo expandido) */}
      <div className="px-3 pb-2">
        <div className="relative">
          <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            value={filter}
            onChange={(e) => onFilterChange(e.target.value)}
            placeholder="Buscar tabela…"
            className="h-9 w-full rounded-lg border border-gray-200 bg-white pl-8 pr-3 text-sm text-gray-700 placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 px-3 py-6 text-sm text-gray-400">
          <Loader2 size={15} className="animate-spin" /> Carregando catálogo…
        </div>
      ) : !catalog || catalog.schemas.length === 0 ? (
        <div className="px-3 py-6 text-center">
          <p className="text-sm text-gray-500">{scanned ? "Catálogo vazio." : "O catálogo ainda não foi atualizado."}</p>
          <p className="mt-1 text-xs text-gray-400">Execute uma varredura para identificar schemas, tabelas, arquivos e colunas.</p>
          {canScan && <SecondaryButton className="mt-3" onClick={onScan}>Atualizar catálogo</SecondaryButton>}
        </div>
      ) : (
        <div className="max-h-[70vh] overflow-auto px-2 pb-3 text-sm">
          <div className="flex items-center gap-1.5 px-2 py-1 font-medium text-gray-700">
            <Cloud size={14} className="text-brand-500" /> {catalog.connection_name ?? catalog.name}
          </div>
          {catalog.schemas.map((s) => {
            const isCollapsed = collapsedSchemas[s.id];
            const tables = s.tables.filter((t) => !f || t.name.toLowerCase().includes(f));
            if (f && tables.length === 0) return null;
            return (
              <div key={s.id} className="ml-1">
                <button
                  onClick={() => setCollapsedSchemas((p) => ({ ...p, [s.id]: !p[s.id] }))}
                  className="flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-gray-700 hover:bg-gray-50"
                >
                  {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                  <Database size={14} className="text-sky-500" />
                  <span className="font-medium">{s.name}</span>
                  <span className="ml-auto rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
                    {tables.length}
                  </span>
                </button>
                {!isCollapsed && (
                  <div className="ml-4 border-l border-gray-100">
                    {tables.map((t) => (
                      <button
                        key={t.id}
                        onClick={() => onSelectTable(t.id)}
                        title={`${s.name}.${t.name}`}
                        className={cn(
                          "relative flex w-full items-center gap-1.5 rounded-md py-1 pl-3 pr-2 text-left",
                          selectedTableId === t.id
                            ? "bg-brand-50 font-medium text-brand-700"
                            : "text-gray-600 hover:bg-gray-50"
                        )}
                      >
                        {selectedTableId === t.id && (
                          <span className="absolute inset-y-1 left-0 w-1 rounded-r-full bg-brand-500" />
                        )}
                        <Table2 size={14} className={selectedTableId === t.id ? "text-brand-500" : "text-gray-400"} />
                        <span className="truncate">{t.name}</span>
                      </button>
                    ))}
                    {tables.length === 0 && <p className="py-1 pl-3 text-xs text-gray-400">Sem tabelas.</p>}
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
