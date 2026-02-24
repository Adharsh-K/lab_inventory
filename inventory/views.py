from django.shortcuts import render

from django.contrib.auth.decorators import login_required
from .models import Request, Component

@login_required
def dashboard(request):
    # Get only the requests belonging to the logged-in student
    my_requests = Request.objects.filter(student=request.user).order_by('-requested_at')
    return render(request, 'inventory/dashboard.html', {'my_requests': my_requests})

from django.shortcuts import render, redirect
from .models import Component, Request, RequestItem
from django.contrib.auth.decorators import login_required

@login_required
def new_request(request):
    components = Component.objects.filter(available_quantity__gt=0)
    
    if request.method == 'POST':
        # Grab all rows from the form
        names = request.POST.getlist('component_name[]')
        quantities = request.POST.getlist('quantity[]')
        
        # Create the Request record
        new_req = Request.objects.create(student=request.user)
        
        # Connect each item to the request
        for name, qty in zip(names, quantities):
            if name.strip() and int(qty) > 0:
                try:
                    component = Component.objects.get(name=name)
                    RequestItem.objects.create(
                        request=new_req,
                        component=component,
                        quantity=qty
                    )
                except Component.DoesNotExist:
                    continue # Skip invalid names
                    
        return redirect('dashboard')

    return render(request, 'inventory/new_request.html', {'components': components})
from django.contrib.auth import login, get_user_model # Change this import
from django.shortcuts import render, redirect

# Get the active User model (whether it's the default or your 'users.User')
User = get_user_model()

def signup(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        full_name = request.POST.get('name')
        
        # Check if email/username already exists
        if User.objects.filter(username=email).exists():
            return render(request, 'registration/signup.html', {'error': 'Email already registered'})

        # Create the user using the active model
        # We use email as the username as you requested
        user = User.objects.create_user(
            username=email, 
            email=email, 
            password=password,
            first_name=full_name
        )
        
        # Note: If your custom 'users.User' model has a specific 'class' field,
        # you should set it here. For now, we'll save the user.
        user.save()

        login(request, user)
        return redirect('dashboard')
        
    return render(request, 'registration/signup.html')