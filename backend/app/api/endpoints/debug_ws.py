from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import asyncio

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter()

@router.websocket("/echo")
async def websocket_echo(websocket: WebSocket):
    """
    Simple WebSocket echo endpoint for debugging WebSocket connections
    """
    client_id = id(websocket)
    logger.debug(f"WebSocket echo connection request received - Client ID: {client_id}")
    
    try:
        # Accept the connection immediately
        logger.debug(f"Attempting to accept WebSocket echo connection")
        await websocket.accept()
        logger.info(f"WebSocket echo connection accepted - Client ID: {client_id}")
        
        # Send initial message
        await websocket.send_text("Connected to echo WebSocket server")
        logger.debug(f"Sent initial message - Client ID: {client_id}")
        
        # Echo loop
        while True:
            try:
                # Wait for a message with timeout
                message = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                logger.debug(f"Received message: {message} - Client ID: {client_id}")
                
                # Echo the message back
                await websocket.send_text(f"Echo: {message}")
                logger.debug(f"Sent echo response - Client ID: {client_id}")
                
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                logger.debug(f"No message received for 30 seconds, sending ping - Client ID: {client_id}")
                try:
                    await websocket.send_text("ping")
                    logger.debug(f"Sent ping - Client ID: {client_id}")
                except Exception as e:
                    logger.error(f"Error sending ping, connection may be dead - Client ID: {client_id}, Error: {str(e)}")
                    break
                    
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
