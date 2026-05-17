import re
import json
import logging
import traceback
from pathlib import Path

from google import genai
from google.genai import types

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# ─── Gemini Setup ────────────────────────────────────────────────────────────
GEMINI_AVAILABLE = False
client = None
MODEL_NAME = "gemini-flash-latest"

if hasattr(settings, 'GEMINI_API_KEY') and settings.GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
        print(f"[ShiftLog] Gemini ready: {MODEL_NAME}")
    except Exception as e:
        print(f"[ShiftLog] Gemini error: {e}")
else:
    print("[ShiftLog] GEMINI_API_KEY not set.")


# ─── Core Extraction Function ─────────────────────────────────────────────────
def extract_document_data(document):
    """
    Main entry point. Uses Gemini to extract fields.
    Handles multi-row tables (returns a list of records) as well as single forms.
    """
    from .models import ExtractedRecord, FieldConfidence

    if not GEMINI_AVAILABLE:
        logger.error("Gemini not available — cannot extract.")
        document.status = "failed"
        document.save()
        return None

    document.status = "processing"
    document.save()

    try:
        file_path = document.file.path
        raw_json = _call_gemini(file_path, document.file_type)

        if raw_json is None:
            raise ValueError("Gemini returned no usable response.")

        parsed = _parse_gemini_response(raw_json)
        # Removed debug prints: print("=== PARSED ==="), print(parsed), print("=== END PARSED ===")

        rows = parsed.get("rows") if isinstance(parsed, dict) else None

        if rows is not None:
            # Multi-row table document
            records = []
            for row_data in rows:
                if not row_data:
                    continue
                record = _build_record(document, row_data)
                errors = _validate_record(record)
                record.has_validation_errors = bool(errors)
                record.validation_errors = errors
                record.raw_extraction = row_data
                record.save()
                _save_field_confidences(record, row_data)
                records.append(record)

            document.status = "extracted"
            document.processed_at = timezone.now()
            document.save()
            return records if records else None

        else:
            # Single form document (if Gemini ever returns a single object without "rows")
            record = _build_record(document, parsed)
            errors = _validate_record(record)
            record.has_validation_errors = bool(errors)
            record.validation_errors = errors
            record.raw_extraction = parsed
            record.save()
            _save_field_confidences(record, parsed)
            document.status = "extracted"
            document.processed_at = timezone.now()
            document.save()
            return record

    except Exception as e:
        logger.error(f"Extraction failed for document {document.id}: {e}")
        traceback.print_exc()
        document.status = "failed"
        document.save()
        return None


# ─── Gemini API Call ──────────────────────────────────────────────────────────
def _call_gemini(file_path, file_type):
    """
    Send file to Gemini and return the raw text (should be a JSON string).
    """
    ext = Path(file_path).suffix.lower()
    if file_type == "pdf" or ext == ".pdf":
        mime_type = "application/pdf"
    elif ext == ".png":
        mime_type = "image/png"
    else:
        mime_type = "image/jpeg"

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
            """Extract all rows from this manufacturing log sheet as JSON.
Return ONLY this structure, no markdown:
{
  "rows": [
    {
      "date": "YYYY-MM-DD or null",
      "shift": "A or B or C or null",
      "employee_number": "string or null",
      "operation_code": "string or null",
      "machine_number": "string or null",
      "work_order_number": "string or null",
      "quantity_produced": integer or null,
      "time_taken": float or null
    }
  ]
}"""
        ]
    )
    return response.text


# ─── JSON Parsing ─────────────────────────────────────────────────────────────
def _parse_gemini_response(raw_text):
    """Clean and parse the JSON response from Gemini."""
    cleaned = re.sub(r"```(?:json)?", "", raw_text).strip().rstrip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    logger.error(f"Could not parse response as JSON: {raw_text[:200]}")
    return {}


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _normalise_date(raw):
    from dateutil.parser import parse
    try:
        dt = parse(raw, dayfirst=False)
        return dt.strftime('%Y-%m-%d')
    except Exception:
        return raw


