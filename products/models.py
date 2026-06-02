from django.db import models

# Create your models here.
class Category(models.Model):

    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    description= models.TextField(blank=True,null=True)
    is_active= models.BooleanField(default=False)

    def __str__(self):
        return self.name