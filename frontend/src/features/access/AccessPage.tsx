import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Search, Shield, ShieldCheck, UserPlus, Users, X } from "lucide-react";

import { api } from "@/lib/api";
import { Card, EmptyState, PageHeader } from "@/components/ui";
import { cn } from "@/lib/cn";

interface AccessUser {
  email: string;
  name: string | null;
  roles: string[];
  is_active: boolean;
  is_admin: boolean;
  has_access: boolean;
}
interface Summary { admins: number; granted: number; total_users: number }

export default function AccessPage() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [onlyWithout, setOnlyWithout] = useState(false);

  const query = useMemo(() => {
    const p = new URLSearchParams();
    if (q.trim()) p.set("q", q.trim());
    if (onlyWithout) p.set("only_without_access", "true");
    return p.toString();
  }, [q, onlyWithout]);

  const { data: summary } = useQuery({ queryKey: ["access-summary"], queryFn: () => api.get<Summary>("/api/v1/access/summary") });
  const { data: users, isLoading } = useQuery({
    queryKey: ["access-users", query],
    queryFn: () => api.get<AccessUser[]>(`/api/v1/access/users?${query}`),
    placeholderData: (p) => p,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["access-users"] });
    qc.invalidateQueries({ queryKey: ["access-summary"] });
  };
  const grant = useMutation({
    mutationFn: (email: string) => api.post("/api/v1/access", { email }),
    onSuccess: invalidate,
  });
  const revoke = useMutation({
    mutationFn: (email: string) => api.del(`/api/v1/access/${encodeURIComponent(email)}`),
    onSuccess: invalidate,
  });
  const busy = grant.isPending || revoke.isPending;

  const rows = users ?? [];

  return (
    <div>
      <PageHeader
        icon={<Users size={22} />}
        title="Usuários & Acessos"
        description="Libere o acesso (somente leitura) à ferramenta para usuários do t2c_data. Administradores têm acesso total automaticamente."
      />

      <div className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-3">
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Administradores</p><p className="mt-1.5 text-2xl font-bold text-gray-900">{summary?.admins ?? "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Acessos liberados</p><p className="mt-1.5 text-2xl font-bold text-brand-600">{summary?.granted ?? "—"}</p></Card>
        <Card className="p-4"><p className="text-xs uppercase tracking-wide text-gray-400">Usuários no t2c_data</p><p className="mt-1.5 text-2xl font-bold text-gray-900">{summary?.total_users ?? "—"}</p></Card>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1 max-w-md">
          <Search size={15} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por e-mail ou nome…" className="h-9 w-full rounded-lg border border-gray-200 bg-white pl-8 pr-3 text-sm outline-none focus:border-brand-500" />
        </div>
        <button
          onClick={() => setOnlyWithout((v) => !v)}
          className={cn("rounded-full border px-3 py-1.5 text-xs font-medium", onlyWithout ? "border-brand-500 bg-brand-50 text-brand-700" : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50")}
        >
          Somente sem acesso
        </button>
      </div>

      <Card className="overflow-hidden p-0">
        {isLoading ? (
          <div className="p-6 text-sm text-gray-400">Carregando…</div>
        ) : rows.length === 0 ? (
          <EmptyState icon={<Users size={22} />} title="Nenhum usuário" description={q ? "Nenhum usuário com esse filtro." : "Digite para buscar usuários do t2c_data."} />
        ) : (
          <table className="min-w-full text-sm">
            <thead><tr className="border-b border-gray-100 bg-gray-50/70 text-xs uppercase text-gray-500">
              <th className="px-5 py-2.5 text-left">Usuário</th><th className="px-5 py-2.5 text-left">Papéis</th>
              <th className="px-5 py-2.5 text-left">Acesso</th><th className="px-5 py-2.5 text-right">Ação</th>
            </tr></thead>
            <tbody>
              {rows.map((u) => (
                <tr key={u.email} className="border-b border-gray-50 last:border-0">
                  <td className="px-5 py-2.5">
                    <div className="font-medium text-gray-800">{u.name ?? u.email}</div>
                    <div className="text-[11px] text-gray-400">{u.email}</div>
                  </td>
                  <td className="px-5 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {u.roles.length ? u.roles.map((r) => (
                        <span key={r} className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[11px] text-gray-600">{r}</span>
                      )) : <span className="text-xs text-gray-400">—</span>}
                    </div>
                  </td>
                  <td className="px-5 py-2.5">
                    {u.is_admin ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-brand-200 bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700"><Shield size={12} /> Admin (total)</span>
                    ) : u.has_access ? (
                      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700"><ShieldCheck size={12} /> Leitura</span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full border border-gray-200 bg-gray-50 px-2.5 py-0.5 text-xs font-medium text-gray-500">Sem acesso</span>
                    )}
                  </td>
                  <td className="px-5 py-2.5 text-right">
                    {u.is_admin ? (
                      <span className="text-xs text-gray-300">—</span>
                    ) : u.has_access ? (
                      <button disabled={busy} onClick={() => revoke.mutate(u.email)} className="inline-flex items-center gap-1 rounded-lg border border-gray-200 px-2.5 py-1 text-xs font-medium text-gray-600 hover:bg-red-50 hover:text-red-600 disabled:opacity-50"><X size={13} /> Revogar</button>
                    ) : (
                      <button disabled={busy} onClick={() => grant.mutate(u.email)} className="inline-flex items-center gap-1 rounded-lg bg-brand-500 px-2.5 py-1 text-xs font-medium text-white hover:bg-brand-600 disabled:opacity-50"><UserPlus size={13} /> Liberar leitura</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <p className="mt-4 flex items-center gap-1.5 text-xs text-gray-400">
        <Check size={13} className="text-emerald-500" /> Acesso liberado é somente leitura. Apenas administradores podem criar, executar ou editar.
      </p>
    </div>
  );
}
