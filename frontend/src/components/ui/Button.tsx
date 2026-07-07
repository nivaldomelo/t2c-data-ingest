import type { ButtonHTMLAttributes, ReactNode } from "react";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/cn";

interface BaseProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  children: ReactNode;
  icon?: ReactNode;
  loading?: boolean;
  size?: "sm" | "md";
}

const sizes = {
  sm: "h-8 px-3 text-xs gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
};

const base =
  "inline-flex items-center justify-center rounded-lg font-semibold transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40 disabled:cursor-not-allowed disabled:opacity-50";

export function PrimaryButton({
  children,
  icon,
  loading,
  size = "md",
  className,
  disabled,
  ...rest
}: BaseProps) {
  return (
    <button
      className={cn(
        base,
        sizes[size],
        "bg-brand-500 text-white shadow-sm hover:bg-brand-600 active:bg-brand-700",
        className
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}

export function SecondaryButton({
  children,
  icon,
  loading,
  size = "md",
  className,
  disabled,
  ...rest
}: BaseProps) {
  return (
    <button
      className={cn(
        base,
        sizes[size],
        "border border-gray-200 bg-white text-gray-700 shadow-sm hover:bg-gray-50 hover:text-gray-900",
        className
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 size={16} className="animate-spin" /> : icon}
      {children}
    </button>
  );
}
