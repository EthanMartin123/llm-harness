import os, pathlib, chromadb, ollama

EMBED = os.getenv("EMBED_MODEL", "nomic-embed-text")
client = ollama.Client(host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434"))
db = chromadb.PersistentClient(path="data/chroma")


def chunk(text, size=800, overlap=120):
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + size]); i += size - overlap
    return out


def embed(texts):
    return client.embed(model=EMBED, input=texts).embeddings


def collection():
    return db.get_or_create_collection("policies", metadata={"hnsw:space": "cosine"})


def ingest_file(path, trust="admin"):
    text = pathlib.Path(path).read_text(errors="ignore")   # W4: no sanitizing of hidden text/HTML comments
    parts = chunk(text)
    ids = [f"{pathlib.Path(path).stem}#{n}" for n in range(len(parts))]
    collection().upsert(ids=ids, documents=parts, embeddings=embed(parts),
                        metadatas=[{"source": str(path), "trust": trust}] * len(parts))
    return ids


def rebuild():
    try:
        db.delete_collection("policies")
    except Exception:
        pass
    for p in sorted(pathlib.Path("data/corpus").glob("*.md")):
        ingest_file(p, trust="admin")
    return collection().count()


def retrieve(query, k=4):
    r = collection().query(query_embeddings=embed([query]), n_results=k)
    return [{"id": i, "text": t, "meta": m}
            for i, t, m in zip(r["ids"][0], r["documents"][0], r["metadatas"][0])]
