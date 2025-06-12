"""
Python WebSocket client to test connection to FastAPI WebSocket endpoint
"""
import asyncio
import websockets
import logging
import sys
import json
from datetime import datetime
import traceback

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def test_websocket_connection(url):
    """Test connection to a WebSocket endpoint"""
    logger.info(f"Attempting to connect to WebSocket at: {url}")
    
    try:
        async with websockets.connect(url) as websocket:
            logger.info(f"Connected to WebSocket at: {url}")
            
            # Send initial message
            message = {
                "type": "user_message",
                "message": "Hello from Python client",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(message))
            logger.info(f"Sent message: {message}")
            
            # Wait for response
            response = await websocket.recv()
            logger.info(f"Received response: {response}")
            
            # Send ping
            ping_message = {
                "type": "ping",
                "timestamp": datetime.now().isoformat()
            }
            await websocket.send(json.dumps(ping_message))
            logger.info(f"Sent ping: {ping_message}")
            
            # Wait for pong
            pong_response = await websocket.recv()
            logger.info(f"Received pong: {pong_response}")
            
            # Keep connection open for a bit
            logger.info("Keeping connection open for 10 seconds...")
            await asyncio.sleep(10)
            
            logger.info("Test completed successfully")
            
    except Exception as e:
        logger.error(f"Error connecting to WebSocket: {str(e)}")
        logger.error(f"Exception traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        return False
    
    return True

async def main():
    """Main function"""
    # Test minimal WebSocket server
    minimal_success = await test_websocket_connection("ws://localhost:8768/ws")
    logger.info(f"Minimal WebSocket test {'succeeded' if minimal_success else 'failed'}")
    
    # Test main application WebSocket endpoint
    project_id = "cafdc31f-3e2f-48fb-92de-af73da4001da"  # Use the same project ID as in the browser client
    main_success = await test_websocket_connection(f"ws://localhost:8000/api/v1/ws/agent-conversation/{project_id}")
    logger.info(f"Main WebSocket test {'succeeded' if main_success else 'failed'}")

if __name__ == "__main__":
    asyncio.run(main())
