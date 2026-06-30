"use client";

import { useEffect, useRef } from "react";
import { PIPELINE_STEPS, type LogEntry } from "@/lib/types";
import { stepIcon } from "./icons";

const LEVEL_COLOR: Record<string, string> = {
  info: "text-slate-300",
  success: "text-emerald-400",
  warn: "text-amber-400",
  error: "text-rose-400",
};

export function StreamProgress({
  logs,
  running,
}: {
  logs: LogEntry[];
  running: boolean;
}) {
  const reached = new Set(logs.map((l) => l.step));
  const current = logs.length ? logs[logs.length - 1].step : null;
  const termRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    termRef.current?.scrollTo({ top: termRef.current.scrollHeight });
  }, [logs.length]);

  return (
    <div className="space-y-3">
      {/* Stepper */}
      <div className="flex flex-wrap gap-1.5">
        {PIPELINE_STEPS.map((step) => {
          const Icon = stepIcon(step);
          const done = reached.has(step);
          const active = running && step === current;
          return (
            <span
              key={step}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-xs font-medium transition ${
                active
                  ? "border-indigo-300 bg-indigo-50 text-indigo-700 shadow-sm shadow-indigo-500/10"
                  : done
                    ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                    : "border-slate-200 bg-white text-slate-400"
              }`}
            >
              <Icon className={`h-3.5 w-3.5 ${active ? "animate-pulse" : ""}`} />
              {step}
            </span>
          );
        })}
      </div>

      {/* Raw log terminal */}
      <div
        ref={termRef}
        className="max-h-72 overflow-y-auto rounded-xl border border-slate-800 bg-[#0b0f17] p-3.5 font-mono text-xs leading-relaxed shadow-inner"
      >
        {logs.map((l, i) => (
          <div key={i} className="whitespace-pre-wrap">
            <span className="text-slate-600">[{String(l.elapsed_ms).padStart(6)}ms]</span>{" "}
            <span className="font-semibold text-indigo-400">[{l.step}]</span>{" "}
            <span className={LEVEL_COLOR[l.level] ?? "text-slate-300"}>{l.message}</span>
          </div>
        ))}
        {running && <span className="inline-block animate-pulse text-amber-400">▌</span>}
      </div>
    </div>
  );
}
