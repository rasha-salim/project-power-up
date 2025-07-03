# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **Intelligent Project Planning System** - an AI-powered project planning application that demonstrates human-AI collaboration through specialized agents. The system transforms project briefs and meeting transcripts into comprehensive, actionable project plans using collaborative AI agents powered by CrewAI and Anthropic Claude.

## Architecture

**Full-stack application with:**
- **Backend**: FastAPI (Python) with async operations
- **Frontend**: Next.js 15 with App Router and TypeScript
- **AI Framework**: CrewAI for agent orchestration
- **LLM**: Anthropic Claude (configurable models)
- **Databases**: 
  - PostgreSQL/SQLite (configurable) for relational data
  - ChromaDB for vector embeddings and semantic search
- **Real-time Communication**: WebSockets for agent conversations
- **Configuration**: YAML-based agent and task definitions

## Development Commands

### Backend (Python/FastAPI)
```bash
cd backend

# Setup
python -m venv venv
source venv/bin/activate  # Unix/macOS
venv\Scripts\activate     # Windows
pip install -r requirements.txt

# Development
uvicorn app.main:app --reload  # Start dev server on :8000
python -m pytest             # Run tests (when available)

# Database operations
python utilities/reset_database.py
python utilities/validate_db_config.py
```

### Frontend (Next.js/TypeScript)
```bash
cd frontend

# Setup & Development
npm install
npm run dev    # Start dev server on :3000
npm run build  # Production build  
npm run start  # Production server
npm run lint   # ESLint check
```

## Key Architectural Patterns

### Configuration-Driven AI Agents
- All agents, tasks, and crews defined in `backend/app/config/agents.yaml`
- Three specialized agents: Technical Analyst, Risk Analyst, Project Planner
- Environment variable substitution for flexible configuration
- Sequential task execution with dependency management

### Service Layer Architecture
- `backend/app/services/` contains business logic
- `agent_service.py` - CrewAI integration and agent orchestration
- `document_upload_service.py` - File processing pipeline
- `project_service.py` - Project CRUD operations
- `websocket_manager.py` - Real-time communication

### Database Layer
- SQLAlchemy ORM with async support
- Connection pooling for PostgreSQL
- Migration system in `backend/app/db/migrations/`
- Dual database support (PostgreSQL/SQLite) via `USE_SQLITE` env var

### Document Processing Pipeline
- ChromaDB vector storage for semantic search
- Support for .docx and .txt files
- Document chunking and embedding generation
- Progress tracking with real-time updates

## Environment Configuration  