# ─── Record Builder (handles both flat Gemini and old nested format) ──────────
def _build_record(document, parsed):
    from .models import ExtractedRecord
    import datetime

    # Helper: if the value is a dict (old OCR format), extract "value"; else return directly
    def get_val(d, key):
        v = d.get(key)
        if isinstance(v, dict):
            return v.get("value")
        return v

    date_value = None
    raw_date = get_val(parsed, "date")
    if raw_date:
        try:
            date_value = datetime.date.fromisoformat(str(raw_date))
        except (ValueError, TypeError):
            pass

    quantity = None
    raw_qty = get_val(parsed, "quantity_produced")
    if raw_qty is not None:
        try:
            quantity = int(raw_qty)
        except (ValueError, TypeError):
            pass

    time_taken = None
    raw_time = get_val(parsed, "time_taken")
    if raw_time is not None:
        try:
            time_taken = float(raw_time)
        except (ValueError, TypeError):
            pass

    shift_raw = str(get_val(parsed, "shift") or "").upper().strip()
    shift = shift_raw if shift_raw in ["A", "B", "C"] else ""

    # Gemini doesn't return per‑field confidence — use 0.9 as default
    overall_confidence = float(parsed.get("overall_confidence", 0.9))

    return ExtractedRecord.objects.create(
        document=document,
        date=date_value,
        shift=shift,
        employee_number=str(get_val(parsed, "employee_number") or ""),
        operation_code=str(get_val(parsed, "operation_code") or ""),
        machine_number=str(get_val(parsed, "machine_number") or ""),
        work_order_number=str(get_val(parsed, "work_order_number") or ""),
        quantity_produced=quantity,
        time_taken=time_taken,
        overall_confidence=overall_confidence,
    )


# ─── Field Confidences (adapted for flat dict) ────────────────────────────────
def _save_field_confidences(record, parsed):
    from .models import FieldConfidence
    tracked = [
        "date", "shift", "employee_number", "operation_code",
        "machine_number", "work_order_number", "quantity_produced", "time_taken"
    ]
    for field in tracked:
        val = parsed.get(field)
        if isinstance(val, dict):
            # Old nested format
            confidence = val.get("confidence", 0.9)
            raw_value = str(val.get("value") or "")
        else:
            # Flat Gemini format
            confidence = 0.9 if val is not None else 0.0
            raw_value = str(val or "")
        FieldConfidence.objects.create(
            record=record,
            field_name=field,
            confidence=confidence,
            raw_value=raw_value,
        )


# ─── Validation (unchanged) ───────────────────────────────────────────────────
VALID_SHIFTS = {"A", "B", "C"}
MACHINE_CODE_PATTERN = re.compile(r'^[A-Z]{1,4}-?\d{1,6}$', re.IGNORECASE)
MAX_REASONABLE_QUANTITY = 100000
MAX_REASONABLE_HOURS = 24


def _validate_record(record):
    errors = []
    if not record.date:
        errors.append({"field": "date", "message": "Date is missing or could not be parsed."})
    if not record.shift:
        errors.append({"field": "shift", "message": "Shift value is missing or invalid (must be A, B, or C)."})
    if not record.employee_number:
        errors.append({"field": "employee_number", "message": "Employee number is missing."})
    if not record.work_order_number:
        errors.append({"field": "work_order_number", "message": "Work order number is missing."})
    if record.quantity_produced is None:
        errors.append({"field": "quantity_produced", "message": "Quantity produced is missing."})
    if record.machine_number and not MACHINE_CODE_PATTERN.match(record.machine_number):
        errors.append({
            "field": "machine_number",
            "message": f"Machine number '{record.machine_number}' doesn't match expected format (e.g. MC-001)."
        })
    if record.quantity_produced is not None:
        if record.quantity_produced <= 0:
            errors.append({"field": "quantity_produced", "message": "Quantity produced must be greater than zero."})
        elif record.quantity_produced > MAX_REASONABLE_QUANTITY:
            errors.append({"field": "quantity_produced", "message": f"Quantity {record.quantity_produced} seems suspiciously high."})
    if record.time_taken is not None:
        if record.time_taken <= 0:
            errors.append({"field": "time_taken", "message": "Time taken must be greater than zero."})
        elif record.time_taken > MAX_REASONABLE_HOURS:
            errors.append({"field": "time_taken", "message": f"Time taken {record.time_taken}h exceeds {MAX_REASONABLE_HOURS}h limit."})
    if record.work_order_number:
        from .models import ExtractedRecord
        if ExtractedRecord.objects.filter(work_order_number=record.work_order_number).exclude(pk=record.pk).exists():
            errors.append({"field": "work_order_number", "message": f"Work order '{record.work_order_number}' already exists."})
    return errors