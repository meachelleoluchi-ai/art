from datetime import date, timedelta

from rest_framework.test import APITestCase
from rest_framework import status

from .models import Book


class BookAPITest(APITestCase):

    def setUp(self):
        self.book = Book.objects.create(
            title="Atomic Habits",
            description="A book about habits",
            author="James Clear",
            isbn="9780735211292",
            published_date="2018-01-01"
        )

    def test_create_book(self):
        data = {
            "title": "The Great Gatsby",
            "description": "Classic novel",
            "author": "F. Scott Fitzgerald",
            "isbn": "1234567890123",
            "published_date": "1925-04-10"
        }

        response = self.client.post(
            "/api/books/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertEqual(
            Book.objects.count(),
            2
        )


    def test_get_books(self):
        response = self.client.get("/api/books/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            len(response.data),
            1
        )


    def test_get_single_book(self):
        response = self.client.get(f"/api/books/{self.book.id}/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data["title"],
            "Atomic Habits"
        )


    def test_get_missing_book_returns_404(self):
        response = self.client.get("/api/books/9999/")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND
        )


    def test_update_book(self):
        data = {
            "title": "Atomic Habits Updated",
            "description": "Updated description",
            "author": "James Clear",
            "isbn": "9780735211292",
            "published_date": "2018-01-01"
        }

        response = self.client.put(
            f"/api/books/{self.book.id}/",
            data,
            format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.book.refresh_from_db()

        self.assertEqual(
            self.book.title,
            "Atomic Habits Updated"
        )


    def test_delete_book(self):
        response = self.client.delete(
            f"/api/books/{self.book.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT
        )

        self.assertEqual(
            Book.objects.count(),
            0
        )


class BookValidationTest(APITestCase):
    """The serializer rules: ISBN format, published date and title."""

    def setUp(self):
        self.book = Book.objects.create(
            title="Atomic Habits",
            description="A book about habits",
            author="James Clear",
            isbn="9780735211292",
            published_date="2018-01-01"
        )

        self.payload = {
            "title": "New Book",
            "description": "",
            "author": "Some Author",
            "isbn": "1234567890123",
            "published_date": "2020-05-01"
        }

    def post(self, **overrides):
        return self.client.post(
            "/api/books/",
            {**self.payload, **overrides},
            format="json"
        )

    def test_hyphenated_isbn_is_normalised(self):
        response = self.post(isbn="978-0-306-40615-7")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertEqual(
            response.data["isbn"],
            "9780306406157"
        )


    def test_isbn_of_wrong_length_is_rejected(self):
        response = self.post(isbn="12345")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("isbn", response.data)


    def test_non_numeric_isbn_is_rejected(self):
        response = self.post(isbn="ABCDEFGHIJ")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("isbn", response.data)


    def test_duplicate_isbn_is_rejected(self):
        response = self.post(isbn="9780735211292")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("isbn", response.data)


    def test_hyphenated_duplicate_isbn_is_rejected(self):
        """A duplicate must be caught even when written with separators."""
        response = self.post(isbn="978-0-7352-1129-2")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("isbn", response.data)


    def test_future_published_date_is_rejected(self):
        tomorrow = date.today() + timedelta(days=1)

        response = self.post(published_date=tomorrow.isoformat())

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("published_date", response.data)


    def test_blank_title_is_rejected(self):
        response = self.post(title="   ")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn("title", response.data)


    def test_title_whitespace_is_trimmed(self):
        response = self.post(title="  Padded Title  ")

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertEqual(
            response.data["title"],
            "Padded Title"
        )


class HealthCheckTest(APITestCase):

    def test_health_endpoint(self):
        response = self.client.get("/health/")

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data,
            {"status": "ok"}
        )
