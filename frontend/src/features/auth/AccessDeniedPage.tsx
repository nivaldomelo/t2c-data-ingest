import { LogOut, ShieldAlert } from "lucide-react";

import { useAuth } from "@/lib/auth";

export default function AccessDeniedPage() {
  const { me, logout } = useAuth();
  return (
    <div className="flex h-screen items-center justify-center bg-graphite-950 px-4">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-graphite-900 p-8 text-center shadow-2xl">
        <div className="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-500/15">
          <ShieldAlert size={26} className="text-brand-400" />
        </div>
        <h1 className="text-xl font-bold text-white">Sem acesso à ferramenta</h1>
        <p className="mt-2 text-sm leading-relaxed text-slate-400">
          Sua conta <span className="font-medium text-slate-200">{me?.email}</span> está autenticada,
          mas ainda não tem acesso liberado ao T2C Data Ingest.
        </p>
        <p className="mt-3 text-sm text-slate-400">
          Peça a um administrador para liberar seu acesso na tela de <span className="text-slate-200">Usuários</span>.
          O acesso concedido é somente para visualização.
        </p>
        <button
          onClick={logout}
          className="mt-6 inline-flex items-center gap-2 rounded-lg border border-white/10 px-4 py-2 text-sm font-medium text-slate-300 transition-colors hover:bg-white/5 hover:text-white"
        >
          <LogOut size={15} /> Sair
        </button>
      </div>
    </div>
  );
}