### Backend (.env)
```bash
# Database
USE_SQLITE=True  # or False for PostgreSQL
POSTGRES_SERVER=localhost
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=project_planning

# Anthropic AI
ANTHROPIC_API_KEY=your_key_here
ANTHROPIC_MODEL=claude-3-haiku-20240307

# Vector Database  
CHROMA_PERSIST_DIRECTORY=./chroma_db

# File Upload
UPLOAD_DIRECTORY=./uploads
MAX_UPLOAD_SIZE=10485760
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Agent Configuration System

The system uses YAML configuration for defining AI agents and tasks with advanced constraint preservation capabilities:

- **Agents**: Role, goal, backstory, LLM settings, tools, constraint preservation rules
- **Tasks**: Description, expected output, dependencies, context requirements, analysis mode handling
- **Crews**: Agent orchestration, process flow, memory management
- **Environment Variables**: Dynamic configuration via `${VARIABLE_NAME}` syntax
- **Constraint Preservation**: Automatic project constraint respect during analysis updates

## Database Schema

Core entities:
- **Projects**: Main planning projects with metadata
- **Documents**: Uploaded files with processing status and progress tracking
- **Analysis**: AI-generated insights and recommendations
- **Agent**: Configuration and execution tracking

## API Structure

RESTful API with WebSocket support:
- `/api/v1/projects/` - Project CRUD operations
- `/api/v1/documents/` - Document upload and management
- `/api/v1/agents/` - Agent configuration and execution
- WebSocket endpoints for real-time agent conversations

## Real-time Features

WebSocket implementation for:
- Agent conversation streaming
- Document processing progress updates  
- Multi-agent collaboration visualization
- Human-in-the-loop interactions
- Constraint violation notifications
- Analysis validation alerts

## Testing & Quality

- Backend: pytest framework (tests in development)
- Frontend: ESLint configuration with Next.js rules
- Type safety: TypeScript throughout frontend
- Configuration validation on startup

## Development Workflow

1. **Backend Development**: Use uvicorn with reload for hot reloading
2. **Frontend Development**: Next.js dev server with fast refresh
3. **Agent Configuration**: Modify `agents.yaml` without code changes
4. **Database Changes**: Create migrations in `backend/app/db/migrations/`
5. **Document Processing**: Test with sample files in `backend/uploads/`

## Development Rules & Guidelines

### **Code Standards**
- **Database Access**: ALL new code MUST use SQLAlchemy AsyncSession pattern
- **TypeScript**: Use TypeScript for all frontend code
- **Async Patterns**: Use async/await consistently
- **Error Handling**: Implement structured logging and graceful degradation

### **Security Requirements**
- **No Secrets**: Never commit API keys or sensitive data
- **Input Validation**: Always validate and sanitize user inputs
- **CORS**: Use environment-appropriate CORS settings
- **Least Privilege**: Follow principle of least privilege

### **Migration Protocol**
- **Follow Plan**: Adhere to docs/database-migration-plan.md
- **Test First**: Test compatibility layer before migrating files
- **Document Progress**: Update migration document with changes
- **No Breaking Changes**: Never break existing functionality

### **Documentation Standards**
- **Update CLAUDE.md**: When adding new architectural patterns
- **Update Kanban**: Add new tasks to project-kanban.html
- **Comment Code**: Include inline comments for complex logic
- **API Documentation**: Document all public APIs

### **Testing Requirements**
- **Coverage**: Maintain test coverage above 80%
- **New Features**: Write tests for all new functionality
- **Mock External**: Mock external API calls in tests
- **Use pytest**: For backend testing

## Recent Major Updates

### AI Agent Constraint Preservation System (Latest - Dec 2024)
- **Issue Resolved**: Agents were replacing entire project timelines during updates instead of preserving constraints
- **Solution**: Comprehensive constraint preservation system with validation and real-time notifications
- **Files Updated**: 
  - `backend/app/config/agents.yaml` - Enhanced agent configurations with constraint preservation rules
  - `backend/app/services/analysis_execution_service.py` - Added context retrieval and validation systems
- **Features Added**:
  - Existing analysis context retrieval for updates (`_get_existing_analysis_context()`)
  - Real-time constraint compliance validation (`_validate_constraint_compliance()`)
  - WebSocket notifications for constraint violations
  - Timeline preservation logic with milestone augmentation
  - Analysis mode distinction (initial vs update)
- **Impact**: Agents now preserve original deadlines, budgets, team sizes while intelligently incorporating new requirements as milestones

### ProjectInsights Real Data Integration  
- **Issue Resolved**: Insights dashboard showing mock data instead of real analysis results
- **Solution**: Fixed data transformation and API routing in ProjectInsights.tsx
- **Files Updated**: `frontend/components/project/ProjectInsights.tsx`, Next.js API routes
- **Impact**: Dashboard now displays actual analysis data with comprehensive visualizations

## Common Debugging

- **Database Issues**: Check connection settings and run validation scripts
- **Agent Failures**: Review agent configuration and API key settings, check constraint preservation logs
- **WebSocket Problems**: Verify CORS configuration and connection handling
- **File Upload Issues**: Check upload directory permissions and size limits
- **Constraint Violations**: Check analysis execution logs for validation errors and constraint compliance