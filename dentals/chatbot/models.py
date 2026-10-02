from django.db import models


class Enquiry(models.Model):
    name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    message = models.TextField()
    intent = models.CharField(max_length=80, blank=True)
    urgency = models.CharField(max_length=30, default="low")
    response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.id} - {self.intent or 'enquiry'}"


class AppointmentRequest(models.Model):
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=30)
    treatment = models.CharField(max_length=200, blank=True)
    preferred_date = models.CharField(max_length=100)
    preferred_time = models.CharField(max_length=100)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=30, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Appointment #{self.id} - {self.name}"


class SymptomAssessment(models.Model):
    session_key = models.CharField(max_length=100, blank=True)
    symptoms = models.TextField()
    possible_conditions = models.JSONField(default=list)
    red_flags = models.JSONField(default=list)
    urgency = models.CharField(max_length=30, default="low")
    advice = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Assessment #{self.id} - {self.urgency}"


class ChatMessage(models.Model):
    session_key = models.CharField(max_length=100, blank=True)
    role = models.CharField(max_length=20)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.role}: {self.message[:40]}"
