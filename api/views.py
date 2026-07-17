from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Book
from .serializer import BookSerializer

# Create your views here.
class BookView(APIView):
    """ List all books, or create a new book """
    def post(self, request, *args, **kwargs):
        # Instantiate the serializer and pass in the request data sent by the client
        serializer = BookSerializer(data=request.data)
        # Check that the request is valid. e.g.: Was the title provided?, if not autoamtically return an error
        serializer.is_valid(raise_exception=True)
        # Save the new book using the serializer
        serializer.save()
        # Return the serialized JSON object of the created book
        return Response(serializer.data)
       
    def get(self, request, *args, **kwargs):
        # Get all books in the table
        books = Book.objects.all()
        # Serialize the list of books, specify `many=True` to tell the serializer we are passing in a list of books and not a single instance
        serializer = BookSerializer(books, many=True)
        # Return the serialized JSON
        return Response(serializer.data)
    
book_view = BookView.as_view()
