from django.urls import path, include
urlpatterns = [
    path('auth/', include('accounts.urls')),
    path('admin/',include('admin_panel.urls')),
    # path('products/', include('products.urls')),
]