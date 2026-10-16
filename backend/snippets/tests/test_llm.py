import pytest

from snippets.services.llm import extract_code


@pytest.mark.parametrize(
    "text, expected",
    [
        ("def f():\n    pass", "def f():\n    pass"),
        ("```python\ndef f():\n    pass\n```", "def f():\n    pass"),
        ("Here you go:\n```js\nconst x = 1\n```\nHope it helps!", "const x = 1"),
        ("```\nplain fence\n```", "plain fence"),
    ],
)
def test_extract_code(text, expected):
    assert extract_code(text) == expected
