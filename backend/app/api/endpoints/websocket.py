from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging
import json
import asyncio
import uuid
import sys
import traceback
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from app.core.config import settings
from app.services.websocket_manager import WebSocketManager
from app.services.agent_service_v2 import AgentServiceV2

# Configure detailed logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add a stream handler if not already present
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

router = APIRouter()

# Create a single global instance of WebSocketManager
ws_manager = WebSocketManager()

# Create a single global instance of AgentServiceV2
agent_service = AgentServiceV2()

# Dictionary to store active connections by project_id and client_id
active_connections = {}

async def broadcast_message(project_id: str, sender_id: str, message: dict):
    """
    Broadcast a message to all connected clients in a project except the sender
    """
    if project_id in active_connections:
        for client_id, websocket in active_connections[project_id].items():
            if client_id != sender_id:
                try:
                    await websocket.send_text(json.dumps(message))
                    logger.debug(f"Broadcast message sent to client {client_id} in project {project_id}")
                except Exception as e:
                    logger.error(f"Error broadcasting message to client {client_id}: {str(e)}")


@router.websocket("/agent-conversation/{project_id}")
async def agent_conversation_websocket(
    websocket: WebSocket,
    project_id: str
):
    """
    WebSocket endpoint for real-time agent conversations
    """
    # Generate a unique client ID
    client_id = str(uuid.uuid4())
    
    # Log connection request
    client_info = f"{websocket.client.host}:{websocket.client.port}" if hasattr(websocket, 'client') else "unknown"
    logger.info(f"WebSocket connection request received - Project: {project_id}, Client ID: {client_id}, Client: {client_info}")
    logger.debug(f"WebSocket headers: {websocket.headers if hasattr(websocket, 'headers') else 'Not available'}")
    
    try:
        # Accept the connection
        await websocket.accept()
        logger.info(f"WebSocket connection accepted - Project: {project_id}, Client ID: {client_id}")
        
        # Store connection information
        if project_id not in active_connections:
            active_connections[project_id] = {}
        active_connections[project_id][client_id] = websocket
        logger.info(f"Added client to active connections - Project: {project_id}, Client ID: {client_id}")
        
        # Send welcome message
        welcome_message = {
            "type": "system_message",
            "message": f"Connected to agent conversation for project {project_id}",
            "client_id": client_id
        }
        await websocket.send_text(json.dumps(welcome_message))
        logger.info(f"Sent welcome message - Project: {project_id}, Client ID: {client_id}")
        
        # Main message handling loop
        while True:
            try:
                # Wait for messages with a timeout
                message_text = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                logger.info(f"Received message - Project: {project_id}, Client ID: {client_id}, Message: {message_text}")
                
                # Parse the message
                try:
                    data = json.loads(message_text)
                    message_type = data.get("type", "unknown")
                    
                    # Handle different message types
                    if message_type == "ping":
                        # Respond to ping with pong
                        pong_message = {
                            "type": "pong",
                            "message": "Server is alive",
                            "timestamp": data.get("timestamp", "")
                        }
                        await websocket.send_text(json.dumps(pong_message))
                        logger.debug(f"Sent pong response - Project: {project_id}, Client ID: {client_id}")
                    
                    elif message_type == "user_message":
                        # Process user message
                        user_message_content = data.get('message', '')
                        logger.info(f"Processing user message - Project: {project_id}, Content: {user_message_content}")
                        
                        # Echo back acknowledgment
                        ack_message = {
                            "type": "acknowledgment",
                            "message": f"Received: {user_message_content}"
                        }
                        await websocket.send_text(json.dumps(ack_message))
                        
                        # Broadcast message to all clients in the same project
                        await broadcast_message(project_id, client_id, {
                            "type": "broadcast",
                            "from_client": client_id,
                            "message": user_message_content
                        })
                        
                    elif message_type == "start_analysis":
                        # Trigger agent analysis with simplified parameters
                        user_context = data.get("user_context")  # Optional user context
                        logger.info(f"Starting agent analysis for project {project_id} requested by client {client_id}")
                        
                        # Send acknowledgment to client
                        await websocket.send_text(json.dumps({
                            "type": "system_message",
                            "message": "Starting agent analysis..."
                        }))
                        
                        try:
                            # Import dependencies here to avoid circular imports
                            from sqlalchemy.ext.asyncio import AsyncSession
                            from app.db.init_db_simple import get_async_db
                            
                            # Get database session
                            db = await anext(get_async_db().__aiter__())
                            
                            # Register the current connection if not already registered
                            if websocket not in ws_manager.active_connections.get(project_id, []):
                                await ws_manager.connect(websocket, project_id)
                            
                            # Use simplified unified analysis execution
                            analysis_id = await agent_service.execute_analysis(
                                project_id=project_id, 
                                db=db, 
                                ws_manager=ws_manager,
                                user_context=user_context
                            )
                            
                            # Send confirmation to client
                            await websocket.send_text(json.dumps({
                                "type": "analysis_started",
                                "analysis_id": analysis_id,
                                "message": "Agent analysis started successfully"
                            }))
                            
                        except Exception as e:
                            logger.error(f"Error starting analysis: {str(e)}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Failed to start analysis: {str(e)}"
                            }))
                        
                    elif message_type == "cancel_analysis":
                        # Cancel agent analysis
                        analysis_id = data.get("analysis_id")
                        logger.info(f"Cancelling agent analysis {analysis_id} for project {project_id} requested by client {client_id}")
                        
                        try:
                            # Cancel the analysis
                            success = await agent_service.cancel_analysis(analysis_id)
                            
                            if success:
                                # Send confirmation to client
                                await websocket.send_text(json.dumps({
                                    "type": "system_message",
                                    "message": "Analysis cancelled successfully"
                                }))
                                
                                # Broadcast cancellation to all clients
                                await broadcast_message(project_id, client_id, {
                                    "type": "analysis_cancelled",
                                    "analysis_id": analysis_id,
                                    "message": "Analysis has been cancelled"
                                })
                            else:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": "Failed to cancel analysis - it may have already completed"
                                }))
                                
                        except Exception as e:
                            logger.error(f"Error cancelling agent analysis: {str(e)}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Failed to cancel analysis: {str(e)}"
                            }))
                    
                    elif message_type == "user_question":
                        # Handle user question about analysis
                        analysis_id = data.get("analysis_id")
                        question = data.get("question")
                        
                        if not analysis_id or not question:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "Missing analysis_id or question"
                            }))
                            continue
                        
                        logger.info(f"Handling user question for analysis {analysis_id}")
                        
                        try:
                            # Import dependencies
                            from sqlalchemy.ext.asyncio import AsyncSession
                            from app.db.init_db_simple import get_async_db
                            
                            # Get database session
                            db = await anext(get_async_db().__aiter__())
                            
                            # Register the current connection if not already registered
                            if websocket not in ws_manager.active_connections.get(project_id, []):
                                await ws_manager.connect(websocket, project_id)
                            
                            # Handle the question using the new unified handler
                            response = await agent_service.handle_user_message(
                                db, project_id, question, analysis_id, ws_manager
                            )
                            
                            # The response is already sent via WebSocket by the handler
                            
                        except Exception as e:
                            logger.error(f"Error handling user question: {str(e)}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Failed to process question: {str(e)}"
                            }))
                    
                    elif message_type == "chat_message":
                        message_text = data.get("message", "")
                        logger.info(f"Received chat message from project {project_id}: {message_text}")
                        
                        try:
                            # Get database session
                            from sqlalchemy.ext.asyncio import AsyncSession
                            from app.db.init_db_simple import get_async_db
                            db = await anext(get_async_db().__aiter__())
                            
                            # Register the current connection if not already registered
                            if websocket not in ws_manager.active_connections.get(project_id, []):
                                await ws_manager.connect(websocket, project_id)
                            
                            logger.debug(f"Calling handle_user_message for project {project_id}")
                            # Handle the message using the new unified handler
                            response = await agent_service.handle_user_message(
                                db, project_id, message_text, None, ws_manager
                            )
                            logger.debug(f"handle_user_message returned: {response}")
                            
                            # The response is already sent via WebSocket by the handler
                            
                        except Exception as e:
                            logger.error(f"Error handling chat message: {str(e)}")
                            logger.error(f"Traceback: {traceback.format_exc()}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Failed to process message: {str(e)}"
                            }))
                    
                    elif message_type == "confirm_analysis":
                        # Confirm and save analysis
                        analysis_id = data.get("analysis_id")
                        
                        if not analysis_id:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "Missing analysis_id"
                            }))
                            continue
                        
                        logger.info(f"Confirming and saving analysis {analysis_id}")
                        
                        try:
                            # Import dependencies
                            from sqlalchemy.ext.asyncio import AsyncSession
                            from app.db.init_db_simple import get_async_db
                            
                            # Get database session
                            db = await anext(get_async_db().__aiter__())
                            
                            # Register the current connection if not already registered
                            if websocket not in ws_manager.active_connections.get(project_id, []):
                                await ws_manager.connect(websocket, project_id)
                            
                            # Confirm and save
                            success = await agent_service.confirm_and_save_analysis(db, analysis_id, ws_manager)
                            
                            if not success:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": "Failed to save analysis"
                                }))
                            
                        except Exception as e:
                            logger.error(f"Error confirming analysis: {str(e)}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Failed to save analysis: {str(e)}"
                            }))
                    
                    elif message_type == "regenerate_with_feedback":
                        # Regenerate analysis with user feedback
                        analysis_id = data.get("analysis_id")
                        user_feedback = data.get("feedback")
                        
                        if not analysis_id or not user_feedback:
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": "Missing analysis_id or feedback"
                            }))
                            continue
                        
                        logger.info(f"Regenerating analysis {analysis_id} with user feedback")
                        
                        try:
                            # Import dependencies
                            from sqlalchemy.ext.asyncio import AsyncSession
                            from app.db.init_db_simple import get_async_db
                            
                            # Get database session
                            db = await anext(get_async_db().__aiter__())
                            
                            # Register the current connection if not already registered
                            if websocket not in ws_manager.active_connections.get(project_id, []):
                                await ws_manager.connect(websocket, project_id)
                            
                            # Regenerate analysis with feedback
                            success = await agent_service.regenerate_analysis_with_feedback(
                                db, analysis_id, user_feedback, ws_manager
                            )
                            
                            if not success:
                                await websocket.send_text(json.dumps({
                                    "type": "error",
                                    "message": "Failed to regenerate analysis"
                                }))
                            
                        except Exception as e:
                            logger.error(f"Error regenerating analysis: {str(e)}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Failed to regenerate analysis: {str(e)}"
                            }))
                    
                    elif message_type == "stop_conversation":
                        # Handle stop conversation request
                        logger.info(f"Stop conversation requested for project {project_id} by client {client_id}")
                        
                        try:
                            # Import dependencies
                            from sqlalchemy.ext.asyncio import AsyncSession
                            from app.db.init_db_simple import get_async_db
                            
                            # Get database session
                            db = await anext(get_async_db().__aiter__())
                            
                            # Stop any running agent conversations by canceling running tasks
                            # We'll use the agent service to stop all running tasks for this project
                            stopped_tasks = []
                            
                            # Get all running analyses for this project and cancel them
                            for analysis_id, task in list(agent_service.analysis_manager.running_tasks.items()):
                                if not task.done():
                                    # Get the analysis data to check if it belongs to this project
                                    pending_analysis = agent_service.analysis_manager.get_pending_analysis(analysis_id)
                                    if pending_analysis and pending_analysis.get('project_id') == project_id:
                                        success = await agent_service.cancel_analysis(analysis_id)
                                        if success:
                                            stopped_tasks.append(analysis_id)
                                            logger.info(f"Cancelled analysis task {analysis_id} for project {project_id}")
                            
                            # Send confirmation back to the client
                            stop_message = {
                                "type": "conversation_stopped",
                                "message": "🛑 Conversation stopped successfully",
                                "stopped_tasks": stopped_tasks
                            }
                            await websocket.send_text(json.dumps(stop_message))
                            
                            # Broadcast to other clients in the same project
                            await broadcast_message(project_id, client_id, {
                                "type": "conversation_stopped",
                                "message": f"Conversation stopped by another user",
                                "stopped_tasks": stopped_tasks
                            })
                            
                        except Exception as e:
                            logger.error(f"Error stopping conversation: {str(e)}")
                            await websocket.send_text(json.dumps({
                                "type": "error",
                                "message": f"Failed to stop conversation: {str(e)}"
                            }))
                    
                    else:
                        # Handle unknown message types
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Unknown message type: {message_type}"
                        }))
                        logger.warning(f"Unknown message type - Project: {project_id}, Client ID: {client_id}, Type: {message_type}")
                        
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
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected - Project: {project_id}, Client ID: {client_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error - Project: {project_id}, Client ID: {client_id}, Error: {str(e)}")
        logger.error(f"Exception traceback: {''.join(traceback.format_exception(type(e), e, e.__traceback__))}")
        
    finally:
        # Clean up connection
        if project_id in active_connections and client_id in active_connections[project_id]:
            del active_connections[project_id][client_id]
            logger.info(f"Removed client from active connections - Project: {project_id}, Client ID: {client_id}")
            
            # Remove project if no more clients
            if not active_connections[project_id]:
                del active_connections[project_id]
                logger.info(f"Removed empty project from active connections - Project: {project_id}")
        
        # Remove from WebSocketManager
        ws_manager.disconnect(websocket, project_id)
        
        # Try to close the connection gracefully if it's still open
        try:
            await websocket.close()
            logger.info(f"Closed WebSocket connection - Project: {project_id}, Client ID: {client_id}")
        except Exception:
            pass
