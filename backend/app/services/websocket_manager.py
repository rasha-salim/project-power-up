import logging
import uuid
from typing import Dict, List, Any, Set
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Manager for WebSocket connections.
    Handles connection management and broadcasting messages to connected clients.
    """
    
    def __init__(self):
        # Map of project_id to list of active websocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Track WebSocket IDs to prevent duplicate connections
        self.connection_ids: Dict[int, str] = {}
    
    async def connect(self, websocket: WebSocket, project_id: str) -> None:
        """
        Connect a new WebSocket client
        
        Args:
            websocket: WebSocket connection
            project_id: ID of the project the client is connecting to
        """
        # Generate a unique ID for this websocket instance
        ws_id = id(websocket)
        
        # Check if this websocket is already connected
        if ws_id in self.connection_ids:
            existing_project = self.connection_ids[ws_id]
            if existing_project == project_id:
                logger.debug(f"WebSocket {ws_id} already connected to project {project_id}")
                return
            else:
                # If connected to a different project, disconnect from the old one first
                logger.debug(f"WebSocket {ws_id} moving from project {existing_project} to {project_id}")
                self.disconnect(websocket, existing_project)
        
        # Note: WebSocket connection is now accepted in the endpoint before calling this method
        logger.debug(f"WebSocketManager.connect called - Project: {project_id}, WebSocket ID: {ws_id}")
        logger.debug(f"WebSocket state in manager.connect: {websocket.client_state if hasattr(websocket, 'client_state') else 'Not available'}")
        
        # Add to active connections for this project
        if project_id not in self.active_connections:
            logger.debug(f"Creating new connection list for project {project_id}")
            self.active_connections[project_id] = []
        
        # Only add if not already in the list
        if websocket not in self.active_connections[project_id]:
            self.active_connections[project_id].append(websocket)
            self.connection_ids[ws_id] = project_id
            logger.info(f"Client connected to project {project_id}. Active connections: {len(self.active_connections[project_id])}")
        else:
            logger.debug(f"WebSocket already in active_connections for project {project_id}")
    
    def disconnect(self, websocket: WebSocket, project_id: str) -> None:
        """
        Disconnect a WebSocket client
        
        Args:
            websocket: WebSocket connection
            project_id: ID of the project the client is disconnecting from
        """
        ws_id = id(websocket)
        
        # Remove from connection IDs tracking
        if ws_id in self.connection_ids:
            del self.connection_ids[ws_id]
        
        # Remove from active connections
        if project_id in self.active_connections:
            if websocket in self.active_connections[project_id]:
                self.active_connections[project_id].remove(websocket)
                logger.info(f"Client disconnected from project {project_id}. Active connections: {len(self.active_connections[project_id])}")
            
            # Clean up empty project entries
            if len(self.active_connections[project_id]) == 0:
                del self.active_connections[project_id]
                logger.info(f"No more active connections for project {project_id}")
    
    async def broadcast(self, project_id: str, message: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients for a project
        
        Args:
            project_id: ID of the project to broadcast to
            message: Message to broadcast
        """
        if project_id not in self.active_connections:
            logger.warning(f"No active connections for project {project_id}")
            return
        
        # Add a unique message ID to prevent duplicate processing on the client
        if 'message_id' not in message:
            message['message_id'] = str(uuid.uuid4())
        
        logger.debug(f"Broadcasting message to {len(self.active_connections[project_id])} clients in project {project_id}: {message['type']}")
        
        # Send message to all connected clients
        disconnected_clients = []
        for websocket in self.active_connections[project_id]:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to client: {str(e)}")
                # Mark client for disconnection
                disconnected_clients.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected_clients:
            self.disconnect(websocket, project_id)
    
    async def send_personal_message(self, websocket: WebSocket, message: Dict[str, Any]) -> None:
        """
        Send a message to a specific client
        
        Args:
            websocket: WebSocket connection to send to
            message: Message to send
        """
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message to client: {str(e)}")
            # Don't disconnect here, as we don't know which project this is for
    
    def get_connection_count(self, project_id: str) -> int:
        """
        Get the number of active connections for a project
        
        Args:
            project_id: ID of the project
            
        Returns:
            int: Number of active connections
        """
        if project_id not in self.active_connections:
            return 0
        
        return len(self.active_connections[project_id])
