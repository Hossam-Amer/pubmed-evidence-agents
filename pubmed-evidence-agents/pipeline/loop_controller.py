import time
import queue as _queue_mod
from config import LOOP_MAX_ITER, OPENBIO_MODEL_ID, VERIFIER_MODEL_ID
from models.schemas import GeneratorOutput, VerifierOutput
from pipeline.generator import generate_answer
from pipeline.verifier import verify_answer


def run_verification_loop(
    clinical_question: str,
    pico: dict,
    chunks: list[dict],
    max_iter: int = LOOP_MAX_ITER,
    loop_log: list[dict] | None = None,
    log_queue: _queue_mod.Queue | None = None,
) -> tuple[GeneratorOutput, int, str, list[dict], VerifierOutput | None]:
    """
    Generate → verify → fix loop.
    Returns (final_output, iteration_count, final_verdict, loop_log_entries,
    final_verifier_output). The last element exposes the verifier's per-claim
    detail (unsupported_claims / suggested_corrections) for the evidence trace.
    """
    if loop_log is None:
        loop_log = []
    t_pipeline = time.time()

    def _log(step: str, message: str, level: str = "info"):
        elapsed = round((time.time() - t_pipeline) * 1000)
        entry = {
            "step": step,
            "message": message,
            "elapsed_ms": elapsed,
            "level": level,
        }
        loop_log.append(entry)
        if log_queue is not None:
            log_queue.put(entry)
        print(f"[{step}] {message}")

    fix_instructions: list[str] = []
    best: GeneratorOutput | None = None
    last_verdict_obj: VerifierOutput | None = None

    for iteration in range(1, max_iter + 1):
        _log(
            "Generator",
            f"Iteration {iteration}/{max_iter} — generating answer with {OPENBIO_MODEL_ID}...",
        )
        t = time.time()
        output = generate_answer(clinical_question, pico, chunks, fix_instructions)
        best = output
        _log(
            "Generator",
            (
                f"Answer generated in {round((time.time()-t)*1000)}ms | "
                f"confidence={output.confidence} | citations={len(output.citations)}"
            ),
        )

        _log("Verifier", f"Verifying with {VERIFIER_MODEL_ID}...")
        t = time.time()
        verdict_obj: VerifierOutput = verify_answer(output.answer, chunks, output.citations)
        last_verdict_obj = verdict_obj
        unsupported = verdict_obj.unsupported_claims
        _log(
            "Verifier",
            (
                f"Verdict: {verdict_obj.verdict.upper()} in {round((time.time()-t)*1000)}ms | "
                f"unsupported_claims={len(unsupported)}"
            ),
            level="success" if verdict_obj.verdict == "pass" else "warn",
        )

        if unsupported:
            for claim in unsupported:
                _log("Verifier", f"  Unsupported: {claim[:120]}", level="warn")

        if verdict_obj.verdict == "pass":
            _log(
                "LoopCtrl",
                f"Early exit at iteration {iteration} — verdict=pass",
                level="success",
            )
            return output, iteration, "pass", loop_log, verdict_obj

        if verdict_obj.verdict == "error":
            output.confidence = "low"
            if iteration < max_iter:
                fix_instructions = [
                    "The previous answer could not be verified. Regenerate a concise answer "
                    "whose every factual claim has a directly supporting inline citation."
                ]
                _log(
                    "LoopCtrl",
                    "Verifier failed after its internal retries — regenerating before the next verification iteration",
                    level="warn",
                )
                continue
            _log(
                "LoopCtrl",
                "Verification failed in the final iteration — returning answer as unverified with confidence=low",
                level="error",
            )
            return output, iteration, "verification_error", loop_log, verdict_obj

        fix_instructions = []
        for index, claim in enumerate(unsupported):
            correction = (
                verdict_obj.suggested_corrections[index]
                if index < len(verdict_obj.suggested_corrections)
                else ""
            )
            instruction = f"Unsupported claim: {claim}"
            if correction:
                instruction += f"\nSuggested correction: {correction}"
            fix_instructions.append(instruction)
        _log(
            "LoopCtrl",
            f"Requesting fix on {len(fix_instructions)} unsupported claim(s) — next iteration...",
        )

    best.confidence = "low"
    _log(
        "LoopCtrl",
        f"Max iterations ({max_iter}) reached — returning best answer with confidence=low",
        level="warn",
    )
    return best, max_iter, "max_iter_exceeded", loop_log, last_verdict_obj
