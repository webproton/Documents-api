# billing/views/change_plan.py
from drf_yasg.utils import swagger_auto_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.accounts.permissions import IsActiveAndNotBlocked
from app.apps.billing.serializers import ChangePlanSerializer, SubscriptionSerializer


class ChangePlanView(APIView):
    """
    Create a Stripe Checkout Session for changing
    the current subscription plan.
    """

    permission_classes = (IsActiveAndNotBlocked,)

    @swagger_auto_schema(
        operation_summary="Change subscription plan",
        operation_description=(
            "If the user has no active paid subscription yet, creates a "
            "Stripe Checkout session for the first payment (response: "
            "checkout_url, session_id). If a paid subscription already "
            "exists, updates it to the new plan and returns the updated "
            "subscription."
        ),
        request_body=ChangePlanSerializer,
        responses={
            200: SubscriptionSerializer,
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
