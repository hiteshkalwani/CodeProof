from django.db import models


class Language(models.TextChoices):
    PYTHON = "python", "Python"
    JAVASCRIPT = "javascript", "JavaScript"


class Snippet(models.Model):
    """A task described in plain language. Its history lives in revisions."""

    description = models.TextField()
    language = models.CharField(max_length=20, choices=Language.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return f"{self.language}: {self.description[:50]}"

    @property
    def latest_revision(self) -> "Revision":
        return self.revisions.order_by("-number").first()


class Revision(models.Model):
    """An immutable (code, tests) pair. Every change, by a model or a person, adds a new one."""

    class Source(models.TextChoices):
        GENERATED = "generated", "Generated from description"
        TESTS_GENERATED = "tests_generated", "Tests generated"
        TESTS_IMPROVED = "tests_improved", "Tests improved from feedback"
        IMPROVED = "improved", "Code improved from feedback"
        REPAIRED = "repaired", "Code repaired from failing tests"
        EDITED = "edited", "Edited by hand"

    snippet = models.ForeignKey(Snippet, related_name="revisions", on_delete=models.CASCADE)
    number = models.PositiveIntegerField()
    source = models.CharField(max_length=20, choices=Source.choices)
    code = models.TextField()
    tests = models.TextField(blank=True)
    feedback = models.TextField(blank=True)
    # Which model wrote this revision and what it cost; empty for hand edits.
    model = models.CharField(max_length=100, blank=True)
    prompt_tokens = models.PositiveIntegerField(default=0)
    completion_tokens = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["number"]
        constraints = [models.UniqueConstraint(fields=["snippet", "number"], name="unique_revision_number")]


class TestRun(models.Model):
    """One execution of a revision's tests in the sandbox."""

    revision = models.ForeignKey(Revision, related_name="runs", on_delete=models.CASCADE)
    passed = models.BooleanField()
    # [{"name": "test_empty", "passed": false, "error": "AssertionError: ..."}]
    results = models.JSONField(default=list)
    output = models.TextField(blank=True)
    timed_out = models.BooleanField(default=False)
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
