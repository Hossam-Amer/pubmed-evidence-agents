import torch
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    AutoModel,
    AutoModelForSequenceClassification,
)
from config import DEVICE, USE_4BIT, HF_TOKEN

try:
    from transformers import BitsAndBytesConfig
    _BNB_AVAILABLE = True
except ImportError:
    _BNB_AVAILABLE = False

_registry: dict = {}


def _bnb_config():
    if not _BNB_AVAILABLE:
        raise ImportError(
            "bitsandbytes not installed. 4-bit quantization unavailable. "
            "Install it or switch to DEPLOY_MODE=groq/together."
        )
    return BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
    )


def load_causal_lm(model_id: str) -> tuple:
    """Load 4-bit quantized causal LM + tokenizer. Cached after first load."""
    if model_id in _registry:
        return _registry[model_id]

    print(f"[ModelLoader] Loading {model_id} ...")
    kwargs: dict = {"token": HF_TOKEN, "device_map": "auto"}
    if USE_4BIT:
        kwargs["quantization_config"] = _bnb_config()
    else:
        kwargs["torch_dtype"] = torch.float32

    tokenizer = AutoTokenizer.from_pretrained(model_id, token=HF_TOKEN)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(model_id, **kwargs)
    model.eval()

    _registry[model_id] = (tokenizer, model)
    print(f"[ModelLoader] {model_id} ready on {DEVICE}.")
    return tokenizer, model


def load_encoder(model_id: str) -> tuple:
    """Load BERT-style encoder (MedCPT). Always runs on CPU — small enough."""
    if model_id in _registry:
        return _registry[model_id]

    print(f"[ModelLoader] Loading encoder {model_id} on CPU ...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=HF_TOKEN)
    model = AutoModel.from_pretrained(model_id, token=HF_TOKEN).to("cpu")
    model.eval()

    _registry[model_id] = (tokenizer, model)
    print(f"[ModelLoader] {model_id} ready on CPU.")
    return tokenizer, model


def load_cross_encoder(model_id: str) -> tuple:
    """Load a sequence-classification cross-encoder (MedCPT). Runs on CPU."""
    if model_id in _registry:
        return _registry[model_id]

    print(f"[ModelLoader] Loading cross-encoder {model_id} on CPU ...")
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=HF_TOKEN)
    model = AutoModelForSequenceClassification.from_pretrained(model_id, token=HF_TOKEN).to("cpu")
    model.eval()

    _registry[model_id] = (tokenizer, model)
    print(f"[ModelLoader] {model_id} ready on CPU.")
    return tokenizer, model


def unload(model_id: str) -> None:
    """Free a model from memory."""
    if model_id in _registry:
        del _registry[model_id]
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
