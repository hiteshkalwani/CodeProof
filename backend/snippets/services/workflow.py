"""Use cases: every state change to a snippet goes through here, never through the views directly."""

import logging

from django.db import transaction
from django.db.models import Max

from snippets.models import Revision, Snippet, TestRun
from snippets.sandbox import executor
from snippets.services import llm, prompts

logger = logging.getLogger(__name__)
Source = Revision.Source


class WorkflowError(Exception):
    """The requested step does not make sense for the snippet's current state."""


def _add_revision(snippet: Snippet, *, source: str, code: str, tests: str, feedback: str = "",
                  completion: llm.Completion | None = None) -> Revision:
    with transaction.atomic():
        # Lock the snippet row so two concurrent requests cannot take the same revision number.
        Snippet.objects.select_for_update().get(pk=snippet.pk)
        number = (snippet.revisions.aggregate(n=Max("number"))["n"] or 0) + 1
        revision = Revision.objects.create(
            snippet=snippet,
            number=number,
            source=source,
            code=code,
            tests=tests,
            feedback=feedback,
            model=completion.model if completion else "",
            prompt_tokens=completion.prompt_tokens if completion else 0,
            completion_tokens=completion.completion_tokens if completion else 0,
        )
        snippet.save(update_fields=["updated_at"])
    return revision


def create_snippet(description: str, language: str) -> Snippet:
    completion = llm.complete(prompts.generate_code(description, language))  # before any DB write
    snippet = Snippet.objects.create(description=description, language=language)
    _add_revision(snippet, source=Source.GENERATED, code=completion.text, tests="", completion=completion)
    return snippet


def write_tests(snippet: Snippet, feedback: str = "") -> Revision:
    """Generate tests, or revise the existing ones when feedback is given."""
    current = snippet.latest_revision
    if feedback and current.tests:
        prompt = prompts.improve_tests(snippet.description, snippet.language, current.code, current.tests, feedback)
        source = Source.TESTS_IMPROVED
    else:
        prompt = prompts.generate_tests(snippet.description, snippet.language, current.code)
        source = Source.TESTS_GENERATED
    completion = llm.complete(prompt)
    return _add_revision(snippet, source=source, code=current.code, tests=completion.text, feedback=feedback,
                         completion=completion)


def improve_code(snippet: Snippet, feedback: str) -> Revision:
    current = snippet.latest_revision
    completion = llm.complete(prompts.improve_code(snippet.description, snippet.language, current.code, feedback))
    return _add_revision(snippet, source=Source.IMPROVED, code=completion.text, tests=current.tests,
                         feedback=feedback, completion=completion)


def edit(snippet: Snippet, code: str, tests: str) -> Revision:
    return _add_revision(snippet, source=Source.EDITED, code=code, tests=tests)


def run(revision: Revision) -> TestRun:
    if not revision.tests.strip():
        raise WorkflowError("This revision has no tests yet. Generate or write tests first.")
    result = executor.run_tests(revision.snippet.language, revision.code, revision.tests)
    return TestRun.objects.create(
        revision=revision,
        passed=result.passed,
        results=result.results,
        output=result.output,
        timed_out=result.timed_out,
        duration_ms=result.duration_ms,
    )


def describe_failures(test_run: TestRun) -> str:
    failed = [f"- {r['name']}: {r['error']}" for r in test_run.results if not r["passed"]]
    return "\n".join(failed) or test_run.output or "The tests did not pass."


def repair(snippet: Snippet, max_attempts: int) -> list[TestRun]:
    """Run the tests; while they fail, ask the model to fix the code (never the tests) and run again.

    Stops on the first green run or after `max_attempts` repairs, whichever comes first.
    """
    revision = snippet.latest_revision
    test_run = revision.runs.last() or run(revision)
    runs = [test_run]
    for attempt in range(1, max_attempts + 1):
        if test_run.passed:
            break
        failures = describe_failures(test_run)
        completion = llm.complete(
            prompts.repair_code(snippet.description, snippet.language, revision.code, revision.tests, failures)
        )
        revision = _add_revision(snippet, source=Source.REPAIRED, code=completion.text, tests=revision.tests,
                                 feedback=failures, completion=completion)
        test_run = run(revision)
        runs.append(test_run)
        logger.info("Repair attempt %s/%s for snippet %s: passed=%s", attempt, max_attempts, snippet.pk, test_run.passed)
    return runs
