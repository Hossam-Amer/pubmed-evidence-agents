import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import type { Confidence, Agreement } from "@/lib/types";

export function Card({
  title,
  icon: Icon,
  action,
  children,
  className = "",
  bodyClassName = "p-4",
}: {
  title?: ReactNode;
  icon?: LucideIcon;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <header className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
            {Icon && <Icon className="h-4 w-4 text-indigo-500" />}
            {title}
          </div>
          {action}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

export function Metric({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: ReactNode;
}) {
  return (
    <div className="card flex items-center gap-3 px-4 py-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-50 text-indigo-600">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">
          {label}
        </div>
        <div className="truncate text-lg font-semibold leading-tight text-slate-800">
          {value}
        </div>
      </div>
    </div>
  );
}

const CONF: Record<Confidence, { dot: string; text: string; bg: string; ring: string }> = {
  high: { dot: "bg-emerald-500", text: "text-emerald-700", bg: "bg-emerald-50", ring: "ring-emerald-200" },
  medium: { dot: "bg-amber-500", text: "text-amber-700", bg: "bg-amber-50", ring: "ring-amber-200" },
  low: { dot: "bg-rose-500", text: "text-rose-700", bg: "bg-rose-50", ring: "ring-rose-200" },
};

export function ConfidenceBadge({ value }: { value: Confidence }) {
  const c = CONF[value] ?? CONF.low;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${c.bg} ${c.text} ${c.ring}`}
    >
      <span className={`h-2 w-2 rounded-full ${c.dot}`} />
      {value.toUpperCase()} confidence
    </span>
  );
}

const AGREE: Record<Agreement, string> = {
  strong: "bg-emerald-50 text-emerald-800 border-emerald-200",
  mixed: "bg-amber-50 text-amber-800 border-amber-200",
  conflicting: "bg-rose-50 text-rose-800 border-rose-200",
  unknown: "bg-slate-50 text-slate-600 border-slate-200",
};

export function agreementStyle(a: Agreement): string {
  return AGREE[a] ?? AGREE.unknown;
}

export function pubmedUrl(pmid: string): string {
  return `https://pubmed.ncbi.nlm.nih.gov/${pmid}/`;
}

// Stable stance colors shared by the charts + explorer.
export const STANCE_COLOR = {
  supports: "#10b981",
  conflicts: "#f43f5e",
  neutral: "#94a3b8",
} as const;
