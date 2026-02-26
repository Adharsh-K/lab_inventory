from django.urls import path
from . import views

urlpatterns = [
    # API Endpoints
    path('api/login/', views.CustomAuthToken.as_view(), name='api-login'),
    path('api/requests/', views.request_list, name='api-request-list'),
    path('api/requests/<int:pk>/update/', views.update_request_status, name='api-update-status'),
    path('api/items/', views.item_list_create, name='items'),
    path('api/items/add/', views.item_list_create), # Reusing the same view for POST
    
    # Web Endpoints
    path('dashboard/', views.dashboard, name='dashboard'),
    path('new_request/', views.new_request, name='new_request'),
    path('signup/', views.signup, name='signup'),
    path('api/history/', views.request_history, name='api-history'),
    path('api/categories/', views.get_categories, name='get_categories'),
    path('api/categories/add/', views.add_category, name='add_category'),
]