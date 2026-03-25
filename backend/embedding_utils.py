import numpy as np
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")


def embed_chunks(chunks):
    """
    Generate embeddings for all chunks.
    """

    texts = [chunk["text"] for chunk in chunks]

    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    for i, chunk in enumerate(chunks):
        chunk["embedding"] = embeddings[i].astype("float32")

    return chunks


def retrieve_chunks(query, index, chunks, top_k=8):
    """
    Retrieve most relevant chunks from FAISS index.
    """

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True
    ).astype("float32")

    D, I = index.search(query_embedding, top_k)

    results = []

    for idx in I[0]:

        if idx == -1:
            continue

        chunk = chunks[idx]

        metadata = [
            f"FILE: {chunk.get('path', 'unknown')}",
            f"TYPE: {chunk.get('type', 'unknown')}",
            f"NAME: {chunk.get('name', 'unknown')}",
        ]

        methods = chunk.get("methods") or []
        if methods:
            metadata.append(f"METHODS: {', '.join(methods)}")

        parent = chunk.get("parent")
        if parent:
            metadata.append(f"PARENT: {parent}")

        metadata_text = "\n".join(metadata)

        formatted_chunk = f"""
    {metadata_text}

{chunk["text"]}
"""

        results.append(formatted_chunk)

    return results