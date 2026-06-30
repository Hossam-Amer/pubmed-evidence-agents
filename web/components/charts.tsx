"use client";

import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
  CartesianGrid,
} from "recharts";
import type { Consensus, LogEntry, TopDoc } from "@/lib/types";
import { deriveStageSpans } from "@/lib/derive";
import { STANCE_COLOR } from "./ui";

type Stance = keyof typeof STANCE_COLOR;

export function stanceOf(pmid: string, consensus?: Consensus): Stance {
  if (!consensus) return "neutral";
  if (consensus.supporting_pmids?.includes(pmid)) return "supports";
  if (consensus.conflicting_pmids?.includes(pmid)) return "conflicts";
  return "neutral";
}

function truncate(s: string, n: number): string {
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

/* ── Feature 1: retrieval score bar chart ──────────────────────────────────── */
export function RetrievalScores({
  docs,
  consensus,
  candidates,
}: {
  docs: TopDoc[];
  consensus?: Consensus;
  candidates?: number | null;
}) {
  if (!docs.length) return <p className="text-sm text-slate-400">No documents retrieved.</p>;

  const data = [...docs]
    .sort((a, b) => b.score - a.score)
    .map((d, i) => ({
      label: `[${i + 1}] ${truncate(d.title || d.pmid, 48)}`,
      score: d.score,
      pmid: d.pmid,
      stance: stanceOf(d.pmid, consensus),
    }));

  return (
    <div>
      <p className="mb-2 text-xs text-slate-500">
        {candidates != null ? (
          <>
            {data.length} selected from {candidates} FAISS candidates · cosine
            similarity (MedCPT)
          </>
        ) : (
          <>{data.length} documents · cosine similarity (MedCPT)</>
        )}
      </p>
      <ResponsiveContainer width="100%" height={Math.max(180, data.length * 30)}>
        <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
          <CartesianGrid horizontal={false} stroke="#eef2f7" />
          <XAxis type="number" domain={[0, "dataMax"]} tick={{ fontSize: 11 }} />
          <YAxis
            type="category"
            dataKey="label"
            width={260}
            tick={{ fontSize: 10 }}
            interval={0}
          />
          <Tooltip
            formatter={(v: number) => [v.toFixed(4), "cosine"]}
            labelFormatter={(l) => String(l)}
          />
          <Bar dataKey="score" radius={[0, 4, 4, 0]}>
            {data.map((d) => (
              <Cell key={d.pmid} fill={STANCE_COLOR[d.stance]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ── Feature 2: timing waterfall ───────────────────────────────────────────── */
export function TimingWaterfall({ logs }: { logs: LogEntry[] }) {
  const spans = deriveStageSpans(logs);
  if (!spans.length) return <p className="text-sm text-slate-400">No timing data.</p>;
  const total = spans[spans.length - 1].end || 1;

  const data = spans.map((s) => ({
    stage: s.stage,
    offset: s.start,
    duration: s.duration,
    pct: Math.round((s.duration / total) * 100),
  }));

  return (
    <ResponsiveContainer width="100%" height={Math.max(180, data.length * 28)}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
        <CartesianGrid horizontal={false} stroke="#eef2f7" />
        <XAxis
          type="number"
          tick={{ fontSize: 11 }}
          tickFormatter={(v) => `${(v / 1000).toFixed(1)}s`}
        />
        <YAxis type="category" dataKey="stage" width={90} tick={{ fontSize: 11 }} interval={0} />
        <Tooltip
          formatter={(v: number, name) =>
            name === "duration" ? [`${v} ms`, "duration"] : [`${v} ms`, "start"]
          }
        />
        {/* transparent spacer pushes each bar to its start offset */}
        <Bar dataKey="offset" stackId="t" fill="transparent" />
        <Bar dataKey="duration" stackId="t" fill="#6366f1" radius={[0, 4, 4, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── Feature 4: evidence landscape (year × score, colored by stance) ───────── */
export function EvidenceLandscape({
  docs,
  consensus,
}: {
  docs: TopDoc[];
  consensus?: Consensus;
}) {
  const points = docs
    .filter((d) => d.year)
    .map((d) => ({
      year: d.year as number,
      score: d.score,
      pmid: d.pmid,
      title: d.title,
      stance: stanceOf(d.pmid, consensus),
    }));

  if (!points.length)
    return (
      <p className="text-sm text-slate-400">
        No publication years available to plot.
      </p>
    );

  return (
    <ResponsiveContainer width="100%" height={260}>
      <ScatterChart margin={{ left: 4, right: 16, top: 8, bottom: 8 }}>
        <CartesianGrid stroke="#eef2f7" />
        <XAxis
          type="number"
          dataKey="year"
          name="year"
          domain={["dataMin - 1", "dataMax + 1"]}
          tick={{ fontSize: 11 }}
          allowDecimals={false}
        />
        <YAxis
          type="number"
          dataKey="score"
          name="cosine"
          tick={{ fontSize: 11 }}
          domain={[0, "dataMax"]}
        />
        <ZAxis range={[80, 80]} />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const p = payload[0].payload as (typeof points)[number];
            return (
              <div className="max-w-xs rounded-md border border-slate-200 bg-white p-2 text-xs shadow">
                <div className="font-semibold">{truncate(p.title, 80)}</div>
                <div className="text-slate-500">
                  {p.year} · cosine {p.score.toFixed(4)} · {p.stance} · PMID {p.pmid}
                </div>
              </div>
            );
          }}
        />
        <Scatter data={points}>
          {points.map((p) => (
            <Cell key={p.pmid} fill={STANCE_COLOR[p.stance]} />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}
