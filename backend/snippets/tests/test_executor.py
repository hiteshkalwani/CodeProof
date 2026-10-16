from snippets.sandbox.executor import MARKER, parse_output


def parse(raw, timed_out=False):
    return parse_output(raw, timed_out=timed_out, duration_ms=5)


def test_timeout_never_passes():
    result = parse("", timed_out=True)
    assert not result.passed and result.timed_out and "Timed out" in result.output


def test_missing_marker_is_reported():
    result = parse("Killed")
    assert not result.passed and result.output == "Killed"


def test_marker_line_is_separated_from_user_output():
    result = parse(f'hello\n{MARKER}{{"results": [{{"name": "t", "passed": true, "error": ""}}]}}')
    assert result.passed and result.output == "hello"
