from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.conf import settings

# India-only E.164: +91 followed by 10 digits
phone_validator = RegexValidator(
    regex=r'^\+91\d{10}$',
    message='Enter a valid Indian phone number in +91XXXXXXXXXX format (10 digits after +91).'
)

class CustomUser(AbstractUser):
    # login stays username/password
    phone_number = models.CharField(
        max_length=13,            # '+91' + 10 digits
        unique=True,
        validators=[phone_validator],
        help_text='Must be +91XXXXXXXXXX'
    )
    display_name = models.CharField(max_length=80)
    # cached lifetime toxicity average (0..1)
    lifetime_toxicity_avg = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.display_name or self.username


class Contact(models.Model):
    class Status(models.TextChoices):
        REQUESTED = 'requested', 'Requested'
        ACCEPTED  = 'accepted',  'Accepted'
        BLOCKED   = 'blocked',   'Blocked'

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='contacts'
    )
    contact = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='contact_of'
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.REQUESTED,
        db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('owner', 'contact')

    def __str__(self):
        return f'{self.owner.username} → {self.contact.username} [{self.status}]'


class CallRecord(models.Model):
    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calls_made'
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='calls_received'
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    avg_toxicity = models.FloatField()  # 0.0 – 1.0
    lang = models.CharField(max_length=20, blank=True, null=True)
    duration_sec = models.IntegerField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['receiver', 'started_at']),
            models.Index(fields=['caller', 'started_at']),
        ]

    def __str__(self):
        return f'{self.caller} → {self.receiver} | {self.avg_toxicity:.2f}'
