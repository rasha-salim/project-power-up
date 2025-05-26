from fastapi import APIRouter
from app.api.endpoints import documents, projects, agents, websocket, test, working_upload

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
api_router.include_router(test.router, prefix="/test", tags=["test"])

# Include working upload endpoint (reliable implementation)
api_router.include_router(working_upload.router, prefix="/working", tags=["working"])
