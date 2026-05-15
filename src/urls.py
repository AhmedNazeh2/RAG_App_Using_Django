from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    RegisterView, MeView,
    ChatView, ChatHistoryView, ChatHistoryDetailView,
    DocumentUploadView, DocumentListView, DocumentDetailView,
)

urlpatterns = [
    # Auth
    path('auth/register/', RegisterView.as_view(), name='auth-register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='auth-login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('auth/me/', MeView.as_view(), name='auth-me'),
    # Documents
    path('documents/', DocumentListView.as_view(), name='document-list'),
    path('documents/upload/', DocumentUploadView.as_view(), name='document-upload'),
    path('documents/<int:pk>/', DocumentDetailView.as_view(), name='document-detail'),
    # Chat
    path('chat/', ChatView.as_view(), name='chat'),
    path('chat/history/', ChatHistoryView.as_view(), name='chat-history'),
    path('chat/history/<int:pk>/', ChatHistoryDetailView.as_view(), name='chat-history-detail'),
]