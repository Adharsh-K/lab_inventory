from django.db import models
from django.conf import settings
from django.forms import ValidationError

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Component(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    total_quantity = models.IntegerField()
    available_quantity = models.IntegerField()

    class Meta:
        verbose_name_plural = "Components"

    def __str__(self):
        return self.name


class Request(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('collected', 'Collected'),
        ('Processing_return', 'Processing_return'),
        ('returned', 'Returned'),
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requests'
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_requests'
    )
    

    requested_at = models.DateTimeField(auto_now_add=True)
    collected_at = models.DateTimeField(null=True, blank=True)
    return_deadline = models.DateField(null=True, blank=True)
    return_date = models.DateTimeField(null=True, blank=True)
    class Meta:
        verbose_name_plural = "Requests"

    def __str__(self):
        return f"Request #{self.id} by {self.student.username}"


class RequestItem(models.Model):
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='items')
    component = models.ForeignKey(Component, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField() # What the student wants
    issued_quantity = models.PositiveIntegerField(default=0) # What they actually got
    quantity = models.PositiveIntegerField() # Requested
    issued_quantity = models.PositiveIntegerField(default=0) # Given by incharge
    returned_quantity = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.component.name} (Issued: {self.issued_quantity}, Returned: {self.returned_quantity})"
    
# inventory/models.py
from django.conf import settings

class Student(models.Model):
    # This links to your users_user table
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='student_profile'
    )
    # This is the "ID" you want to search by (e.g., Roll No)
    student_id_code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.student_id_code} - {self.user.first_name}"

from django.db.models.signals import post_save
from django.dispatch import receiver

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Request, RequestItem
