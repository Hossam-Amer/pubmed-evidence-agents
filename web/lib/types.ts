// Mirrors pubmed-evidence-agents/models/schemas.py (PipelineOutput) + the evidence_trace shape
// assembled in pubmed-evidence-agents/pipeline/orchestrator.py.

export type Confidence = "high" | "medium" | "low";

export interface Citation {
  id?: number;
  pmid: string;
  title?: string;
  year?: number;
  journal?: string;
  journal_abbreviation?: string;
  publication_date?: string;
  publication_types?: string[];
  doi?: string;
  pmc?: string;
  first_author?: string;
  cited_by_count?: number | null;
}

export interface TopDoc {
  pmid: string;
  title: string;
  year?: number | null;
  score: number;
  text?: string;
  journal?: string;
  journal_abbreviation?: string;
  publication_date?: string;
  publication_types?: string[];
  doi?: string;
  pmc?: string;
  first_author?: string;
  cited_by_count?: number | null;
  rrf_score?: number;
  bm25_score?: number;
}

export interface Verification {
  verdict: string;
  status?: string;
  unsupported_claims: string[];
  suggested_corrections: string[];
  error?: string | null;
}

export type Agreement = "strong" | "mixed" | "conflicting" | "unknown";

export interface Consensus {
  agreement: Agreement;
  supporting_pmids: string[];
  conflicting_pmids: string[];
  summary: string;
}

export interface ConfidenceBreakdown {
  level?: Confidence;
  self_reported?: string;
  mean_top_score?: number;
  supporting_pmids?: number;
  verifier_verdict?: string;
  unsupported_claims?: number;
  thresholds?: Record<string, number>;
}

export interface Pico {
  P: string;
  I: string;
  C?: string | null;
  O: string;
  queries: string[];
}

export interface EvidenceTrace {
  pico: Pico;
  queries_used: string[];
  top_k_docs: TopDoc[];
  verification_iterations: number;
  verification_verdict: string;
  verification?: Verification;
  consensus?: Consensus;
  confidence_breakdown?: ConfidenceBreakdown;
  retrieval?: { candidates: number | null; selected: number };
  cache_hit: boolean;
  latency_seconds: number;
}

export interface PipelineResult {
  answer: string;
  citations: Citation[];
  confidence: Confidence;
  evidence_trace: EvidenceTrace;
  debug_log?: LogEntry[];
}

export type LogLevel = "info" | "success" | "warn" | "error";

export interface LogEntry {
  step: string;
  message: string;
  elapsed_ms: number;
  level: LogLevel;
}

export type StreamItem =
  | { type: "log"; data: LogEntry }
  | { type: "result"; data: PipelineResult }
  | { type: "error"; data: { message: string } };

// Ordered set of step names emitted by orchestrator._log — drives the stepper.
export const PIPELINE_STEPS = [
  "Pipeline",
  "PICO",
  "Cache",
  "PubMed",
  "Preprocess",
  "Embed",
  "FAISS",
  "TopK",
  "Consensus",
  "Generator",
  "Verifier",
  "LoopCtrl",
] as const;
