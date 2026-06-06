from django.urls import path, include

urlpatterns = [
    path('auth/', include('accounts.urls')),
    
    # User routes
    path('user/', include('products.user_urls')),
    
    # Admin routes
    path('admin/', include('admin_panel.urls')),
    path('admin/', include('products.admin_urls')),
]