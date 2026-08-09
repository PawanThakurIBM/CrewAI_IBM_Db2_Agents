"""
Standalone smoke-test for ibm-granite/granite-embedding-125m-english.

Run BEFORE re-ingesting the knowledge base:
    .venv/bin/python scripts/test_granite_embedding.py

Expected output:
    Model loaded OK
    Embedding shape: (1, 768)
    Sample values (first 5): [...]
    ✓ ibm-granite/granite-embedding-125m-english is ready to use
"""
from sentence_transformers import SentenceTransformer

MODEL = "ibm-granite/granite-embedding-125m-english"

print(f"Loading {MODEL} …")
model = SentenceTransformer(MODEL)
print("Model loaded OK")

embedding = model.encode(["test airline delay sentence"])
print(f"Embedding shape: {embedding.shape}")
print(f"Sample values (first 5): {embedding[0][:5].tolist()}")

assert embedding.shape == (1, 768), f"Expected (1, 768), got {embedding.shape}"
print(f"\n✓ {MODEL} is ready to use")
