from django.conf import settings
from rest_framework import serializers

from snippets.models import Language, Revision, Snippet, TestRun

MAX_SOURCE_CHARS = 20_000  # the sandbox receives code + tests through one environment variable


class TestRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = TestRun
        fields = ["id", "passed", "results", "output", "timed_out", "duration_ms", "created_at"]


class RevisionSerializer(serializers.ModelSerializer):
    runs = TestRunSerializer(many=True, read_only=True)

    class Meta:
        model = Revision
        fields = ["id", "number", "source", "code", "tests", "feedback", "model", "prompt_tokens",
                  "completion_tokens", "created_at", "runs"]


def snippet_status(snippet: Snippet) -> str:
    """passing / failing / untested, from the latest revision's latest run (uses prefetched data)."""
    revisions = list(snippet.revisions.all())
    runs = list(revisions[-1].runs.all()) if revisions else []
    if not runs:
        return "untested"
    return "passing" if runs[-1].passed else "failing"


class SnippetListSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = Snippet
        fields = ["id", "description", "language", "status", "created_at", "updated_at"]

    def get_status(self, snippet: Snippet) -> str:
        return snippet_status(snippet)


class SnippetDetailSerializer(SnippetListSerializer):
    revisions = RevisionSerializer(many=True, read_only=True)

    class Meta(SnippetListSerializer.Meta):
        fields = SnippetListSerializer.Meta.fields + ["revisions"]


class CreateSnippetSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=2000, trim_whitespace=True)
    language = serializers.ChoiceField(choices=Language.choices)


class FeedbackSerializer(serializers.Serializer):
    feedback = serializers.CharField(max_length=2000, trim_whitespace=True)


class OptionalFeedbackSerializer(serializers.Serializer):
    feedback = serializers.CharField(max_length=2000, trim_whitespace=True, required=False, allow_blank=True, default="")


class EditSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=MAX_SOURCE_CHARS, trim_whitespace=False)
    tests = serializers.CharField(max_length=MAX_SOURCE_CHARS, trim_whitespace=False, allow_blank=True)


class RepairSerializer(serializers.Serializer):
    max_attempts = serializers.IntegerField(min_value=1, max_value=settings.MAX_REPAIR_ATTEMPTS,
                                            default=settings.MAX_REPAIR_ATTEMPTS)
