from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
import logging
import os
from app.db.init_db_simple import get_async_db
from app.services.document_generation_service import document_generation_service

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/{project_id}/generate/brief")
async def generate_project_brief(
    project_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Generate markdown document from project brief sections
    """
    try:
        document_metadata = await document_generation_service.generate_project_brief_markdown(db, project_id)
        
        if not document_metadata:
            raise HTTPException(status_code=400, detail="Failed to generate project brief document")
        
        return {
            "status": "success",
            "message": "Project brief document generated successfully",
            "document": document_metadata
        }
        
    except Exception as e:
        logger.error(f"Error generating project brief document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating document: {str(e)}")

@router.post("/{project_id}/generate/analysis")
async def generate_analysis_report(
    project_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Generate markdown document from project analysis data
    """
    try:
        document_metadata = await document_generation_service.generate_analysis_report_markdown(db, project_id)
        
        if not document_metadata:
            raise HTTPException(status_code=400, detail="Failed to generate analysis report document")
        
        return {
            "status": "success",
            "message": "Analysis report document generated successfully",
            "document": document_metadata
        }
        
    except Exception as e:
        logger.error(f"Error generating analysis report document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating document: {str(e)}")

@router.post("/{project_id}/generate/comprehensive")
async def generate_comprehensive_report(
    project_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Generate comprehensive markdown document with both brief and analysis
    """
    try:
        document_metadata = await document_generation_service.generate_comprehensive_report_markdown(db, project_id)
        
        if not document_metadata:
            raise HTTPException(status_code=400, detail="Failed to generate comprehensive report document")
        
        return {
            "status": "success",
            "message": "Comprehensive report document generated successfully",
            "document": document_metadata
        }
        
    except Exception as e:
        logger.error(f"Error generating comprehensive report document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating document: {str(e)}")

@router.get("/{project_id}/documents")
async def list_generated_documents(
    project_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    List all generated documents for a project
    """
    try:
        documents = await document_generation_service.list_generated_documents(db, project_id)
        
        return {
            "status": "success",
            "documents": documents,
            "count": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Error listing generated documents: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error listing documents: {str(e)}")

@router.get("/{project_id}/documents/{document_id}")
async def get_document_content(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get the content of a generated document
    """
    try:
        content = await document_generation_service.get_document_content(db, project_id, document_id)
        
        if content is None:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "status": "success",
            "content": content
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document content: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error getting document content: {str(e)}")

@router.get("/{project_id}/documents/{document_id}/download")
async def download_document(
    project_id: str,
    document_id: str,
    db: AsyncSession = Depends(get_async_db)
):
    """
    Download a generated document file
    """
    try:
        # Get document metadata
        documents = await document_generation_service.list_generated_documents(db, project_id)
        document = None
        
        for doc in documents:
            if doc.get('id') == document_id:
                document = doc
                break
        
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")
        
        file_path = document.get('file_path')
        if not file_path or not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Document file not found")
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Return file as download
        filename = document.get('filename', 'document.md')
        
        return Response(
            content=content,
            media_type='text/markdown',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading document: {str(e)}")