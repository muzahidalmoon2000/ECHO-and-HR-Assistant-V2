import os
import numpy as np
import faiss
import pickle
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

FAISS_INDEX_PATH = "faiss.index"
FAISS_META_PATH = "file_metadata.pkl"

def cosine_similarity(vec1, vec2):
    a = np.array(vec1)
    b = np.array(vec2)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def embed_texts(texts):
    response = client.embeddings.create(
        input=texts,
        model="text-embedding-3-small"
    )
    return [item.embedding for item in response.data]

def build_faiss_index(files, index_name="file"):
    texts = [f.get("extracted_text") or f.get("name", "") for f in files]
    texts = [t[:2000] for t in texts]

    embeddings = client.embeddings.create(
        input=texts,
        model="text-embedding-3-small"
    ).data
    matrix = np.array([e.embedding for e in embeddings]).astype("float32")

    index = faiss.IndexFlatL2(len(matrix[0]))
    index.add(matrix)

    faiss.write_index(index, f"faiss_{index_name}.index")
    with open(f"{index_name}_metadata.pkl", "wb") as f:
        pickle.dump(files, f)

    print(f"✅ FAISS index saved as faiss_{index_name}.index")

def rank_files_by_similarity(query, top_k=5, index_name="file"):
    if not os.path.exists(f"faiss_{index_name}.index") or not os.path.exists(f"{index_name}_metadata.pkl"):
        print("❌ FAISS index or metadata missing.")
        return []

    index = faiss.read_index(f"faiss_{index_name}.index")
    with open(f"{index_name}_metadata.pkl", "rb") as f:
        files = pickle.load(f)

    query_embedding = client.embeddings.create(
        input=[query],
        model="text-embedding-3-small"
    ).data[0].embedding
    query_vec = np.array([query_embedding]).astype("float32")

    distances, indices = index.search(query_vec, len(files))

    def hybrid_score(file, distance):
        text = (file.get("extracted_text") or file.get("name", "")).lower()
        query_lower = query.lower()
        keywords = query_lower.split()

        exact_phrase_bonus = 0.2 if query_lower in text else 0
        keyword_match_count = sum(1 for kw in keywords if kw in text)
        keyword_bonus = 0.02 * keyword_match_count

        year_bonus = 0
        for word in keywords:
            if word.isdigit() and len(word) == 4:
                if word in text:
                    year_bonus = 0.1
                break

        score = -float(distance) + exact_phrase_bonus + keyword_bonus + year_bonus
        return float(score)

    scored_files = []
    for idx, dist in zip(indices[0], distances[0]):
        if 0 <= idx < len(files):
            file = files[idx]
            score = hybrid_score(file, dist)
            file["hybrid_score"] = float(score)
            scored_files.append(file)

    sorted_files = sorted(scored_files, key=lambda f: f["hybrid_score"], reverse=True)
    return sorted_files[:top_k]
