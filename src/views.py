from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import RegisterSerializer, UserSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'Account created successfully.'},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


import logging
from django.shortcuts import get_object_or_404
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Document
from .rag_service import embed_document, delete_document_embeddings
from .serializers import DocumentUploadSerializer, DocumentSerializer

logger = logging.getLogger(__name__)


class DocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = serializer.validated_data['file']

        doc = Document.objects.create(
            owner=request.user,
            filename=uploaded_file.name,
            file=uploaded_file,
            file_size=uploaded_file.size,
        )

        try:
            chunk_count = embed_document(
                file_path=doc.file.path,
                document_id=doc.id,
                user_id=request.user.id,
                filename=doc.filename,
            )
            doc.chunk_count = chunk_count
            doc.save(update_fields=['chunk_count'])
        except Exception as exc:
            logger.error('Embedding failed for document %s: %s', doc.id, exc)
            doc.delete()
            return Response(
                {'error': f'Failed to process document: {str(exc)}'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        return Response(
            DocumentSerializer(doc).data,
            status=status.HTTP_201_CREATED,
        )


class DocumentListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        documents = Document.objects.filter(owner=request.user)
        serializer = DocumentSerializer(documents, many=True)
        return Response(serializer.data)


class DocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        doc = get_object_or_404(Document, pk=pk, owner=request.user)

        delete_document_embeddings(document_id=doc.id, user_id=request.user.id)

        try:
            doc.file.delete(save=False)
        except Exception as exc:
            logger.warning('Could not delete file for doc %s: %s', doc.id, exc)

        doc.delete()
        return Response(
            {'message': 'Document deleted successfully.'},
            status=status.HTTP_200_OK,
        )


from .rag_service import retrieve_relevant_chunks, generate_answer
from .models import ChatMessage
from .serializers import ChatQuestionSerializer, ChatMessageSerializer

logger = logging.getLogger(__name__)


class ChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChatQuestionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        question = serializer.validated_data['question']

        recent_history = (
            ChatMessage.objects
            .filter(owner=request.user)
            .order_by('created_at')  
            .values('question', 'answer')
        )
        chat_history = list(recent_history)

        # Retrieve relevant document chunks for this user
        chunks = retrieve_relevant_chunks(query=question, user_id=request.user.id)

        try:
            answer = generate_answer(
                question=question,
                context_chunks=chunks,
                chat_history=chat_history,  
            )
        except Exception as exc:
            logger.error('LLM error for user %s: %s', request.user.id, exc)
            return Response(
                {'error': f'Failed to generate answer: {str(exc)}'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # Format source references
        sources = [
            f'{fname} \u2014 chunk {cidx}'
            for _, fname, cidx in chunks
        ]

        # Persist the Q&A pair
        msg = ChatMessage.objects.create(
            owner=request.user,
            question=question,
            answer=answer,
            sources=sources,
        )

        return Response(
            ChatMessageSerializer(msg).data,
            status=status.HTTP_201_CREATED,
        )


class ChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        messages = ChatMessage.objects.filter(owner=request.user)[:20]
        serializer = ChatMessageSerializer(reversed(list(messages)), many=True)
        return Response(serializer.data)


class ChatHistoryDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        msg = get_object_or_404(ChatMessage, pk=pk, owner=request.user)
        msg.delete()
        return Response(
            {'message': 'Chat entry deleted successfully.'},
            status=status.HTTP_200_OK,
        )
