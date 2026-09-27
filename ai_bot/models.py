from django.db import models
from django.conf import settings
from pgvector.django import HnswIndex, VectorField

from ai_bot.rag.embeddings import EMBEDDING_DIM


class ChatDialog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_dialogs",
    )
    title = models.CharField(max_length=255, default="New chat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return f"{self.title} ({self.user})"


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    dialog = models.ForeignKey(
        ChatDialog,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("created_at",)

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"


class KnowledgeSource(models.Model):
    """One indexed origin - a knowledge base file or a group of tables."""

    name = models.CharField(max_length=100, unique=True)
    # Hash of the produced chunk text, so re-indexing can skip untouched sources.
    checksum = models.CharField(max_length=64)
    chunk_count = models.PositiveIntegerField(default=0)
    indexed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return f"{self.name} ({self.chunk_count} chunks)"


class KnowledgeChunk(models.Model):
    source = models.ForeignKey(
        KnowledgeSource,
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    embedding = VectorField(dimensions=EMBEDDING_DIM)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            HnswIndex(
                name="kb_chunk_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]

    def __str__(self):
        return f"{self.source.name}: {self.content[:50]}"
