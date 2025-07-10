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
        logger.info(f"📥 Download request: project_id={project_id}, document_id={document_id}")
        
        # Get document metadata
        logger.info(f"🔍 Fetching documents list for project {project_id}")
        documents = await document_generation_service.list_generated_documents(db, project_id)
        
        logger.info(f"📋 Found {len(documents)} documents for project {project_id}")
        for i, doc in enumerate(documents):
            logger.info(f"  Document {i+1}: id={doc.get('id')}, filename={doc.get('filename')}, file_path={doc.get('file_path')}")
        
        document = None
        for doc in documents:
            if doc.get('id') == document_id:
                document = doc
                logger.info(f"✅ Found matching document: {doc}")
                break
        
        if not document:
            logger.error(f"❌ Document with ID {document_id} not found in {len(documents)} available documents")
            logger.error(f"Available document IDs: {[doc.get('id') for doc in documents]}")
            raise HTTPException(status_code=404, detail=f"Document not found. Available documents: {len(documents)}")
        
        # Check if content is stored in database (new format)
        if 'content' in document:
            logger.info(f"📦 Content found in database for document {document_id}")
            content = document['content']
            logger.info(f"✅ Database content retrieved, length: {len(content)} characters")
        else:
            # Fallback to file system for legacy documents
            file_path = document.get('file_path')
            logger.info(f"📁 Fallback to file system: {file_path}")
            
            if not file_path:
                logger.error(f"❌ No content in database and no file_path found in document metadata: {document}")
                raise HTTPException(status_code=404, detail="Document content not available")
                
            if not os.path.exists(file_path):
                logger.error(f"❌ File does not exist at path: {file_path}")
                logger.info(f"🔍 Checking if directory exists: {os.path.dirname(file_path)}")
                logger.info(f"Directory exists: {os.path.exists(os.path.dirname(file_path))}")
                if os.path.exists(os.path.dirname(file_path)):
                    logger.info(f"📂 Files in directory: {os.listdir(os.path.dirname(file_path))}")
                raise HTTPException(status_code=404, detail=f"Document content not found in database or file system")
            
            # Read file content
            logger.info(f"📖 Reading file content from: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            logger.info(f"✅ File read successfully, content length: {len(content)} characters")
        
        # Return file as download
        filename = document.get('filename', 'document.md')
        logger.info(f"📤 Returning file download: {filename}")
        
        return Response(
            content=content,
            media_type='text/markdown',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        
    except HTTPException as he:
        logger.error(f"❌ HTTP Exception in download: {he.status_code} - {he.detail}")
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error downloading document: {str(e)}")
        logger.error(f"Exception type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error downloading document: {str(e)}")