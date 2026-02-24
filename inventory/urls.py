from django.urls import path
from . import views

urlpatterns = [
    path('signup/', views.signup, name='signup'),
    path('', views.dashboard, name='dashboard'),
    path('new-request/', views.new_request, name='new_request'), # Add this
]