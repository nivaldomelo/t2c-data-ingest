import type { ReactNode } from "react";
import { Info, Lightbulb } from "lucide-react";

/**
 * Faixa de ajuda no topo de uma tela/seção/formulário: explica o que é feito ali e como usar.
 * tone: info (azul, neutro) | tip (âmbar, dica de preenchimento).
 */
export function HelpBanner({
  title,
  children,
  tone = "info",
}: {
  title?: string;
  children: ReactNode;
  tone?: "info" | "tip";
}) {
  const tip = tone === "tip";
  return (
    <div
      className={
        "flex gap-2.5 rounded-xl border px-3.5 py-2.5 text-sm " +
        (tip
          ? "border-amber-200 bg-amber-50 text-amber-900"
          : "border-sky-200 bg-sky-50 text-sky-900")
      }
    >
      {tip ? <Lightbulb size={16} className="mt-0.5 shrink-0 text-amber-500" /> : <Info size={16} className="mt-0.5 shrink-0 text-sky-500" />}
      <div className="space-y-1 leading-relaxed">
        {title && <p className="font-semibold">{title}</p>}
        <div className="[&_code]:rounded [&_code]:bg-black/5 [&_code]:px-1 [&_code]:text-[12px]">{children}</div>
      </div>
    </div>
  );
}

/** Texto de ajuda curto abaixo de um campo de formulário. */
export function FieldHint({ children }: { children: ReactNode }) {
  return <p className="mt-1 text-xs leading-relaxed text-gray-500">{children}</p>;
}
