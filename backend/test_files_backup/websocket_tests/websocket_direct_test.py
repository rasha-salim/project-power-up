"""
Direct WebSocket connection test script
"""
import asyncio
import websockets
import logging
import json
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = "cafdc31f-3e2f-48fb-92de-af73da4001da"
WEBSOCKET_URL = f"ws://localhost:8000/api/v1/ws/agent-conversation/{PROJECT_ID}"

async def test_websocket():
    """Test WebSocket connection directly"""
    logger.info(f"Connecting to WebSocket at {WEBSOCKET_URL}")
    
    try:
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            logger.info("Connected to WebSocket")
            
            # Wait for initial connection message
            response = await websocket.recv()
            logger.info(f"Received: {response}")
            
            # Send a ping message
            ping_message = {
                "type": "ping",
                "timestamp": "2025-06-11T11:50:00Z"
            }
            await websocket.send(json.dumps(ping_message))
            logger.info("Sent ping message")
            
            # Wait for pong response
            response = await websocket.recv()
            logger.info(f"Received: {response}")
            
            # Send start_analysis message
            start_message = {
                "type": "start_analysis"
            }
            await websocket.send(json.dumps(start_message))
            logger.info("Sent start_analysis message")
            
            # Wait for messages for 30 seconds
            logger.info("Waiting for messages for 30 seconds...")
            try:
                for _ in range(10):  # Try to receive 10 messages or until timeout
                    response = await asyncio.wait_for(websocket.recv(), timeout=3.0)
                    logger.info(f"Received: {response}")
            except asyncio.TimeoutError:
                logger.info("No more messages received within timeout")
            
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
