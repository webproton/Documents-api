# billing/views/change_plan.py
from drf_yasg.utils import swagger_auto_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.billing.serializers import ChangePlanSerializer


class ChangePlanView(APIView):
    """
    Create a Stripe Checkout Session for changing
    the current subscription plan.
    """

    permission_classes = (IsAuthenticated,)

    @swagger_auto_schema(
        operation_summary="Change subscription plan",
        operation_description=(
            "Create a Checkout session for the first paid subscription "
            "or change the existing Stripe subscription to another plan."
        ),
        request_body=ChangePlanSerializer,
        responses={
            200: "Checkout session or updated subscription.",
            400: "Invalid plan or subscription state.",
        },
    )
    def post(self, request, *args, **kwargs):
        serializer = ChangePlanSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)
