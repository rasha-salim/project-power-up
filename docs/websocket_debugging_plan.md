# WebSocket Debugging Plan - Resolving Code 1006 Error

## Problem Summary
We're experiencing WebSocket close code 1006 (abnormal closure) when trying to connect to our FastAPI WebSocket endpoint. This error indicates the connection is being closed without a proper close frame, suggesting the connection is failing at a very early stage.

## Root Cause Analysis

Based on what we've tried, the issue is likely one of the following:
1. **Middleware interference** - FastAPI middleware might be blocking or interfering with WebSocket upgrade
2. **Route registration order** - WebSocket routes might need special handling in FastAPI
3. **Async context issues** - Problems with async/await in the WebSocket handler
4. **HTTP/WebSocket upgrade failure** - The HTTP-to-WebSocket upgrade process might be failing

## Debugging Plan

### Phase 1: Isolate the Problem (NEW APPROACHES)

#### 1.1 Create a Minimal FastAPI App with ONLY WebSocket
Create a completely separate minimal FastAPI application to test if WebSocket works in isolation:

```python
# minimal_fastapi_ws.py
from fastapi import FastAPI, WebSocket
import uvicorn

app = FastAPI()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("Hello WebSocket")
    await websocket.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

This will tell us if the issue is with FastAPI WebSocket in general or specific to our implementation.

#### 1.2 Test WebSocket Without Any Middleware
Create a test endpoint in our main app but bypass ALL middleware:

```python
# Add this directly to main.py BEFORE any middleware
@app.websocket("/test-ws-raw")
async def test_websocket_raw(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("Direct WebSocket - No Middleware")
    await websocket.close()
```

#### 1.3 Network-Level Debugging
Use browser developer tools to inspect the actual HTTP upgrade request:
- Check the Network tab for the WebSocket upgrade request
- Look for response headers and status codes
- Check if the upgrade request even reaches the server

### Phase 2: Systematic Elimination

#### 2.1 Remove All Complexity from Current Implementation
Temporarily modify our WebSocket endpoint to be absolutely minimal:

```python
@router.websocket("/agent-conversation/{project_id}")
async def agent_conversation_websocket(websocket: WebSocket, project_id: str):
    try:
        await websocket.accept()
        await websocket.send_text("Connected")
        await websocket.close()
    except Exception as e:
        print(f"WebSocket error: {e}")
```

#### 2.2 Test Different WebSocket Libraries
Instead of browser WebSocket, test with:
- `websocat` command-line tool
- `wscat` npm package
- Raw TCP connection to see the HTTP upgrade

#### 2.3 Check for Port/Firewall Issues
- Test on different ports (8001, 8080, 3000)
- Temporarily disable Windows Firewall
- Check if any antivirus is interfering

### Phase 3: Advanced Debugging

#### 3.1 Enable Starlette Debug Logging
Add detailed logging to see the WebSocket upgrade process:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logging.getLogger("uvicorn.protocols.websockets").setLevel(logging.DEBUG)
```

#### 3.2 Inspect FastAPI/Starlette Source
Check if our WebSocket route is being registered correctly:

```python
# Add after app creation
print("Registered routes:")
for route in app.routes:
    print(f"  {route}")
```

#### 3.3 Test with Different ASGI Servers
Try running with different ASGI servers:
- Hypercorn instead of Uvicorn
- Daphne (Django Channels ASGI server)

### Phase 4: Alternative Approaches

#### 4.1 Use Starlette Directly
Create a pure Starlette WebSocket endpoint to bypass FastAPI:

```python
from starlette.websockets import WebSocket
from starlette.routing import WebSocketRoute

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("Starlette WebSocket")
    await websocket.close()

# Add to routes
WebSocketRoute("/starlette-ws", endpoint=websocket_endpoint)
```

#### 4.2 Implement Long Polling as Fallback
If WebSocket continues to fail, implement a long-polling endpoint as a temporary solution while debugging continues.

## Implementation Order

1. **Start with Phase 1.1** - Create minimal FastAPI WebSocket app
2. **If that works**, proceed to Phase 1.2 - Test without middleware
3. **If that fails**, go to Phase 3.1 - Enable debug logging
4. **Network debugging** (Phase 1.3) should be done in parallel
5. **Only proceed to Phase 4** if all else fails

## Success Criteria

We'll know we've found the issue when:
1. We can establish a WebSocket connection without code 1006
2. We can send and receive at least one message
3. The connection closes gracefully

## What NOT to Do (Already Tried)

- Don't create more HTML/Python test clients
- Don't modify CORS settings (already set to allow all)
- Don't create more simplified endpoint variants
- Don't test with standalone WebSocket servers

## Next Immediate Step

Create the minimal FastAPI WebSocket application (Phase 1.1) and test it on a different port. This will immediately tell us if the issue is with our specific implementation or a broader environmental issue.
