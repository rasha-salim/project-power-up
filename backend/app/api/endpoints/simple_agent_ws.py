"""
Simplified WebSocket endpoint for agent conversations
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import json
import asyncio
import traceback
import sys
import uuid

# Configure detailed logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add a stream handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

router = APIRouter()

@router.websocket("/simple-agent/{project_id}")
async def simple_agent_websocket(
    websocket: WebSocket,
    project_id: str
):
    """
    Simplified WebSocket endpoint for testing agent conversations
    """
    client_id = str(uuid.uuid4())
    
    logger.info(f"WebSocket connection request received - Project: {project_id}, Client ID: {client_id}")
    
    try:
        # Accept the connection immediately
        logger.debug(f"Attempting to accept WebSocket connection for project {project_id}")
        await websocket.accept()
        logger.info(f"WebSocket connection accepted - Project: {project_id}, Client ID: {client_id}")
        
        # Send initial connection message
        welcome_message = {
            "type": "system_message",
            "message": f"Connected to simple agent WebSocket for project {project_id}",
            "client_id": client_id
        }
        await websocket.send_text(json.dumps(welcome_message))
        logger.info(f"Sent welcome message to client - Project: {project_id}, Client ID: {client_id}")
        
        # Main message handling loop
        while True:
            try:
                # Wait for messages with a timeout
                message_text = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                logger.info(f"Received message from client - Project: {project_id}, Client ID: {client_id}, Message: {message_text}")
                
                # Parse the message
                try:
                    message_data = json.loads(message_text)
                    message_type = message_data.get("type", "unknown")
                    
                    # Handle different message types
                    if message_type == "ping":
                        # Respond to ping with pong
                        pong_message = {
                            "type": "pong",
                            "message": "Server is alive",
                            "timestamp": message_data.get("timestamp", "")
                        }
                        await websocket.send_text(json.dumps(pong_message))
                        logger.debug(f"Sent pong response - Project: {project_id}, Client ID: {client_id}")
                    else:
                        # Echo the message back
                        echo_message = {
                            "type": "echo",
                            "original_message": message_data,
                            "message": f"Echo: {message_text}"
                        }
                        await websocket.send_text(json.dumps(echo_message))
                        logger.info(f"Sent echo response - Project: {project_id}, Client ID: {client_id}")
                        
                except json.JSONDecodeError:
                    # Handle non-JSON messages
                    logger.warning(f"Received non-JSON message - Project: {project_id}, Client ID: {client_id}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Invalid JSON format"
                    }))
                    
            except asyncio.TimeoutError:
                # Send ping on timeout to keep connection alive
                logger.debug(f"Message receive timeout - Project: {project_id}, Client ID: {client_id}")
                ping_message = {
                    "type": "ping",
                    "message": "Server ping"
                }
                await websocket.send_text(json.dumps(ping_message))
                logger.debug(f"Sent server ping - Project: {project_id}, Client ID: {client_id}")
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected during message handling - Project: {project_id}, Client ID: {client_id}")
                break
                
            except Exception as e:
                logger.error(f"Error handling message - Project: {project_id}, Client ID: {client_id}, Error: {str(e)}")
                logger.error(f"Exception traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
                # Don't break, try to keep the connection alive
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected - Project: {project_id}, Client ID: {client_id}")
        
    except Exception as e:
        logger.error(f"WebSocket error - Project: {project_id}, Client ID: {client_id}, Error: {str(e)}")
        logger.error(f"Exception traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        
        # Try to close the connection gracefully
        try:
            await websocket.close(code=1011, reason="Internal server error")
            logger.info(f"Closed WebSocket connection with error code - Project: {project_id}, Client ID: {client_id}")
        except Exception:
            pass
