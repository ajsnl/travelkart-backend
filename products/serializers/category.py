from rest_framework import serializers
from products.models import Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = [
            'id',
            'name',
            'slug',
            'description',
            'parent',
            'is_active',
            'created_at'
        ]
        read_only_fields = ['id']

    def validate_name(self, value):
        qs = Category.objects.filter(is_deleted=False, name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A category with this name already exists (case-insensitive check).")
        return value
