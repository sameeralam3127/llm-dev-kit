"""
Prompt Templates Module
Provides prompt templates for different use cases
"""
from typing import Optional


def build_rag_prompt(query: str, context: str) -> str:
    """
    Build a prompt for RAG (Retrieval-Augmented Generation)
    
    Args:
        query: User's question
        context: Retrieved context from documents
    
    Returns:
        Formatted prompt for the LLM
    """
    return f"""You are a helpful AI assistant. Answer the question based ONLY on the provided context.

Context:
{context}

Question: {query}

Instructions:
- Answer based only on the context provided
- If the context doesn't contain relevant information, say so
- Be concise and accurate
- Cite specific parts of the context when possible

Answer:"""


def build_chat_prompt(query: str) -> str:
    """
    Build a prompt for general chat (no RAG)
    
    Args:
        query: User's question
    
    Returns:
        Formatted prompt for the LLM
    """
    return f"""You are a helpful AI assistant. Answer the following question.

Question: {query}

Answer:"""


def get_system_prompt(role: str = "assistant") -> str:
    """
    Get system prompts for different roles
    
    Args:
        role: The role type (assistant, code, analyst, summarizer)
    
    Returns:
        System prompt for the specified role
    """
    prompts = {
        "assistant": """You are a helpful, friendly, and knowledgeable AI assistant.
Provide clear, accurate, and concise responses.""",
        
        "code": """You are an expert programmer and code reviewer.
Provide clean, well-documented code with best practices.
Explain your reasoning and suggest improvements.""",
        
        "analyst": """You are a data analyst expert.
Analyze information thoroughly and provide insights.
Use clear reasoning and support conclusions with evidence.""",
        
        "summarizer": """You are an expert at summarizing content.
Create concise, accurate summaries that capture key points.
Maintain the original meaning and important details.""",
        
        "teacher": """You are a patient and knowledgeable teacher.
Explain concepts clearly with examples.
Break down complex topics into understandable parts."""
    }
    
    return prompts.get(role, prompts["assistant"])


def build_summarization_prompt(text: str, max_words: int = 200) -> str:
    """
    Build a prompt for text summarization
    
    Args:
        text: Text to summarize
        max_words: Maximum words in summary
    
    Returns:
        Formatted summarization prompt
    """
    return f"""Summarize the following text in approximately {max_words} words.
Focus on the main points and key information.

Text:
{text}

Summary:"""


def build_extraction_prompt(text: str, entity_type: str) -> str:
    """
    Build a prompt for information extraction
    
    Args:
        text: Text to extract from
        entity_type: Type of entities to extract
    
    Returns:
        Formatted extraction prompt
    """
    return f"""Extract all {entity_type} from the following text.
List them clearly and concisely.

Text:
{text}

Extracted {entity_type}:"""


def build_analysis_prompt(text: str, aspect: str = "general") -> str:
    """
    Build a prompt for text analysis
    
    Args:
        text: Text to analyze
        aspect: Aspect to focus on (sentiment, themes, etc.)
    
    Returns:
        Formatted analysis prompt
    """
    return f"""Analyze the following text focusing on {aspect}.
Provide detailed insights and observations.

Text:
{text}

Analysis:"""

# Made with Bob
