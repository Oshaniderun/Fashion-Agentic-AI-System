"""
Unit tests for EmbeddingService in Agent 2.
Verifies model initialization, single & batch encoding, dimensionality,
empty/invalid input safety, and model caching.
"""

import sys
from pathlib import Path

agent_dir = Path(__file__).resolve().parent.parent
workspace_dir = agent_dir.parent.parent
sys.path.insert(0, str(workspace_dir))
sys.path.insert(0, str(agent_dir))

import pytest
from app.services.embedding_service import EmbeddingService, get_embedding_service


def test_embedding_service_initialization():
    service = EmbeddingService(model_name="all-MiniLM-L6-v2")
    assert service.model_name == "all-MiniLM-L6-v2"
    dim = service.get_embedding_dimension()
    assert dim == 384


def test_single_text_embedding():
    service = EmbeddingService(model_name="all-MiniLM-L6-v2")
    emb = service.generate_embedding("beige suede loafers")
    assert isinstance(emb, list)
    assert len(emb) == 384
    assert all(isinstance(val, float) for val in emb)

    # Test alias method
    emb_query = service.encode_query("beige suede loafers")
    assert len(emb_query) == 384


def test_batch_embedding():
    service = EmbeddingService(model_name="all-MiniLM-L6-v2")
    texts = [
        "white linen shirt",
        "navy blue oxford formal shirt",
        "brown leather shoes"
    ]
    embeddings = service.generate_embeddings(texts)
    assert isinstance(embeddings, list)
    assert len(embeddings) == 3
    for vec in embeddings:
        assert isinstance(vec, list)
        assert len(vec) == 384
        assert all(isinstance(val, float) for val in vec)

    # Test alias method
    batch_emb = service.encode_batch(texts)
    assert len(batch_emb) == 3


def test_empty_and_invalid_input_handling():
    service = EmbeddingService(model_name="all-MiniLM-L6-v2")

    # Empty list
    assert service.generate_embeddings([]) == []

    # Mixed valid, empty, None, and non-string inputs
    texts = ["valid text", "", None, "   ", "another valid text"]
    embeddings = service.generate_embeddings(texts)
    assert len(embeddings) == 5

    # Check that valid texts get non-zero or encoded vectors
    assert len(embeddings[0]) == 384
    assert len(embeddings[4]) == 384

    # Check that empty/None texts return zero-vectors of correct dimension
    assert embeddings[1] == [0.0] * 384
    assert embeddings[2] == [0.0] * 384
    assert embeddings[3] == [0.0] * 384


def test_model_caching_and_singleton():
    service1 = get_embedding_service("all-MiniLM-L6-v2")
    service2 = get_embedding_service("all-MiniLM-L6-v2")
    assert service1 is service2

    # Verify model object in cache is shared if loaded
    if service1.model is not None:
        assert service1.model is service2.model
