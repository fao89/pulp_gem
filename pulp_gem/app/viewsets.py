from gettext import gettext as _

from django_filters.rest_framework import filterset
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import detail_route
from rest_framework import serializers, status
from rest_framework.response import Response

from pulpcore.plugin.serializers import (
    AsyncOperationResponseSerializer,
    RepositoryPublishURLSerializer,
    RepositorySyncURLSerializer,
)
from pulpcore.plugin.tasking import enqueue_with_reservation
from pulpcore.plugin.viewsets import (
    ContentViewSet,
    RemoteViewSet,
    OperationPostponedResponse,
    PublisherViewSet,
)

from . import tasks
from .models import GemContent, GemRemote, GemPublisher
from .serializers import GemContentSerializer, GemRemoteSerializer, GemPublisherSerializer


class GemContentFilter(filterset.FilterSet):
    """
    FilterSet for GemContent.
    """

    class Meta:
        model = GemContent
        fields = [
            'name',
            'version'
        ]


class GemContentViewSet(ContentViewSet):
    """
    ViewSet for GemContent.
    """

    endpoint_name = 'gem/gems'
    queryset = GemContent.objects.all()
    serializer_class = GemContentSerializer
    filter_class = GemContentFilter


class GemRemoteViewSet(RemoteViewSet):
    """
    ViewSet for Gem Remotes.
    """

    endpoint_name = 'gem'
    queryset = GemRemote.objects.all()
    serializer_class = GemRemoteSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to sync gem content.",
        responses={202: AsyncOperationResponseSerializer}
    )
    @detail_route(methods=('post',), serializer_class=RepositorySyncURLSerializer)
    def sync(self, request, pk):
        """
        Synchronizes a repository.

        The ``repository`` field has to be provided.
        """
        remote = self.get_object()
        serializer = RepositorySyncURLSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data.get('repository')
        mirror = serializer.validated_data.get('mirror', True)
        result = enqueue_with_reservation(
            tasks.synchronize,
            [repository, remote],
            kwargs={
                'remote_pk': remote.pk,
                'repository_pk': repository.pk,
                'mirror': mirror,
            }
        )
        return OperationPostponedResponse(result, request)


class GemPublisherViewSet(PublisherViewSet):
    """
    ViewSet for Gem Publishers.
    """

    endpoint_name = 'gem'
    queryset = GemPublisher.objects.all()
    serializer_class = GemPublisherSerializer

    @swagger_auto_schema(
        operation_description="Trigger an asynchronous task to publish gem content.",
        responses={202: AsyncOperationResponseSerializer}
    )
    @detail_route(methods=('post',), serializer_class=RepositoryPublishURLSerializer)
    def publish(self, request, pk):
        """
        Publishes a repository.

        Either the ``repository`` or the ``repository_version`` fields can
        be provided but not both at the same time.
        """
        publisher = self.get_object()
        serializer = RepositoryPublishURLSerializer(data=request.data,
                                                    context={'request': request})
        serializer.is_valid(raise_exception=True)
        repository_version = serializer.validated_data.get('repository_version')

        result = enqueue_with_reservation(
            tasks.publish,
            [repository_version.repository, publisher],
            kwargs={
                'publisher_pk': str(publisher.pk),
                'repository_version_pk': str(repository_version.pk)
            }
        )
        return OperationPostponedResponse(result, request)
