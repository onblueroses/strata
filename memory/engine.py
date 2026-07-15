#!/usr/bin/env python3
"""Daemonless BM25 retrieval with optional static embeddings and RRF fusion."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from memory.config import MemoryConfig, load_config
from memory.telemetry import append_event

K1 = 1.5
B = 0.75
RRF_K = 60
BM25_LOW_CONFIDENCE_THRESHOLD = 0.4
DOC_CHAR_BUDGET = 6000
MODEL2VEC_ENCODE_BATCH_SIZE = 128
MODEL2VEC_MAX_LENGTH = 512
TOKEN_RE = re.compile(r"\w+")
SAFE_COMPONENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")

_STATIC_MODEL_CLASS: Any | None = None
_STATIC_MODEL: Any | None = None
_STATIC_MODEL_NAME: str | None = None
_MODEL2VEC_CHECKED = False
_MODEL2VEC_INSTALLED = False
_MODEL2VEC_ERROR: str | None = None


class SearchResults(list[dict[str, Any]]):
    """Hit dictionaries with mode and telemetry metadata attached."""

    def __init__(
        self,
        hits: list[dict[str, Any]],
        *,
        search_mode: str,
        telemetry: dict[str, Any],
        fusion_unavailable: str | None = None,
    ) -> None:
        super().__init__(hits)
        self.search_mode = search_mode
        self.telemetry = telemetry
        self.fusion_unavailable = fusion_unavailable


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[3:end], text[end + 4 :].lstrip("\n")
    return "", text


def fm_get(frontmatter: str, key: str) -> str:
    match = re.search(
        r"^[ \t]*" + re.escape(key) + r":[ \t]*(.+?)[ \t]*$",
        frontmatter,
        re.M,
    )
    return match.group(1).strip() if match else ""


def _record_text(record: dict[str, Any], separator: str = " ") -> str:
    return separator.join(
        str(record.get(field, ""))
        for field in ("title", "description", "body")
        if record.get(field)
    )


def _snippet(text: str, target_len: int = 220) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= target_len:
        return compact
    window = compact[: target_len + 60]
    best = max(
        window.rfind(marker, 0, target_len) for marker in (". ", "! ", "? ", "; ")
    )
    if best > target_len * 0.5:
        return compact[: best + 1].strip()
    cut = compact[:target_len].rfind(" ")
    return compact[: cut if cut > 0 else target_len].strip() + "..."


def _safe_component(value: str) -> bool:
    return SAFE_COMPONENT_RE.fullmatch(value) is not None and value not in {".", ".."}


def _source_fingerprint(text: str, path: Path) -> dict[str, Any]:
    stat = path.stat()
    return {
        "mtime_ns": stat.st_mtime_ns,
        "size": stat.st_size,
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }


def load_memory_corpus(config: MemoryConfig | None = None) -> list[dict[str, Any]]:
    """Load configured cards and project/area summaries without exposing host paths."""

    cfg = config or load_config()
    records: list[dict[str, Any]] = []
    if cfg.cards_dir.exists():
        for path in sorted(cfg.cards_dir.glob("*.md")):
            card_id = path.stem
            if path.name == "MEMORY.md" or path.name.startswith("."):
                continue
            if not _safe_component(card_id) or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
                frontmatter, body = split_frontmatter(text)
                records.append(
                    {
                        "id": card_id,
                        "title": fm_get(frontmatter, "name") or card_id,
                        "description": fm_get(frontmatter, "description"),
                        "type": fm_get(frontmatter, "type") or "memory",
                        "body": body.strip(),
                        "source": "card",
                        "path": f"memory/cards/{path.name}",
                        "path_root": "state",
                        **_source_fingerprint(text, path),
                    }
                )
            except (OSError, UnicodeDecodeError, ValueError):
                continue

    for kind, directory_name in (("project", "projects"), ("area", "areas")):
        base = cfg.kb_dir / directory_name
        if not base.exists():
            continue
        for path in sorted(base.glob("*/summary.md")):
            entity_name = path.parent.name
            if not _safe_component(entity_name) or not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
                frontmatter, body = split_frontmatter(text)
                heading = re.search(r"^#\s+(.+)$", body, re.M)
                title = (
                    heading.group(1).strip()
                    if heading
                    else (fm_get(frontmatter, "entity") or entity_name)
                )
                clean = re.sub(r"\n{3,}", "\n\n", body.strip())
                if len(clean) > 4000:
                    clean = clean[:4000].rstrip() + " ..."
                status = fm_get(frontmatter, "status")
                records.append(
                    {
                        "id": f"{kind}:{entity_name}",
                        "title": title,
                        "description": status[:300]
                        if status
                        else clean.split("\n", 1)[0][:300],
                        "type": "entity",
                        "body": clean,
                        "source": "entity-summary",
                        "path": f"{directory_name}/{entity_name}/summary.md",
                        "path_root": "kb",
                        **_source_fingerprint(text, path),
                    }
                )
            except (OSError, UnicodeDecodeError, ValueError):
                continue
    return records


def _reject_duplicate_record_ids(records: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for record in records:
        if "id" not in record:
            raise ValueError("corpus record is missing id")
        doc_id = str(record["id"])
        if doc_id in seen:
            raise ValueError(f"duplicate record id in corpus: {doc_id}")
        seen.add(doc_id)


def _resolve_corpus(
    corpus: str | Path | list[dict[str, Any]] | tuple[dict[str, Any], ...],
    config: MemoryConfig,
) -> tuple[list[dict[str, Any]], bool, str]:
    if isinstance(corpus, (list, tuple)):
        records = [dict(record) for record in corpus]
        _reject_duplicate_record_ids(records)
        return records, False, "fixture"
    if corpus == "memory":
        records = load_memory_corpus(config)
        _reject_duplicate_record_ids(records)
        return records, True, "memory"
    path = Path(corpus).expanduser()
    if not path.is_file():
        raise ValueError(f"unknown corpus: {str(corpus)!r}")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, list) or not all(isinstance(row, dict) for row in loaded):
        raise ValueError("corpus JSON must be an array of objects")
    records = [dict(row) for row in loaded]
    _reject_duplicate_record_ids(records)
    return records, False, f"file:{path.name}"


class BM25Index:
    def __init__(self, records: list[dict[str, Any]]) -> None:
        self.records = records
        self.ids = [str(record["id"]) for record in records]
        self.doc_tokens = [
            Counter(tokenize(_record_text(record))) for record in records
        ]
        self.n_docs = len(records)
        self.pos = {doc_id: index for index, doc_id in enumerate(self.ids)}
        self.doc_len = [sum(frequencies.values()) for frequencies in self.doc_tokens]
        self.avgdl = (sum(self.doc_len) / self.n_docs) if self.n_docs else 1.0
        if self.avgdl <= 0:
            self.avgdl = 1.0
        frequencies: defaultdict[str, int] = defaultdict(int)
        for term_counts in self.doc_tokens:
            for term in term_counts:
                frequencies[term] += 1
        self.idf = {
            term: math.log(1 + (self.n_docs - count + 0.5) / (count + 0.5))
            for term, count in frequencies.items()
        }

    def _contribution(self, term: str, doc_index: int) -> float:
        frequency = self.doc_tokens[doc_index].get(term, 0)
        if frequency == 0:
            return 0.0
        length = self.doc_len[doc_index]
        denominator = frequency + K1 * (1 - B + B * length / self.avgdl)
        return self.idf.get(term, 0.0) * (frequency * (K1 + 1)) / denominator

    def rank(self, query: str) -> list[tuple[str, float]]:
        terms = sorted(set(tokenize(query)))
        if not terms:
            return []
        ranked = [
            (
                self.ids[index],
                sum(self._contribution(term, index) for term in terms),
            )
            for index in range(self.n_docs)
        ]
        return sorted(ranked, key=lambda item: (-item[1], item[0]))

    def top_term_contributions(self, query: str, doc_id: str, n: int = 2) -> float:
        """Return the top-N term evidence, independent of overall query length."""

        index = self.pos.get(str(doc_id))
        if index is None:
            return 0.0
        contributions = sorted(
            (self._contribution(term, index) for term in set(tokenize(query))),
            reverse=True,
        )
        return sum(value for value in contributions[:n] if value > 0.0)

    def query_term_contributions(self, query: str, doc_id: str) -> dict[str, float]:
        index = self.pos.get(str(doc_id))
        if index is None:
            return {}
        return {
            term: contribution
            for term in sorted(set(tokenize(query)))
            if (contribution := self._contribution(term, index)) > 0.0
        }


def _reset_model_state() -> None:
    global _STATIC_MODEL_CLASS, _STATIC_MODEL, _STATIC_MODEL_NAME
    global _MODEL2VEC_CHECKED, _MODEL2VEC_INSTALLED, _MODEL2VEC_ERROR
    _STATIC_MODEL_CLASS = None
    _STATIC_MODEL = None
    _STATIC_MODEL_NAME = None
    _MODEL2VEC_CHECKED = False
    _MODEL2VEC_INSTALLED = False
    _MODEL2VEC_ERROR = None


def _check_model2vec_import(config: MemoryConfig) -> bool:
    global _STATIC_MODEL_CLASS, _MODEL2VEC_CHECKED
    global _MODEL2VEC_INSTALLED, _MODEL2VEC_ERROR
    if config.embedding_model is None:
        _MODEL2VEC_ERROR = "embedding model is not configured"
        return False
    if _MODEL2VEC_CHECKED:
        return _MODEL2VEC_INSTALLED
    _MODEL2VEC_CHECKED = True
    try:
        try:
            from model2vec import StaticModel  # type: ignore[import-not-found]
        except ImportError:
            from model2vec.model import StaticModel  # type: ignore[import-not-found]
        _STATIC_MODEL_CLASS = StaticModel
        _MODEL2VEC_INSTALLED = True
        _MODEL2VEC_ERROR = None
        return True
    except Exception as exc:  # optional dependency may fail during its own import
        _STATIC_MODEL_CLASS = None
        _MODEL2VEC_INSTALLED = False
        _MODEL2VEC_ERROR = f"{type(exc).__name__}: {exc}"
        return False


def _load_static_model(config: MemoryConfig) -> Any | None:
    global _STATIC_MODEL, _STATIC_MODEL_NAME, _MODEL2VEC_INSTALLED, _MODEL2VEC_ERROR
    model_name = config.embedding_model
    if model_name is None or not _check_model2vec_import(config):
        return None
    if _STATIC_MODEL is not None and _STATIC_MODEL_NAME == model_name:
        return _STATIC_MODEL
    model_class = _STATIC_MODEL_CLASS
    if model_class is None:
        return None
    try:
        _STATIC_MODEL = model_class.from_pretrained(model_name)
        _STATIC_MODEL_NAME = model_name
        return _STATIC_MODEL
    except Exception as exc:
        _STATIC_MODEL = None
        _STATIC_MODEL_NAME = None
        _MODEL2VEC_INSTALLED = False
        _MODEL2VEC_ERROR = f"{type(exc).__name__}: {exc}"
        return None


def model2vec_status(config: MemoryConfig | None = None) -> dict[str, Any]:
    cfg = config or load_config()
    installed = _check_model2vec_import(cfg)
    return {
        "configured": cfg.embedding_model is not None,
        "installed": installed,
        "model": cfg.embedding_model,
        "model_loaded": _STATIC_MODEL is not None,
        "error": _MODEL2VEC_ERROR,
    }


def _cache_entries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "id": str(record["id"]),
            "mtime_ns": int(record.get("mtime_ns", 0)),
            "size": int(record.get("size", 0)),
            "sha256": str(record.get("sha256", "")),
        }
        for record in records
    ]


def _cache_paths(config: MemoryConfig) -> tuple[Path, Path]:
    return config.cache_dir / "vectors.npy", config.cache_dir / "ids.json"


def _load_cached_vectors(
    records: list[dict[str, Any]], config: MemoryConfig
) -> Any | None:
    vectors_path, ids_path = _cache_paths(config)
    try:
        import numpy as np

        metadata = json.loads(ids_path.read_text(encoding="utf-8"))
        if metadata != {
            "model": config.embedding_model,
            "doc_char_budget": DOC_CHAR_BUDGET,
            "entries": _cache_entries(records),
        }:
            return None
        vectors = np.load(vectors_path, allow_pickle=False)
        if vectors.ndim != 2 or vectors.shape[0] != len(records):
            return None
        return vectors.astype("float32", copy=False)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None


def _encode_texts(model: Any, texts: list[str]) -> Any:
    import numpy as np

    vectors = np.asarray(
        model.encode(
            texts,
            batch_size=MODEL2VEC_ENCODE_BATCH_SIZE,
            max_length=MODEL2VEC_MAX_LENGTH,
        ),
        dtype=np.float32,
    )
    if vectors.ndim == 1:
        vectors = vectors.reshape(1, -1)
    return vectors


def _save_vector_cache(
    records: list[dict[str, Any]], vectors: Any, config: MemoryConfig
) -> None:
    import numpy as np

    config.cache_dir.mkdir(parents=True, exist_ok=True)
    vectors_path, ids_path = _cache_paths(config)
    metadata = {
        "model": config.embedding_model,
        "doc_char_budget": DOC_CHAR_BUDGET,
        "entries": _cache_entries(records),
    }
    pid = os.getpid()
    temporary_vectors = vectors_path.with_name(f"vectors.{pid}.tmp.npy")
    temporary_ids = ids_path.with_name(f"ids.{pid}.json.tmp")
    try:
        np.save(temporary_vectors, vectors.astype("float32", copy=False))
        temporary_ids.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        os.replace(temporary_vectors, vectors_path)
        os.replace(temporary_ids, ids_path)
    finally:
        temporary_vectors.unlink(missing_ok=True)
        temporary_ids.unlink(missing_ok=True)


def _vector_rank(
    query: str,
    records: list[dict[str, Any]],
    *,
    cacheable: bool,
    config: MemoryConfig,
) -> tuple[list[tuple[str, float]] | None, str | None]:
    if not records:
        return [], None
    model = _load_static_model(config)
    if model is None:
        return None, _MODEL2VEC_ERROR or "model2vec is unavailable"
    try:
        import numpy as np

        query_vector = _encode_texts(model, [query])[0]
        vectors = _load_cached_vectors(records, config) if cacheable else None
        if vectors is not None and vectors.shape[1] != query_vector.shape[0]:
            vectors = None
        if vectors is None:
            texts = [_record_text(record, "\n")[:DOC_CHAR_BUDGET] for record in records]
            vectors = _encode_texts(model, texts)
            if cacheable:
                _save_vector_cache(records, vectors, config)
        document_norms = np.linalg.norm(vectors, axis=1)
        query_norm = np.linalg.norm(query_vector)
        similarities = (vectors @ query_vector) / (
            (document_norms * query_norm) + 1e-12
        )
        similarities = np.nan_to_num(similarities, nan=0.0, posinf=0.0, neginf=0.0)
        ranked = [
            (str(record["id"]), float(similarities[index]))
            for index, record in enumerate(records)
        ]
        return sorted(ranked, key=lambda item: (-item[1], item[0])), None
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _rrf_fuse(*ranked_lists: list[tuple[str, float]]) -> list[tuple[str, float]]:
    scores: defaultdict[str, float] = defaultdict(float)
    for ranked in ranked_lists:
        for rank, (doc_id, _score) in enumerate(ranked, 1):
            scores[doc_id] += 1.0 / (RRF_K + rank)
    return sorted(scores.items(), key=lambda item: (-item[1], item[0]))


def _top_rank_score(ranked: list[tuple[str, float]] | None) -> float:
    return float(ranked[0][1]) if ranked else 0.0


def _low_confidence(bm25_top_score: float, n_hits: int) -> bool:
    return n_hits == 0 or bm25_top_score < BM25_LOW_CONFIDENCE_THRESHOLD


def search(
    query: str,
    k: int = 10,
    corpus: str | Path | list[dict[str, Any]] | tuple[dict[str, Any], ...] = "memory",
    *,
    use_embeddings: bool = True,
    origin: str | None = None,
    config: MemoryConfig | None = None,
) -> SearchResults:
    """Return ranked hits while keeping all externally visible paths root-relative."""

    started = time.perf_counter()
    cfg = config or load_config()
    records, cacheable, corpus_name = _resolve_corpus(corpus, cfg)
    record_by_id = {str(record["id"]): record for record in records}
    query_terms = tokenize(query)
    bm25_index = BM25Index(records)
    bm25_ranked = bm25_index.rank(query) if query_terms else []
    bm25_top_score = _top_rank_score(bm25_ranked)
    vector_top_score: float | None = None
    final_ranked = bm25_ranked
    search_mode = "bm25"
    fusion_unavailable: str | None = None

    if use_embeddings and query_terms:
        vector_ranked, vector_error = _vector_rank(
            query,
            records,
            cacheable=cacheable,
            config=cfg,
        )
        if vector_ranked is not None:
            vector_top_score = _top_rank_score(vector_ranked)
            final_ranked = _rrf_fuse(bm25_ranked, vector_ranked)
            search_mode = "fused"
        else:
            fusion_unavailable = vector_error

    limit = max(int(k), 0)
    hits: list[dict[str, Any]] = []
    for doc_id, score in final_ranked[:limit]:
        record = record_by_id[doc_id]
        hit = {
            "id": doc_id,
            "score": float(score),
            "source": record.get("source", "memory"),
            "snippet": _snippet(str(record.get("body", ""))),
            "title": record.get("title", doc_id),
            "search_mode": search_mode,
            "top_terms_score": bm25_index.top_term_contributions(query, doc_id),
            "term_contribs": bm25_index.query_term_contributions(query, doc_id),
        }
        if isinstance(record.get("path"), str):
            hit["path"] = record["path"]
            hit["path_root"] = record.get("path_root")
        hits.append(hit)

    latency_ms = (time.perf_counter() - started) * 1000.0
    rank_top_score = float(hits[0]["score"]) if hits else 0.0
    n_hits = len(hits)
    low_confidence = _low_confidence(bm25_top_score, n_hits)
    top_score = max(bm25_top_score, vector_top_score or 0.0) if n_hits else 0.0
    payload: dict[str, Any] = {
        "corpus": corpus_name,
        "query": query,
        "n_hits": n_hits,
        "top_score": top_score,
        "rank_top_score": rank_top_score,
        "bm25_top_score": bm25_top_score,
        "vector_top_score": vector_top_score,
        "low_confidence": low_confidence,
        "is_miss": n_hits == 0 or low_confidence,
        "miss_reason": "no_hits"
        if n_hits == 0
        else ("low_confidence" if low_confidence else None),
        "scores": [float(hit["score"]) for hit in hits],
        "latency_ms": round(latency_ms, 3),
        "search_mode": search_mode,
        "returned_ids": [str(hit["id"]) for hit in hits],
    }
    if origin is not None:
        payload["origin"] = origin
    if cfg.telemetry_enabled:
        append_event(cfg.telemetry_file, "kb_query", payload)
    return SearchResults(
        hits,
        search_mode=search_mode,
        telemetry=payload,
        fusion_unavailable=fusion_unavailable,
    )


__all__ = [
    "B",
    "BM25Index",
    "BM25_LOW_CONFIDENCE_THRESHOLD",
    "K1",
    "RRF_K",
    "SearchResults",
    "load_memory_corpus",
    "model2vec_status",
    "search",
    "tokenize",
]
