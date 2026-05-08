from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import faiss
except ImportError:  # pragma: no cover - optional dependency fallback
    faiss = None

try:
    import numpy as np
except ImportError:  # pragma: no cover - optional dependency fallback
    np = None

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional dependency fallback
    PdfReader = None

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency fallback
    requests = None

from runtime.contracts import ToolResult
from tools.path_policy import AGENTIC_ROOT


DOCUMENTS_DIR = (AGENTIC_ROOT / "data" / "documents").resolve()
VECTOR_DB_DIR = (AGENTIC_ROOT / "coding_output" / "vector_db").resolve()
FAISS_INDEX_PATH = (VECTOR_DB_DIR / "documents.index").resolve()
METADATA_PATH = (VECTOR_DB_DIR / "documents_metadata.json").resolve()

DEFAULT_EMBED_MODEL = "nomic-embed-text:latest"


def _ensure_vector_db_dir() -> None:
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)


def _model_provider() -> str:
    return os.getenv("MODEL_PROVIDER", "azure").strip().lower() or "azure"


def _embedding_model() -> str:
    provider = _model_provider()
    if provider == "azure":
        deployment = os.getenv("AZURE_OPENAI_EMBEDDING", "").strip()
        if deployment:
            return deployment
        return "AZURE_OPENAI_EMBEDDING"
    if provider == "openai":
        model = os.getenv("OPENAI_EMBEDDING", "").strip()
        if model:
            return model
        return "OPENAI_EMBEDDING"
    return os.getenv("OLLAMA_EMBEDDINGS", DEFAULT_EMBED_MODEL).strip() or DEFAULT_EMBED_MODEL


def _azure_embed_endpoint() -> tuple[str, str, str | None]:
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
    api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "").strip() or "2024-02-01"
    deployment = os.getenv("AZURE_OPENAI_EMBEDDING", "").strip()

    if not endpoint:
        raise RuntimeError("Missing AZURE_OPENAI_ENDPOINT in environment.")
    if not api_key:
        raise RuntimeError("Missing AZURE_OPENAI_API_KEY in environment.")
    if not deployment:
        raise RuntimeError("Missing AZURE_OPENAI_EMBEDDING in environment.")

    if endpoint.endswith("/openai/v1"):
        url = f"{endpoint}/embeddings"
        return url, api_key, None

    if endpoint.endswith("/openai"):
        url = f"{endpoint}/deployments/{deployment}/embeddings"
        return url, api_key, api_version

    url = f"{endpoint}/openai/deployments/{deployment}/embeddings"
    return url, api_key, api_version


def _ollama_embed_base_url() -> str:
    configured = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip()
    if not configured:
        configured = "http://localhost:11434/v1"

    parsed = urlparse(configured)
    if not parsed.scheme:
        configured = f"http://{configured}"
        parsed = urlparse(configured)

    base = f"{parsed.scheme}://{parsed.netloc}"
    if not parsed.netloc:
        base = "http://localhost:11434"
    return base.rstrip("/")


def _openai_embed_endpoint() -> tuple[str, dict[str, str]]:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY in environment.")

    base_url = os.getenv("OPENAI_BASE_URL", "").strip().rstrip("/") or "https://api.openai.com/v1"
    model = os.getenv("OPENAI_EMBEDDING", "").strip()
    if not model:
        raise RuntimeError("Missing OPENAI_EMBEDDING in environment.")

    url = f"{base_url}/embeddings"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return url, headers


