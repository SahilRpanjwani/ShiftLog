from django.urls import path
from . import views

app_name = "documents"

urlpatterns = [
    path("", views.upload, name="upload"),
    path("history/", views.document_list, name="document_list"),
    path("<uuid:pk>/", views.document_detail, name="document_detail"),
    path("<uuid:pk>/review/", views.review, name="review"),
    path("<uuid:pk>/re-extract/", views.re_extract, name="re_extract"),
    path("<uuid:pk>/delete/", views.delete_document, name="delete_document"),
    path("<uuid:pk>/status/", views.extraction_status, name="extraction_status"),
    path("<uuid:pk>/review/<int:record_id>/", views.review, name="review_record"),
]