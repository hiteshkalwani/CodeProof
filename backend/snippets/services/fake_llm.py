"""Scripted model for demo mode (LLM_PROVIDER=fake) and tests.

Whatever the description, it answers with a palindrome checker whose first draft has a bug, so the
generate -> test -> repair loop can be demonstrated end to end without an API key.
"""

from snippets.services.llm import Completion
from snippets.services.prompts import Prompt

SCRIPT = {
    "python": {
        "generate_code": "def is_palindrome(text: str) -> bool:\n    return text == text[::-1]\n",
        "fixed_code": (
            "def is_palindrome(text: str) -> bool:\n"
            "    cleaned = [ch.lower() for ch in text if ch.isalnum()]\n"
            "    return cleaned == cleaned[::-1]\n"
        ),
        "generate_tests": (
            "def test_simple_palindrome():\n    assert is_palindrome(\"racecar\")\n\n\n"
            "def test_not_a_palindrome():\n    assert not is_palindrome(\"hello\")\n\n\n"
            "def test_ignores_case():\n    assert is_palindrome(\"Level\")\n\n\n"
            "def test_ignores_spaces_and_punctuation():\n    assert is_palindrome(\"A man, a plan, a canal: Panama\")\n\n\n"
            "def test_empty_string():\n    assert is_palindrome(\"\")\n"
        ),
        "extra_test": "\n\ndef test_single_character():\n    assert is_palindrome(\"x\")\n",
    },
    "javascript": {
        "generate_code": "function isPalindrome(text) {\n  return text === text.split('').reverse().join('')\n}\n",
        "fixed_code": (
            "function isPalindrome(text) {\n"
            "  const cleaned = text.toLowerCase().replace(/[^a-z0-9]/g, '')\n"
            "  return cleaned === cleaned.split('').reverse().join('')\n"
            "}\n"
        ),
        "generate_tests": (
            'test("simple palindrome", () => assert.strictEqual(isPalindrome("racecar"), true))\n'
            'test("not a palindrome", () => assert.strictEqual(isPalindrome("hello"), false))\n'
            'test("ignores case", () => assert.strictEqual(isPalindrome("Level"), true))\n'
            'test("ignores spaces and punctuation", () => assert.strictEqual(isPalindrome("A man, a plan, a canal: Panama"), true))\n'
            'test("empty string", () => assert.strictEqual(isPalindrome(""), true))\n'
        ),
        "extra_test": 'test("single character", () => assert.strictEqual(isPalindrome("x"), true))\n',
    },
}


def _language(prompt: Prompt) -> str:
    return "javascript" if " javascript " in f" {prompt.user.lower()} " else "python"


def complete(prompt: Prompt) -> Completion:
    script = SCRIPT[_language(prompt)]
    text = {
        "generate_code": script["generate_code"],
        "generate_tests": script["generate_tests"],
        "improve_tests": prompt.user.split("Current tests:\n", 1)[-1].split("\n\nReviewer feedback:", 1)[0]
        + script["extra_test"],
        "improve_code": script["fixed_code"],
        "repair_code": script["fixed_code"],
    }[prompt.task]
    # Rough token estimate so the UI's cost column has something real-shaped to show.
    return Completion(text=text.strip() + "\n", model="fake", prompt_tokens=len(prompt.user) // 4, completion_tokens=len(text) // 4)
