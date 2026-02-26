# inventory/serializers.py
from rest_framework import serializers
from .models import Request, RequestItem

class RequestItemSerializer(serializers.ModelSerializer):
    
    # This grabs the 'name' from the related Component model
    item_name = serializers.ReadOnlyField(source='component.name') 

    class Meta:
        model = RequestItem
        # Add 'item_name' to the fields list
        fields = ['component', 'item_name', 'quantity','issued_quantity', 'returned_quantity']

class ItemRequestSerializer(serializers.ModelSerializer):
    # This pulls all linked items into the single JSON response
    student_id = serializers.ReadOnlyField(source='student.student_profile.student_id_code')
    items = RequestItemSerializer(many=True, read_only=True)
    student_name = serializers.CharField(source='student.first_name', read_only=True)

    class Meta:
        model = Request
        fields = ['id', 'student_name', 'student_id', 'status', 'items',]

from .models import Component as Item  # Ensure you import your Item model

from .models import Component
        
from django.db.models import Sum
from rest_framework import serializers
from .models import  Request

from rest_framework import serializers
from .models import Component, Category # Ensure these are imported

class ItemSerializer(serializers.ModelSerializer):
    # 1. Define custom fields
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    category_name = serializers.CharField(source='category.name', read_only=True)
    available_quantity = serializers.IntegerField(required=False)

    # 2. REQUIRED: The Meta class tells Django which model this is for
    class Meta:
        model = Component  # or 'Item' if you imported it as such
        fields = [
            'id', 
            'name', 
            'category', 
            'category_name', 
            'total_quantity', 
            'available_quantity'
        ]

    # 3. Dynamic initialization to prevent the "ID 5 not found" error
    def __init__(self, *args, **kwargs):
        super(ItemSerializer, self).__init__(*args, **kwargs)
        # This refreshes the category list every time the form is opened
        self.fields['category'].queryset = Category.objects.all()

    def create(self, validated_data):
        # Default available_quantity to total_quantity if not provided
        if 'available_quantity' not in validated_data:
            validated_data['available_quantity'] = validated_data.get('total_quantity')
        return super().create(validated_data)