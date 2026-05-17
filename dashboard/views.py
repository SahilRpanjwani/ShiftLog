from django.shortcuts import render
from django.db.models import Count, Sum, Avg, Q
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

from documents.models import Document, ExtractedRecord


def dashboard(request):
    """
    Main analytics dashboard.
    All numbers scoped to last 30 days by default,
    with an option to view all-time via ?range=all
    """
    date_range = request.GET.get("range", "30d")

    if date_range == "all":
        qs_docs = Document.objects.all()
        qs_records = ExtractedRecord.objects.all()
    else:
        since = timezone.now() - timedelta(days=30)
        qs_docs = Document.objects.filter(uploaded_at__gte=since)
        qs_records = ExtractedRecord.objects.filter(document__uploaded_at__gte=since)

    # ── Top‑level KPI cards ──────────────────────────────────────────────────
    total_uploads = qs_docs.count()
    total_extracted = qs_docs.filter(status__in=["extracted", "reviewed"]).count()
    total_reviewed = qs_docs.filter(status="reviewed").count()
    total_failed = qs_docs.filter(status="failed").count()
    validation_failures = qs_records.filter(has_validation_errors=True).count()
    pending_review = qs_records.filter(is_reviewed=False).exclude(
        document__status="failed"
    ).count()
    avg_confidence = qs_records.aggregate(avg=Avg("overall_confidence"))["avg"] or 0.0

    # ── Shift‑wise summary ───────────────────────────────────────────────────
    shift_summary = (
        qs_records
        .exclude(shift="")
        .values("shift")
        .annotate(
            count=Count("id"),
            total_quantity=Sum("quantity_produced"),
            avg_time=Avg("time_taken"),
        )
        .order_by("shift")
    )

    # ── Machine‑wise summary (top 10) ────────────────────────────────────────
    machine_summary = (
        qs_records
        .exclude(machine_number="")
        .values("machine_number")
        .annotate(
            count=Count("id"),
            total_quantity=Sum("quantity_produced"),
        )
        .order_by("-total_quantity")[:10]
    )

    # ── Quantity stats ───────────────────────────────────────────────────────
    quantity_stats = qs_records.aggregate(
        total=Sum("quantity_produced"),
        average=Avg("quantity_produced"),
    )

    # ── Uploads over time (last 14 days) ─────────────────────────────────────
    last_14 = timezone.now() - timedelta(days=14)
    uploads_over_time = (
        Document.objects
        .filter(uploaded_at__gte=last_14)
        .annotate(day=TruncDate("uploaded_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    uploads_labels = [str(row["day"]) for row in uploads_over_time]
    uploads_data = [row["count"] for row in uploads_over_time]

    # ── Chart data for Shift / Machine / Status ──────────────────────────────
    shift_labels = [f"Shift {row['shift']}" for row in shift_summary]
    shift_counts = [row["count"] for row in shift_summary]

    machine_labels = [row["machine_number"] for row in machine_summary]
    machine_quantities = [row["total_quantity"] or 0 for row in machine_summary]

    status_breakdown = (
        qs_docs
        .values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )
    status_labels = [row["status"].capitalize() for row in status_breakdown]
    status_counts = [row["count"] for row in status_breakdown]

    # ── Recent activity feed (first record per document) ─────────────────────
    recent_docs = Document.objects.order_by("-uploaded_at")[:8]
    # Prefetch first record for each doc to avoid N+1 queries
    recent_docs = recent_docs.prefetch_related("extracted_records")
    # Attach the first record in Python – template can iterate doc.first_record
    for doc in recent_docs:
        doc.first_record = doc.extracted_records.first()

    context = {
        # KPIs
        "total_uploads": total_uploads,
        "total_extracted": total_extracted,
        "total_reviewed": total_reviewed,
        "total_failed": total_failed,
        "validation_failures": validation_failures,
        "pending_review": pending_review,
        "avg_confidence": round(avg_confidence * 100, 1),

        # Table summaries
        "shift_summary": shift_summary,
        "machine_summary": machine_summary,
        "quantity_stats": quantity_stats,

        # Chart data
        "uploads_labels": uploads_labels,
        "uploads_data": uploads_data,
        "shift_labels": shift_labels,
        "shift_counts": shift_counts,
        "machine_labels": machine_labels,
        "machine_quantities": machine_quantities,
        "status_labels": status_labels,
        "status_counts": status_counts,

        # Activity feed
        "recent_documents": recent_docs,

        # Range toggle
        "date_range": date_range,
    }

    return render(request, "dashboard/dashboard.html", context)


def record_search(request):
    """Search and filter across extracted records."""
    records = ExtractedRecord.objects.select_related("document").order_by("-created_at")

    q = request.GET.get("q", "").strip()
    if q:
        records = records.filter(
            Q(work_order_number__icontains=q) |
            Q(machine_number__icontains=q) |
            Q(employee_number__icontains=q) |
            Q(operation_code__icontains=q) |
            Q(document__original_filename__icontains=q)
        )

    shift = request.GET.get("shift", "").strip().upper()
    if shift in ["A", "B", "C"]:
        records = records.filter(shift=shift)

    reviewed = request.GET.get("reviewed", "").strip()
    if reviewed == "true":
        records = records.filter(is_reviewed=True)
    elif reviewed == "false":
        records = records.filter(is_reviewed=False)

    errors_only = request.GET.get("errors", "").strip()
    if errors_only == "true":
        records = records.filter(has_validation_errors=True)

    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()
    if date_from:
        records = records.filter(date__gte=date_from)
    if date_to:
        records = records.filter(date__lte=date_to)

    from django.core.paginator import Paginator
    paginator = Paginator(records, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "total_count": records.count(),
        "q": q,
        "shift": shift,
        "reviewed": reviewed,
        "errors_only": errors_only,
        "date_from": date_from,
        "date_to": date_to,
    }
    return render(request, "dashboard/record_search.html", context)