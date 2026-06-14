class ProfileService:
    @staticmethod
    def save_profile_picture(user, serializer):
        """Saves new profile picture, deleting the old one if it exists."""
        if user.profile_picture:
            try:
                user.profile_picture.delete(save=False)
            except Exception as e:
                print(f"Error deleting old profile picture: {e}")
        serializer.save()
