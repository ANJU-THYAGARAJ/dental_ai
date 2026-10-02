from django.shortcuts import render

# Create your views here.

import json
import os

import cv2
import numpy as np
import pytesseract

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from PIL import Image
from pypdf import PdfReader

from .models import (
    Enquiry,
    AppointmentRequest,
    SymptomAssessment,
    ChatMessage,
)

from ai.groq_service import analyse_message

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)


def home(request):
    return render(request, "dentalcare/home.html")


def enquiry_page(request):
    return render(request, "dentalcare/enquiry.html")


def emergency_page(request):
    return render(request, "dentalcare/emergency.html")


def appointment_page(request):
    return render(request, "dentalcare/appointment.html")


def chatbot_page(request):
    return render(request, "dentalcare/chatbot.html")

def _history(request):
    return request.session.get(
        "dental_history",
        []
    )


def _save_history(request, role, content):

    history = _history(request)

    history.append({
        "role": role,
        "content": content,
    })

    # Keep only latest 12 messages
    request.session["dental_history"] = history[-12:]
    request.session.modified = True


def _is_emergency(result):

    return (
        result.get("urgency") == "emergency"
        or bool(result.get("red_flags"))
    )


@require_http_methods(["POST"])
def chatbot_message(request):

    try:
        data = json.loads(
            request.body or "{}"
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON.",
            },
            status=400,
        )

    message = str(
        data.get("message", "")
    ).strip()

    if not message:

        return JsonResponse(
            {
                "success": False,
                "error": "Message is required.",
            },
            status=400,
        )

    history = _history(request)

    ai_history = history + [
        {
            "role": "user",
            "content": message,
        }
    ]


    try:

        result = analyse_message(
            message,
            ai_history
        )

    except Exception:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "AI service is temporarily unavailable. "
                    "Please try again."
                ),
            },
            status=503,
        )

    reply = result.get(
        "reply",
        "Please tell me more."
    )

    if _is_emergency(result):

        reply += (
            "\n\nBecause you mentioned a possible "
            "emergency warning sign, please seek "
            "urgent professional dental or medical "
            "care rather than relying on this chatbot."
        )

    _save_history(
        request,
        "user",
        message
    )

    _save_history(
        request,
        "assistant",
        reply
    )

    session_key = (
        request.session.session_key or ""
    )

    # Save user chat
    ChatMessage.objects.create(
        session_key=session_key,
        role="user",
        message=message,
    )

    # Save assistant chat
    ChatMessage.objects.create(
        session_key=session_key,
        role="assistant",
        message=reply,
    )
    # Save enquiry
    Enquiry.objects.create(
        message=message,
        intent=result.get("intent", ""),
        urgency=result.get("urgency", "low"),
        response=reply,
    )
    # Save symptom assessment
    symptoms = result.get(
        "symptoms",
        []
    )

    if symptoms:

        SymptomAssessment.objects.create(
            session_key=session_key,
            symptoms=", ".join(symptoms),
            possible_conditions=result.get(
                "possible_conditions",
                []
            ),
            red_flags=result.get(
                "red_flags",
                []
            ),
            urgency=result.get(
                "urgency",
                "low"
            ),
            advice=reply,
        )

    return JsonResponse(
        {
            "success": True,
            "reply": reply,
            "intent": result.get("intent"),
            "symptoms": result.get(
                "symptoms",
                []
            ),
            "possible_conditions": result.get(
                "possible_conditions",
                []
            ),
            "red_flags": result.get(
                "red_flags",
                []
            ),
            "urgency": result.get(
                "urgency",
                "low"
            ),
            "follow_up_questions": result.get(
                "follow_up_questions",
                []
            ),
        }
    )

@require_http_methods(["POST"])
def reset_chat(request):

    request.session["dental_history"] = []
    request.session.modified = True

    return JsonResponse(
        {
            "success": True
        }
    )

