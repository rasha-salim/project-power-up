"""
WebSocket Integration Test for CrewAI and Anthropic

This script tests the WebSocket integration with CrewAI and Anthropic.
It connects to the WebSocket endpoint and starts an analysis, then
displays the real-time updates from the agents.
"""

import asyncio
import websockets
import json
import logging
import os
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
WEBSOCKET_URL = "ws://localhost:8000/api/v1/ws/agent-conversation/"
PROJECT_ID = "cafdc31f-3e2f-48fb-92de-af73da4001da"  # Valid project ID

async def test_websocket_integration():
    """Test the WebSocket integration with CrewAI and Anthropic"""
    
    # Connect to the WebSocket endpoint
    logger.info(f"Connecting to WebSocket at {WEBSOCKET_URL}{PROJECT_ID}")
    
    try:
        async with websockets.connect(f"{WEBSOCKET_URL}{PROJECT_ID}") as websocket:
            # Wait for connection established message
            response = await websocket.recv()
            data = json.loads(response)
            logger.info(f"Connection established: {data}")
            
            # Start an analysis
            logger.info("Starting analysis...")
            await websocket.send(json.dumps({
                "type": "start_analysis"
            }))
            
            # Listen for messages until analysis is completed
            while True:
                response = await websocket.recv()
                data = json.loads(response)
                
                if data.get("type") == "analysis_status":
                    status = data.get("status")
                    message = data.get("message")
                    logger.info(f"Analysis status: {status} - {message}")
                    
                    # If analysis is completed, exit the loop
                    if status == "completed" or status == "analysis_completed":
                        logger.info("Analysis completed!")
                        break
                        
                elif data.get("type") == "agent_message":
                    sender = data.get("sender_name")
                    message = data.get("message")
                    logger.info(f"Agent message from {sender}: {message}")
                    
                elif data.get("type") == "agent_thought":
                    sender = data.get("sender_name")
                    message = data.get("message")
                    logger.info(f"Agent thought from {sender}: {message}")
                    
                elif data.get("type") == "analysis_result":
                    result = data.get("result")
                    logger.info(f"Analysis result: {result}")
                    
                elif data.get("type") == "error":
                    error_message = data.get("message")
                    logger.error(f"Error: {error_message}")
                    break
                    
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_websocket_integration())
