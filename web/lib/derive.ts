import type { LogEntry } from "./types";

export interface StageSpan {
  stage: string;
  start: number; // ms from pipeline start
  duration: number; // ms
  end: number;
}

/**
 * Turn the cumulative `elapsed_ms` log timeline into per-stage spans for the
 * timing waterfall. Each log entry marks "stage X was active at time T"; a
 * stage's span runs from its first entry to the next entry of any stage.
 */
export function deriveStageSpans(logs: LogEntry[]): StageSpan[] {
  if (logs.length === 0) return [];
  const sorted = [...logs].sort((a, b) => a.elapsed_ms - b.elapsed_ms);
  const spans: Record<string, { start: number; end: number }> = {};

  for (let i = 0; i < sorted.length; i++) {
    const cur = sorted[i];
    const next = sorted[i + 1];
    const start = cur.elapsed_ms;
    const end = next ? next.elapsed_ms : cur.elapsed_ms;
    const existing = spans[cur.step];
    if (existing) {
      existing.start = Math.min(existing.start, start);
      existing.end = Math.max(existing.end, end);
    } else {
      spans[cur.step] = { start, end };
    }
  }

  return Object.entries(spans)
    .map(([stage, { start, end }]) => ({
      stage,
      start,
      duration: Math.max(0, end - start),
      end,
    }))
    .filter((s) => s.duration > 0)
    .sort((a, b) => a.start - b.start);
}
