"use client";

import { useMemo, useState } from "react";
import {
  BookOpen,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  ExternalLink,
  Gauge,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import type { Citation, TopDoc, Verification } from "@/lib/types";
import { Card, pubmedUrl } from "./ui";

type Reliability = {
  label: "High" | "Moderate" | "Limited";
  score: number;
  reasons: string[];
  className: string;
};

function publicationTypeSignal(types: string[] = []): { points: number; reason?: string } {
  const lowered = types.map((t) => t.toLowerCase());
  if (lowered.some((t) => t.includes("meta-analysis") || t.includes("systematic review"))) {
    return { points: 30, reason: "systematic review/meta-analysis" };
  }
  if (lowered.some((t) => t.includes("randomized controlled trial"))) {
    return { points: 28, reason: "randomized controlled trial" };
  }
  if (lowered.some((t) => t.includes("clinical trial"))) {
    return { points: 20, reason: "clinical trial" };
  }
  if (lowered.some((t) => t.includes("review"))) {
    return { points: 12, reason: "review article" };
  }
  return { points: 6, reason: types[0] };
}

function reliabilityFor(doc?: TopDoc, citation?: Citation, grounded = true): Reliability {
  const source = { ...doc, ...citation };
  const reasons: string[] = [];
  let score = 0;

  const typeSignal = publicationTypeSignal(source.publication_types ?? []);
  score += typeSignal.points;
  if (typeSignal.reason) reasons.push(typeSignal.reason);

  if (source.year) {
    const age = new Date().getFullYear() - source.year;
    if (age <= 5) {
      score += 15;
      reasons.push("recent study");
    } else if (age <= 10) {
      score += 10;
      reasons.push("within 10 years");
    } else {
      score += 4;
      reasons.push("older evidence");
    }
  }

  const cited = source.cited_by_count;
  if (typeof cited === "number") {
    if (cited >= 100) {
      score += 20;
      reasons.push("highly cited");
    } else if (cited >= 25) {
      score += 14;
      reasons.push("well cited");
    } else if (cited >= 5) {
      score += 8;
      reasons.push("some citation uptake");
    } else {
      score += 3;
      reasons.push("low citation uptake");
    }
  }

  if (source.score != null) {
    if (source.score >= 0.75) {
      score += 20;
      reasons.push("strong retrieval match");
    } else if (source.score >= 0.55) {
      score += 12;
      reasons.push("moderate retrieval match");
    } else {
      score += 5;
      reasons.push("weaker retrieval match");
    }
  }

  if (source.journal || source.journal_abbreviation) {
    score += 6;
    reasons.push("journal indexed in PubMed");
  }

  if (grounded) {
    score += 10;
    reasons.push("answer claims verified against retrieved text");
  }

  if (score >= 70) {
    return {
      label: "High",
      score,
      reasons,
      className: "border-emerald-200 bg-emerald-50 text-emerald-700",
    };
  }
  if (score >= 45) {
    return {
      label: "Moderate",
      score,
      reasons,
      className: "border-amber-200 bg-amber-50 text-amber-700",
    };
  }
  return {
    label: "Limited",
    score,
    reasons,
    className: "border-slate-200 bg-slate-50 text-slate-600",
  };
}

function Detail({ label, value }: { label: string; value?: string | number | null }) {
  if (value === undefined || value === null || value === "") return null;
  return (
    <div>
      <dt className="text-[10px] font-medium uppercase text-slate-400">{label}</dt>
      <dd className="mt-0.5 text-xs text-slate-700">{value}</dd>
    </div>
  );
}

/** Render answer text with [n] citation markers turned into interactive chips. */
function AnnotatedAnswer({
  answer,
  setActive,
}: {
  answer: string;
  active: number | null;
  setActive: (id: number | null) => void;
}) {
  const parts = useMemo(() => answer.split(/(\[\d+\])/g), [answer]);
  return (
    <p className="whitespace-pre-wrap text-sm leading-7 text-slate-800">
      {parts.map((part, i) => {
        const m = part.match(/^\[(\d+)\]$/);
        if (!m) return <span key={i}>{part}</span>;
        const id = Number(m[1]);
        return (
          <span
            key={i}
            className="cite-marker"
            onMouseEnter={() => setActive(id)}
            onMouseLeave={() => setActive(null)}
            onClick={() =>
              document
                .getElementById(`cite-${id}`)
                ?.scrollIntoView({ behavior: "smooth", block: "center" })
            }
          >
            {part}
          </span>
        );
      })}
    </p>
  );
}

export function EvidenceExplorer({
  answer,
  citations,
  docs,
  verification,
}: {
  answer: string;
  citations: Citation[];
  docs: TopDoc[];
  verification?: Verification;
}) {
  const [active, setActive] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Set<number>>(new Set());
  const textByPmid = useMemo(
    () => Object.fromEntries(docs.map((d) => [d.pmid, d.text ?? ""])),
    [docs],
  );
  const docByPmid = useMemo(
    () => Object.fromEntries(docs.map((d) => [d.pmid, d])),
    [docs],
  );

  const seen = new Set<string>();
  const uniqueCitations = citations.filter((c) => {
    if (seen.has(c.pmid)) return false;
    seen.add(c.pmid);
    return true;
  });

  const toggle = (id: number) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });

  const unsupported = verification?.unsupported_claims ?? [];
  const corrections = verification?.suggested_corrections ?? [];
  const grounded = verification?.verdict === "pass" && unsupported.length === 0;
  const verificationUnavailable =
    !!verification && verification.verdict !== "pass" && verification.verdict !== "fix";

  return (
    <div className="space-y-5">
      <Card icon={ClipboardList} title="Clinical answer">
        <AnnotatedAnswer answer={answer} active={active} setActive={setActive} />
      </Card>

      {verification && (
        <Card
          icon={grounded ? ShieldCheck : ShieldAlert}
          title={
            grounded ? (
              <span className="text-emerald-700">All claims grounded</span>
            ) : verificationUnavailable ? (
              <span className="text-red-700">Verification unavailable</span>
            ) : (
              <span className="text-amber-700">
                {unsupported.length} unsupported claim{unsupported.length === 1 ? "" : "s"}
              </span>
            )
          }
        >
          {grounded ? (
            <p className="text-sm text-slate-500">
              The verifier found every claim supported by the retrieved passages.
            </p>
          ) : verificationUnavailable ? (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-900">
              The verifier could not complete its evidence check. This answer is unverified and
              should not be treated as grounded.
            </div>
          ) : (
            <ul className="space-y-2">
              {unsupported.map((claim, i) => (
                <li
                  key={i}
                  className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
                >
                  <div>{claim}</div>
                  {corrections[i] && (
                    <div className="mt-1.5 text-xs text-amber-700">
                      <span className="font-semibold">Suggested fix:</span> {corrections[i]}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}

      <Card icon={BookOpen} title={`Citations · ${uniqueCitations.length}`}>
        <div className="space-y-2">
          {uniqueCitations.map((c) => {
            const id = c.id ?? 0;
            const isActive = active === id;
            const isOpen = expanded.has(id);
            const text = textByPmid[c.pmid];
            const doc = docByPmid[c.pmid];
            const source = { ...doc, ...c };
            const reliability = reliabilityFor(doc, c, grounded);
            const citedBy =
              typeof source.cited_by_count === "number"
                ? source.cited_by_count.toLocaleString()
                : "Not available";
            const journal = source.journal || source.journal_abbreviation;
            const pubTypes = source.publication_types?.join(", ");
            return (
              <div
                id={`cite-${id}`}
                key={`${c.pmid}-${id}`}
                onMouseEnter={() => setActive(id)}
                onMouseLeave={() => setActive(null)}
                className={`rounded-xl border-l-[3px] p-3 transition-colors ${
                  isActive
                    ? "border-indigo-500 bg-indigo-50/70"
                    : "border-slate-200 bg-slate-50/70"
                }`}
              >
                <div className="text-sm text-slate-800">
                  <span className="font-semibold text-indigo-600">[{id}]</span> {c.title || "Untitled"}{" "}
                  {c.year ? <span className="text-slate-400">({c.year})</span> : null}
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                  <span
                    className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 font-medium ${reliability.className}`}
                    title={reliability.reasons.join("; ")}
                  >
                    <Gauge className="h-3 w-3" />
                    Reliability: {reliability.label}
                  </span>
                  <a
                    href={pubmedUrl(c.pmid)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-indigo-600 hover:underline"
                  >
                    PMID {c.pmid}
                    <ExternalLink className="h-3 w-3" />
                  </a>
                  {source.doi && (
                    <a
                      href={`https://doi.org/${source.doi}`}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-indigo-600 hover:underline"
                    >
                      DOI
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  {text && (
                    <button
                      onClick={() => toggle(id)}
                      className="inline-flex items-center gap-1 text-slate-500 hover:text-slate-800"
                    >
                      {isOpen ? (
                        <>
                          Hide abstract <ChevronUp className="h-3 w-3" />
                        </>
                      ) : (
                        <>
                          Show abstract <ChevronDown className="h-3 w-3" />
                        </>
                      )}
                    </button>
                  )}
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-2 rounded-lg border border-slate-200 bg-white/70 p-2 md:grid-cols-3">
                  <Detail label="Journal" value={journal} />
                  <Detail label="Published" value={source.publication_date ?? source.year} />
                  <Detail label="Study type" value={pubTypes} />
                  <Detail label="First author" value={source.first_author} />
                  <Detail label="Cited by" value={citedBy} />
                  <Detail
                    label="Relevance"
                    value={source.score != null ? source.score.toFixed(4) : undefined}
                  />
                </dl>
                <div className="mt-2 text-[11px] leading-relaxed text-slate-500">
                  <span className="font-medium text-slate-600">Reliability basis:</span>{" "}
                  {reliability.reasons.length
                    ? reliability.reasons.join("; ")
                    : "limited metadata available"}
                  .
                </div>
                {isOpen && text && (
                  <p className="mt-2 border-t border-slate-200 pt-2 text-xs leading-relaxed text-slate-600">
                    {text}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
