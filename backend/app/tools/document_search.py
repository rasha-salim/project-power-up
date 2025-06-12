import logging
from typing import List, Dict, Any, Optional
from crewai.tools import BaseTool
import chromadb
from chromadb.config import Settings
import os

logger = logging.getLogger(__name__)

class DocumentSearchTool(BaseTool):
    """Tool for searching project documents using ChromaDB"""
    
    name: str = "document_search"
    description: str = "Search for information in project documents based on a query"
    
    def __init__(self, project_id: str):
        """
        Initialize the document search tool
        
        Args:
            project_id: ID of the project to search documents for
        """
        super().__init__()
        self.project_id = project_id
        self.chroma_client = self._connect_to_chromadb()
    
    def _connect_to_chromadb(self):
        """
        Connect to ChromaDB
        
        Returns:
            ChromaDB client
        """
        chroma_db_dir = os.getenv("CHROMA_DB_DIR", "./chroma_db")
        logger.info(f"Connecting to ChromaDB at {chroma_db_dir}")
        
        try:
            client = chromadb.Client(Settings(
                persist_directory=chroma_db_dir,
                anonymized_telemetry=False
            ))
            return client
        except Exception as e:
            logger.error(f"Error connecting to ChromaDB: {e}")
            raise
    
    def _run(self, query: str, limit: int = 5) -> str:
        """
        Run the tool to search for documents
        
        Args:
            query: Search query
            limit: Maximum number of results to return
            
        Returns:
            String with search results
        """
        logger.info(f"Searching documents for project {self.project_id} with query: {query}")
        
        try:
            # Get the collection for this project
            collection_name = f"project_{self.project_id}"
            
            try:
                collection = self.chroma_client.get_collection(collection_name)
            except Exception as e:
                logger.warning(f"Collection {collection_name} not found: {e}")
                return "No documents found for this project."
            
            # Search for documents
            results = collection.query(
                query_texts=[query],
                n_results=limit
            )
            
            # Format results
            if not results or not results["documents"] or len(results["documents"][0]) == 0:
                return "No relevant documents found for your query."
            
            formatted_results = []
            for i in range(len(results["documents"][0])):
                document_text = results["documents"][0][i]
                metadata = results["metadatas"][0][i] if results.get("metadatas") and results["metadatas"][0] else {}
                
                source = metadata.get("source", "Unknown document")
                document_id = metadata.get("document_id", "Unknown ID")
                
                formatted_results.append(
                    f"Document: {source} (ID: {document_id})\n"
                    f"Relevance: {i+1}/{len(results['documents'][0])}\n"
                    f"Content: {document_text}\n"
                )
            
            return "\n\n".join(formatted_results)
        
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return f"Error searching documents: {str(e)}"
