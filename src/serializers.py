from django.contrib.auth.models import User
from rest_framework import serializers


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ('username', 'email', 'password')

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already taken.')
        return value

    def validate_email(self, value):
        if value and User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email', ''),
            password=validated_data['password'],
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'email')
        

from rest_framework import serializers
from django.conf import settings

from .models import Document


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        allowed_extensions = ['.pdf', '.txt']
        name = value.name.lower()
        if not any(name.endswith(ext) for ext in allowed_extensions):
            raise serializers.ValidationError(
                'Only .txt and .pdf files are supported.'
            )
        if value.size > settings.MAX_UPLOAD_SIZE:
            raise serializers.ValidationError(
                f'File size exceeds the {settings.MAX_UPLOAD_SIZE // (1024*1024)} MB limit.'
            )
        return value


class DocumentSerializer(serializers.ModelSerializer):
    file_size_display = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = ('id', 'filename', 'file_size', 'file_size_display', 'chunk_count', 'uploaded_at')
        read_only_fields = fields

    def get_file_size_display(self, obj):
        size = obj.file_size
        if size < 1024:
            return f'{size} B'
        if size < 1024 ** 2:
            return f'{size / 1024:.1f} KB'
        return f'{size / (1024 ** 2):.1f} MB'        
            
        
from rest_framework import serializers
from .models import ChatMessage

class ChatQuestionSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=2000, allow_blank=False)


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ('id', 'question', 'answer', 'sources', 'created_at')
        read_only_fields = fields        
        
        

