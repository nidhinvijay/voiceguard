# core/forms.py
from django.contrib.auth.forms import UserCreationForm
from django import forms
from django.core.exceptions import ValidationError
from .models import CustomUser
import re

PHONE_REGEX = re.compile(r'^\+91\d{10}$')

def normalize_phone(value: str) -> str:
    """Remove spaces/dashes. If 10 digits, prepend +91. Otherwise expect +91XXXXXXXXXX."""
    if not value:
        return value
    v = re.sub(r'[\s\-]', '', value)
    # If user enters 10 digits, assume India and prepend +91
    if re.fullmatch(r'\d{10}', v):
        v = f'+91{v}'
    return v

class SignUpForm(UserCreationForm):
    display_name = forms.CharField(
        max_length=80,
        required=True,
        label="Display name",
        widget=forms.TextInput(attrs={"placeholder": "Your name as others see it"})
    )
    phone_number = forms.CharField(
        max_length=13,
        required=True,
        label="Phone number (+91 only)",
        help_text="Format: +91XXXXXXXXXX",
        widget=forms.TextInput(attrs={"placeholder": "+91XXXXXXXXXX"})
    )
    # AbstractUser already has email; make it optional in the form
    email = forms.EmailField(
        required=False,
        label="Email (optional)",
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com"})
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ("username", "display_name", "phone_number", "email")

    def clean_phone_number(self):
        raw = self.cleaned_data.get("phone_number", "")
        normalized = normalize_phone(raw)
        if not PHONE_REGEX.fullmatch(normalized):
            raise ValidationError("Enter a valid Indian phone number in +91XXXXXXXXXX format.")
        # Uniqueness check (DB constraint also exists)
        if CustomUser.objects.filter(phone_number=normalized).exists():
            raise ValidationError("This phone number is already registered.")
        return normalized

    def save(self, commit=True):
        user = super().save(commit=False)
        user.display_name = self.cleaned_data["display_name"]
        user.phone_number = self.cleaned_data["phone_number"]
        # email stays optional
        user.email = self.cleaned_data.get("email", "")
        if commit:
            user.save()
        return user
