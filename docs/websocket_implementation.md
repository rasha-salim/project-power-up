# WebSocket Implementation Documentation

## Overview

This document outlines the WebSocket implementation in the Project Power-Up backend application. The WebSocket functionality enables real-time communication between clients and the server for agent conversations and updates.

## Core Implementation

### Main WebSocket Endpoint

**File**: `app/api/endpoints/websocket.py`

The primary WebSocket endpoint is implemented in the FastAPI application at the route `/agent-conversation/{project_id}`. This endpoint:

1. Accepts WebSocket connections for a specific project
2. Generates a unique client ID for each connection
3. Manages active connections in an in-memory dictionary
4. Handles various message types (ping/pong, user messages)
5. Broadcasts messages to other clients in the same project
6. Implements connection cleanup on disconnect
7. Includes detailed logging for connection lifecycle events

Key features of the implementation:

- **Connection Management**: Uses a nested dictionary structure to store active connections by project ID and client ID
- **Message Handling**: Parses JSON messages and handles different message types
- **Keep-Alive Mechanism**: Sends periodic server pings and responds to client pings
- **Error Handling**: Gracefully handles WebSocket disconnects and other exceptions
- **Logging**: Detailed logging at various levels to trace connection lifecycle and message flow

### WebSocket Manager

**File**: `app/services/websocket_manager.py`

A service class that manages WebSocket connections and provides methods for:

- Adding connections to the active connections pool
- Removing connections from the pool
- Broadcasting messages to all clients in a project

## Test Clients and Utilities

Throughout the development process, several test clients and utilities were created to test and debug the WebSocket functionality:

1. **Python WebSocket Client**
   - **File**: `backend/python_ws_client.py`
   - A command-line Python client using the `websockets` library to test connections to the WebSocket endpoint

2. **Standalone WebSocket Server**
   - **File**: `backend/standalone_ws_server.py`
   - A simple WebSocket echo server implemented with the `websockets` library for testing WebSocket functionality independently of FastAPI

3. **HTML WebSocket Clients**:
   - **File**: `backend/standalone_ws_client.html`
     - A browser-based WebSocket client with UI controls for connect, disconnect, send message, and ping
   - **File**: `backend/minimal_ws_client.html`
     - A simplified version of the WebSocket client for basic testing
   - **File**: `backend/debug_ws_client.html`
     - An enhanced WebSocket client with additional debugging features

4. **Simple Agent WebSocket Implementation**
   - **File**: `backend/app/api/endpoints/simple_agent_ws.py`
     - A simplified WebSocket endpoint implementation used for testing and debugging

5. **PowerShell Test Script**
   - **File**: `backend/run_websocket_test.ps1`
     - A script to automate WebSocket testing

## Implementation Process

The WebSocket implementation went through several iterations to address connection stability issues:

1. **Initial Implementation**: Started with a complex implementation that integrated with agent services
2. **Troubleshooting**: Identified issues with connection acceptance and handling
3. **Simplified Testing**: Created standalone test clients and servers to isolate WebSocket functionality
4. **Clean Implementation**: Rebuilt the WebSocket endpoint with a minimal, clean implementation focusing on core functionality
5. **Incremental Complexity**: Plan to incrementally add complexity after confirming stable connections

## Current Status

The current implementation provides a clean, minimal WebSocket endpoint that:
- Accepts connections
- Handles basic message types
- Implements connection management
- Includes detailed logging

However, there are still some connection issues to resolve, particularly with WebSocket close code 1006 (abnormal closure).

## Next Steps

1. Resolve remaining connection stability issues
2. Integrate with agent services for message processing
3. Implement authentication and authorization for WebSocket connections
4. Add database integration for persistent message storage
5. Enhance error handling and recovery mechanisms

## Configuration

The WebSocket endpoint is configured through the FastAPI application with CORS settings in `app/main.py` that allow WebSocket connections:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

## Debugging Tips

When troubleshooting WebSocket connection issues:
1. Check the server logs for connection lifecycle events
2. Verify CORS settings if connecting from a different origin
3. Look for WebSocket close codes and reasons
4. Test with simplified clients to isolate issues
5. Ensure proper error handling in both client and server code

## Debugging Session: Resolving WebSocket Close Code 1006

### Problem
The WebSocket connection was failing with close code 1006 (abnormal closure) when trying to connect to the main application's WebSocket endpoint. The error occurred immediately upon connection attempt, suggesting the connection was failing at a very early stage.

### Debugging Process

1. **Created Minimal Test Servers**: Built several minimal FastAPI applications to isolate the issue:
   - Bare minimum FastAPI with WebSocket (worked )
   - FastAPI with CORS middleware (worked )
   - FastAPI with startup event (worked )
   - Main app without database initialization (worked )

2. **Key Discovery**: The test endpoint added directly to main.py (`/test-ws-direct`) worked, but the router-based endpoint failed.

3. **Root Cause**: The WebSocket URL path was incorrect. The frontend was trying to connect to:
   - `/agent-conversation/{project_id}`
   
   But the actual path, due to router prefixes, was:
   - `/api/v1/ws/agent-conversation/{project_id}`

### Solution

The WebSocket endpoint is accessible at the following URL pattern:
```
ws://localhost:8000/api/v1/ws/agent-conversation/{project_id}
```

This path is constructed from:
- Main app prefix: `/api/v1` (defined in main.py)
- WebSocket router prefix: `/ws` (defined in routes.py)
- Endpoint path: `/agent-conversation/{project_id}` (defined in websocket.py)

### Lessons Learned

1. **Always verify the complete URL path** when dealing with nested routers in FastAPI
2. **Test endpoints directly** before testing through routers to isolate routing issues
3. **WebSocket close code 1006** often indicates the endpoint doesn't exist or isn't accessible
4. **Progressive isolation testing** (minimal → with middleware → with startup → full app) is effective for debugging

### Test Files Created During Debugging

- `test_ws_isolation.py` - Progressive complexity tests
- `test_isolation.html` - HTML client for testing different endpoints
- `test_main_no_db.py` - Main app without database initialization
- `minimal_fastapi_ws.py` - Bare minimum WebSocket server
- `minimal_ws_test.html` - Test client for minimal server

### Final Working Configuration

- **WebSocket Endpoint**: `/api/v1/ws/agent-conversation/{project_id}`
- **CORS Settings**: Allow all origins (for development)
- **Connection Management**: In-memory dictionary by project_id and client_id
- **Message Format**: JSON with message types (ping, pong, user_message, system_message)
