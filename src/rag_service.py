from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import List, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


# Text extraction 

def extract_text_from_file(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == '.txt':
        with open(path, 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()

    if suffix == '.pdf':
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(path))
            pages = [page.extract_text() or '' for page in reader.pages]
            return '\n'.join(pages)
        except Exception as exc:
            logger.error('PDF extraction failed: %s', exc)
            raise ValueError(f'Could not extract text from PDF: {exc}') from exc

    raise ValueError(f'Unsupported file type: {suffix}')


# Chunking 

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    if not words:
        return []

    chunks: List[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(' '.join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap 

    return [c for c in chunks if c.strip()]


# Embedding functions 

def _get_openai_embeddings(texts: List[str]) -> List[List[float]]:
    import openai
    openai.api_key = settings.OPENAI_API_KEY
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model='text-embedding-3-small',
        input=texts,
    )
    return [item.embedding for item in response.data]


def _get_local_embeddings(texts: List[str]) -> List[List[float]]:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer('all-MiniLM-L6-v2')
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()


def get_embeddings(texts: List[str]) -> List[List[float]]:
    if settings.OPENAI_API_KEY:
        return _get_openai_embeddings(texts)
    return _get_local_embeddings(texts)


# ChromaDB as a vecdb

def _get_chroma_collection(user_id: int):
    import chromadb
    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    collection_name = f'user_{user_id}'
    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={'hnsw:space': 'cosine'},
    )
    return collection


# Public API 

def embed_document(file_path: str,document_id: int,user_id: int,filename: str) -> int:

    text = extract_text_from_file(file_path)
    if not text.strip():
        raise ValueError('Document appears to be empty or contains no extractable text.')

    chunk_size = getattr(settings, 'CHUNK_SIZE', 500)
    chunk_overlap = getattr(settings, 'CHUNK_OVERLAP', 50)
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=chunk_overlap)

    if not chunks:
        raise ValueError('No text chunks could be created from the document.')

    embeddings = get_embeddings(chunks)
    collection = _get_chroma_collection(user_id)

    ids = [f'doc_{document_id}_chunk_{i}' for i in range(len(chunks))]
    metadatas = [
        {
            'document_id': str(document_id),
            'filename': filename,
            'chunk_index': str(i),
        }
        for i in range(len(chunks))
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=chunks,
        metadatas=metadatas,
    )

    logger.info(
        'Embedded document %s for user %s: %d chunks', document_id, user_id, len(chunks)
    )
    return len(chunks)


def delete_document_embeddings(document_id: int, user_id: int) -> None:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        collection_name = f'user_{user_id}'
        existing = [c.name for c in client.list_collections()]
        if collection_name not in existing:
            return
        collection = client.get_collection(collection_name)
        results = collection.get(where={'document_id': str(document_id)})
        if results and results['ids']:
            collection.delete(ids=results['ids'])
            logger.info(
                'Deleted %d vectors for document %s', len(results['ids']), document_id
            )
    except Exception as exc:
        logger.error('Error deleting embeddings for doc %s: %s', document_id, exc)


def retrieve_relevant_chunks(query: str,user_id: int,top_k: int = 5) -> List[Tuple[str, str, str]]:
    try:
        import chromadb
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        collection_name = f'user_{user_id}'
        existing = [c.name for c in client.list_collections()]
        if collection_name not in existing:
            return []

        collection = client.get_collection(collection_name)
        if collection.count() == 0:
            return []

        query_embedding = get_embeddings([query])[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, collection.count()),
            include=['documents', 'metadatas', 'distances'],
        )

        chunks = []
        for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
            filename = meta.get('filename', 'unknown')
            chunk_idx = meta.get('chunk_index', '?')
            chunks.append((doc, filename, chunk_idx))

        return chunks

    except Exception as exc:
        logger.error('Retrieval error for user %s: %s', user_id, exc)
        return []


# LLM call 

def generate_answer(question: str, context_chunks: List[Tuple[str, str, str]]) -> str:
    if not context_chunks:
        return (
            "I couldn't find any relevant information in your documents to answer "
            'this question. Please upload documents that contain the relevant content.'
        )

    context_text = '\n\n---\n\n'.join(
        f'[Source: {fname}, chunk {cidx}]\n{text}'
        for text, fname, cidx in context_chunks
    )

    system_prompt = (
        'You are a helpful assistant that answers questions based strictly on the '
        'provided document context. '
        'If the context does not contain enough information, say so clearly. '
        'Be concise, accurate, and cite the source filename when relevant.'
    )

    user_prompt = (
        f'Context from uploaded documents:\n\n{context_text}\n\n'
        f'Question: {question}\n\n'
        'Please answer based on the context above.'
    )

    provider = getattr(settings, 'LLM_PROVIDER', 'openai')

    if provider == 'groq' and getattr(settings, 'GROQ_API_KEY', ''):
        return _call_groq(system_prompt, user_prompt)

    if getattr(settings, 'OPENAI_API_KEY', ''):
        return _call_openai(system_prompt, user_prompt)

    # No API key — return a helpful stub
    return (
        '[LLM not configured] Based on your documents, here is the relevant context:\n\n'
        + context_text[:500]
    )


def _call_openai(system_prompt: str, user_prompt: str) -> str:
    import openai
    client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


def _call_groq(system_prompt: str, user_prompt: str) -> str:
    import openai  # Groq uses an OpenAI-compatible API
    client = openai.OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url='https://api.groq.com/openai/v1',
    )
    response = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()