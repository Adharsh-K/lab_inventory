from django.contrib import admin
from .models import Component, Request, RequestItem
from django.utils import timezone
from django.contrib import messages
import csv
from django.http import HttpResponse

class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 0
    fields = ['component', 'quantity', 'issued_quantity', 'returned_quantity']
    
    def get_readonly_fields(self, request, obj=None):
        if obj:
            if obj.status == 'returned':
                return ['component', 'quantity', 'issued_quantity', 'returned_quantity']
            if obj.status == 'collected':
                return ['component', 'quantity', 'issued_quantity']
        return ['component', 'quantity', 'returned_quantity']

@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'status', 'return_date', 'requested_at']
    list_filter = ['status', 'requested_at']
    inlines = [RequestItemInline]
    search_fields = ['student__username', 'student__first_name', 'student__email']
    actions = ['export_to_csv'] # Added the action here

    # --- CSV EXPORT FUNCTION ---
    def export_to_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="idealab_requests.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Student', 'Status', 'Request Date', 'Return Date'])
        for obj in queryset:
            writer.writerow([obj.id, obj.student.username, obj.status, obj.requested_at, obj.return_date])
        return response
    export_to_csv.short_description = "Download selected as CSV"

    # --- COMBINED SAVE MODEL ---
    def save_model(self, request, obj, form, change):
        if obj.status == 'returned':
            items = obj.items.all()
            for item in items:
                if item.returned_quantity < item.issued_quantity:
                    obj.status = 'collected'
                    messages.error(request, f"CANNOT RETURN: {item.component.name} is still missing {item.issued_quantity - item.returned_quantity} units!")
                    super().save_model(request, obj, form, change)
                    return 

            if not obj.return_date:
                obj.return_date = timezone.now().date()
        
        super().save_model(request, obj, form, change)

    # --- READONLY FIELDS ---
    def get_readonly_fields(self, request, obj=None):
        if obj:
            if obj.status == 'returned':
                return [f.name for f in self.model._meta.fields] + ['student']
            if obj.status == 'collected':
                return [f.name for f in self.model._meta.fields if f.name not in ['status', 'return_date']]
        return ['collected_at']

    # --- FIELDSETS ---
    def get_fieldsets(self, request, obj=None):
        sections = [
            ('Main Info', {'fields': ('student', 'status')}),
        ]
        if obj and (obj.collected_at or obj.return_date):
            sections.append(('Timestamps', {
                'fields': ('collected_at', 'return_date'),
            }))
        return sections

# Register Component separately
admin.site.register(Component)