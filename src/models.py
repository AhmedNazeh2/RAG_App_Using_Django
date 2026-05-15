from django.contrib.auth.models import User
from django.db import models

def user_document_path(instance, filename):
    return f'documents/user_{instance.owner.id}/{filename}'

class Document(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    filename = models.CharField(max_length=255)
    file = models.FileField(upload_to=user_document_path)
    file_size = models.PositiveIntegerField(default=0, help_text='File size in bytes')
    chunk_count = models.PositiveIntegerField(default=0, help_text='Number of embedded chunks')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']
    def __str__(self):
        return f'{self.filename} (owner: {self.owner.username})'    
    
    
from django.contrib.auth.models import User
from django.db import models

class ChatMessage(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    question = models.TextField()
    answer = models.TextField()
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.owner.username}] {self.question[:60]}'
    
    