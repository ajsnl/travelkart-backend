from django.db import transaction
from rest_framework.exceptions import ValidationError
from accounts.models import Address

class AddressService:
    @staticmethod
    def create_address(user, serializer):
        """Creates an address, automatically making it the default if it is the first address."""
        with transaction.atomic():
            if not Address.objects.filter(user=user).exists():
                serializer.save(user=user, is_default=True)
                return

            if serializer.validated_data.get('is_default'):
                Address.objects.filter(user=user, is_default=True).update(is_default=False)
            
            serializer.save(user=user)

    @staticmethod
    def update_address(user, address, serializer):
        """Updates an address and handles default flag toggle logic."""
        with transaction.atomic():
            if serializer.validated_data.get('is_default'):
                Address.objects.filter(
                    user=user,
                    is_default=True
                ).exclude(id=address.id).update(is_default=False)

            serializer.save()

    @staticmethod
    def delete_address(address):
        """Validates and deletes the address. Standard users cannot delete their default address."""
        if address.is_default:
            raise ValidationError({"error": "Cannot delete default address"})
        address.delete()

    @staticmethod
    def set_default_address(user, address):
        """Sets a specific address as the default address, clearing other default settings."""
        with transaction.atomic():
            Address.objects.filter(
                user=user,
                is_default=True
            ).update(is_default=False)

            address.is_default = True
            address.save()
