import faiss
import numpy as np

def create_vector_store(chunks):

    embeddings = [chunk["embedding"] for chunk in chunks]

    dimension = len(embeddings[0])

    index = faiss.IndexFlatL2(dimension)

    index.add(np.array(embeddings).astype("float32"))

    return index

def search(index, query_embedding, chunks, top_k=5):

    D, I = index.search(query_embedding, top_k)

    results = []

    for idx in I[0]:
        results.append(chunks[idx])

    return results