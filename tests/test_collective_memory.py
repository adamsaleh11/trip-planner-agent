from types import SimpleNamespace


def test_gemini_share_pipeline_scrubs_before_and_after_model_response():
    from app.services.collective_memory import GeminiSharePipeline

    calls = []

    class FakeModels:
        def generate_content(self, *, model, contents, config):
            calls.append({"model": model, "contents": contents, "config": config})
            assert "adam@example.com" not in contents
            assert "@ada" not in contents
            assert "555-123-4567" not in contents
            return SimpleNamespace(text="The pastry was excellent. Contact @stillhere")

    pipeline = GeminiSharePipeline(
        client=SimpleNamespace(models=FakeModels()),
        scrub_model="gemini-flash-test",
        embedding_model="gemini-embedding-test",
        embedding_dims=3,
    )

    scrubbed = pipeline.scrub(
        "Ada liked the pastry. Email adam@example.com @ada 555-123-4567",
        blocked_terms=["Ada"],
    )

    assert scrubbed == "The pastry was excellent. Contact"
    assert calls[0]["model"] == "gemini-flash-test"
    assert "Ada" in calls[0]["contents"]


def test_gemini_share_pipeline_embeds_with_configured_model_and_dimensions():
    from app.services.collective_memory import GeminiSharePipeline

    calls = []

    class FakeModels:
        def embed_content(self, *, model, contents, config):
            calls.append({"model": model, "contents": contents, "config": config})
            return SimpleNamespace(
                embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3])]
            )

    pipeline = GeminiSharePipeline(
        client=SimpleNamespace(models=FakeModels()),
        scrub_model="gemini-flash-test",
        embedding_model="gemini-embedding-test",
        embedding_dims=3,
    )

    embedding = pipeline.embed("pastry lisbon food")

    assert embedding == [0.1, 0.2, 0.3]
    assert calls == [
        {
            "model": "gemini-embedding-test",
            "contents": "pastry lisbon food",
            "config": {"output_dimensionality": 3},
        }
    ]
