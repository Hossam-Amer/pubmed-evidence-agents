import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")  # avoid MKL vs LLVM OpenMP conflict
import torch
from dotenv import load_dotenv

load_dotenv()

DEPLOY_MODE  = os.environ.get("DEPLOY_MODE", "groq")  # "groq" | "hf" | "together" | "local"
HF_TOKEN     = os.environ.get("HF_TOKEN", None)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", None)
NCBI_API_KEY = os.environ.get("NCBI_API_KEY", "")

# HuggingFace model IDs — MedCPT always runs locally (CPU, BERT-size)
MEDCPT_QUERY_ID   = "ncbi/MedCPT-Query-Encoder"
MEDCPT_ARTICLE_ID = "ncbi/MedCPT-Article-Encoder"
MEDCPT_CROSS_ID   = "ncbi/MedCPT-Cross-Encoder"   # second-stage reranker (CPU)

# Model IDs — defaults depend on deploy mode; all overridable via .env
# "groq"    → free Llama base models via Groq API
# "hf"      → medical fine-tunes via HF Inference API (requires accepted gated access)
# "together"→ Together AI serverless models
if DEPLOY_MODE == "groq":
    OPENBIO_MODEL_ID = os.environ.get("OPENBIO_MODEL_ID", "llama-3.1-8b-instant")
    VERIFIER_MODEL_ID = os.environ.get("VERIFIER_MODEL_ID", "qwen/qwen3.6-27b")
elif DEPLOY_MODE == "hf":
    OPENBIO_MODEL_ID = os.environ.get("OPENBIO_MODEL_ID", "aaditya/Llama3-OpenBioLLM-8B")
    VERIFIER_MODEL_ID = os.environ.get("VERIFIER_MODEL_ID", "m42-health/Llama3-Med42-8B")
else:
    OPENBIO_MODEL_ID = os.environ.get("OPENBIO_MODEL_ID", "meta-llama/Meta-Llama-3-8B-Instruct-Lite")
    VERIFIER_MODEL_ID = os.environ.get("VERIFIER_MODEL_ID", "meta-llama/Llama-3.3-70B-Instruct-Turbo")

# Backward-compatible alias for integrations that imported the former name.
MED42_MODEL_ID = VERIFIER_MODEL_ID

# Hardware (used in local mode and for MedCPT)
DEVICE   = "cuda" if torch.cuda.is_available() else "cpu"
USE_4BIT = DEVICE == "cuda"

# Pipeline constants
PUBMED_MAX_RESULTS = 20
CHUNK_SIZE         = 256
CHUNK_OVERLAP      = 32
EMBED_CANDIDATE_K  = int(os.environ.get("EMBED_CANDIDATE_K", "30"))
BM25_CANDIDATE_K   = int(os.environ.get("BM25_CANDIDATE_K", str(EMBED_CANDIDATE_K)))
RERANK_TOP_K       = int(os.environ.get("RERANK_TOP_K", "12"))
LOOP_MAX_ITER      = 2
CACHE_TTL_SECONDS  = 86400  # 24h

# LLM prompt budgets. Groq rejects oversized request bodies before tokenization,
# so its defaults are intentionally smaller than the other hosted/local modes.
if DEPLOY_MODE == "groq":
    _PICO_INPUT_DEFAULT = "1800"
    _RAG_CONTEXT_DEFAULT = "3600"
    # Keep each abstract compact so all 12 reranked papers fit in the synthesis prompt.
    _RAG_PASSAGE_DEFAULT = "260"
    _VERIFY_CONTEXT_DEFAULT = "3200"
    _VERIFY_PASSAGE_DEFAULT = "400"
else:
    _PICO_INPUT_DEFAULT = "3000"
    _RAG_CONTEXT_DEFAULT = "6000"
    _RAG_PASSAGE_DEFAULT = "700"
    _VERIFY_CONTEXT_DEFAULT = "5000"
    _VERIFY_PASSAGE_DEFAULT = "550"

PICO_INPUT_TOKEN_BUDGET      = int(os.environ.get("PICO_INPUT_TOKEN_BUDGET", _PICO_INPUT_DEFAULT))
RAG_CONTEXT_TOKEN_BUDGET     = int(os.environ.get("RAG_CONTEXT_TOKEN_BUDGET", _RAG_CONTEXT_DEFAULT))
RAG_PASSAGE_TOKEN_BUDGET     = int(os.environ.get("RAG_PASSAGE_TOKEN_BUDGET", _RAG_PASSAGE_DEFAULT))
VERIFY_CONTEXT_TOKEN_BUDGET  = int(os.environ.get("VERIFY_CONTEXT_TOKEN_BUDGET", _VERIFY_CONTEXT_DEFAULT))
VERIFY_PASSAGE_TOKEN_BUDGET  = int(os.environ.get("VERIFY_PASSAGE_TOKEN_BUDGET", _VERIFY_PASSAGE_DEFAULT))
GROQ_MAX_REQUEST_BYTES       = int(os.environ.get("GROQ_MAX_REQUEST_BYTES", "18000"))
GROQ_RETRY_ATTEMPTS          = int(os.environ.get("GROQ_RETRY_ATTEMPTS", "6"))
GROQ_MAX_RETRY_WAIT_SECONDS  = float(os.environ.get("GROQ_MAX_RETRY_WAIT_SECONDS", "120"))
GROQ_MIN_REQUEST_INTERVAL_SECONDS = float(os.environ.get("GROQ_MIN_REQUEST_INTERVAL_SECONDS", "1.5"))

# Retrieval quality
RRF_K              = 60     # reciprocal-rank-fusion constant (per-query fusion)
USE_CROSS_ENCODER  = os.environ.get("USE_CROSS_ENCODER", "1") not in ("0", "false", "False", "")
USE_BM25           = os.environ.get("USE_BM25", "1") not in ("0", "false", "False", "")

# Together AI client — optional; required only when DEPLOY_MODE=together
try:
    from together import Together
    _together_key = os.environ.get("TOGETHER_API_KEY")
    together_client = Together(api_key=_together_key) if _together_key else None
except ImportError:
    together_client = None
