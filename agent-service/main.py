from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import sys
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ollama_client import get_models
from app.rag import hybrid_query
from app.prompts import get_system_prompt

app = FastAPI(
    title="LLM Agent Service",
    description="Intelligent agent service for advanced LLM interactions",
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
class AgentRequest(BaseModel):
    query: str
    model: str
    context: Optional[Dict[str, Any]] = None
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 2000


class AgentResponse(BaseModel):
    response: str
    model: str
    reasoning: Optional[str] = None
    sources: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskRequest(BaseModel):
    task_type: str
    parameters: Dict[str, Any]
    model: str


class TaskResponse(BaseModel):
    result: Any
    status: str
    metadata: Optional[Dict[str, Any]] = None


# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "agent"}


# Get available models
@app.get("/api/models")
async def list_models():
    try:
        models = get_models()
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Agent query endpoint with reasoning
@app.post("/api/agent/query", response_model=AgentResponse)
async def agent_query(request: AgentRequest):
    try:
        # Use custom system prompt or default
        system_prompt = request.system_prompt or get_system_prompt("assistant")
        
        # Build context-aware query
        context_str = ""
        if request.context:
            context_str = f"\nContext: {json.dumps(request.context)}\n"
        
        full_query = f"{system_prompt}\n{context_str}\nUser Query: {request.query}"
        
        # Get response using RAG
        response = hybrid_query(full_query, model=request.model)
        
        return AgentResponse(
            response=response,
            model=request.model,
            reasoning="Query processed with RAG and context awareness",
            sources=None,
            metadata={
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Task execution endpoint
@app.post("/api/agent/task", response_model=TaskResponse)
async def execute_task(request: TaskRequest):
    try:
        task_handlers = {
            "summarize": handle_summarize,
            "analyze": handle_analyze,
            "generate": handle_generate,
            "extract": handle_extract
        }
        
        handler = task_handlers.get(request.task_type)
        if not handler:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown task type: {request.task_type}"
            )
        
        result = await handler(request.parameters, request.model)
        
        return TaskResponse(
            result=result,
            status="completed",
            metadata={"task_type": request.task_type}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Task handlers
async def handle_summarize(params: Dict[str, Any], model: str) -> str:
    text = params.get("text", "")
    query = f"Summarize the following text concisely:\n\n{text}"
    return hybrid_query(query, model=model)


async def handle_analyze(params: Dict[str, Any], model: str) -> str:
    text = params.get("text", "")
    aspect = params.get("aspect", "general")
    query = f"Analyze the following text focusing on {aspect}:\n\n{text}"
    return hybrid_query(query, model=model)


async def handle_generate(params: Dict[str, Any], model: str) -> str:
    prompt = params.get("prompt", "")
    style = params.get("style", "professional")
    query = f"Generate content in {style} style based on: {prompt}"
    return hybrid_query(query, model=model)


async def handle_extract(params: Dict[str, Any], model: str) -> str:
    text = params.get("text", "")
    entity_type = params.get("entity_type", "key information")
    query = f"Extract {entity_type} from the following text:\n\n{text}"
    return hybrid_query(query, model=model)


# Chain multiple agent calls
@app.post("/api/agent/chain")
async def chain_queries(requests: List[AgentRequest]):
    try:
        results = []
        context = {}
        
        for req in requests:
            # Add previous results to context
            req.context = {**context, **(req.context or {})}
            
            # Execute query
            response = await agent_query(req)
            results.append(response)
            
            # Update context with result
            context[f"step_{len(results)}"] = response.response
        
        return {
            "results": results,
            "final_context": context
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

# Made with Bob
