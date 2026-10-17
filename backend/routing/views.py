import logging

import requests
from rest_framework.response import Response
from rest_framework.views import APIView

from routing.serializers import AnalyzeSerializer
from routing.services.analyze import analyze_trip
from routing.services.errors import TripError

logger = logging.getLogger(__name__)


def flatten_errors(errors) -> str:
    if isinstance(errors, dict):
        parts = []
        for key, value in errors.items():
            message = flatten_errors(value)
            if key == "non_field_errors":
                parts.append(message)
            else:
                parts.append(f"{key}: {message}")
        return " ".join(parts)
    if isinstance(errors, (list, tuple)):
        return flatten_errors(errors[0]) if errors else "Invalid request."
    return str(errors)


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class AnalyzeView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = AnalyzeSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({"detail": flatten_errors(serializer.errors)}, status=400)

        data = serializer.validated_data
        try:
            payload = analyze_trip(
                origin=data["origin"],
                destination=data["destination"],
                departure=data["departure"],
                load_lb=data["load_lb"],
                sample_miles=data["sample_miles"],
            )
        except TripError as exc:
            return Response({"detail": str(exc)}, status=exc.status)
        except requests.Timeout:
            return Response({"detail": "A map or weather service timed out. Try again."}, status=504)
        except requests.RequestException:
            logger.exception("upstream request failed")
            return Response({"detail": "A map or weather service failed. Try again."}, status=502)
        return Response(payload)
