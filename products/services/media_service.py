from django.core.files.storage import default_storage
from rest_framework.exceptions import ValidationError

class MediaService:
    @staticmethod
    def upload_product_media(file_obj):
        """Uploads a product file/image to default_storage (Cloudinary) and returns its URL."""
        if not file_obj:
            raise ValidationError({"error": "No file provided"})

        file_name = default_storage.save(f"travelkart/products/{file_obj.name}", file_obj)
        file_url = default_storage.url(file_name)
        return {
            "message": "Upload successful",
            "image_url": file_url
        }
