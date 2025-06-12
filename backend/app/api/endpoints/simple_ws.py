"""
Simple WebSocket endpoint for testing
"""
from fastapi import APIRouter, WebSocket
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/echo")
async def websocket_echo(websocket: WebSocket):
    """
    Simple echo WebSocket endpoint for testing
    """
    logger.info("WebSocket echo connection request received")
    
    await websocket.accept()
    logger.info("WebSocket echo connection accepted")
    
    try:
        # Send initial message
        await websocket.send_text("Connected to echo WebSocket")
        logger.info("Sent initial message to client")
        
        # Echo loop
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message: {data}")
            await websocket.send_text(f"Echo: {data}")
            logger.info(f"Sent echo response: {data}")
            
    except Exception as e:
        logger.error(f"WebSocket echo error: {str(e)}")
