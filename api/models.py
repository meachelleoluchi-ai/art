from django.db import models

# Create your models here.
class Book(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    author = models.CharField(max_length=255)     
    isbn = models.CharField(max_length=17, unique=True)
    published_date = models.DateField()

    def __str__(self):
        return self.title