from django.urls import path, include

urlpatterns = [
    path('auth/', include('accounts.urls')),
    
    # User routes
    path('user/', include('products.user_urls')),
    
    # Admin routes
    path('admin/', include('admin_panel.urls')),
    path('admin/', include('products.admin_urls')),

    #wishlist routes
    path('wishlist/', include('wishlist.urls')),

    #cart routes
    path('cart/', include('cart.urls')),

    #order routes
    path('orders/',include('orders.urls')),

    #promotion routes
    path('promotions/',include('promotions.urls')),

    #wallet routes
    path('wallet/',include('wallet.urls')),

    #reviews routes
    path('reviews/',include('reviews.urls')),
]