from fastapi import APIRouter
from app.api.endpoints import documents_sqlalchemy, projects, agents, websocket, insights, document_generation, debug


api_router = APIRouter()

# Include all endpoint routers
# Use the SQLAlchemy-based document endpoints instead of the original ones
# The frontend is expecting the upload endpoint at /api/v1/documents/upload
api_router.include_router(documents_sqlalchemy.router, prefix="/documents", tags=["documents"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(insights.router, prefix="/insights", tags=["insights"])
api_router.include_router(document_generation.router, prefix="/documents/generate", tags=["document-generation"])
api_router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
api_router.include_router(debug.router, prefix="/debug", tags=["debug"])
