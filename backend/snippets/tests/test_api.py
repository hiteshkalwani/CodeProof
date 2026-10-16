"""The generate -> test -> repair loop through the HTTP API, with the scripted LLM and the real runner scripts."""

import shutil

import pytest

from snippets.models import Revision
from snippets.sandbox.executor import SandboxUnavailable
from snippets.services.llm import LLMError

pytestmark = pytest.mark.django_db


def create(api, language="python"):
    response = api.post("/api/snippets/", {"description": "Check if a string is a palindrome", "language": language},
                        format="json")
    assert response.status_code == 201, response.data
    return response.data


def test_create_generates_first_revision(api):
    snippet = create(api)

    assert snippet["status"] == "untested"
    [revision] = snippet["revisions"]
    assert revision["number"] == 1 and revision["source"] == "generated"
    assert "def is_palindrome" in revision["code"] and revision["tests"] == ""
    assert revision["model"] == "fake" and revision["prompt_tokens"] > 0


@pytest.mark.parametrize("language", ["python", "javascript"])
def test_repair_loop_turns_failing_tests_green(api, local_sandbox, language):
    if language == "javascript" and not shutil.which("node"):
        pytest.skip("node is not installed")
    snippet = create(api, language)
    sid = snippet["id"]

    snippet = api.post(f"/api/snippets/{sid}/tests/", {}, format="json").data
    assert snippet["revisions"][-1]["source"] == "tests_generated"

    snippet = api.post(f"/api/snippets/{sid}/run/", format="json").data
    first_run = snippet["revisions"][-1]["runs"][-1]
    assert snippet["status"] == "failing"
    assert sum(not r["passed"] for r in first_run["results"]) == 2  # case + punctuation

    snippet = api.post(f"/api/snippets/{sid}/repair/", {"max_attempts": 3}, format="json").data
    assert snippet["status"] == "passing"
    sources = [r["source"] for r in snippet["revisions"]]
    assert sources == ["generated", "tests_generated", "repaired"]
    # The repair changed the code, never the tests.
    assert snippet["revisions"][-1]["tests"] == snippet["revisions"][1]["tests"]
    assert snippet["revisions"][-1]["feedback"].count("- ") == 2


def test_repair_stops_after_max_attempts(api, local_sandbox, monkeypatch):
    from snippets.services import fake_llm

    monkeypatch.setitem(fake_llm.SCRIPT["python"], "fixed_code", fake_llm.SCRIPT["python"]["generate_code"])
    sid = create(api)["id"]
    api.post(f"/api/snippets/{sid}/tests/", {}, format="json")

    snippet = api.post(f"/api/snippets/{sid}/repair/", {"max_attempts": 2}, format="json").data
    assert snippet["status"] == "failing"
    assert [r["source"] for r in snippet["revisions"]].count("repaired") == 2


def test_repair_on_green_snippet_does_not_call_the_model(api, local_sandbox, monkeypatch):
    sid = create(api)["id"]
    api.post(f"/api/snippets/{sid}/tests/", {}, format="json")
    api.post(f"/api/snippets/{sid}/repair/", {}, format="json")
    count = Revision.objects.count()

    monkeypatch.setattr("snippets.services.llm.complete", lambda prompt: pytest.fail("model was called"))
    snippet = api.post(f"/api/snippets/{sid}/repair/", {}, format="json").data
    assert snippet["status"] == "passing" and Revision.objects.count() == count


def test_improve_tests_with_feedback_keeps_old_tests(api):
    sid = create(api)["id"]
    api.post(f"/api/snippets/{sid}/tests/", {}, format="json")
    snippet = api.post(f"/api/snippets/{sid}/tests/", {"feedback": "Cover a single character"}, format="json").data

    latest = snippet["revisions"][-1]
    assert latest["source"] == "tests_improved" and latest["feedback"] == "Cover a single character"
    assert "test_empty_string" in latest["tests"] and "test_single_character" in latest["tests"]


def test_hand_edit_creates_revision_without_model(api):
    sid = create(api)["id"]
    snippet = api.post(f"/api/snippets/{sid}/edit/", {"code": "def f():\n    return 1\n", "tests": ""}, format="json").data

    latest = snippet["revisions"][-1]
    assert latest["source"] == "edited" and latest["model"] == "" and latest["prompt_tokens"] == 0


def test_list_shows_status_without_revisions(api, local_sandbox, django_assert_max_num_queries):
    sid = create(api)["id"]
    create(api)
    api.post(f"/api/snippets/{sid}/tests/", {}, format="json")
    api.post(f"/api/snippets/{sid}/run/", format="json")

    with django_assert_max_num_queries(3):  # snippets + revisions + runs, regardless of count
        response = api.get("/api/snippets/")
    assert [s["status"] for s in response.data] == ["failing", "untested"]
    assert "revisions" not in response.data[0]


def test_delete(api):
    sid = create(api)["id"]
    assert api.delete(f"/api/snippets/{sid}/").status_code == 204
    assert api.get(f"/api/snippets/{sid}/").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {"description": "", "language": "python"},
        {"description": "x", "language": "cobol"},
        {"description": "x" * 2001, "language": "python"},
    ],
)
def test_create_validation(api, payload):
    assert api.post("/api/snippets/", payload, format="json").status_code == 400


def test_edit_rejects_oversized_code(api):
    sid = create(api)["id"]
    response = api.post(f"/api/snippets/{sid}/edit/", {"code": "x" * 20_001, "tests": ""}, format="json")
    assert response.status_code == 400


def test_run_without_tests_is_a_conflict(api):
    sid = create(api)["id"]
    response = api.post(f"/api/snippets/{sid}/run/", format="json")
    assert response.status_code == 409 and "no tests" in response.data["detail"]


def test_model_failure_is_502_and_creates_nothing(api, monkeypatch):
    def fail(prompt):
        raise LLMError("The model request failed. Try again in a moment.")

    monkeypatch.setattr("snippets.services.llm.complete", fail)
    response = api.post("/api/snippets/", {"description": "x", "language": "python"}, format="json")
    assert response.status_code == 502
    assert api.get("/api/snippets/").data == []


def test_sandbox_down_is_503(api, monkeypatch):
    def down(*args):
        raise SandboxUnavailable("The test sandbox is unavailable.")

    monkeypatch.setattr("snippets.sandbox.executor.run_tests", down)
    sid = create(api)["id"]
    api.post(f"/api/snippets/{sid}/tests/", {}, format="json")
    assert api.post(f"/api/snippets/{sid}/run/", format="json").status_code == 503
