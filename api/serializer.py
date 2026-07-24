from datetime import date

from rest_framework import serializers

from .models import Book


class BookSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = [
            'id',
            'title',
            'description',
            'author',
            'isbn',
            'published_date',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def to_internal_value(self, data):
        # Strip ISBN separators before field validation runs, so the uniqueness
        # check compares the same compact form that is stored. Normalising in
        # validate_isbn would be too late — that runs after the field's
        # validators, letting a hyphenated duplicate through to the database.
        if isinstance(data, dict) and isinstance(data.get('isbn'), str):
            data = data.copy()
            data['isbn'] = data['isbn'].replace('-', '').replace(' ', '')

        return super().to_internal_value(data)

    def validate_isbn(self, value):
        if not value.isdigit():
            raise serializers.ValidationError(
                "ISBN must contain only digits, hyphens and spaces."
            )

        if len(value) not in (10, 13):
            raise serializers.ValidationError(
                "ISBN must be 10 or 13 digits long."
            )

        return value

    def validate_published_date(self, value):
        if value > date.today():
            raise serializers.ValidationError(
                "Published date cannot be in the future."
            )

        return value

    def validate_title(self, value):
        stripped = value.strip()

        if not stripped:
            raise serializers.ValidationError("Title cannot be blank.")

        return stripped