def _extract_image_text(image):

    if image.mode != "RGB":
        image = image.convert("RGB")   #ocr

    image_np = np.array(image)

    # RGB -> Gray
    gray = cv2.cvtColor(
        image_np,
        cv2.COLOR_RGB2GRAY
    )

    # Increase resolution
    gray = cv2.resize(
        gray,
        None,
        fx=2,
        fy=2,
        interpolation=cv2.INTER_CUBIC
    )

    # Normalize
    normalized = cv2.normalize(
        gray,
        None,
        0,
        255,
        cv2.NORM_MINMAX
    )

    # Blur
    blurred = cv2.GaussianBlur(
        normalized,
        (3, 3),
        0
    )

    # OTSU
    otsu = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )[1]

    # Adaptive threshold
    adaptive = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11
    )

    processed_images = [
        gray,
        normalized,
        otsu,
        adaptive,
    ]

    configs = [
        "--oem 3 --psm 3",
        "--oem 3 --psm 4",
        "--oem 3 --psm 6",
        "--oem 3 --psm 11",
    ]

    results = []

    for processed_image in processed_images:

        for config in configs:

            try:

                text = pytesseract.image_to_string(
                    processed_image,
                    config=config
                ).strip()

                if text:
                    results.append(text)

            except Exception:
                continue

    if not results:
        return ""

    return max(
        results,
        key=len
    )

@require_http_methods(["POST"])
def upload_chat_file(request):
    # Get uploaded file
    uploaded_file = request.FILES.get("file")

    if not uploaded_file:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Please select a file before "
                    "clicking Upload."
                ),
            },
            status=400,
        )
    allowed_extensions = {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
    }

    extension = os.path.splitext(
        uploaded_file.name
    )[1].lower()

    if extension not in allowed_extensions:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Unsupported file type. "
                    "Please upload PDF, PNG, JPG or JPEG."
                ),
            },
            status=400,
        )

    max_size = 10 * 1024 * 1024

    if uploaded_file.size > max_size:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "File must be smaller than 10 MB."
                ),
            },
            status=400,
        )

    try:

        extracted_text = ""

        if extension == ".pdf":

            reader = PdfReader(
                uploaded_file
            )

            for page in reader.pages:

                page_text = (
                    page.extract_text() or ""
                )

                extracted_text += (
                    page_text + "\n"
                )

        else:

            try:

                image = Image.open(
                    uploaded_file
                )

                extracted_text = _extract_image_text(
                    image
                )

            except pytesseract.TesseractNotFoundError:

                return JsonResponse(
                    {
                        "success": False,
                        "error": (
                            "Tesseract OCR is not installed "
                            "or the configured path is incorrect."
                        ),
                    },
                    status=500,
                )

            except Exception:

                return JsonResponse(
                    {
                        "success": False,
                        "error": (
                            "Unable to process the uploaded image."
                        ),
                    },
                    status=500,
                )
        extracted_text = extracted_text.strip()

      
        if not extracted_text:

            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        "The file was uploaded successfully, "
                        "but no readable text was found."
                    ),
                },
                status=400,
            )

        extracted_text = extracted_text[:12000]
#ai prompt
        document_prompt = f"""
You are DentalCare AI.

The patient uploaded a dental or insurance document.

Analyze the extracted document text and explain the
important information in simple language.

Extract information when available:

- Patient name
- Insurance provider
- Insurance plan
- Member ID
- Policy information
- Treatment or procedure
- Dental conditions
- Dates
- Important instructions

If this is an insurance document:

Do NOT say that insurance coverage is definitely confirmed
unless the document explicitly confirms it.

Coverage depends on the patient's specific policy and
should be verified with the dental clinic or insurance
provider.

If information is missing, clearly mention what is missing.

Do not provide a diagnosis.

DOCUMENT TEXT:

{extracted_text}
"""

        try:

            history = _history(request)

            result = analyse_message(
                document_prompt,
                history
            )

        except Exception:

            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        "The document was read successfully, "
                        "but AI analysis failed."
                    ),
                },
                status=503,
            )

        reply = result.get(
            "reply",
            "The document was analyzed successfully."
        )

        session_key = (
            request.session.session_key or ""
        )

        
        ChatMessage.objects.create(
            session_key=session_key,
            role="user",
            message=(
                f"Uploaded document: "
                f"{uploaded_file.name}"
            ),
        )

      
        ChatMessage.objects.create(
            session_key=session_key,
            role="assistant",
            message=reply,
        )

        _save_history(
            request,
            "user",
            f"Uploaded document: {uploaded_file.name}"
        )

        _save_history(
            request,
            "assistant",
            reply
        )

        
        return JsonResponse(
            {
                "success": True,
                "filename": uploaded_file.name,
                "reply": reply,
            }
        )

    except Exception:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Unable to process the uploaded file."
                ),
            },
            status=500,
        )
