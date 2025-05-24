from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging
import json
from typing import Dict, List, Any
import asyncio
from app.db.init_db import get_db
from app.services.websocket_manager import WebSocketManager
from app.services.agent_service import AgentService

router = APIRouter()
logger = logging.getLogger(__name__)

# Create a WebSocket connection manager
ws_manager = WebSocketManager()

@router.websocket("/agent-conversation/{project_id}")
async def agent_conversation_websocket(
    websocket: WebSocket,
    project_id: str
):
    """
    WebSocket endpoint for real-time agent conversations
    """
    await websocket.accept()
    
    # Add the connection to the manager
    await ws_manager.connect(websocket, project_id)
    
    try:
        # Create agent service
        agent_service = AgentService()
        
        # Send initial connection message
        await websocket.send_json({
            "type": "connection_established",
            "project_id": project_id,
            "message": "Connected to agent conversation"
        })
        
        # Listen for messages from the client
        while True:
            # Receive message from the client
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Process the message based on its type
            if message_data.get("type") == "user_message":
                # User sent a message to the agents
                user_message = message_data.get("message", "")
                
                # Broadcast the user message to all connections for this project
                await ws_manager.broadcast(
                    project_id,
                    {
                        "type": "user_message",
                        "sender": "user",
                        "message": user_message,
                        "timestamp": message_data.get("timestamp")
                    }
                )
                
                # Process the user message with agents
                # This is where we would integrate with CrewAI
                asyncio.create_task(
                    process_user_message(project_id, user_message)
                )
                
            elif message_data.get("type") == "start_analysis":
                # User wants to start a new analysis
                asyncio.create_task(
                    start_agent_analysis(project_id)
                )
                
            elif message_data.get("type") == "ping":
                # Client ping to keep connection alive
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": message_data.get("timestamp")
                })
                
    except WebSocketDisconnect:
        # Remove the connection when client disconnects
        ws_manager.disconnect(websocket, project_id)
        logger.info(f"Client disconnected from project {project_id}")
        
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        # Try to send error message before disconnecting
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"An error occurred: {str(e)}"
            })
        except:
            pass
        # Disconnect the client
        ws_manager.disconnect(websocket, project_id)

async def process_user_message(project_id: str, message: str):
    """
    Process a user message with the AI agents
    """
    try:
        # This would be integrated with CrewAI
        # For now, we'll simulate agent responses
        
        # Technical Analysis Agent response
        await asyncio.sleep(1)  # Simulate processing time
        await ws_manager.broadcast(
            project_id,
            {
                "type": "agent_message",
                "sender": "technical_agent",
                "sender_name": "Technical Analysis Agent",
                "message": f"Analyzing technical aspects of: {message}",
                "timestamp": None  # This would be set in a real implementation
            }
        )
        
        # Risk Assessment Agent response
        await asyncio.sleep(2)  # Simulate processing time
        await ws_manager.broadcast(
            project_id,
            {
                "type": "agent_message",
                "sender": "risk_agent",
                "sender_name": "Risk Assessment Agent",
                "message": f"Evaluating potential risks in: {message}",
                "timestamp": None
            }
        )
        
        # Project Planning Agent response
        await asyncio.sleep(3)  # Simulate processing time
        await ws_manager.broadcast(
            project_id,
            {
                "type": "agent_message",
                "sender": "planning_agent",
                "sender_name": "Project Planning Agent",
                "message": f"Creating project plan based on: {message}",
                "timestamp": None
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing user message: {str(e)}")
        await ws_manager.broadcast(
            project_id,
            {
                "type": "error",
                "message": f"Error processing message: {str(e)}"
            }
        )

async def start_agent_analysis(project_id: str):
    """
    Start a full agent analysis for a project
    """
    try:
        # Notify clients that analysis is starting
        await ws_manager.broadcast(
            project_id,
            {
                "type": "analysis_status",
                "status": "starting",
                "message": "Starting agent analysis"
            }
        )
        
        # This would be integrated with CrewAI
        # For now, we'll simulate the analysis process
        
        # Simulate document processing
        await asyncio.sleep(2)
        await ws_manager.broadcast(
            project_id,
            {
                "type": "analysis_status",
                "status": "processing_documents",
                "message": "Processing project documents"
            }
        )
        
        # Simulate technical analysis
        await asyncio.sleep(3)
        await ws_manager.broadcast(
            project_id,
            {
                "type": "agent_message",
                "sender": "technical_agent",
                "sender_name": "Technical Analysis Agent",
                "message": "I've analyzed the technical requirements and identified key components needed."
            }
        )
        
        # Simulate risk assessment
        await asyncio.sleep(3)
        await ws_manager.broadcast(
            project_id,
            {
                "type": "agent_message",
                "sender": "risk_agent",
                "sender_name": "Risk Assessment Agent",
                "message": "Based on the project scope, I've identified several potential risk factors that need mitigation."
            }
        )
        
        # Simulate project planning
        await asyncio.sleep(3)
        await ws_manager.broadcast(
            project_id,
            {
                "type": "agent_message",
                "sender": "planning_agent",
                "sender_name": "Project Planning Agent",
                "message": "I've developed an initial project timeline with key milestones and resource allocations."
            }
        )
        
        # Simulate completion
        await asyncio.sleep(2)
        await ws_manager.broadcast(
            project_id,
            {
                "type": "analysis_status",
                "status": "completed",
                "message": "Analysis completed successfully"
            }
        )
        
    except Exception as e:
        logger.error(f"Error starting agent analysis: {str(e)}")
        await ws_manager.broadcast(
            project_id,
            {
                "type": "error",
                "message": f"Error during analysis: {str(e)}"
            }
        )
