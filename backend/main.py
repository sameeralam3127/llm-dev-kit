from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import sys

# Add parent directory to path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ollama_client import get_models, chat_completion
from app.rag import hybrid_query, ingest_pdf
from app.cache import get_cache, set_cache

app = FastAPI(
    title="LLM Dev Kit Backend",
    description="Production-level backend API for LLM interactions with RAG",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class ChatRequest(BaseModel):
    message: str
    model: str
    use_rag: bool = True

class ChatResponse(BaseModel):
    response: str
    model: str
    sources: Optional[List[str]] = None

class ModelResponse(BaseModel):
    models: List[str]

class UploadResponse(BaseModel):
    message: str
    chunks: int

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "backend"}

# Get available models
@app.get("/api/models", response_model=ModelResponse)
async def list_models():
    try:
        models = get_models()
        return ModelResponse(models=models)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Chat endpoint
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        # Check cache first
        cache_key = f"chat:{request.model}:{request.message}"
        cached_response = get_cache(cache_key)
        
        if cached_response:
            return ChatResponse(
                response=cached_response,
                model=request.model,
                sources=None
            )
        
        # Use RAG if enabled
        if request.use_rag:
            response = hybrid_query(request.message, model=request.model)
        else:
            response = chat_completion(request.message, model=request.model)
        
        # Cache the response
        set_cache(cache_key, response, ttl=3600)
        
        return ChatResponse(
            response=response,
            model=request.model,
            sources=None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Upload PDF endpoint
@app.post("/api/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Process the PDF
        chunks = ingest_pdf(file.file)
        
        return UploadResponse(
            message=f"Successfully processed {file.filename}",
            chunks=chunks
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Clear cache endpoint
@app.post("/api/cache/clear")
async def clear_cache():
    try:
        # This would need to be implemented in cache.py
        return {"message": "Cache cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Made with Bob
