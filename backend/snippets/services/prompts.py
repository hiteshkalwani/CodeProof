"""Prompts for each task. The model for each task is chosen here, in one place."""

from dataclasses import dataclass

from django.conf import settings

SYSTEM = (
    "You are a careful senior engineer. Reply with exactly one fenced code block and nothing else. "
    "Use only the standard library. Do not read files, use the network, or print."
)

TEST_STYLE = {
    "python": (
        "Write each test as a top-level function named test_<behaviour> that uses plain `assert`. "
        "Do not import pytest or unittest, and do not redefine the code under test."
    ),
    "javascript": (
        'Write each test as test("<behaviour>", () => { ... }) using the global `assert` '
        "(Node's assert module, e.g. assert.strictEqual). Do not use require/import, and do not redefine the code under test."
    ),
}


@dataclass(frozen=True)
class Prompt:
    task: str
    model: str
    system: str
    user: str


def generate_code(description: str, language: str) -> Prompt:
    return Prompt(
        "generate_code",
        settings.LLM_CODE_MODEL,
        SYSTEM,
        f"Write a {language} function for this task. Handle edge cases.\n\nTask:\n{description}",
    )


def generate_tests(description: str, language: str, code: str) -> Prompt:
    return Prompt(
        "generate_tests",
        settings.LLM_TEST_MODEL,
        SYSTEM,
        f"Write 5-8 focused {language} tests for the task below. Test the task's requirements, not just what "
        f"the code happens to do: include edge cases. {TEST_STYLE[language]}\n\n"
        f"Task:\n{description}\n\nCode under test:\n{code}",
    )


def improve_tests(description: str, language: str, code: str, tests: str, feedback: str) -> Prompt:
    return Prompt(
        "improve_tests",
        settings.LLM_TEST_MODEL,
        SYSTEM,
        f"Revise these {language} tests according to the reviewer's feedback. Keep tests that are still "
        f"valid. {TEST_STYLE[language]}\n\nTask:\n{description}\n\nCode under test:\n{code}\n\n"
        f"Current tests:\n{tests}\n\nReviewer feedback:\n{feedback}",
    )


def improve_code(description: str, language: str, code: str, feedback: str) -> Prompt:
    return Prompt(
        "improve_code",
        settings.LLM_CODE_MODEL,
        SYSTEM,
        f"Revise this {language} code according to the reviewer's feedback. Keep the function name and "
        f"signature unless the feedback asks otherwise.\n\nTask:\n{description}\n\nCode:\n{code}\n\n"
        f"Reviewer feedback:\n{feedback}",
    )


def repair_code(description: str, language: str, code: str, tests: str, failures: str) -> Prompt:
    return Prompt(
        "repair_code",
        settings.LLM_CODE_MODEL,
        SYSTEM,
        f"This {language} code fails some of its tests. Fix the code so every test passes. The tests are the "
        f"specification: do not change them, and do not special-case test inputs.\n\nTask:\n{description}\n\n"
        f"Code:\n{code}\n\nTests:\n{tests}\n\nFailures:\n{failures}",
    )
