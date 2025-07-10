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
    description: str = "Search for information in project documents based on a query. Takes query as input and returns relevant document content."
    project_id: str = ""
    chroma_client: Any = None
    has_chroma_documents: bool = False
    
    # Add args_schema if needed by CrewAI
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, project_id: str):
        """
        Initialize the document search tool
        
        Args:
            project_id: ID of the project to search documents for
        """
        super().__init__()
        self.project_id = project_id
        
        # Import dependencies here to avoid circular imports
        from app.db.init_db_simple import get_chroma_client
        self.chroma_client = get_chroma_client()
        
        # Set up a flag to track if ChromaDB has documents
        self.has_chroma_documents = False
        
        # Log tool initialization
        logger.info(f"DocumentSearchTool initialized for project {project_id}")
        print(f"TOOL INIT: DocumentSearchTool for project {project_id}")
        
        # Skip test run during initialization to avoid CrewAI conflicts
        # The tool will be tested when actually used by agents
        print(f"TOOL INIT: DocumentSearchTool ready for project {project_id}")
    
    def _get_documents_from_db(self) -> List[Dict]:
        """
        Get documents directly from the database as a fallback
        using a synchronous approach to avoid async context issues
        
        Returns:
            List of document dictionaries
        """
        import os
        from sqlalchemy import create_engine, text, exc
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy.pool import QueuePool
        from dotenv import load_dotenv
        import time
        
        load_dotenv()
        
        # Use unified database configuration from settings
        from app.core.config import settings
        database_url = settings.DATABASE_URI
        
        # Convert from async to sync format if needed for PostgreSQL
        if database_url.startswith("postgresql+asyncpg"):
            database_url = database_url.replace("postgresql+asyncpg", "postgresql")
        elif database_url.startswith("postgresql://") and settings.is_postgresql:
            # Already in sync format, keep as is
            pass
        
        logger.info(f"Fetching documents synchronously from database for project {self.project_id}")
        logger.info(f"Using database: {database_url}")
        
        # Set up retry parameters
        max_retries = 3
        retry_delay = 1  # seconds
        attempt = 0
        
        while attempt < max_retries:
            attempt += 1
            try:
                # Create a synchronous engine with connection pooling and timeout settings
                engine = create_engine(
                    database_url,
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_timeout=30,
                    pool_recycle=1800,  # Recycle connections after 30 minutes
                    connect_args={"connect_timeout": 10}  # 10 seconds connection timeout
                )
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                
                with SessionLocal() as session:
                    # Execute a raw SQL query to get documents for this project
                    query = text(
                        """SELECT id, filename, file_path, content_type, 
                                  description, doc_metadata 
                           FROM documents 
                           WHERE project_id = :project_id"""
                    )
                    
                    result = session.execute(query, {"project_id": self.project_id})
                    
                    # Convert result to list of dictionaries
                    documents = []
                    for row in result:
                        doc = {
                            "id": str(row.id),
                            "filename": row.filename,
                            "file_path": row.file_path,
                            "content_type": row.content_type,
                            "description": row.description,
                        }
                    
                        # Get content from document chunks if available
                        try:
                            chunk_query = text(
                                """SELECT content FROM document_chunks 
                                   WHERE document_id = :doc_id 
                                   ORDER BY chunk_index ASC"""
                            )
                            chunk_result = session.execute(chunk_query, {"doc_id": row.id})
                            content_parts = [chunk.content for chunk in chunk_result if chunk.content]
                            logger.info(f"Retrieved {len(content_parts)} chunks for document {row.id}")
                        except Exception as chunk_error:
                            logger.warning(f"Error retrieving chunks for document {row.id}: {chunk_error}")
                            content_parts = []
                    
                        if content_parts:
                            doc["content"] = " ".join(content_parts)
                        else:
                            doc["content"] = "Document content not available"
                        
                        documents.append(doc)
                    
                    logger.info(f"Successfully retrieved {len(documents)} documents from database for project {self.project_id}")
                    return documents
                
            except exc.SQLAlchemyError as db_error:
                logger.error(f"Database error on attempt {attempt}/{max_retries}: {db_error}")
                if attempt < max_retries:
                    logger.info(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.error("Maximum retry attempts reached, giving up")
                    return []
            except Exception as e:
                logger.error(f"Error fetching documents from database: {e}")
                return []
        
        # If we've exhausted all retry attempts
        logger.error("Failed to fetch documents after multiple attempts")
        return []
    
    def batch_search(self, queries: list, limit_per_query: int = 3) -> str:
        """
        Perform multiple document searches in a single operation to reduce API calls
        
        Args:
            queries: List of search queries to execute
            limit_per_query: Maximum results per query
            
        Returns:
            Combined search results from all queries
        """
        logger.info(f"BATCH DOCUMENT SEARCH - Project: {self.project_id}, Queries: {queries}")
        print(f"BATCH DOCUMENT SEARCH - Project: {self.project_id}, Queries: {len(queries)} queries")
        
        all_results = []
        seen_content = set()  # Avoid duplicate content
        
        for query in queries:
            try:
                # Get results for this query
                query_results = self._search_single_query(query, limit_per_query)
                
                # Add unique results to combined results
                for result in query_results:
                    content_hash = hash(result.get('content', '')[:200])  # Hash first 200 chars
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        result['query'] = query  # Track which query found this
                        all_results.append(result)
                        
            except Exception as e:
                logger.error(f"Error in batch search for query '{query}': {e}")
                continue
        
        # Format combined results
        if not all_results:
            return "No relevant documents found for any of the search queries."
        
        # Organize results by relevance and query
        formatted_sections = []
        
        # Group by query for better organization
        query_groups = {}
        for result in all_results:
            query = result.get('query', 'unknown')
            if query not in query_groups:
                query_groups[query] = []
            query_groups[query].append(result)
        
        # Format each query group
        for query, results in query_groups.items():
            if results:
                formatted_sections.append(f"## Results for '{query}':")
                for i, result in enumerate(results[:limit_per_query]):
                    formatted_sections.append(
                        f"**Document {i+1}**: {result.get('source', 'Unknown')}\n"
                        f"**Content**: {result.get('content', 'No content')}\n"
                    )
                formatted_sections.append("")  # Add spacing between query groups
        
        combined_result = "\n".join(formatted_sections)
        logger.info(f"Batch search complete: {len(all_results)} unique results from {len(queries)} queries")
        return combined_result
    
    def _search_single_query(self, query: str, limit: int) -> list:
        """
        Execute a single search query and return results as list of dictionaries
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of result dictionaries
        """
        results = []
        
        try:
            # Try ChromaDB first
            collection_name = f"project_{self.project_id}"
            
            if self.chroma_client is not None:
                try:
                    collection = self.chroma_client.get_collection(collection_name)
                    chroma_results = collection.query(
                        query_texts=[query],
                        n_results=limit
                    )
                    
                    if chroma_results and chroma_results["documents"] and len(chroma_results["documents"][0]) > 0:
                        for i in range(len(chroma_results["documents"][0])):
                            document_text = chroma_results["documents"][0][i]
                            metadata = chroma_results["metadatas"][0][i] if chroma_results.get("metadatas") else {}
                            
                            results.append({
                                'source': metadata.get("source", "Unknown document"),
                                'document_id': metadata.get("document_id", "Unknown ID"),
                                'content': document_text,
                                'relevance': i + 1
                            })
                        return results
                        
                except Exception as e:
                    logger.warning(f"ChromaDB search failed for query '{query}': {e}")
            
            # Fall back to database search
            documents = self._get_documents_from_db()
            if documents:
                for doc in documents:
                    if "content" not in doc or not doc["content"]:
                        continue
                    
                    # Simple keyword matching
                    if query.lower() in doc["content"].lower():
                        results.append({
                            'source': doc.get('filename', 'Unnamed'),
                            'document_id': doc.get('id', 'Unknown'),
                            'content': doc.get('content', '')[:500] + "...",
                            'relevance': len(results) + 1
                        })
                        
                        if len(results) >= limit:
                            break
            
        except Exception as e:
            logger.error(f"Error in single query search for '{query}': {e}")
        
        return results
    
    def _run(self, query: str, limit: int = 5) -> str:
        """
        Run the tool to search for documents
        
        Args:
            query: Search query
            limit: Maximum number of results to return
            
        Returns:
            String with search results
        """
        logger.info(f"DOCUMENT SEARCH TOOL CALLED - Project: {self.project_id}, Query: '{query}', Limit: {limit}")
        print(f"DOCUMENT SEARCH TOOL CALLED - Project: {self.project_id}, Query: '{query}'")  # Console output for visibility
        print(f"TOOL EXECUTION START: {self.__class__.__name__} at {__import__('datetime').datetime.now()}")  # Timestamp for tracking
        
        try:
            # First try with ChromaDB
            collection_name = f"project_{self.project_id}"
            results = None
            
            # Verify ChromaDB connection is available
            if self.chroma_client is None:
                logger.warning("ChromaDB client is not initialized, falling back to database")
                self.has_chroma_documents = False
            else:
                try:
                    # Test if ChromaDB is responsive by listing collections
                    if hasattr(self.chroma_client, "list_collections"):
                        try:
                            # Quick smoke test to verify ChromaDB is operational
                            collection_list = self.chroma_client.list_collections()
                            logger.info(f"ChromaDB connection verified with {len(collection_list)} collections")
                        except Exception as conn_error:
                            logger.error(f"ChromaDB connection test failed: {conn_error}")
                            logger.warning("Falling back to database query")
                            self.has_chroma_documents = False
                            # Skip the rest of ChromaDB operations
                            raise RuntimeError(f"ChromaDB connection failed: {conn_error}")
                    
                    # Try to get the collection for this project
                    collection = self.chroma_client.get_collection(collection_name)
                    
                    # Search for documents
                    results = collection.query(
                        query_texts=[query],
                        n_results=limit
                    )
                    
                    # Check if we got actual results
                    if results and results["documents"] and len(results["documents"][0]) > 0:
                        logger.info(f"Found {len(results['documents'][0])} results in ChromaDB")
                        self.has_chroma_documents = True
                    else:
                        logger.warning("No results in ChromaDB, falling back to database")
                        self.has_chroma_documents = False
                except Exception as e:
                    logger.warning(f"Error searching ChromaDB: {e}")
                    self.has_chroma_documents = False
            
            # If no results in ChromaDB or ChromaDB failed, fall back to database
            if not self.has_chroma_documents:
                # Fall back to direct database query
                documents = self._get_documents_from_db()
                
                if not documents:
                    return "No documents found for this project."
                
                # Very basic search - just check if query appears in document content
                relevant_docs = []
                for doc in documents:
                    # Skip documents without content
                    if "content" not in doc or not doc["content"]:
                        continue
                        
                    # Simple keyword matching
                    if query.lower() in doc["content"].lower():
                        relevant_docs.append(doc)
                    
                    # Limit to requested number
                    if len(relevant_docs) >= limit:
                        break
                
                if not relevant_docs:
                    # Try less strict matching - match any word in the query
                    query_words = query.lower().split()
                    for doc in documents:
                        if "content" not in doc or not doc["content"]:
                            continue
                            
                        doc_content = doc["content"].lower()
                        if any(word in doc_content for word in query_words):
                            if doc not in relevant_docs:
                                relevant_docs.append(doc)
                        
                        if len(relevant_docs) >= limit:
                            break
                
                # Format results from database
                if not relevant_docs:
                    return "No relevant documents found for your query."
                    
                formatted_results = []
                for i, doc in enumerate(relevant_docs):
                    formatted_results.append(
                        f"Document: {doc.get('filename', 'Unnamed')} (ID: {doc.get('id', 'Unknown')}\n"
                        f"Relevance: {i+1}/{len(relevant_docs)}\n"
                        f"Content snippet: {doc.get('content', '')[:500]}..."
                    )
                
                result = "\n\n".join(formatted_results)
                print(f"DATABASE FALLBACK COMPLETE: Found {len(formatted_results)} results, total length: {len(result)} characters")
                return result
            
            # Format results from ChromaDB (if we have them)
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
            
            result = "\n\n".join(formatted_results)
            print(f"TOOL EXECUTION COMPLETE: Found {len(formatted_results)} results, total length: {len(result)} characters")
            return result
        
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            print(f"TOOL EXECUTION ERROR: {str(e)}")
            return f"Error searching documents: {str(e)}"
