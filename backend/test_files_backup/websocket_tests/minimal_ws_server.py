"""
Minimal FastAPI WebSocket server for testing
"""
import uvicorn
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware with explicit WebSocket support
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Minimal WebSocket endpoint for testing
    """
    client_id = id(websocket)
    logger.debug(f"WebSocket connection request received - Client ID: {client_id}")
    
    try:
        # Accept the connection immediately
        logger.debug(f"Attempting to accept WebSocket connection")
        await websocket.accept()
        logger.info(f"WebSocket connection accepted - Client ID: {client_id}")
        
        # Send initial message
        await websocket.send_text("Connected to minimal WebSocket server")
        logger.debug(f"Sent initial message - Client ID: {client_id}")
        
        # Echo loop
        while True:
            try:
                # Wait for a message
                message = await websocket.receive_text()
                logger.debug(f"Received message: {message} - Client ID: {client_id}")
                
                # Echo the message back
                await websocket.send_text(f"Echo: {message}")
                logger.debug(f"Sent echo response - Client ID: {client_id}")
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected - Client ID: {client_id}")
                break
                
            except Exception as e:
                logger.error(f"Error handling WebSocket message - Client ID: {client_id}, Error: {str(e)}")
                try:
                    await websocket.send_text(f"Error: {str(e)}")
                except:
                    logger.error(f"Failed to send error message - Client ID: {client_id}")
                    break
                    
    except Exception as e:
        logger.error(f"Error setting up WebSocket connection - Client ID: {client_id}, Error: {str(e)}")
        try:
            await websocket.close(code=1011)
        except:
            pass

@app.get("/")
async def root():
    """
    Root endpoint for health check
    """
    return {"message": "Minimal WebSocket server is running"}

if __name__ == "__main__":
    uvicorn.run("minimal_ws_server:app", host="0.0.0.0", port=8768, log_level="debug")
