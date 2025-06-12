from fastapi import FastAPI, WebSocket
import uvicorn
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Minimal WebSocket Test Server"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    print(f"WebSocket connection attempt from {websocket.client}")
    try:
        await websocket.accept()
        print("WebSocket connection accepted")
        
        await websocket.send_text("Hello from minimal WebSocket server!")
        
        # Wait for a message
        data = await websocket.receive_text()
        print(f"Received: {data}")
        
        await websocket.send_text(f"Echo: {data}")
        
        # Close gracefully
        await websocket.close()
        print("WebSocket connection closed")
        
    except Exception as e:
        print(f"WebSocket error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("Starting minimal WebSocket server on port 8001...")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="debug")
