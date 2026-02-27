from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone # --- REQUIRED IMPORT ---

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination

from .models import Category, Request as ItemRequest, RequestItem, Student
from .models import Component as Item 
from .serializers import ItemRequestSerializer, ItemSerializer

# Get the active User model
User = get_user_model()

# ==========================================
# 🌐 WEB VIEWS (Student Portal)
# ==========================================

@login_required
def dashboard(request):
    """View for students to see their own request history."""
    my_requests = ItemRequest.objects.filter(student=request.user).order_by('-requested_at')
    return render(request, 'inventory/dashboard.html', {'my_requests': my_requests})

@login_required
def new_request(request):
    """View for students to submit a new component request."""
    # Using 'Item' as imported above to avoid naming confusion
    components = Item.objects.filter(available_quantity__gt=0)
    
    if request.method == 'POST':
        names = request.POST.getlist('component_name[]')
        quantities = request.POST.getlist('quantity[]')
        
        new_req = ItemRequest.objects.create(student=request.user)
        
        for name, qty in zip(names, quantities):
            if name.strip() and int(qty) > 0:
                try:
                    component = Item.objects.get(name=name)
                    RequestItem.objects.create(
                        request=new_req,
                        component=component,
                        quantity=qty
                    )
                except Item.DoesNotExist:
                    continue 
                    
        return redirect('dashboard')

    return render(request, 'inventory/new_request.html', {'components': components})

def signup(request):
    """Student registration view with Student ID support."""
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        full_name = request.POST.get('name')
        roll_no = request.POST.get('student_id') 
        
        if User.objects.filter(username=email).exists():
            return render(request, 'registration/signup.html', {'error': 'Email already registered'})

        user = User.objects.create_user(
            username=email, 
            email=email, 
            password=password,
            first_name=full_name,
            role='student'
        )
        
        # Create the linked Student profile entry
        Student.objects.create(user=user, student_id_code=roll_no)

        login(request, user)
        return redirect('dashboard')
        
    return render(request, 'registration/signup.html')


# ==========================================
# 📱 API VIEWS (Flutter Incharge App)
# ==========================================

class CustomAuthToken(ObtainAuthToken):
    """Login endpoint for Incharges (is_staff) only."""
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
    """Fetch all requests for the Incharge app's pending list."""
    requests = ItemRequest.objects.all().order_by('-requested_at')
    serializer = ItemRequestSerializer(requests, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def request_history(request):
    """
    PAGINATED History view with filtering.
    This is the final version that handles Search (ID/Name) and Date Range.
    """
    queryset = ItemRequest.objects.all().order_by('-requested_at')
    
    # 1. Get Params from Flutter
    search_query = request.query_params.get('student_id')
    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')

    # 2. Apply Dynamic Filters (Search by Roll No, Name, or Username)
    if search_query:
        queryset = queryset.filter(
            Q(student__student_profile__student_id_code__icontains=search_query) |
            Q(student__first_name__icontains=search_query) |
            Q(student__last_name__icontains=search_query) |
            Q(student__username__icontains=search_query)
        )

    # 3. Apply Date Filtering
    if start_date and end_date:
        queryset = queryset.filter(requested_at__date__range=[start_date, end_date])

    # 4. Pagination (Limit to 15 per page)
    paginator = PageNumberPagination()
    paginator.page_size = 15
    
    result_page = paginator.paginate_queryset(queryset, request)
    if result_page is not None:
        serializer = ItemRequestSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    # Fallback
    serializer = ItemRequestSerializer(queryset, many=True)
    return Response(serializer.data)




@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_request_status(request, pk):
    """Handles Issuing and Returning logic with Stock Management & Timestamps."""
    item_request = get_object_or_404(ItemRequest, pk=pk)
    new_status = request.data.get('status')
    data_map = request.data.get('issued_items')

    if not new_status:
        return Response({"error": "No status provided"}, status=400)

    # --- 1. ISSUING FLOW ---
    if new_status == 'collected' and item_request.status != 'collected':
        item_request.collected_at = timezone.now()
        
        items = RequestItem.objects.filter(request=item_request).order_by('id')
        for index, item in enumerate(items):
            final_qty = item.quantity 
            if data_map and str(index) in data_map:
                final_qty = int(data_map[str(index)])
            
            item.issued_quantity = final_qty 
            item.save()

            component = item.component
            component.available_quantity -= final_qty
            component.save()

        item_request.status = 'collected'
        item_request.save()

    # --- 2. RETURNING FLOW ---
    elif new_status == 'processing_return' and data_map:
        items = RequestItem.objects.filter(request=item_request).order_by('id')
        
        for index, item in enumerate(items):
            qty_returned_now = int(data_map.get(str(index), 0))
            if qty_returned_now > 0:
                current_total_returned = (item.returned_quantity or 0) + qty_returned_now
                
                if current_total_returned <= item.issued_quantity:
                    comp = item.component
                    # Use min to ensure available never exceeds total_quantity
                    comp.available_quantity = min(comp.available_quantity + qty_returned_now, comp.total_quantity)
                    comp.save()

                    item.returned_quantity = current_total_returned
                    item.save()

        # --- NEW LOGIC: Check if everything is back ---
        updated_items = RequestItem.objects.filter(request=item_request)
        # Check if all items that were issued are now fully returned
        all_returned = all(
            (i.returned_quantity or 0) >= (i.issued_quantity or 0) 
            for i in updated_items if (i.issued_quantity or 0) > 0
        )

        if all_returned:
            item_request.status = 'returned'
            item_request.return_date = timezone.now()
        else:
            # Keep it as collected so it stays in the "Active" list in Flutter
            item_request.status = 'collected'
            
        item_request.save()

    # --- 3. OTHER STATUS UPDATES (Rejected, etc.) ---
    else:
        item_request.status = new_status
        item_request.save()

    return Response({
        "message": "Update successful", 
        "current_status": item_request.status,
        "returned_at": item_request.return_date # Helpful for debugging
    }, status=200)
@api_view(['GET', 'POST'])
def item_list_create(request):
    """Inventory Management: View stock or add new items."""
    if request.method == 'GET':
        items = Item.objects.all()
        serializer = ItemSerializer(items, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        serializer = ItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(available_quantity=request.data.get('total_quantity'))
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)

@api_view(['GET'])
def get_categories(request):
    """Returns list of categories for dropdowns."""
    categories = Category.objects.all()
    data = [{"id": cat.id, "name": cat.name} for cat in categories]
    return Response(data)

@api_view(['POST'])
def add_category(request):
    """Adds a new category string to the DB."""
    name = request.data.get('name')
    if name:
        category, created = Category.objects.get_or_create(name=name)
        if created:
            return Response({"id": category.id, "name": category.name}, status=201)
        return Response({"error": "Already exists"}, status=400)
    return Response({"error": "Name required"}, status=400)