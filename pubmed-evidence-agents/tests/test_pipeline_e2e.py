import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from pipeline import cache as query_cache

_TEST_CASE = """
65-year-old male with type 2 diabetes, HbA1c 9.2%, on metformin 1g twice daily.
Physician is considering adding an SGLT2 inhibitor.
What is the cardiovascular benefit evidence for SGLT2 inhibitors in type 2 diabetes?
"""


def setup_function():
    query_cache.clear()


@pytest.mark.integration
def test_full_pipeline_text_only():
    from pipeline.orchestrator import run_pipeline

    result = run_pipeline(_TEST_CASE)

    assert result.answer, "Answer must not be empty"
    assert result.confidence in ("high", "medium", "low")
    assert isinstance(result.citations, list)
    assert result.evidence_trace["pico"][
        "I"
    ], "Intervention (I) must be extracted from PICO"
    assert (
        len(result.evidence_trace["top_k_docs"]) > 0
    ), "Must retrieve at least one document"
    assert result.evidence_trace["verification_iterations"] >= 1


@pytest.mark.integration
def test_cache_hit_on_repeat():
    from pipeline.orchestrator import run_pipeline

    run_pipeline(_TEST_CASE)  # first call — populates cache
    result = run_pipeline(_TEST_CASE)  # second call — should hit cache
    assert result.evidence_trace["cache_hit"] is True


@pytest.mark.integration
def test_no_results_graceful():
    from pipeline.orchestrator import run_pipeline

    # Nonsense query — should get no PubMed results and return gracefully
    result = run_pipeline("zxqwerty nonsense clinical case 123456")
    assert result.confidence == "low"
    assert "No relevant literature" in result.answer or result.answer


@pytest.mark.integration
def test_pico_extraction_fields():
    from pipeline.query_agent import extract_pico

    pico = extract_pico(_TEST_CASE)
    assert pico.P, "Population must be non-empty"
    assert pico.I, "Intervention must be non-empty"
    assert pico.O, "Outcome must be non-empty"
    assert len(pico.queries) >= 1, "At least one query must be generated"


def test_verification_loop_does_not_exit_on_high_confidence_fix(monkeypatch):
    from pipeline.loop_controller import run_verification_loop
    from models.schemas import GeneratorOutput, VerifierOutput

    def fake_generate_answer(clinical_question, pico, chunks, fix_instructions):
        return GeneratorOutput(answer="x", citations=[], confidence="high")

    def fake_verify_answer(answer, chunks, citations):
        return VerifierOutput(
            verdict="fix",
            unsupported_claims=["unsupported detail not in passages"],
            suggested_corrections=["correct the unsupported detail"],
        )

    monkeypatch.setattr(
        "pipeline.loop_controller.generate_answer", fake_generate_answer
    )
    monkeypatch.setattr("pipeline.loop_controller.verify_answer", fake_verify_answer)

    output, iteration_count, final_verdict, loop_log, verdict_obj = (
        run_verification_loop(
            clinical_question="Test question",
            pico={},
            chunks=[],
            max_iter=2,
        )
    )

    assert iteration_count == 2
    assert final_verdict == "max_iter_exceeded"
    assert output.confidence == "low"
    assert verdict_obj.verdict == "fix"
    assert any("Requesting fix" in entry["message"] for entry in loop_log)


def test_verification_loop_forwards_claims_and_corrections(monkeypatch):
    from pipeline.loop_controller import run_verification_loop
    from models.schemas import GeneratorOutput, VerifierOutput

    received_instructions = []
    verdicts = iter([
        VerifierOutput(
            verdict="fix",
            unsupported_claims=["unsupported dose"],
            suggested_corrections=["remove the dose"],
        ),
        VerifierOutput(
            verdict="pass",
            unsupported_claims=[],
            suggested_corrections=[],
        ),
    ])

    def fake_generate_answer(clinical_question, pico, chunks, fix_instructions):
        received_instructions.append(list(fix_instructions))
        return GeneratorOutput(answer="x", citations=[], confidence="high")

    def fake_verify_answer(answer, chunks, citations):
        return next(verdicts)

    monkeypatch.setattr("pipeline.loop_controller.generate_answer", fake_generate_answer)
    monkeypatch.setattr("pipeline.loop_controller.verify_answer", fake_verify_answer)

    _, iteration_count, final_verdict, _, _ = run_verification_loop(
        clinical_question="Test question", pico={}, chunks=[], max_iter=2
    )

    assert iteration_count == 2
    assert final_verdict == "pass"
    assert received_instructions[0] == []
    assert received_instructions[1] == [
        "Unsupported claim: unsupported dose\nSuggested correction: remove the dose"
    ]


def test_verification_error_returns_unverified_low_confidence(monkeypatch):
    from pipeline.loop_controller import run_verification_loop
    from models.schemas import GeneratorOutput, VerifierOutput

    monkeypatch.setattr(
        "pipeline.loop_controller.generate_answer",
        lambda *args: GeneratorOutput(answer="x", citations=[], confidence="high"),
    )
    monkeypatch.setattr(
        "pipeline.loop_controller.verify_answer",
        lambda *args: VerifierOutput(
            verdict="error",
            unsupported_claims=[],
            suggested_corrections=[],
            error="invalid model response",
        ),
    )

    output, iterations, verdict, _, verification = run_verification_loop(
        clinical_question="Test question", pico={}, chunks=[], max_iter=2
    )

    assert iterations == 2
    assert verdict == "verification_error"
    assert output.confidence == "low"
    assert verification.verdict == "error"
