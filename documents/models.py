from django.db import models
import uuid


class Document(models.Model):
    """Represents an uploaded file (image or PDF)."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("extracted", "Extracted"),
        ("reviewed", "Reviewed"),
        ("failed", "Failed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to="uploads/%Y/%m/%d/")
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10)  # 'image' or 'pdf'
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.original_filename} ({self.status})"


class ExtractedRecord(models.Model):
    """Structured data extracted from a Document by Gemini."""

    SHIFT_CHOICES = [
        ("A", "Shift A"),
        ("B", "Shift B"),
        ("C", "Shift C"),
        ("", "Unknown"),
    ]

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, related_name="records"
    )

    # Core extracted fields
    date = models.DateField(null=True, blank=True)
    shift = models.CharField(max_length=5, choices=SHIFT_CHOICES, blank=True)
    employee_number = models.CharField(max_length=50, blank=True)
    operation_code = models.CharField(max_length=50, blank=True)
    machine_number = models.CharField(max_length=50, blank=True)
    work_order_number = models.CharField(max_length=100, blank=True)
    quantity_produced = models.IntegerField(null=True, blank=True)
    time_taken = models.FloatField(null=True, blank=True, help_text="In hours")
    row_number = models.IntegerField(default=1)

    # Raw Gemini response for debugging/audit
    raw_extraction = models.JSONField(default=dict, blank=True)

    # Overall confidence (0.0 – 1.0) averaged across fields
    overall_confidence = models.FloatField(default=0.0)

    # Validation
    has_validation_errors = models.BooleanField(default=False)
    validation_errors = models.JSONField(default=list, blank=True)

    # Review state
    is_reviewed = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Record for {self.document.original_filename}"


class FieldConfidence(models.Model):
    """Per-field confidence score from Gemini extraction."""

    record = models.ForeignKey(
        ExtractedRecord, on_delete=models.CASCADE, related_name="field_confidences"
    )
    field_name = models.CharField(max_length=100)
    confidence = models.FloatField()  # 0.0 – 1.0
    raw_value = models.CharField(max_length=500, blank=True)  # what Gemini saw
    is_uncertain = models.BooleanField(default=False)  # True if confidence < 0.6

    def save(self, *args, **kwargs):
        self.is_uncertain = self.confidence < 0.6
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.field_name}: {self.confidence:.0%}"