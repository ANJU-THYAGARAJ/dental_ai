from django.urls import path
from . import views

app_name = "chatbot"

urlpatterns = [
    path("", views.home, name="home"),
    path("enquiry/", views.enquiry_page, name="enquiry"),
    path("emergency/", views.emergency_page, name="emergency"),
    path("appointment/", views.appointment_page, name="appointment"),
    path("chatbot/", views.chatbot_page, name="chatbot"),
    path("chatbot/message/", views.chatbot_message, name="chatbot_message"),
    path("chatbot/reset/", views.reset_chat, name="reset_chat"),
    path("appointment/create/", views.create_appointment, name="create_appointment"),
    path("appointment/cancel/", views.cancel_appointment, name="cancel_appointment"),
    path("appointment/reschedule/", views.reschedule_appointment, name="reschedule_appointment"),
    path("chatbot/upload/",views.upload_chat_file,name="upload_chat_file"),
]
