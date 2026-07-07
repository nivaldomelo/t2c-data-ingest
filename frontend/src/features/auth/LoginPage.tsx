import { useState } from "react";
import type { FormEvent } from "react";
import { AlertCircle, Zap } from "lucide-react";

import { useAuth } from "@/lib/auth";
import { PrimaryButton } from "@/components/ui";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [showMfa, setShowMfa] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password, mfaCode || undefined);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Falha no login";
      if (/mfa|c[oó]digo|2fa|autentica/i.test(message)) setShowMfa(true);
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  const field =
    "mt-1.5 w-full rounded-lg border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-500/20";

  return (
    <div className="flex min-h-screen">
      {/* Painel lateral de marca (grafite + laranja) */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-graphite-900 p-12 text-white lg:flex">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="absolute -bottom-32 -left-16 h-80 w-80 rounded-full bg-brand-500/10 blur-3xl" />
        <div className="relative flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500 shadow-glow">
            <Zap size={20} className="text-white" fill="white" />
          </div>
          <span className="text-lg font-bold">T2C Data Ingest</span>
        </div>
        <div className="relative">
          <h2 className="text-3xl font-bold leading-tight">
            Ingestão, jobs e pipelines <span className="text-brand-400">em um só lugar.</span>
          </h2>
          <p className="mt-4 max-w-md text-sm leading-relaxed text-slate-400">
            Plataforma operacional de dados inspirada em Databricks e Airflow — execução
            Spark/Python, orquestração de pipelines e observabilidade de execuções.
          </p>
        </div>
        <div className="relative text-xs text-slate-500">Complementar ao t2c_data · ambiente corporativo</div>
      </div>

      {/* Formulário */}
      <div className="flex w-full items-center justify-center bg-slate-50 px-4 lg:w-1/2">
        <form onSubmit={onSubmit} className="w-full max-w-sm">
          <div className="mb-8 lg:hidden">
            <div className="flex items-center gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-500">
                <Zap size={18} className="text-white" fill="white" />
              </div>
              <span className="text-lg font-bold text-gray-900">T2C Data Ingest</span>
            </div>
          </div>

          <h1 className="text-2xl font-bold tracking-tight text-gray-900">Bem-vindo de volta</h1>
          <p className="mt-1 text-sm text-gray-500">Entre com sua conta do t2c_data.</p>

          {error && (
            <div className="mt-5 flex items-start gap-2 rounded-lg border border-red-200 bg-red-50 px-3.5 py-2.5 text-sm text-red-700">
              <AlertCircle size={16} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="mt-6">
            <label className="text-sm font-medium text-gray-700">E-mail</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="voce@empresa.com"
              className={field}
            />
          </div>

          <div className="mt-4">
            <label className="text-sm font-medium text-gray-700">Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••"
              className={field}
            />
          </div>

          {showMfa && (
            <div className="mt-4">
              <label className="text-sm font-medium text-gray-700">Código MFA</label>
              <input
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                placeholder="000000"
                className={`${field} tracking-[0.4em]`}
              />
              <p className="mt-1 text-xs text-gray-400">Informe o código do seu app autenticador.</p>
            </div>
          )}

          <PrimaryButton type="submit" loading={busy} className="mt-6 w-full">
            Entrar
          </PrimaryButton>
        </form>
      </div>
    </div>
  );
}
