from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Contact, CallRecord

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Profile', {'fields': ('display_name', 'phone_number', 'lifetime_toxicity_avg')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Profile', {'fields': ('display_name', 'phone_number')}),
    )
    list_display = ('username', 'display_name', 'phone_number', 'email', 'lifetime_toxicity_avg', 'is_active', 'is_staff')
    search_fields = ('username', 'display_name', 'phone_number', 'email')

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('owner', 'contact', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('owner__username', 'owner__display_name', 'contact__username', 'contact__display_name')

@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = ('caller', 'receiver', 'avg_toxicity', 'started_at', 'ended_at', 'duration_sec', 'lang')
    list_filter = ('started_at', 'caller', 'receiver')
    search_fields = ('caller__username', 'caller__display_name', 'receiver__username', 'receiver__display_name')
