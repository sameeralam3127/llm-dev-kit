# LLM Dev Kit - Production Deployment

A production-ready web application with containerized backend, agent service, and Open WebUI frontend for LLM interactions with RAG capabilities.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Open WebUI (Frontend)                    │
│                    Port: 3000 (Host: 8080)                   │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┐
        │                │                │
┌───────▼──────┐  ┌──────▼──────┐  ┌─────▼──────┐
│   Backend    │  │    Agent    │  │   Ollama   │
│   Service    │  │   Service   │  │  (Local)   │
│  Port: 8000  │  │ Port: 8001  │  │Port: 11434 │
└───────┬──────┘  └──────┬──────┘  └────────────┘
        │                │
        └────────┬───────┘
                 │
        ┌────────┼────────┐
        │        │        │
┌───────▼──┐ ┌──▼────┐ ┌─▼──────┐
│  Redis   │ │Chroma │ │ Ollama │
│  Cache   │ │Vector │ │  Host  │
│Port: 6379│ │ DB    │ │        │
└──────────┘ └───────┘ └────────┘
```

## 📋 Prerequisites

- Docker and Docker Compose installed
- Ollama installed and running locally (or accessible via network)
- At least 8GB RAM available
- 10GB free disk space

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd llm-dev-kit
git checkout feature/prod-web-app
```

### 2. Configure Environment

Copy and edit the production environment file:

```bash
cp .env.production .env
```

Edit `.env` and update:

- `OLLAMA_HOST`: Your Ollama server URL
- `WEBUI_SECRET_KEY`: Generate a secure random string
- Other settings as needed

### 3. Install Ollama Models

Ensure you have the required models:

```bash
# Install a chat model
ollama pull llama2

# Install an embedding model for RAG
ollama pull nomic-embed-text
```

### 4. Start Services

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Check service health
docker-compose -f docker-compose.prod.yml ps
```

### 5. Access the Application

- **Open WebUI**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **Agent Service**: http://localhost:8001
- **API Documentation**:
  - Backend: http://localhost:8000/docs
  - Agent: http://localhost:8001/docs

## 🔧 Services

### Backend Service (Port 8000)

FastAPI-based backend providing:

- Model management
- Chat completions
- PDF upload and processing
- RAG query handling
- Caching layer

**Endpoints:**

- `GET /health` - Health check
- `GET /api/models` - List available models
- `POST /api/chat` - Chat with LLM
- `POST /api/upload` - Upload PDF for RAG
- `POST /api/cache/clear` - Clear cache

### Agent Service (Port 8001)

Advanced agent service for:

- Context-aware queries
- Task execution (summarize, analyze, generate, extract)
- Chain multiple queries
- Custom system prompts

**Endpoints:**

- `GET /health` - Health check
- `GET /api/models` - List models
- `POST /api/agent/query` - Agent query with reasoning
- `POST /api/agent/task` - Execute specific tasks
- `POST /api/agent/chain` - Chain multiple queries

### Open WebUI (Port 3000)

Modern web interface providing:

- Chat interface
- Model selection
- Document upload
- Conversation history
- User authentication

## 📚 API Usage Examples

### Backend Chat

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is machine learning?",
    "model": "llama2",
    "use_rag": false
  }'
```

### Agent Query

```bash
curl -X POST http://localhost:8001/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Explain quantum computing",
    "model": "llama2",
    "context": {"domain": "physics"},
    "temperature": 0.7
  }'
```

### Agent Task Execution

```bash
curl -X POST http://localhost:8001/api/agent/task \
  -H "Content-Type: application/json" \
  -d '{
    "task_type": "summarize",
    "parameters": {
      "text": "Long text to summarize..."
    },
    "model": "llama2"
  }'
```

## 🛠️ Development

### Building Individual Services

```bash
# Build backend
docker build -t llm-backend ./backend

# Build agent service
docker build -t llm-agent ./agent-service
```

### Running in Development Mode

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Agent Service
cd agent-service
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

## 🔍 Monitoring

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f agent
docker-compose -f docker-compose.prod.yml logs -f open-webui
```

### Check Service Health

```bash
# Backend
curl http://localhost:8000/health

# Agent
curl http://localhost:8001/health

# Redis
docker exec llm-redis redis-cli ping

# ChromaDB
curl http://localhost:8000/api/v1/heartbeat
```

## 🧹 Maintenance

### Stop Services

```bash
docker-compose -f docker-compose.prod.yml down
```

### Stop and Remove Volumes

```bash
docker-compose -f docker-compose.prod.yml down -v
```

### Update Services

```bash
# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Rebuild and restart
docker-compose -f docker-compose.prod.yml up -d --build
```

### Clear Cache

```bash
# Via API
curl -X POST http://localhost:8000/api/cache/clear

# Via Redis CLI
docker exec llm-redis redis-cli FLUSHALL
```

## 🔒 Security Considerations

1. **Change Default Secrets**: Update `WEBUI_SECRET_KEY` in `.env`
2. **Network Security**: Use proper firewall rules in production
3. **HTTPS**: Configure reverse proxy (nginx/traefik) for SSL
4. **Authentication**: Enable and configure Open WebUI authentication
5. **API Keys**: Implement API key authentication for backend/agent services

## 🐛 Troubleshooting

### Ollama Connection Issues

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Update OLLAMA_HOST in .env if needed
# For Docker Desktop on Mac/Windows: http://host.docker.internal:11434
# For Linux: http://172.17.0.1:11434
```

### Container Issues

```bash
# Check container status
docker-compose -f docker-compose.prod.yml ps

# Restart specific service
docker-compose -f docker-compose.prod.yml restart backend

# View detailed logs
docker-compose -f docker-compose.prod.yml logs --tail=100 backend
```

### Port Conflicts

If ports are already in use, edit `docker-compose.prod.yml`:

```yaml
services:
  backend:
    ports:
      - "8080:8000" # Change host port
```

## 📦 Data Persistence

Data is persisted in Docker volumes:

- `llm-redis-data`: Redis cache
- `llm-chroma-data`: Vector database
- `llm-webui-data`: Open WebUI data

### Backup Volumes

```bash
# Backup ChromaDB
docker run --rm -v llm-chroma-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/chroma-backup.tar.gz -C /data .

# Backup Open WebUI
docker run --rm -v llm-webui-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/webui-backup.tar.gz -C /data .
```

## 🚀 Production Deployment

For production deployment:

1. Use a reverse proxy (nginx/traefik) for SSL termination
2. Set up proper monitoring (Prometheus/Grafana)
3. Configure log aggregation (ELK stack)
4. Implement rate limiting
5. Set up automated backups
6. Use secrets management (Vault/AWS Secrets Manager)
7. Configure resource limits in docker-compose

## 📄 License

[Your License Here]

## 🤝 Contributing

[Contributing Guidelines]

## 📞 Support

For issues and questions:

- GitHub Issues: [Repository Issues]
- Documentation: [Wiki/Docs Link]
