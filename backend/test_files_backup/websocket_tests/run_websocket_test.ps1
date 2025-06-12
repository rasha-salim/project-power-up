# Activate the virtual environment
.\venv\Scripts\Activate.ps1

# Install websockets if not already installed
pip install websockets

# Run the WebSocket integration test
python test_websocket_integration.py
