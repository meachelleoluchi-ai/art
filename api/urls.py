from django.urls import path
from .views import BookView, BookDetailView

urlpatterns = [
    path('books/', BookView.as_view(), name='book-list'),
    path('books/<int:pk>/', BookDetailView.as_view(), name='book-detail'),
]