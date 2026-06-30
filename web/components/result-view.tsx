"use client";

import { useState } from "react";
import {
  BarChart3,
  Braces,
  ChevronDown,
  ChevronRight,
  Clock,
  Database,
  FileText,
  Gauge,
  Map as MapIcon,
  RefreshCw,
  Scale,
  Timer,
} from "lucide-react";
import type { LogEntry, Pico, PipelineResult } from "@/lib/types";
import { Card, ConfidenceBadge, Metric, agreementStyle } from "./ui";
import { EvidenceExplorer } from "./evidence-explorer";
import { PicoEditor } from "./pico-editor";
import { EvidenceLandscape, RetrievalScores, TimingWaterfall } from "./charts";

function ConfidenceBreakdown({ result }: { result: PipelineResult }) {
  const b = result.evidence_trace.confidence_breakdown;
  if (!b || Object.keys(b).length === 0) return null;
  const rows: [string, string][] = [
    ["Calibrated level", String(b.level ?? result.confidence)],
    ["Model self-report", String(b.self_reported ?? "—")],
    ["Mean top cosine", b.mean_top_score != null ? b.mean_top_score.toFixed(4) : "—"],
    ["Supporting PMIDs", String(b.supporting_pmids ?? "—")],
    ["Verifier verdict", String(b.verifier_verdict ?? "—")],
    ["Unsupported claims", String(b.unsupported_claims ?? "—")],
  ];
  return (
    <Card icon={Gauge} title="Confidence breakdown">
      <table className="w-full text-xs">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k} className="border-b border-slate-100 last:border-0">
              <td className="py-1.5 text-slate-500">{k}</td>
              <td className="py-1.5 text-right font-medium text-slate-800">{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] leading-relaxed text-slate-400">
        Computed from retrieval + grounding signals, not the model&apos;s self-report.
      </p>
    </Card>
  );
}

export function ResultView({
  result,
  logs,
  onRerun,
  running,
}: {
  result: PipelineResult;
  logs: LogEntry[];
  onRerun: (pico: Pico) => void;
  running: boolean;
}) {
  const [showTrace, setShowTrace] = useState(false);
  const trace = result.evidence_trace;
  const consensus = trace.consensus;
  const showConsensus =
    consensus && consensus.agreement !== "unknown" && consensus.agreement !== "strong";

  return (
    <div className="space-y-5">
      {/* Metrics */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <div className="card col-span-2 flex items-center px-4 py-3 md:col-span-1">
          <ConfidenceBadge value={result.confidence} />
        </div>
        <Metric icon={Clock} label="Latency" value={`${trace.latency_seconds?.toFixed(1)}s`} />
        <Metric icon={RefreshCw} label="Verif. loops" value={trace.verification_iterations} />
        <Metric icon={FileText} label="Docs used" value={trace.top_k_docs.length} />
        <Metric icon={Database} label="Cache" value={trace.cache_hit ? "Hit" : "Miss"} />
      </div>

      {/* Consensus banner */}
      {showConsensus && consensus && (
        <div
          className={`flex items-start gap-2.5 rounded-2xl border p-3.5 text-sm ${agreementStyle(consensus.agreement)}`}
        >
          <Scale className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <span className="font-semibold capitalize">Evidence {consensus.agreement}.</span>{" "}
            {consensus.summary || "Retrieved studies do not fully agree."}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <EvidenceExplorer
            answer={result.answer}
            citations={result.citations}
            docs={trace.top_k_docs}
            verification={trace.verification}
          />
        </div>

        <div className="space-y-5">
          <PicoEditor pico={trace.pico} onRerun={onRerun} running={running} />
          <ConfidenceBreakdown result={result} />
        </div>
      </div>

      {/* Visualizations */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <Card icon={BarChart3} title="Retrieval scores">
          <RetrievalScores
            docs={trace.top_k_docs}
            consensus={consensus}
            candidates={trace.retrieval?.candidates}
          />
        </Card>
        <Card icon={MapIcon} title="Evidence landscape · year × relevance">
          <EvidenceLandscape docs={trace.top_k_docs} consensus={consensus} />
        </Card>
        <Card icon={Timer} title="Timing waterfall" className="lg:col-span-2">
          <TimingWaterfall logs={logs} />
        </Card>
      </div>

      {/* Raw trace */}
      <Card
        icon={Braces}
        title="Full evidence trace (JSON)"
        action={
          <button
            onClick={() => setShowTrace((s) => !s)}
            className="text-slate-400 hover:text-slate-700"
          >
            {showTrace ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        }
      >
        {showTrace ? (
          <pre className="max-h-96 overflow-auto rounded-xl bg-slate-900 p-3.5 text-xs leading-relaxed text-slate-200">
            {JSON.stringify(trace, null, 2)}
          </pre>
        ) : (
          <p className="text-xs text-slate-400">Expand to inspect the raw pipeline trace.</p>
        )}
      </Card>
    </div>
  );
}