# CREATE APPOINTMENT
@require_http_methods(["POST"])
def create_appointment(request):

    try:

        data = json.loads(
            request.body or "{}"
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON.",
            },
            status=400,
        )

    required = [
        "name",
        "phone",
        "preferred_date",
        "preferred_time",
    ]

    missing = [
        field
        for field in required
        if not str(
            data.get(field, "")
        ).strip()
    ]

    if missing:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    f"Please provide: "
                    f"{', '.join(missing)}."
                ),
            },
            status=400,
        )

    appointment = AppointmentRequest.objects.create(

        name=str(
            data.get("name")
        ).strip(),

        phone=str(
            data.get("phone")
        ).strip(),

        treatment=str(
            data.get(
                "treatment",
                ""
            )
        ).strip(),

        preferred_date=str(
            data.get(
                "preferred_date"
            )
        ).strip(),

        preferred_time=str(
            data.get(
                "preferred_time"
            )
        ).strip(),

        notes=str(
            data.get(
                "notes",
                ""
            )
        ).strip(),
    )

    return JsonResponse(
        {
            "success": True,
            "appointment_id": appointment.id,
            "message": (
                f"Appointment request "
                f"#{appointment.id} has been submitted. "
                "The clinic can review and confirm "
                "the requested time."
            ),
        }
    )

# RESCHEDULE APPOINTMENT
@require_http_methods(["GET", "POST"])
def reschedule_appointment(request):

    if request.method == "GET":

        return render(
            request,
            "dentalcare/reschedule_appointment.html"
        )

    try:

        data = json.loads(
            request.body or "{}"
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON.",
            },
            status=400,
        )

    required = [
        "name",
        "phone",
        "appointment_id",
        "new_date",
        "new_time",
    ]

    missing = [
        field
        for field in required
        if not str(
            data.get(field, "")
        ).strip()
    ]

    if missing:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    f"Please provide: "
                    f"{', '.join(missing)}."
                ),
            },
            status=400,
        )

    appointment_id = str(
        data.get("appointment_id")
    ).strip()

    try:

        appointment = (
            AppointmentRequest.objects.get(
                id=appointment_id
            )
        )

    except AppointmentRequest.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Appointment not found. "
                    "Please check your appointment ID."
                ),
            },
            status=404,
        )

    name = str(
        data.get("name")
    ).strip()

    phone = str(
        data.get("phone")
    ).strip()

    if (
        appointment.name.lower() != name.lower()
        or appointment.phone != phone
    ):

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "The name or phone number "
                    "does not match this appointment."
                ),
            },
            status=403,
        )

    appointment.preferred_date = str(
        data.get("new_date")
    ).strip()

    appointment.preferred_time = str(
        data.get("new_time")
    ).strip()

    appointment.save()

    return JsonResponse(
        {
            "success": True,
            "appointment_id": appointment.id,
            "message": (
                f"Appointment #{appointment.id} "
                "has been rescheduled successfully."
            ),
        }
    )

# CANCEL APPOINTMENT
@require_http_methods(["GET", "POST"])
def cancel_appointment(request):

    if request.method == "GET":

        return render(
            request,
            "dentalcare/cancel_appointment.html"
        )

    try:

        data = json.loads(
            request.body or "{}"
        )

    except json.JSONDecodeError:

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid JSON.",
            },
            status=400,
        )

    required = [
        "name",
        "phone",
        "appointment_id",
    ]

    missing = [
        field
        for field in required
        if not str(
            data.get(field, "")
        ).strip()
    ]

    if missing:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    f"Please provide: "
                    f"{', '.join(missing)}."
                ),
            },
            status=400,
        )

    appointment_id = str(
        data.get("appointment_id")
    ).strip()

    try:

        appointment = (
            AppointmentRequest.objects.get(
                id=appointment_id
            )
        )

    except AppointmentRequest.DoesNotExist:

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "Appointment not found. "
                    "Please check your appointment ID."
                ),
            },
            status=404,
        )

    name = str(
        data.get("name")
    ).strip()

    phone = str(
        data.get("phone")
    ).strip()

    if (
        appointment.name.lower() != name.lower()
        or appointment.phone != phone
    ):

        return JsonResponse(
            {
                "success": False,
                "error": (
                    "The name or phone number "
                    "does not match this appointment."
                ),
            },
            status=403,
        )

    appointment.delete()

    return JsonResponse(
        {
            "success": True,
            "appointment_id": appointment_id,
            "message": (
                f"Appointment #{appointment_id} "
                "has been cancelled successfully."
            ),
        }
    )

