import logging
from typing import Dict, List, Any
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
    
    async def connect(self, websocket: WebSocket, project_id: str) -> None:
        """
        Connect a new WebSocket client
        
        Args:
            websocket: WebSocket connection
            project_id: ID of the project the client is connecting to
        """
        # Accept the connection
        await websocket.accept()
        
        # Add to active connections for this project
        if project_id not in self.active_connections:
            self.active_connections[project_id] = []
        
        self.active_connections[project_id].append(websocket)
        logger.info(f"Client connected to project {project_id}. Active connections: {len(self.active_connections[project_id])}")
    
    def disconnect(self, websocket: WebSocket, project_id: str) -> None:
        """
        Disconnect a WebSocket client
        
        Args:
            websocket: WebSocket connection
            project_id: ID of the project the client is disconnecting from
        """
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