def _embed_texts(texts: list[str]) -> list[list[float]]:
    if requests is None:
        raise RuntimeError("requests package is required for embeddings.")
    if not texts:
        return []

    if _model_provider() == "azure":
        url, api_key, api_version = _azure_embed_endpoint()
        params = {"api-version": api_version} if api_version else None
        response = requests.post(
            url,
            params=params,
            headers={"api-key": api_key, "Content-Type": "application/json"},
            json={"input": texts, **({"model": _embedding_model()} if api_version is None else {})},
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        if not isinstance(data, list) or not data:
            raise RuntimeError("Azure embeddings response did not contain any embeddings.")

        indexed_vectors: list[tuple[int, list[float]]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            embedding = item.get("embedding")
            index = int(item.get("index", len(indexed_vectors)))
            if not isinstance(embedding, list):
                raise RuntimeError("Azure embeddings response did not contain a valid embedding vector.")
            indexed_vectors.append((index, embedding))

        if not indexed_vectors:
            raise RuntimeError("Azure embeddings response did not contain any valid embedding vectors.")

        indexed_vectors.sort(key=lambda pair: pair[0])
        return [embedding for _, embedding in indexed_vectors]

    if _model_provider() == "openai":
        url, headers = _openai_embed_endpoint()
        response = requests.post(
            url,
            headers=headers,
            json={"model": _embedding_model(), "input": texts},
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data", [])
        if not isinstance(data, list) or not data:
            raise RuntimeError("OpenAI embeddings response did not contain any embeddings.")

        indexed_vectors: list[tuple[int, list[float]]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            embedding = item.get("embedding")
            index = int(item.get("index", len(indexed_vectors)))
            if not isinstance(embedding, list):
                raise RuntimeError("OpenAI embeddings response did not contain a valid embedding vector.")
            indexed_vectors.append((index, embedding))

        if not indexed_vectors:
            raise RuntimeError("OpenAI embeddings response did not contain any valid embedding vectors.")

        indexed_vectors.sort(key=lambda pair: pair[0])
        return [embedding for _, embedding in indexed_vectors]

    model = _embedding_model()
    base = _ollama_embed_base_url()
    embed_url = f"{base}/api/embed"
    response = requests.post(
        embed_url,
        json={"model": model, "input": texts},
        timeout=180,
    )

    if response.ok:
        payload = response.json()
        embeddings = payload.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            return embeddings

    # Fallback for older Ollama endpoint.
    fallback_url = f"{base}/api/embeddings"
    embeddings: list[list[float]] = []
    for text in texts:
        fallback_response = requests.post(
            fallback_url,
            json={"model": model, "prompt": text},
            timeout=180,
        )
        fallback_response.raise_for_status()
        payload = fallback_response.json()
        embedding = payload.get("embedding")
        if not isinstance(embedding, list):
            raise RuntimeError("Ollama embeddings response did not contain a valid embedding vector.")
        embeddings.append(embedding)
    return embeddings


def _read_pdf(path: Path) -> str:
    if PdfReader is None:
        raise RuntimeError(
            "pypdf package is required to index PDF documents. Install with "
            "'.\\.venv\\Scripts\\python.exe -m pip install pypdf'."
        )

    reader = PdfReader(str(path))
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        if page_text.strip():
            pages.append(page_text)
    return "\n".join(pages)


def _read_document(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def _chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative.")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size.")

    chunks: list[str] = []
    start = 0
    step = chunk_size - chunk_overlap
    while start < len(clean):
        chunk = clean[start : start + chunk_size].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


@dataclass
class _ChunkRecord:
    source: str
    chunk_id: int
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"source": self.source, "chunk_id": self.chunk_id, "text": self.text}


def _collect_document_chunks(chunk_size: int, chunk_overlap: int) -> list[_ChunkRecord]:
    if not DOCUMENTS_DIR.exists():
        raise RuntimeError(f"Documents directory does not exist: '{DOCUMENTS_DIR}'.")

    supported = {".pdf", ".txt", ".md"}
    files = sorted(
        [
            path
            for path in DOCUMENTS_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in supported
        ],
        key=lambda path: path.name.lower(),
    )
    if not files:
        raise RuntimeError(
            "No supported documents found in data/documents. Supported: .pdf, .txt, .md."
        )

    records: list[_ChunkRecord] = []
    for file_path in files:
        raw_text = _read_document(file_path)
        chunks = _chunk_text(raw_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for index, chunk in enumerate(chunks):
            records.append(
                _ChunkRecord(
                    source=str(file_path.relative_to(AGENTIC_ROOT)),
                    chunk_id=index,
                    text=chunk,
                )
            )
    return records


def build_documents_vector_db(chunk_size: int = 1100, chunk_overlap: int = 200, batch_size: int = 16):
    """
    Build a FAISS vector DB from files in `data/documents` using the configured embedding provider.

    Parameters:
        chunk_size (int): Maximum characters per chunk.
        chunk_overlap (int): Overlap in characters between consecutive chunks.
        batch_size (int): Number of chunks embedded per request.

    Returns:
        ToolResult:
            - data (dict): Build details such as document count, chunk count and storage paths.
            - summary (str): Short explanation of indexing result.
            - error (str | None): Failure reason if indexing cannot be completed.
    """
    if faiss is None:
        return ToolResult.failure(
            "faiss-cpu package is required. Install with '.\\.venv\\Scripts\\python.exe -m pip install faiss-cpu'.",
            summary="Could not build vector DB because FAISS is unavailable.",
        )
    if np is None:
        return ToolResult.failure(
            "numpy package is required for vector indexing.",
            summary="Could not build vector DB because numpy is unavailable.",
        )

    try:
        records = _collect_document_chunks(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    except Exception as exc:
        return ToolResult.failure(str(exc), summary="Could not prepare document chunks for vector DB.")

    if not records:
        return ToolResult.failure(
            "No text chunks were generated from documents.",
            summary="Could not build vector DB because there is no chunkable text.",
        )

    vectors: list[list[float]] = []
    try:
        texts = [record.text for record in records]
        for start in range(0, len(texts), max(1, batch_size)):
            batch = texts[start : start + max(1, batch_size)]
            vectors.extend(_embed_texts(batch))
    except Exception as exc:
        return ToolResult.failure(
            f"Embedding generation failed: {exc}",
            summary="Could not build vector DB because embeddings failed.",
        )

    if len(vectors) != len(records):
        return ToolResult.failure(
            "Embedding count does not match chunk count.",
            summary="Could not build vector DB due to inconsistent embedding output.",
        )

    matrix = np.asarray(vectors, dtype="float32")
    if matrix.ndim != 2 or matrix.shape[0] == 0:
        return ToolResult.failure(
            "Embedding matrix is empty or invalid.",
            summary="Could not build vector DB due to invalid embeddings.",
        )

    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(int(matrix.shape[1]))
    index.add(matrix)

    _ensure_vector_db_dir()
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    metadata_payload = {
        "embedding_model": _embedding_model(),
        "documents_dir": str(DOCUMENTS_DIR.relative_to(AGENTIC_ROOT)),
        "chunks": [record.to_dict() for record in records],
    }
    with METADATA_PATH.open("w", encoding="utf-8") as file:
        json.dump(metadata_payload, file, indent=2, ensure_ascii=False)

    unique_documents = sorted({record.source for record in records})
    return ToolResult.ok(
        data={
            "embedding_model": _embedding_model(),
            "documents": unique_documents,
            "documents_count": len(unique_documents),
            "chunks_count": len(records),
            "index_path": str(FAISS_INDEX_PATH),
            "metadata_path": str(METADATA_PATH),
        },
        summary=f"Built FAISS vector DB for {len(unique_documents)} document(s) with {len(records)} chunks.",
    )


def ensure_documents_vector_db():
    """
    Ensure FAISS vector DB artifacts exist before runtime starts.

    Returns:
        ToolResult:
            - data (dict): Initialization status and artifact paths.
            - summary (str): Short explanation of whether DB already existed or was built.
            - error (str | None): Failure reason if DB could not be initialized.
    """
    if FAISS_INDEX_PATH.exists() and METADATA_PATH.exists():
        return ToolResult.ok(
            data={
                "status": "existing",
                "index_path": str(FAISS_INDEX_PATH),
                "metadata_path": str(METADATA_PATH),
            },
            summary="Vector DB already exists and will be reused.",
        )
    return build_documents_vector_db()


def query_documents_vector_db(query: str, top_k: int = 5, rebuild_if_missing: bool = True):
    """
    Query the documents FAISS vector DB with semantic search.

    Parameters:
        query (str): User question or query text.
        top_k (int): Number of top matching chunks to return.
        rebuild_if_missing (bool): Build the DB automatically if index files are missing.

    Returns:
        ToolResult:
            - data (dict): Matched chunks with source and relevance score.
            - summary (str): Short explanation of retrieval result.
            - error (str | None): Failure reason if retrieval cannot be completed.
    """
    if not query or not str(query).strip():
        return ToolResult.failure("Query cannot be empty.", summary="Could not query vector DB.")
    if faiss is None or np is None:
        return ToolResult.failure(
            "faiss-cpu and numpy are required for vector search.",
            summary="Could not query vector DB because FAISS dependencies are unavailable.",
        )

    if rebuild_if_missing and (not FAISS_INDEX_PATH.exists() or not METADATA_PATH.exists()):
        build_result = build_documents_vector_db()
        if not build_result.success:
            return build_result

    if not FAISS_INDEX_PATH.exists() or not METADATA_PATH.exists():
        return ToolResult.failure(
            "Vector DB does not exist. Run build_documents_vector_db first.",
            summary="Could not query vector DB because index files are missing.",
        )

    try:
        with METADATA_PATH.open("r", encoding="utf-8") as file:
            metadata = json.load(file)
        chunks = metadata.get("chunks", [])
        index = faiss.read_index(str(FAISS_INDEX_PATH))
    except Exception as exc:
        return ToolResult.failure(
            f"Failed to load vector DB artifacts: {exc}",
            summary="Could not load vector DB for querying.",
        )

    try:
        query_vector = _embed_texts([query])[0]
    except Exception as exc:
        return ToolResult.failure(
            f"Failed to generate query embedding: {exc}",
            summary="Could not query vector DB because embedding generation failed.",
        )

    query_matrix = np.asarray([query_vector], dtype="float32")
    current_embedding_model = _embedding_model()
    stored_embedding_model = str(metadata.get("embedding_model", "")).strip()
    query_dim = int(query_matrix.shape[1]) if query_matrix.ndim == 2 else 0
    index_dim = int(getattr(index, "d", 0))

    if rebuild_if_missing and (
        stored_embedding_model != current_embedding_model or query_dim != index_dim
    ):
        rebuild_result = build_documents_vector_db()
        if not rebuild_result.success:
            return ToolResult.failure(
                error=(
                    "Vector DB is incompatible with the current embedding configuration and "
                    f"rebuild failed. Stored model='{stored_embedding_model}', current "
                    f"model='{current_embedding_model}', stored dim={index_dim}, query dim={query_dim}. "
                    f"Rebuild error: {rebuild_result.error or rebuild_result.summary}"
                ),
                summary="Could not query vector DB because the stored index is incompatible.",
                data={
                    "stored_embedding_model": stored_embedding_model,
                    "current_embedding_model": current_embedding_model,
                    "stored_index_dim": index_dim,
                    "query_embedding_dim": query_dim,
                    "rebuild_error": rebuild_result.error,
                },
            )

        try:
            with METADATA_PATH.open("r", encoding="utf-8") as file:
                metadata = json.load(file)
            chunks = metadata.get("chunks", [])
            index = faiss.read_index(str(FAISS_INDEX_PATH))
        except Exception as exc:
            return ToolResult.failure(
                f"Vector DB rebuild succeeded, but reloading artifacts failed: {exc}",
                summary="Could not reload rebuilt vector DB artifacts.",
            )

    faiss.normalize_L2(query_matrix)
    if query_matrix.ndim != 2 or query_matrix.shape[1] != int(getattr(index, "d", 0)):
        return ToolResult.failure(
            error=(
                "Embedding dimension mismatch after compatibility checks. "
                f"Query dim={query_matrix.shape[1] if query_matrix.ndim == 2 else 'invalid'}, "
                f"index dim={getattr(index, 'd', 'unknown')}."
            ),
            summary="Could not query vector DB because embedding dimensions do not match.",
            data={
                "stored_embedding_model": str(metadata.get("embedding_model", "")).strip(),
                "current_embedding_model": current_embedding_model,
                "stored_index_dim": int(getattr(index, "d", 0)),
                "query_embedding_dim": int(query_matrix.shape[1]) if query_matrix.ndim == 2 else None,
            },
        )

    k = max(1, min(int(top_k), len(chunks)))
    scores, indices = index.search(query_matrix, k)

    matches: list[dict[str, Any]] = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue
        chunk = chunks[idx]
        matches.append(
            {
                "source": chunk.get("source"),
                "chunk_id": chunk.get("chunk_id"),
                "score": float(score),
                "text": chunk.get("text", ""),
            }
        )

    return ToolResult.ok(
        data={
            "query": query,
            "top_k": k,
            "embedding_model": metadata.get("embedding_model", _embedding_model()),
            "matches": matches,
        },
        summary=f"Retrieved {len(matches)} matching chunk(s) from documents vector DB.",
    )


def check_news(query: str = "artificial intelligence", language: str = "en", size: int = 5):
    """
    Fetch latest news using NewsData API.

    Parameters:
        query (str): Search phrase, for example "artificial intelligence".
        language (str): Language filter, default "en".
        size (int): Number of articles to return, capped at 10.

    Returns:
        ToolResult:
            - data (dict): List of normalized articles with title, link and description.
            - summary (str): Short explanation of result size.
            - error (str | None): Failure reason when request/configuration fails.
    """
    if requests is None:
        return ToolResult.failure(
            "requests package is required for news retrieval.",
            summary="Could not fetch news because HTTP dependency is missing.",
        )

    api_key = os.getenv("NEWSDATA_API_KEY", "").strip()
    if not api_key:
        return ToolResult.failure(
            "Missing NEWSDATA_API_KEY in environment.",
            summary="Could not fetch news because API key is missing.",
        )

    normalized_query = str(query).strip()
    if not normalized_query:
        return ToolResult.failure("Query cannot be empty.", summary="Could not fetch news.")

    limit = max(1, min(int(size), 10))
    url = "https://newsdata.io/api/1/latest"
    params = {
        "apikey": api_key,
        "q": normalized_query,
        "language": language,
        "size": limit,
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return ToolResult.failure(
            f"News API request failed: {exc}",
            summary="Could not fetch latest news.",
        )

    items = payload.get("results", [])
    if not isinstance(items, list):
        items = []

    articles: list[dict[str, Any]] = []
    for item in items[:limit]:
        description = (
            str(item.get("description") or item.get("content") or "").strip()
        )
        if len(description) > 420:
            description = f"{description[:417]}..."
        articles.append(
            {
                "title": item.get("title"),
                "url": item.get("link"),
                "description": description,
                "published_at": item.get("pubDate"),
                "source": item.get("source_name") or item.get("source_id"),
            }
        )

    return ToolResult.ok(
        data={
            "query": normalized_query,
            "total_results": payload.get("totalResults"),
            "articles": articles,
            "next_page": payload.get("nextPage"),
        },
        summary=f"Fetched {len(articles)} latest article(s) from NewsData.",
    )


TOOLS = {
    "query_documents_vector_db": query_documents_vector_db,
    "check_news": check_news,
}
