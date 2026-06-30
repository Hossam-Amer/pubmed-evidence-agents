"use client";

import { useEffect, useState } from "react";
import { Plus, Puzzle, RefreshCw, X } from "lucide-react";
import type { Pico } from "@/lib/types";
import { Card } from "./ui";

export function PicoEditor({
  pico,
  onRerun,
  running,
}: {
  pico: Pico;
  onRerun: (edited: Pico) => void;
  running: boolean;
}) {
  const [P, setP] = useState(pico.P);
  const [I, setI] = useState(pico.I);
  const [C, setC] = useState(pico.C ?? "");
  const [O, setO] = useState(pico.O);
  const [queries, setQueries] = useState<string[]>(pico.queries);

  useEffect(() => {
    setP(pico.P);
    setI(pico.I);
    setC(pico.C ?? "");
    setO(pico.O);
    setQueries(pico.queries);
  }, [pico]);

  const dirty =
    P !== pico.P ||
    I !== pico.I ||
    (C || "") !== (pico.C ?? "") ||
    O !== pico.O ||
    JSON.stringify(queries) !== JSON.stringify(pico.queries);

  const inputCls =
    "focus-ring mt-1 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm text-slate-800";

  const field = (label: string, value: string, set: (v: string) => void, multiline = false) => (
    <label className="block">
      <span className="text-[11px] font-semibold uppercase tracking-wide text-violet-600">
        {label}
      </span>
      {multiline ? (
        <textarea value={value} onChange={(e) => set(e.target.value)} rows={2} className={`${inputCls} resize-y`} />
      ) : (
        <input value={value} onChange={(e) => set(e.target.value)} className={inputCls} />
      )}
    </label>
  );

  return (
    <Card icon={Puzzle} title="PICO · edit & re-run">
      <p className="mb-3 text-xs leading-relaxed text-slate-500">
        Correct the extracted PICO or hand-tune the PubMed queries, then re-run —
        this skips extraction and retrieves against your edits.
      </p>
      <div className="space-y-2.5">
        {field("Population", P, setP, true)}
        {field("Intervention", I, setI)}
        {field("Comparison", C, setC)}
        {field("Outcome", O, setO)}
      </div>

      <div className="mt-3">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-violet-600">
          PubMed queries
        </span>
        <div className="mt-1.5 space-y-1.5">
          {queries.map((q, i) => (
            <div key={i} className="flex gap-1.5">
              <input
                value={q}
                onChange={(e) => setQueries((qs) => qs.map((v, j) => (j === i ? e.target.value : v)))}
                className="focus-ring flex-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 font-mono text-xs text-slate-700"
              />
              <button
                onClick={() => setQueries((qs) => qs.filter((_, j) => j !== i))}
                className="rounded-lg border border-slate-200 px-2 text-slate-400 transition hover:border-rose-200 hover:text-rose-600"
                title="Remove query"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
          <button
            onClick={() => setQueries((qs) => [...qs, ""])}
            className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:underline"
          >
            <Plus className="h-3.5 w-3.5" /> add query
          </button>
        </div>
      </div>

      <button
        disabled={running || !dirty || queries.filter((q) => q.trim()).length === 0}
        onClick={() =>
          onRerun({
            P,
            I,
            C: C.trim() || null,
            O,
            queries: queries.map((q) => q.trim()).filter(Boolean),
          })
        }
        className="btn-primary mt-4 w-full"
      >
        <RefreshCw className={`h-4 w-4 ${running ? "animate-spin" : ""}`} />
        {running ? "Running…" : dirty ? "Re-run with edits" : "No edits yet"}
      </button>
    </Card>
  );
}
