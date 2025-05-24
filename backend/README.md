# Intelligent Project Planning System - Backend

This is the backend component of the Intelligent Project Planning System, an AI-powered project planning solution that leverages collaborative AI agents to transform project requirements into comprehensive plans.

## Architecture

The backend is built with:

- **FastAPI**: Modern, high-performance web framework for building APIs
- **CrewAI**: Framework for orchestrating AI agent collaboration
- **Anthropic Claude**: LLM powering the AI agents
- **SQLAlchemy**: SQL toolkit and ORM for database interactions
- **PostgreSQL/SQLite**: Relational database (configurable)
- **ChromaDB**: Vector database for document embeddings and semantic search
- **WebSockets**: Real-time communication for agent conversations
- **YAML-based Configuration**: Configuration-driven approach for agents and tasks

## Configuration-Driven Approach

The system uses a configuration-driven approach for defining AI agents, tasks, and crews. This allows for:

- **Flexibility**: Easily modify agent behaviors without changing code
- **Scalability**: Add new agents or tasks by updating YAML files
- **Maintainability**: Separate configuration from code
- **Environment-Specific Settings**: Use environment variables for different settings

### Configuration Structure

Agent configurations are defined in `app/config/agents.yaml`:

```yaml
version: "1.0"
agents:
  technical_analyst:
    role: "Technical Analyst"
    goal: "Analyze project requirements and provide technical recommendations"
    backstory: "You are an experienced technical architect..."
    verbose: true
    allow_delegation: false
    # Additional agent configuration...

tasks:
  technical_analysis:
    description: "Analyze project requirements and provide technical recommendations"
    expected_output: "Technical analysis report with architecture recommendations and technology stack"
    agent: "technical_analyst"
    # Additional task configuration...

crews:
  project_analysis_crew:
    name: "Project Analysis Crew"
    description: "Analyze project requirements and create a comprehensive project plan"
    agents:
      - technical_analyst
      - risk_analyst
      - project_planner
    # Additional crew configuration...
```

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL (optional, can use SQLite for development)
- Anthropic API key

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/project-power-up.git
   cd project-power-up/backend
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows: `venv\Scripts\activate`
   - Unix/MacOS: `source venv/bin/activate`

4. Install dependencies:
   ```bash
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
   ```bash
   uvicorn app.main:app --reload
   ```

The API will be available at http://localhost:8000.

## API Endpoints

- **GET /api/v1/agents/status**: Get the status of all AI agents
- **GET /api/v1/agents/{agent_id}**: Get a specific agent by ID
- **POST /api/v1/agents/tasks**: Create a new task for an AI agent
- **GET /api/v1/agents/tasks/{task_id}/result**: Get the result of an agent task
- **POST /api/v1/agents/analysis/start**: Start a full crew analysis for a project
- **GET /api/v1/agents/analysis/{analysis_id}/status**: Get the status and results of a crew analysis

## Project Structure

```
backend/
├── app/
│   ├── api/                # API endpoints
│   ├── config/             # Configuration files and loaders
│   │   ├── agents.yaml     # Agent, task, and crew configurations
│   │   └── config_loader.py # YAML configuration loader
│   ├── core/               # Core application components
│   ├── db/                 # Database models and initialization
│   ├── models/             # Pydantic models
│   ├── services/           # Business logic services
│   │   └── agent_service.py # Agent orchestration service
│   └── main.py             # Application entry point
├── requirements.txt        # Python dependencies
└── .env                    # Environment variables
```

## Development

### Adding New Agents

To add a new agent:

1. Update the `agents.yaml` file with the new agent configuration
2. No code changes required unless the agent needs custom functionality

### Customizing Agent Behavior

To customize agent behavior:

1. Modify the agent's configuration in `agents.yaml`
2. Update the agent's prompt templates if needed
3. Adjust the agent's task description and expected output

### Switching LLM Providers

The system currently uses Anthropic's Claude model, but can be adapted to use other LLM providers:

1. Update the `.env` file with the appropriate API keys
2. Modify the `agent_service.py` file to use the desired LLM provider
3. Update the agent configurations in `agents.yaml`

## Testing

To run tests:

```bash
pytest
```

## License

