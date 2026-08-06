# billing/views/change_plan.py
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

    def post(self, request, *args, **kwargs):
        serializer = ChangePlanSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result)
