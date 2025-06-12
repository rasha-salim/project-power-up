"""
Standalone WebSocket server for testing
"""
import asyncio
import websockets
import logging
import sys
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Store active connections
active_connections = set()

# WebSocket server handler
async def echo_handler(websocket):
    """Handle WebSocket connections"""
    client_id = id(websocket)
    client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}" if hasattr(websocket, 'remote_address') else "unknown"
    
    logger.info(f"Client {client_id} connected from {client_info}")
    logger.debug(f"Path: {websocket.path if hasattr(websocket, 'path') else 'Not available'}")
    logger.debug(f"Headers: {websocket.request_headers if hasattr(websocket, 'request_headers') else 'Not available'}")
    
    # Add to active connections
    active_connections.add(websocket)
    
    try:
        # Send welcome message
        welcome_message = {
            "type": "connection_established",
            "message": "Welcome to the standalone WebSocket server!",
            "timestamp": datetime.now().isoformat()
        }
        await websocket.send(json.dumps(welcome_message))
        logger.info(f"Sent welcome message to client {client_id}")
        
        # Echo loop
        async for message in websocket:
            logger.info(f"Received message from client {client_id}: {message}")
            
            try:
                # Try to parse as JSON
                data = json.loads(message)
                message_type = data.get("type", "unknown")
                
                if message_type == "ping":
                    # Respond to ping with pong
                    response = {
                        "type": "pong",
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send(json.dumps(response))
                    logger.debug(f"Sent pong response to client {client_id}")
                    
                elif message_type == "user_message":
                    # Echo user message
                    response = {
                        "type": "agent_message",
                        "message": f"Echo: {data.get('message', '')}",
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send(json.dumps(response))
                    logger.info(f"Sent echo response to client {client_id}")
                    
                elif message_type == "start_analysis":
                    # Simulate starting analysis
                    logger.info(f"Client {client_id} requested to start analysis")
                    
                    # Send acknowledgment
                    await websocket.send(json.dumps({
                        "type": "analysis_started",
                        "message": "Analysis started successfully",
                        "timestamp": datetime.now().isoformat()
                    }))
                    
                    # Simulate progress updates
                    for i in range(1, 6):
                        await asyncio.sleep(1)  # Wait 1 second between updates
                        await websocket.send(json.dumps({
                            "type": "analysis_progress",
                            "progress": i * 20,
                            "message": f"Processing step {i}/5...",
                            "timestamp": datetime.now().isoformat()
                        }))
                    
                    # Send completion message
                    await websocket.send(json.dumps({
                        "type": "analysis_complete",
                        "message": "Analysis completed successfully",
                        "timestamp": datetime.now().isoformat()
                    }))
                    
                else:
                    # Echo unknown message types
                    response = {
                        "type": "echo",
                        "original_type": message_type,
                        "message": f"Received unknown message type: {message_type}",
                        "timestamp": datetime.now().isoformat()
                    }
                    await websocket.send(json.dumps(response))
                    logger.info(f"Sent echo for unknown message type to client {client_id}")
                    
            except json.JSONDecodeError:
                # Not JSON, just echo as text
                await websocket.send(f"Echo: {message}")
                logger.info(f"Sent plain text echo to client {client_id}")
            
    except websockets.exceptions.ConnectionClosed as e:
        logger.info(f"Client {client_id} disconnected: {e}")
    except Exception as e:
        logger.error(f"Error handling client {client_id}: {e}")
        logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
    finally:
        # Remove from active connections
        active_connections.remove(websocket)
        logger.info(f"Client {client_id} removed from active connections. Total active: {len(active_connections)}")

# Start WebSocket server
async def main():
    """Start the WebSocket server"""
    host = "localhost"
    port = 8767  # Changed port to avoid conflicts
    
    logger.info(f"Starting standalone WebSocket server on {host}:{port}")
    
    try:
        async with websockets.serve(echo_handler, host, port):
            logger.info(f"WebSocket server running on ws://{host}:{port}")
            await asyncio.Future()  # Run forever
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        logger.error(f"Exception details: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
        logger.error(f"Exception details: {type(e).__name__}: {str(e)}")
