"""Test main app without database initialization"""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create app with same configuration as main
app = FastAPI(
    title="Test Project Planning System API",
    description="Testing WebSocket without DB",
    version="0.1.0",
)

# Add CORS middleware exactly like main app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add test WebSocket endpoint
@app.websocket("/test-ws")
async def test_websocket(websocket: WebSocket):
    logger.info(f"WebSocket connection attempt from {websocket.client}")
    try:
        await websocket.accept()
        logger.info("WebSocket accepted")
        await websocket.send_text("Test main app without DB works!")
        await websocket.close()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")

# Add startup event WITHOUT database initialization
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up application (no DB)...")
    logger.info("Startup complete!")

# Add the same WebSocket endpoint from your router
@app.websocket("/agent-conversation/{project_id}")
async def agent_conversation_websocket(websocket: WebSocket, project_id: str):
    logger.info(f"Agent conversation WebSocket for project {project_id}")
    try:
        await websocket.accept()
        await websocket.send_text(f"Connected to project {project_id}")
        await websocket.close()
    except Exception as e:
        logger.error(f"Agent WebSocket error: {e}")

if __name__ == "__main__":
    logger.info("Starting test main app without DB on port 8003...")
    uvicorn.run(app, host="0.0.0.0", port=8003)
