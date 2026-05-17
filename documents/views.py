from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from django.db.models import Q

import os
import logging

from .models import Document, ExtractedRecord, FieldConfidence
from .services import extract_document_data

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE_MB = 10


# ─── Upload ───────────────────────────────────────────────────────────────────

def upload(request):
    if request.method == "POST":
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            messages.error(request, "No file was uploaded.")
            return render(request, "documents/upload.html")

        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            messages.error(request, f"Unsupported file type '{ext}'. Please upload a PDF, JPG, or PNG.")
            return render(request, "documents/upload.html")

        if uploaded_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
            messages.error(request, f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB}MB.")
            return render(request, "documents/upload.html")

        file_type = "pdf" if ext == ".pdf" else "image"

        document = Document.objects.create(
            file=uploaded_file,
            original_filename=uploaded_file.name,
            file_type=file_type,
            status="pending",
        )

        result = extract_document_data(document)

        if not result:
            messages.warning(request, "File uploaded but extraction failed. You can manually enter the data below.")
            if not ExtractedRecord.objects.filter(document=document).exists():
                ExtractedRecord.objects.create(document=document)
        else:
            if isinstance(result, list):
                messages.success(request, f"Document uploaded. {len(result)} row(s) detected — please review and correct the extracted data below.")
            else:
                messages.success(request, "Document uploaded and processed successfully.")

        return redirect("documents:review", pk=document.pk)

    return render(request, "documents/upload.html")


# ─── Document List ────────────────────────────────────────────────────────────

def document_list(request):
    queryset =Document.objects.all().prefetch_related("records")

    search_query = request.GET.get("search", "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(original_filename__icontains=search_query) |
            Q(records__work_order_number__icontains=search_query) |
            Q(records__machine_number__icontains=search_query)
        ).distinct()

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "status_filter": status_filter,
        "status_choices": Document.STATUS_CHOICES,
        "total_count": queryset.count(),
    }
    return render(request, "documents/document_list.html", context)


# ─── Document Detail ──────────────────────────────────────────────────────────

def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
    record = ExtractedRecord.objects.filter(document=document).first()
    field_confidences = {}
    if record:
        for fc in record.field_confidences.all():
            field_confidences[fc.field_name] = fc

    context = {
        "document": document,
        "record": record,
        "field_confidences": field_confidences,
    }
    return render(request, "documents/document_detail.html", context)


# ─── Review ───────────────────────────────────────────────────────────────────

def review(request, pk):
    document = get_object_or_404(Document, pk=pk)
    record = ExtractedRecord.objects.filter(document=document).first()
    if not record:
        record = ExtractedRecord.objects.create(document=document)

    field_confidences = {fc.field_name: fc for fc in record.field_confidences.all()}

    if request.method == "POST":
        record.date = request.POST.get("date") or None
        record.shift = request.POST.get("shift", "").strip().upper()
        record.employee_number = request.POST.get("employee_number", "").strip()
        record.operation_code = request.POST.get("operation_code", "").strip()
        record.machine_number = request.POST.get("machine_number", "").strip()
        record.work_order_number = request.POST.get("work_order_number", "").strip()
        record.reviewer_notes = request.POST.get("reviewer_notes", "").strip()

        try:
            record.quantity_produced = int(request.POST.get("quantity_produced", "").strip())
        except (ValueError, TypeError):
            record.quantity_produced = None

        try:
            record.time_taken = float(request.POST.get("time_taken", "").strip())
        except (ValueError, TypeError):
            record.time_taken = None

        from .services import _validate_record
        errors = _validate_record(record)
        record.has_validation_errors = bool(errors)
        record.validation_errors = errors
        record.is_reviewed = True
        record.reviewed_at = timezone.now()
        record.save()

        document.status = "reviewed"
        document.save()

        if errors:
            messages.warning(request, f"Record saved with {len(errors)} validation issue(s). Please check highlighted fields.")
        else:
            messages.success(request, "Record reviewed and saved successfully.")

        return redirect("documents:document_detail", pk=document.pk)

    context = {
        "document": document,
        "record": record,
        "field_confidences": field_confidences,
        "shift_choices": ExtractedRecord.SHIFT_CHOICES,
        "validation_error_map": {e["field"]: e["message"] for e in record.validation_errors},
    }
    return render(request, "documents/review.html", context)


# ─── Re-extract ───────────────────────────────────────────────────────────────

@require_POST
def re_extract(request, pk):
    document = get_object_or_404(Document, pk=pk)
    ExtractedRecord.objects.filter(document=document).delete()
    document.status = "pending"
    document.save()

    result = extract_document_data(document)

    if not result:
        messages.error(request, "Re-extraction failed. Please review manually.")
    else:
        if isinstance(result, list):
            messages.success(request, f"Re-extraction completed. {len(result)} records extracted.")
        else:
            messages.success(request, "Re-extraction completed successfully.")

    return redirect("documents:review", pk=document.pk)


# ─── Delete Document ──────────────────────────────────────────────────────────

@require_POST
def delete_document(request, pk):
    document = get_object_or_404(Document, pk=pk)
    if document.file and os.path.exists(document.file.path):
        try:
            os.remove(document.file.path)
        except OSError as e:
            logger.warning(f"Could not delete file {document.file.path}: {e}")

    document.delete()
    messages.success(request, f"Document '{document.original_filename}' deleted.")
    return redirect("documents:document_list")


# ─── AJAX Status ──────────────────────────────────────────────────────────────

def extraction_status(request, pk):
    document = get_object_or_404(Document, pk=pk)
    record = ExtractedRecord.objects.filter(document=document).first()
    data = {
        "status": document.status,
        "processed_at": document.processed_at.isoformat() if document.processed_at else None,
    }
    if record:
        data["has_record"] = True
        data["overall_confidence"] = record.overall_confidence
        data["has_validation_errors"] = record.has_validation_errors
    else:
        data["has_record"] = False

    return JsonResponse(data)