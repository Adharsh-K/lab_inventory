from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Change 'register' to 'urls'
    path('admin/', admin.site.urls),
    
    # Add this line to handle Login/Logout/Password management
    path('accounts/', include('django.contrib.auth.urls')), 
    
    # Your app URLs
    path('', include('inventory.urls')), 
]