# LLM Dev Kit

A local-first AI chat workspace for building and testing LLM applications with Ollama, FastAPI, Streamlit, ChromaDB, Redis, RAG, tests, hot reload, and an MCP entrypoint.

## What You Get

- Modern chat UI in Streamlit
- FastAPI backend for reusable chat and ingest APIs
- Local Ollama model and embedding calls
- PDF ingestion with retrieval-augmented generation
- ChromaDB vector search
- Redis response caching
- MCP server exposing local assistant tools
- Docker hot reload for frontend and backend development
- Focused pytest coverage for prompt, cache, and RAG behavior

## Architecture

```text
Streamlit Web UI
      |
      v
FastAPI Chat API
      |
      +--> Redis cache
      +--> Ollama embeddings/generation
      +--> ChromaDB vector search
      |
      v
RAG response

MCP Client --> MCP Server --> same local RAG service
```

## Services

| Service | Port | Purpose |
| --- | ---: | --- |
| `web` | `8501` | Streamlit AI chat UI |
| `api` | `8001` | FastAPI chat, model, health, and PDF ingest endpoints |
| `redis` | `6379` | Response cache |
| `chroma` | `8000` | Vector database |
| `mcp` | stdio | Optional MCP tool server |

## Prerequisites

- Docker and Docker Compose
- Ollama running on your machine
- Python 3.12+ for local development outside Docker

Install Ollama from [ollama.com](https://ollama.com).

## Start Ollama

```bash
ollama serve
ollama pull llama3.1
ollama pull nomic-embed-text
```

## Run With Docker Hot Reload

```bash
docker compose up --build
```

Open:

- Web UI: `http://localhost:8501`
- API docs: `http://localhost:8001/docs`

The `api` and `web` services mount `./app` into the containers. Backend changes reload through Uvicorn, and Streamlit reruns on save.

## API Examples

```bash
curl http://localhost:8001/health
curl http://localhost:8001/models
curl -X POST http://localhost:8001/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Summarize my knowledge base","model":"llama3.1"}'
```

## MCP Usage

This repo includes `mcp.json` for MCP-compatible clients:

```json
{
  "mcpServers": {
    "llm-dev-kit": {
      "command": "docker",
      "args": ["compose", "run", "--rm", "mcp"]
    }
  }
}
```

Available MCP tools:

- `list_ollama_models`
- `ask_llm_dev_kit`

Run the MCP service directly:

```bash
docker compose --profile mcp run --rm mcp
```

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api:api --reload --port 8001
streamlit run app/main.py
```

Use `sample.env` as the starting point for `.env`.

## Testing

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python3 -m pytest
```

`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` avoids unrelated globally installed pytest plugins interfering with this project.

## Useful Docker Commands

```bash
docker compose up --build
docker compose logs -f api
docker compose logs -f web
docker compose down
docker compose down -v
```

## Troubleshooting

If Ollama is not reachable from Docker, confirm it is running locally:

```bash
ollama list
```

If models are missing:

```bash
ollama pull llama3.1
ollama pull nomic-embed-text
```

If PDF retrieval returns no context, make sure the PDF contains selectable text rather than scanned images.
