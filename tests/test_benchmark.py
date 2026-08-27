from evaluation.run_benchmark import run


def test_seed_benchmark_passes():
    result = run()
    assert result["failed"] == 0
    assert result["historical_knowledge_coverage"] == 1.0
    assert result["cases"][0]["passed"] is True
    assert all(result["cases"][0]["checks"].values())
