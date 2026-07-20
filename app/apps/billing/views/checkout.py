from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.billing.serializers import CheckoutSerializer


class CheckoutView(APIView):
    """
    API endpoint for creating a Stripe Checkout session.

    Validates the selected subscription plan before
    creating a checkout session.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        serializer = CheckoutSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        return Response(serializer.validated_data, status=status.HTTP_200_OK)
