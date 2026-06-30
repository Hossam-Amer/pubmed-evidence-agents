"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Stethoscope, Terminal, Trash2 } from "lucide-react";
import { readNdjsonStream } from "@/lib/stream";
import type { LogEntry, Pico, PipelineResult } from "@/lib/types";
import { QueryForm } from "@/components/query-form";
import { StreamProgress } from "@/components/stream-progress";
import { ResultView } from "@/components/result-view";
import { Card } from "@/components/ui";

export default function Home() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [online, setOnline] = useState<boolean | null>(null);
  const [cacheSize, setCacheSize] = useState<number>(0);

  const lastText = useRef("");
  const abortRef = useRef<AbortController | null>(null);

  const checkHealth = useCallback(async () => {
    try {
      const r = await fetch("/api/health", { cache: "no-store" });
      const d = await r.json();
      setOnline(d.status === "ok");
      setCacheSize(d.cache?.size ?? 0);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  const run = useCallback(
    async (clinicalText: string, pico?: Pico) => {
      lastText.current = clinicalText;
      setLogs([]);
      setResult(null);
      setError(null);
      setRunning(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const form = new FormData();
      form.set("clinical_text", clinicalText);
      if (pico) form.set("pico_json", JSON.stringify(pico));

      try {
        const res = await fetch("/api/query", {
          method: "POST",
          body: form,
          signal: controller.signal,
        });
        await readNdjsonStream(res, (item) => {
          if (item.type === "log") setLogs((prev) => [...prev, item.data]);
          else if (item.type === "result") setResult(item.data);
          else if (item.type === "error") setError(item.data.message);
        });
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError(String(e));
      } finally {
        setRunning(false);
        abortRef.current = null;
        checkHealth();
      }
    },
    [checkHealth],
  );

  const cancel = () => abortRef.current?.abort();
  const clearCache = async () => {
    await fetch("/api/cache", { method: "DELETE" });
    checkHealth();
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <div className="brand-gradient flex h-12 w-12 items-center justify-center rounded-2xl shadow-lg shadow-indigo-500/25">
            <Stethoscope className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              pubmed-evidence-agents
            </h1>
            <p className="text-sm text-slate-500">
              Medical Evidence Retrieval Agent - PubMed RAG with grounded verification
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${
              online === null
                ? "border-slate-200 bg-white text-slate-400"
                : online
                  ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                  : "border-rose-200 bg-rose-50 text-rose-700"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                online === null ? "bg-slate-300" : online ? "bg-emerald-500" : "bg-rose-500"
              }`}
            />
            {online === null
              ? "checking..."
              : online
                ? `online - ${cacheSize} cached`
                : "backend offline"}
          </span>
          <button onClick={clearCache} className="btn-ghost" title="Flush query cache">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </header>

      <section className="mb-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(320px,460px)] lg:items-stretch">
        <div className="flex min-h-[260px] flex-col justify-center rounded-2xl border border-slate-200/70 bg-white/85 p-6 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_8px_24px_-12px_rgba(15,23,42,0.12)]">
          <p className="mb-3 text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">
            Evidence pipeline
          </p>
          <h2 className="max-w-2xl text-3xl font-bold tracking-tight text-slate-950 sm:text-4xl">
            Ask a clinical question and inspect the evidence trail.
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-slate-600">
            The system turns a case into PICO queries, retrieves PubMed abstracts,
            reranks them, generates a cited answer, and verifies each claim against
            the source passages.
          </p>
        </div>
        <div className="grid gap-4">
          <figure className="overflow-hidden rounded-2xl border border-slate-200/70 bg-slate-950 shadow-[0_1px_2px_rgba(15,23,42,0.04),0_8px_24px_-12px_rgba(15,23,42,0.12)]">
            <div className="border-b border-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-white/70">
              Demo video
            </div>
            <video
              src="/pubmed-evidence-agents-demo.mp4"
              className="aspect-video w-full bg-slate-950 object-contain"
              autoPlay
              controls
              loop
              muted
              playsInline
              preload="metadata"
            >
              <a href="/pubmed-evidence-agents-demo.mp4">Open demo video</a>
            </video>
          </figure>
          <figure className="overflow-hidden rounded-2xl border border-slate-200/70 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.04),0_8px_24px_-12px_rgba(15,23,42,0.12)]">
            <img
              src="/pipeline-diagram.svg"
              alt="pubmed-evidence-agents retrieval, generation, and verification pipeline"
              className="max-h-[240px] w-full object-contain p-4"
            />
          </figure>
        </div>
      </section>

      <Card icon={Stethoscope} title="Clinical question">
        <QueryForm onSubmit={(t) => run(t)} onCancel={cancel} running={running} />
      </Card>

      {(running || logs.length > 0) && (
        <section className="mt-6">
          <Card icon={Terminal} title="Pipeline progress">
            <StreamProgress logs={logs} running={running} />
          </Card>
        </section>
      )}

      {error && (
        <div className="mt-6 flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0" />
          <div>
            <div className="font-semibold">Pipeline error</div>
            <div className="mt-0.5 text-rose-600">{error}</div>
          </div>
        </div>
      )}

      {result && (
        <section className="mt-6 animate-fade-in">
          <ResultView
            result={result}
            logs={logs}
            running={running}
            onRerun={(pico) => run(lastText.current, pico)}
          />
        </section>
      )}

      <footer className="mt-10 text-center text-xs text-slate-400">
        Evidence is retrieved from PubMed and verified against source passages. Not a
        substitute for clinical judgement.
      </footer>
    </main>
  );
}
