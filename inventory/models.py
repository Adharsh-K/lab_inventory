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
    return_date = models.DateField(null=True, blank=True)
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
    
    

from django.db.models.signals import post_save
from django.dispatch import receiver

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Request, RequestItem

# --- SIGNAL 1: THE COLLECTION (STOCK OUT) ---
@receiver(post_save, sender=Request)
def handle_inventory_collection(sender, instance, **kwargs):
    """
    When status changes to 'collected', subtract the issued_quantity 
    from the component's available stock.
    """
    if instance.status == 'collected' and instance.collected_at is None:
        items = instance.items.all()
        for item in items:
            component = item.component
            component.available_quantity -= item.issued_quantity
            component.save()
        
        # Stamp the collection time so this logic only runs ONCE
        Request.objects.filter(pk=instance.pk).update(collected_at=timezone.now())


# --- SIGNAL 2: THE PARTIAL RETURN (STOCK IN) ---
@receiver(pre_save, sender=RequestItem)
def handle_partial_returns(sender, instance, **kwargs):
    """
    When the Incharge updates the 'returned_quantity', calculate the 
    difference and add it back to the component's available stock.
    """
    if instance.pk:  # Only run if the item already exists in the DB
        try:
            # Get the version currently in the database before the save happens
            previous_item = RequestItem.objects.get(pk=instance.pk)
            
            # Calculate the difference: (New Amount) - (Old Amount)
            # If student brought back 2 and now brings 3 more, total is 5. 
            # Diff = 5 - 2 = 3. We add 3 back to stock.
            diff = instance.returned_quantity - previous_item.returned_quantity
            
            if diff > 0:
                component = instance.component
                component.available_quantity += diff
                component.save()
                
        except RequestItem.DoesNotExist:
            # This handles the rare case where a record might be missing
            pass