class CategoryService:
    @staticmethod
    def soft_delete_category(category):
        category.is_deleted = True
        category.save()
