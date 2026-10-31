import type { ReactNode } from "react";

export function Spinner({ label }: { label: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-slate-600">
      <span
        aria-hidden="true"
        className="size-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600"
      />
      {label}
    </span>
  );
}

const tones = {
  error: "border-red-200 bg-red-50 text-red-800",
  notice: "border-amber-200 bg-amber-50 text-amber-900",
};

export function Alert({ tone, children }: { tone: keyof typeof tones; children: ReactNode }) {
  return (
    <p role={tone === "error" ? "alert" : "status"} className={`rounded-md border px-3 py-2 text-sm ${tones[tone]}`}>
      {children}
    </p>
  );
}
