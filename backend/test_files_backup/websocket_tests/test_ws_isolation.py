"""Test WebSocket with progressive complexity to isolate the issue"""
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test 1: Bare minimum FastAPI with WebSocket
def test_bare_minimum():
    app = FastAPI()
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("Test 1: Bare minimum works!")
        await websocket.close()
    
    logger.info("Test 1: Running bare minimum FastAPI with WebSocket on port 8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)

# Test 2: Add CORS middleware
def test_with_cors():
    app = FastAPI()
    
    # Add CORS exactly like main app
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("Test 2: With CORS works!")
        await websocket.close()
    
    logger.info("Test 2: Running FastAPI with CORS middleware on port 8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)

# Test 3: Add startup event
def test_with_startup():
    app = FastAPI()
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["*"],
    )
    
    @app.on_event("startup")
    async def startup_event():
        logger.info("Startup event triggered")
    
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_text("Test 3: With startup event works!")
        await websocket.close()
    
    logger.info("Test 3: Running FastAPI with CORS and startup event on port 8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        test_num = sys.argv[1]
        if test_num == "1":
            test_bare_minimum()
        elif test_num == "2":
            test_with_cors()
        elif test_num == "3":
            test_with_startup()
        else:
            print("Usage: python test_ws_isolation.py [1|2|3]")
    else:
        print("Usage: python test_ws_isolation.py [1|2|3]")
        print("  1: Bare minimum FastAPI with WebSocket")
        print("  2: Add CORS middleware")
        print("  3: Add startup event")
