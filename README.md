# Intelligent Project Planning System

An AI-powered project planning system that demonstrates the future of human-AI collaboration. This system transforms project briefs and meeting transcripts into comprehensive, actionable project plans through collaborative AI agents that think, discuss, and reason together while keeping humans in the loop.

## Project Vision

The Intelligent Project Planning System showcases how AI agents can work *with* humans, not replace them, to tackle complex planning challenges. The system features:

- **Collaborative AI Agents**: Three specialized AI agents that work together to analyze projects
- **Human-in-the-Loop Design**: AI amplifies human judgment rather than replacing it
- **Interactive Dashboard**: Visual, interactive insights rather than text walls
- **Conversation-Driven Interface**: Natural dialogue instead of form filling
- **Configuration-Driven Architecture**: Easily modify agent behaviors without changing code

## System Architecture

### Backend

- **FastAPI**: Async Python framework for the API
- **CrewAI**: Framework for orchestrating AI agent collaboration
- **Anthropic Claude**: LLM powering the AI agents (Claude 3 Haiku)
- **PostgreSQL/SQLite**: Relational database for structured data (configurable)
- **ChromaDB**: Vector database for document embeddings and semantic search
- **WebSockets**: Real-time communication for agent conversations
- **YAML Configuration**: Configuration-driven approach for defining agents and tasks

### Frontend

- **Next.js**: React framework with App Router and server components
- **Tailwind CSS**: Utility-first CSS framework for styling
- **React**: UI library for building the interface
- **Chart.js**: Library for data visualization

## AI Agents

The system features three specialized AI agents, all defined through configuration:

1. **Technical Analysis Agent**: Analyzes architecture, tech stack, and feasibility
2. **Risk Assessment Agent**: Identifies potential risks and mitigation strategies
3. **Project Planning Agent**: Creates roadmaps, timelines, and resource plans

### Configuration-Driven Approach

All agents, tasks, and crews are defined in YAML configuration files, allowing for:

- Easy modification of agent behaviors without code changes
- Flexible role and goal definitions
- Environment-specific settings through variable substitution
- Simplified addition of new agents and tasks

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL
- Anthropic API key

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

5. Create a `.env` file with the following variables:
   ```
   # Database Configuration
   USE_SQLITE=True
   POSTGRES_SERVER=localhost
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   POSTGRES_DB=project_planning
   POSTGRES_PORT=5432

   # Anthropic API Configuration
   ANTHROPIC_API_KEY=your_api_key_here
   ANTHROPIC_MODEL=claude-3-haiku-20240307

   # Vector Database Configuration
   CHROMA_PERSIST_DIRECTORY=./chroma_db

   # File Upload Configuration
   UPLOAD_DIRECTORY=./uploads
   MAX_UPLOAD_SIZE=10485760  # 10MB in bytes
   ```

6. Run the server:
   ```
   uvicorn app.main:app --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   ```

3. Create a `.env.local` file with the following variables:
   ```
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. Run the development server:
   ```
   npm run dev
   ```

5. Open [http://localhost:3000](http://localhost:3000) in your browser

## Development Phases

1. **Phase 1: Get Agents Talking** (Weeks 1-4)
   - CrewAI basic setup with 3 specialized agents
   - Document processing pipeline
   - Simple chat interface to test agent interactions
   - Basic FastAPI backend with Claude integration

2. **Phase 2: Human-AI Collaboration** (Weeks 5-8)
   - Interactive agent conversations with human input
   - Agents asking clarifying questions
   - Multi-agent discussions that humans can observe
   - Real-time WebSocket chat interface

3. **Phase 3: Dashboard Magic** (Weeks 9-12)
   - Dynamic dashboard with tabs for different insights
   - Interactive visualizations
   - Export functionality
   - Polished UI that showcases the AI insights

## Future Roadmap

The following features are planned for future iterations:

1. **Agent Memory System** (Phase 4)
   - Persistent conversation history between sessions
   - Context-aware agents that remember previous interactions
   - Versioned project insights to track evolution over time
   - Session management for pausing and resuming analyses

2. **Enhanced Personalization** (Phase 5)
   - User preference tracking and adaptation
   - Project lead-specific communication styles
   - Learning from feedback to improve future analyses
   - Customizable insight presentation

3. **Advanced Analysis Features** (Phase 6)
   - Incremental analysis updates (vs. full re-analysis)
   - Comparative analysis between versions
   - Deeper integration with project management tools
   - Extended document understanding capabilities

These planned enhancements will build upon the core functionality while maintaining the system's focus on human-AI collaboration and actionable insights.

## License
