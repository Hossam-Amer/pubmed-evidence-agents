import torch
import numpy as np
from config import MEDCPT_QUERY_ID, MEDCPT_ARTICLE_ID
from pipeline.model_loader import load_encoder

_BATCH_SIZE = 32


def _cls_embed(model_id: str, encoded) -> np.ndarray:
    _, model = load_encoder(model_id)
    with torch.no_grad():
        output = model(**encoded)
    return output.last_hidden_state[:, 0, :].cpu().numpy()  # CLS token


def embed_articles(units: list[dict]) -> np.ndarray:
    """
    Embed articles with the MedCPT Article Encoder using its trained input
    format: each article is a [title, abstract] pair joined with [SEP]. Passing
    a bare abstract (as the old code did) is off-distribution and degrades the
    embeddings — this fixes that.
    """
    print(f"[Embeddings] Encoding {len(units)} articles (title [SEP] abstract) with MedCPT ...")
    tokenizer, _ = load_encoder(MEDCPT_ARTICLE_ID)
    pairs = [[u.get("title", ""), u.get("text", "")] for u in units]

    embeddings: list[np.ndarray] = []
    for i in range(0, len(pairs), _BATCH_SIZE):
        batch = pairs[i: i + _BATCH_SIZE]
        encoded = tokenizer(
            batch,
            truncation=True,
            padding=True,
            max_length=512,
            return_tensors="pt",
        )
        embeddings.append(_cls_embed(MEDCPT_ARTICLE_ID, encoded))

    return np.vstack(embeddings).astype("float32")


def embed_query(query: str) -> np.ndarray:
    """Embed a single query string with the MedCPT Query Encoder. Returns (D,)."""
    tokenizer, _ = load_encoder(MEDCPT_QUERY_ID)
    encoded = tokenizer(
        [query],
        truncation=True,
        padding=True,
        max_length=64,  # MedCPT queries are short
        return_tensors="pt",
    )
    return _cls_embed(MEDCPT_QUERY_ID, encoded)[0].astype("float32")
