from rest_framework import serializers


class AnalyzeSerializer(serializers.Serializer):
    origin = serializers.CharField(max_length=200, trim_whitespace=True)
    destination = serializers.CharField(max_length=200, trim_whitespace=True)
    departure = serializers.DateTimeField()
    load_lb = serializers.FloatField(min_value=1, max_value=200_000)
    sample_miles = serializers.IntegerField()

    def validate_origin(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("Enter an origin.")
        return value

    def validate_destination(self, value: str) -> str:
        if not value:
            raise serializers.ValidationError("Enter a destination.")
        return value

    def validate_sample_miles(self, value: int) -> int:
        if value not in (10, 25, 50):
            raise serializers.ValidationError("sample_miles must be 10, 25, or 50.")
        return value

    def validate_departure(self, value):
        raw = str(self.initial_data.get("departure", ""))
        tail = raw[10:]
        if not (raw.endswith("Z") or "+" in tail or "-" in tail):
            raise serializers.ValidationError("departure must include a timezone offset.")
        return value
