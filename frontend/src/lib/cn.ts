// Tiny className joiner (avoids adding clsx as a dependency).
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}
