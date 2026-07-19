from django.test import TestCase
from django.urls import reverse
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