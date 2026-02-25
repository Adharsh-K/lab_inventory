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
    items = RequestItemSerializer(many=True, read_only=True)
    student_name = serializers.CharField(source='student.username', read_only=True)

    class Meta:
        model = Request
        fields = ['id', 'student_name', 'status', 'items',]