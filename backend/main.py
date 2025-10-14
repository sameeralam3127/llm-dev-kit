from ollama_fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    message: str

@app.post("/chat")
async def chat_endpoint(data: ChatMessage):
    user_message = data.message.lower()
    # Simple logic for now
    if "hello" in user_message:
        reply = "Hi there! 👋"
    elif "bye" in user_message:
        reply = "Goodbye! 👋"
    else:
        reply = "I'm just a simple bot!"
    return {"reply": reply}
