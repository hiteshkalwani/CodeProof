from django.db.models import Prefetch
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import exception_handler

from snippets import serializers as s
from snippets.models import Revision, Snippet
from snippets.sandbox.executor import SandboxUnavailable
from snippets.services import workflow
from snippets.services.llm import LLMError

# Map domain errors to HTTP once, here, so the services stay framework-free.
ERROR_STATUS = {
    LLMError: status.HTTP_502_BAD_GATEWAY,
    SandboxUnavailable: status.HTTP_503_SERVICE_UNAVAILABLE,
    workflow.WorkflowError: status.HTTP_409_CONFLICT,
}


def handle_exception(exc, context):
    for error, code in ERROR_STATUS.items():
        if isinstance(exc, error):
            return Response({"detail": str(exc)}, status=code)
    return exception_handler(exc, context)


class SnippetViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin,
                     viewsets.GenericViewSet):
    """Snippets and the actions of the generate -> test -> repair loop. Every action returns the full snippet."""

    throttle_scope = "llm"

    def get_queryset(self):
        return Snippet.objects.prefetch_related(
            Prefetch("revisions", queryset=Revision.objects.order_by("number").prefetch_related("runs"))
        )

    def get_serializer_class(self):
        return s.SnippetListSerializer if self.action == "list" else s.SnippetDetailSerializer

    def get_throttles(self):
        # Reads are free; anything that may call the model or the sandbox is rate limited.
        return [] if self.request.method in ("GET", "HEAD", "OPTIONS", "DELETE") else [ScopedRateThrottle()]

    def _validated(self, serializer_class):
        serializer = serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def _snippet_response(self, snippet: Snippet, code=status.HTTP_200_OK):
        return Response(s.SnippetDetailSerializer(self.get_queryset().get(pk=snippet.pk)).data, status=code)

    def create(self, request):
        data = self._validated(s.CreateSnippetSerializer)
        return self._snippet_response(workflow.create_snippet(**data), status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def tests(self, request, pk=None):
        snippet = self.get_object()
        workflow.write_tests(snippet, **self._validated(s.OptionalFeedbackSerializer))
        return self._snippet_response(snippet)

    @action(detail=True, methods=["post"])
    def improve(self, request, pk=None):
        snippet = self.get_object()
        workflow.improve_code(snippet, **self._validated(s.FeedbackSerializer))
        return self._snippet_response(snippet)

    @action(detail=True, methods=["post"])
    def edit(self, request, pk=None):
        snippet = self.get_object()
        workflow.edit(snippet, **self._validated(s.EditSerializer))
        return self._snippet_response(snippet)

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        snippet = self.get_object()
        workflow.run(snippet.latest_revision)
        return self._snippet_response(snippet)

    @action(detail=True, methods=["post"])
    def repair(self, request, pk=None):
        # shortcut: runs in the request (up to attempts x (LLM call + sandbox run)); move to a task queue when attempts or traffic grow
        snippet = self.get_object()
        workflow.repair(snippet, **self._validated(s.RepairSerializer))
        return self._snippet_response(snippet)

