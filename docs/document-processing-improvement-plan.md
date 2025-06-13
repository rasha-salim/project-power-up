# Document Processing Pipeline Improvement Plan

This document outlines a comprehensive plan to enhance the document processing pipeline for the Project Power-Up system, focusing on improving how documents are processed and prepared for agentic analysis.

## Current Limitations

1. Limited file type support (only TXT files fully implemented)
2. Basic chunking strategy based on character count
3. No specific embedding model configured
4. Limited context window (1000 characters) for agent analysis
5. No document prioritization
6. Simulated agent analysis instead of real AI agents

## Implementation Plan

### Phase 1: Immediate Improvements

#### 1. Expand File Type Support

**Goal**: Add proper support for DOCX files in addition to TXT files.

**Implementation Steps**:

1. Add `python-docx` library to `requirements.txt`:
   ```
   python-docx==0.8.11
   ```

2. Update the `process_document` method in `DocumentProcessor` class:

```python
async def process_document(self, document_id: str, file_path: str, db) -> None:
    try:
        logger.info(f"Starting processing of document {document_id} at path {file_path}")
        
        # Update document status to processing
        await self.update_document_status(db, document_id, "processing")
        
        # Verify file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found at path {file_path}")
            await self.update_document_status(db, document_id, "error")
            await self.update_document(
                db,
                document_id,
                DocumentUpdate(doc_metadata={"error": "File not found"})
            )
            return
        
        # Extract text from document based on file type
        file_ext = os.path.splitext(file_path)[1].lower()
        logger.info(f"Detected file extension: {file_ext}")
        
        if file_ext == ".pdf":
            # PDF support will be added in future phases
            logger.warning(f"PDF support not yet implemented for {file_path}")
            text_content = "PDF content would be extracted here"
            
        elif file_ext == ".docx":
            # Use python-docx to extract text from DOCX files
            from docx import Document as DocxDocument
            
            docx_document = DocxDocument(file_path)
            paragraphs = [p.text for p in docx_document.paragraphs if p.text.strip()]
            text_content = "\n\n".join(paragraphs)
            logger.info(f"Extracted DOCX content from {file_path}, size: {len(text_content)} characters")
            
        elif file_ext == ".txt":
            # Simple text file reading
            with open(file_path, "r", encoding="utf-8") as f:
                text_content = f.read()
            logger.info(f"Read text file content from {file_path}, size: {len(text_content)} characters")
                
        else:
            logger.error(f"Unsupported file type: {file_ext}")
            await self.update_document_status(db, document_id, "error")
            await self.update_document(
                db,
                document_id,
                DocumentUpdate(doc_metadata={"error": f"Unsupported file type: {file_ext}"})
            )
            return
        
        # Continue with existing processing...
        # (chunking and vectorization)
```

#### 3. Specify an Embedding Model

**Goal**: Configure a specific embedding model for document vectorization.

**Implementation Steps**:

1. Add sentence-transformers to `requirements.txt`:
   ```
   sentence-transformers==2.2.2
   ```

2. Update the ChromaDB configuration in `app/db/init_db.py`:

```python
def get_chroma_client():
    """Get or create a ChromaDB client"""
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    
    # Use sentence-transformers for embeddings
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"  # A good balance between performance and quality
    )
    
    # Configure ChromaDB client
    client = chromadb.Client(
        Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=settings.CHROMA_PERSIST_DIRECTORY
        )
    )
    
    return client
```

3. Update the `_vectorize_chunks` method to use the embedding function:

```python
async def _vectorize_chunks(self, document_id: str, chunks: List[str]) -> None:
    """
    Vectorize text chunks and store in ChromaDB
    
    Args:
        document_id: ID of the document
        chunks: List of text chunks to vectorize
    """
    # Get ChromaDB client
    client = get_chroma_client()
    
    # Get or create collection with the embedding function
    from chromadb.utils import embedding_functions
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    collection = client.get_or_create_collection(
        name="documents",
        embedding_function=sentence_transformer_ef
    )
    
    logger.info(f"Connected to ChromaDB collection 'documents' with embedding model 'all-MiniLM-L6-v2'")
    
    # Continue with existing implementation...
```

#### 6. Implement Real AI Agents

**Goal**: Replace simulated agent responses with actual AI agent implementation.

**Implementation Steps**:

1. Update the `execute_crew_analysis` method in `AgentService` class to use real agents:

