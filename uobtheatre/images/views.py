from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import exceptions

from uobtheatre.images.serializers import ImageSerializer
from uobtheatre.images.abilities import UplaodImage


class ImageView(APIView):
    # MultiPartParser AND FormParser
    # https://www.django-rest-framework.org/api-guide/parsers/#multipartparser
    # "You will typically want to use both FormParser and MultiPartParser
    # together in order to fully support HTML form data."
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, *_, **__):
        if not request.user.is_authenticated or not UplaodImage.user_has(request.user):
            raise exceptions.AuthenticationFailed

        file_serializer = ImageSerializer(data=request.data)
        if not file_serializer.is_valid():
            return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        file_serializer.save()
        return Response(file_serializer.data, status=status.HTTP_201_CREATED)
