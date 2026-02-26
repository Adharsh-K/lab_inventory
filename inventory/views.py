from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied

from .models import  Category, Request, RequestItem
from .serializers import ItemRequestSerializer
from .models import Component as Item  # Assuming your Component model is the one representing inventory items
from .serializers import  ItemSerializer  # Serializer for listing/creating items

# Get the active User model
User = get_user_model()

# ==========================================
# 🌐 WEB VIEWS (Student Portal)
# ==========================================

@login_required
def dashboard(request):
    """View for students to see their own request history."""
    my_requests = Request.objects.filter(student=request.user).order_by('-requested_at')
    return render(request, 'inventory/dashboard.html', {'my_requests': my_requests})

@login_required
def new_request(request):
    """View for students to submit a new component request."""
    components = Component.objects.filter(available_quantity__gt=0)
    
    if request.method == 'POST':
        names = request.POST.getlist('component_name[]')
        quantities = request.POST.getlist('quantity[]')
        
        new_req = Request.objects.create(student=request.user)
        
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
                    continue 
                    
        return redirect('dashboard')

    return render(request, 'inventory/new_request.html', {'components': components})


def signup(request):
    """Student registration view with Student ID support."""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        full_name = request.POST.get('name')
        # 1. Grab the roll number from the form
        roll_no = request.POST.get('student_id') 
        
        if User.objects.filter(username=email).exists():
            return render(request, 'registration/signup.html', {'error': 'Email already registered'})

        # 2. Create the User with the correct role
        user = User.objects.create_user(
            username=email, 
            email=email, 
            password=password,
            first_name=full_name,
            role='student' # Matches your users_user table structure
        )
        
        # 3. Create the linked Student profile entry
        # This is where the actual ID is stored for your audit/history
        from .models import Student
        Student.objects.create(user=user, student_id_code=roll_no)

        login(request, user)
        return redirect('dashboard')
        
    return render(request, 'registration/signup.html')


# ==========================================
# 📱 API VIEWS (Flutter Incharge App)
# ==========================================

class CustomAuthToken(ObtainAuthToken):
    """Login endpoint that restricts access to Incharges (is_staff) only."""
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        if not user.is_staff:
            raise PermissionDenied("Access denied. Only IdeaLab Incharges can log in.")

        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'is_staff': user.is_staff
        })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_list(request):
    """Fetch all requests for the Incharge app's list views."""
    requests = Request.objects.all().order_by('-requested_at')
    serializer = ItemRequestSerializer(requests, many=True)
    return Response(serializer.data)

@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_request_status(request, pk):
    item_request = get_object_or_404(Request, pk=pk)
    new_status = request.data.get('status')
    
    # Map from Flutter: {"0": 5, "1": 2} (Index: Quantity)
    data_map = request.data.get('issued_items')

    if not new_status:
        return Response({"error": "No status provided"}, status=400)

    # --- FLOW A: ISSUING ---
    if new_status == 'collected' and item_request.status != 'collected':
        items = RequestItem.objects.filter(request=item_request).order_by('id')
        for index, item in enumerate(items):
            final_qty = item.quantity 
            if data_map and str(index) in data_map:
                final_qty = int(data_map[str(index)])
            
            item.issued_quantity = final_qty 
            item.save()

            # Deduct from master stock
            component = item.component
            component.available_quantity -= final_qty
            component.save()

        item_request.status = new_status
        item_request.save()

    # --- FLOW B: RETURNING (Handles Partial Returns) ---
    elif new_status == 'processing_return' and data_map:
        items = RequestItem.objects.filter(request=item_request).order_by('id')
        all_returned = True
        
        for index, item in enumerate(items):
            qty_returned_now = int(data_map.get(str(index), 0))
            
            if qty_returned_now > 0:
                # Add back to master inventory
                comp = item.component
                comp.available_quantity += qty_returned_now
                comp.save()

                # Update RequestItem (Cumulative)
                item.returned_quantity = (item.returned_quantity or 0) + qty_returned_now
                item.save()

            # Check if this item still has a balance
            if item.returned_quantity < item.issued_quantity:
                all_returned = False

        # If everything is back, mark 'returned', otherwise keep 'collected'
        item_request.status = 'returned' if all_returned else 'collected'
        item_request.save()

    # --- FALLBACK: Simple Changes ---
    else:
        item_request.status = new_status
        item_request.save()

    return Response({
        "message": "Update successful", 
        "current_status": item_request.status
    }, status=200)

# inventory/views.py

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_history(request):
    """Advanced filtering for audit and history."""
    queryset = Request.objects.all().order_by('-requested_at')
    
    # 1. Filter by Student ID
    student_id = request.query_params.get('student_id')
    if student_id:
        queryset = queryset.filter(student__username=student_id)
        
    # 2. Filter by Date Range (YYYY-MM-DD)
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    if start_date and end_date:
        queryset = queryset.filter(requested_at__date__range=[start_date, end_date])

    serializer = ItemRequestSerializer(queryset, many=True)
    return Response(serializer.data)

# inventory/views.py
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Request
from .serializers import ItemRequestSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_history(request):
    """View to handle audit logs with date filtering."""
    # Start with all requests, newest first
    queryset = Request.objects.all().order_by('-requested_at')
    
    # 1. Get parameters from Flutter (?start_date=...&end_date=...)
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    
    # 2. Apply filtering if dates are provided
    if start_date and end_date:
        # We use __date__ to ignore the time part of the timestamp
        queryset = queryset.filter(requested_at__date__range=[start_date, end_date])

    serializer = ItemRequestSerializer(queryset, many=True)
    return Response(serializer.data)

from django.db.models import Q # Add this import at the top
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Request , Component
from .serializers import ItemRequestSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_history(request):
    """Handles filtered audit logs for the Incharge."""
    # Start with all requests
    queryset = Request.objects.all().order_by('-requested_at')
    
    # 1. Get search parameters from Flutter
    search_query = request.query_params.get('student_id')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')

    # 2. Dynamic Search (ID or Name)
    if search_query:
        queryset = queryset.filter(
            Q(student__student_profile__student_id_code__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query)
        )

    # 3. Date Range Filtering
    if start_date and end_date:
        queryset = queryset.filter(requested_at__date__range=[start_date, end_date])

    serializer = ItemRequestSerializer(queryset, many=True)
    return Response(serializer.data)

@api_view(['GET', 'POST'])
def item_list_create(request):
    if request.method == 'GET':
        items = Item.objects.all()
        serializer = ItemSerializer(items, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        # --- DEBUG START ---
        from .models import Category
        existing_ids = list(Category.objects.values_list('id', flat=True))
        print(f"DEBUG: All Category IDs in DB: {existing_ids}")
        print(f"DEBUG: Flutter sent Category ID: {request.data.get('category')}")
        # --- DEBUG END ---
        serializer = ItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(available_quantity=request.data.get('total_quantity'))
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)
    
@api_view(['GET'])
def get_categories(request):
    categories = Category.objects.all()
    # Simple manual serialization or use a CategorySerializer
    data = [{"id": cat.id, "name": cat.name} for cat in categories]
    return Response(data)
@api_view(['POST'])
def add_category(request):
    name = request.data.get('name')
    if name:
        category, created = Category.objects.get_or_create(name=name)
        if created:
            return Response({"id": category.id, "name": category.name}, status=201)
        return Response({"error": "Already exists"}, status=400)
    return Response({"error": "Name required"}, status=400)