```python
async def execute_crew_analysis(self, analysis_id: str, project_id: str, db: AsyncSession) -> None:
    """
    Execute a crew analysis
    
    Args:
        analysis_id: ID of the analysis
        project_id: ID of the project to analyze
        db: Database session
    """
    try:
        logger.info(f"Executing crew analysis {analysis_id} for project {project_id}")
        
        # Check if all documents for this project are processed
        # (existing code)
        
        # Set up Anthropic LLM
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")
        
        if not anthropic_api_key:
            logger.error("ANTHROPIC_API_KEY not found in environment variables")
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")
        
        # Initialize the Anthropic LLM
        from langchain_anthropic import ChatAnthropic
        llm = ChatAnthropic(model_name=anthropic_model, anthropic_api_key=anthropic_api_key)
        
        # Load crew configuration
        crew_config = self.config_loader.get_crew_config("project_analysis_crew")
        if not crew_config:
            logger.error("Crew configuration not found")
            raise ValueError("Crew configuration not found")
        
        # Create agents (existing code)
        technical_agent = self._create_technical_agent()
        technical_agent.llm = llm
        
        risk_agent = self._create_risk_agent()
        risk_agent.llm = llm
        
        planning_agent = self._create_planning_agent()
        planning_agent.llm = llm
        
        # Prepare document content for agents (existing code)
        
        # Create tasks for each agent with document content
        technical_task = self._create_technical_task(technical_agent, context_str)
        risk_task = self._create_risk_task(risk_agent, context_str)
        planning_task = self._create_planning_task(planning_agent, project_id, [technical_task, risk_task])
        
        # Create the crew
        from crewai import Crew, Process
        crew = Crew(
            agents=[technical_agent, risk_agent, planning_agent],
            tasks=[technical_task, risk_task, planning_task],
            verbose=crew_config.get("verbose", True),
            process=Process.sequential,  # Execute tasks in sequence
            memory=crew_config.get("memory", False)
        )
        
        # Run the crew - UNCOMMENT THIS TO USE REAL AGENTS
        result = crew.kickoff()
        
        # Parse and store the results
        analysis_results = {
            "technical_analysis": self._extract_technical_analysis(result),
            "risk_assessment": self._extract_risk_assessment(result),
            "project_plan": self._extract_project_plan(result),
            "analysis_id": analysis_id,
            "completed_at": str(datetime.now())
        }
        
        # Store the results
        project_service = ProjectService()
        await project_service.store_project_insights(db, project_id, analysis_results)
        
        logger.info(f"Completed crew analysis {analysis_id} for project {project_id}")
        
    except Exception as e:
        logger.error(f"Error executing crew analysis {analysis_id}: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
```

2. Add helper methods to extract structured results from agent outputs:

```python
def _extract_technical_analysis(self, crew_result: str) -> Dict[str, Any]:
    """Extract technical analysis from crew result"""
    # In a real implementation, this would parse the crew result
    # For now, we'll extract sections based on headers
    
    # Look for sections like "# Technical Analysis", "## Architecture", etc.
    # This is a simplified implementation
    
    architecture = ""
    tech_stack = ""
    feasibility = ""
    
    # Simple parsing based on headers
    lines = crew_result.split("\n")
    current_section = None
    
    for line in lines:
        if "architecture" in line.lower() and line.startswith("#"):
            current_section = "architecture"
            continue
        elif "tech stack" in line.lower() and line.startswith("#"):
            current_section = "tech_stack"
            continue
        elif "feasibility" in line.lower() and line.startswith("#"):
            current_section = "feasibility"
            continue
        elif line.startswith("#"):
            current_section = None
            continue
            
        if current_section == "architecture":
            architecture += line + "\n"
        elif current_section == "tech_stack":
            tech_stack += line + "\n"
        elif current_section == "feasibility":
            feasibility += line + "\n"
    
    return {
        "architecture": architecture.strip(),
        "tech_stack": tech_stack.strip(),
        "feasibility": feasibility.strip()
    }

# Similar methods for _extract_risk_assessment and _extract_project_plan
```

### Phase 2: Future Improvements

#### 2. Enhanced Chunking System

**Next Steps**:

1. Implement semantic chunking based on paragraph or section boundaries
2. Add support for hierarchical chunking to preserve document structure
3. Implement adaptive chunk sizes based on content complexity
4. Add metadata to chunks about their position in the document structure

**Implementation Plan**:
- Research and evaluate text splitting libraries like LangChain's text splitters
- Implement a more sophisticated chunking strategy that respects semantic boundaries
- Add configuration options for chunk size and overlap
- Store additional metadata about chunk relationships

#### 4. Improved Context Window

**Next Steps**:

1. Implement a sliding context window approach
2. Add support for retrieving relevant chunks based on query
3. Implement a summarization step for large documents
4. Add support for hierarchical context (document → section → paragraph)

**Implementation Plan**:
- Implement a retrieval-augmented generation (RAG) approach
- Add a query generation step to identify relevant chunks
- Implement a summarization service using the same LLM
- Create a hierarchical context structure for better navigation

#### 5. Document Prioritization

**Next Steps**:

1. Implement relevance scoring for documents
2. Add support for user-defined document importance
3. Implement automatic document categorization
4. Add support for document relationships

**Implementation Plan**:
- Add a relevance scoring system based on semantic similarity
- Implement a user interface for setting document importance
- Add automatic categorization using the embedding model
- Create a graph-based representation of document relationships

## Implementation Timeline

### Phase 1 (Immediate Improvements)
- Week 1: Expand file type support (DOCX)
- Week 1: Specify embedding model
- Week 2: Implement real AI agents

### Phase 2 (Future Improvements)
- Week 3-4: Enhanced chunking system
- Week 5-6: Improved context window
- Week 7-8: Document prioritization

## Required Dependencies

Add the following to `requirements.txt`:

```
python-docx==0.8.11
sentence-transformers==2.2.2
langchain==0.0.267
langchain-anthropic==0.0.6
crewai==0.28.0
```

## Conclusion

This implementation plan provides a roadmap for enhancing the document processing pipeline in the Project Power-Up system. The immediate improvements focus on expanding file type support, specifying an embedding model, and implementing real AI agents. Future improvements will address more sophisticated chunking strategies, improved context windows, and document prioritization.

By following this plan, the system will be better equipped to process and analyze documents, providing more accurate and comprehensive insights to users.
