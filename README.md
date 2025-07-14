# Intelligent Project Planning System

An AI-powered project planning application that demonstrates the future of human-AI collaboration through specialized agents. Transform project briefs and meeting transcripts into comprehensive, actionable project plans using collaborative AI agents powered by CrewAI and Anthropic Claude.

Please check this video for a demo of the application: https://www.youtube.com/watch?v=SZJKN0FNaTw&ab_channel=RashaSalim

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)
![Node.js](https://img.shields.io/badge/node.js-18+-green.svg)
![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue.svg)

## 🚀 Key Features

### AI-Powered Collaboration
- **Multi-Agent Analysis**: Three specialized AI agents (Technical Analyst, Risk Analyst, Project Planner) collaborate to provide comprehensive project insights
- **Real-time Conversations**: Watch agents discuss and reason through project challenges in real-time via WebSocket connections
- **Human-in-the-Loop**: AI amplifies human judgment rather than replacing it, keeping users involved in critical decisions

### Intelligent Document Processing
- **Smart Document Upload**: Support for .docx and .txt files with automatic content extraction
- **Semantic Search**: ChromaDB-powered vector search for intelligent document analysis
- **Context Preservation**: Agents maintain context across multiple analysis sessions

### Interactive Project Insights
- **Dynamic Dashboard**: Visual, interactive insights with comprehensive project metrics
- **Real-time Updates**: Live progress tracking and constraint compliance monitoring
- **Export Capabilities**: Generate comprehensive reports and project documentation

### Configuration-Driven Architecture
- **YAML Configuration**: Easily modify agent behaviors, tasks, and workflows without code changes
- **Flexible Deployment**: Support for both PostgreSQL and SQLite databases
- **Environment-Aware**: Seamless configuration for development, staging, and production environments

## 🏗️ Architecture Overview

### Backend (Python/FastAPI)
- **FastAPI**: High-performance async API framework
- **CrewAI**: Multi-agent orchestration and collaboration framework
- **Anthropic Claude**: Advanced language models for intelligent analysis
- **ChromaDB**: Vector database for semantic document search
- **PostgreSQL/SQLite**: Flexible database options for structured data storage
- **WebSockets**: Real-time bidirectional communication

### Frontend (Next.js/TypeScript)
- **Next.js 15**: React framework with App Router and server components
- **TypeScript**: Type-safe development for enhanced reliability
- **Tailwind CSS**: Utility-first CSS framework for rapid UI development
- **Real-time UI**: WebSocket integration for live agent conversations

### AI Agent System
1. **Technical Analyst**: Architecture analysis, technology recommendations, feasibility assessment
2. **Risk Analyst**: Risk identification, impact assessment, mitigation strategies
3. **Project Planner**: Timeline creation, resource planning, milestone definition

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.9 or higher
- Node.js 18 or higher
- PostgreSQL (optional - SQLite supported for development)
- Anthropic API key

### Backend Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/intelligent-project-planning.git
   cd intelligent-project-planning
   ```

2. **Set up Python environment**
   ```bash
   cd backend
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create a `.env` file in the `backend` directory:
   ```env
   # Database Configuration
   USE_SQLITE=True                    # Set to False for PostgreSQL
   POSTGRES_SERVER=localhost
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_password
   POSTGRES_DB=project_planning
   POSTGRES_PORT=5432

   # Anthropic API Configuration
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ANTHROPIC_MODEL=claude-3-haiku-20240307

   # Vector Database Configuration
   CHROMA_PERSIST_DIRECTORY=./chroma_db

   # File Upload Configuration
   UPLOAD_DIRECTORY=./uploads
   MAX_UPLOAD_SIZE=10485760  # 10MB in bytes
   ```

5. **Start the backend server**
   ```bash
   uvicorn app.main:app --reload
   ```
   
   The API will be available at `http://localhost:8000`

### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install Node.js dependencies**
   ```bash
   npm install
   ```

3. **Configure environment variables**
   
   Create a `.env.local` file in the `frontend` directory:
   ```env
   NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

4. **Start the development server**
   ```bash
   npm run dev
   ```
   
   The application will be available at `http://localhost:3000`

## 🎯 Usage Guide

### Creating Your First Project

1. **Access the Application**: Navigate to `http://localhost:3000`
2. **Create New Project**: Click "New Project" and fill in basic project information
3. **Upload Documents**: Add project briefs, requirements documents, or meeting transcripts
4. **Start Analysis**: Click "Start Analysis" to begin the AI agent collaboration
5. **Review Insights**: Watch the real-time agent conversations and review generated insights
6. **Save Results**: Confirm and save the analysis to your project for future reference

### Working with Agents

- **Technical Analysis**: Get architectural recommendations, technology stack suggestions, and complexity assessments
- **Risk Assessment**: Identify potential project risks with impact analysis and mitigation strategies  
- **Project Planning**: Receive detailed timelines, milestone definitions, and resource requirements

### Advanced Features

- **Incremental Analysis**: Request updates to existing analysis with new requirements or constraints
- **Agent Conversations**: Engage directly with specific agents for targeted questions
- **Export Options**: Generate comprehensive reports in multiple formats
- **Constraint Preservation**: Agents respect original project constraints when updating analysis

## 🔧 Development

### Database Management

**SQLite (Development)**
```bash
# Reset database
python utilities/reset_database.py

# Validate configuration
python utilities/validate_db_config.py
```

**PostgreSQL (Production)**
```bash
# Setup PostgreSQL
python utilities/setup_postgresql.py

# Run migrations
python utilities/db_utils/migrate_add_columns.py
```

### Testing

**Backend Testing**
```bash
cd backend
python -m pytest  # When test suite is implemented
```

**Frontend Testing**
```bash
cd frontend
npm run lint     # ESLint checks
npm run build    # Production build test
```

### API Documentation

When running the backend server, interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🐳 Docker Support

**Development with Docker Compose**
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## 🌐 Deployment

### Environment Configuration

**Production Environment Variables**
```env
# Security
SECRET_KEY=your_secure_secret_key
CORS_ORIGINS=["https://yourdomain.com"]

# Database
USE_SQLITE=False
POSTGRES_SERVER=your_postgres_host
POSTGRES_USER=your_postgres_user
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=project_planning

# API Keys
ANTHROPIC_API_KEY=your_production_api_key
```

### Deployment Platforms

The application is designed to work with various deployment platforms:

- **Railway**: Backend deployment with PostgreSQL
- **Netlify**: Frontend static deployment
- **Vercel**: Alternative frontend deployment
- **Heroku**: Full-stack deployment option
- **AWS/GCP/Azure**: Cloud platform deployment

### HTTPS Configuration

For production deployments, ensure:
- HTTPS is enabled for both frontend and backend
- CORS origins are properly configured
- WebSocket connections use WSS protocol

## 🤝 Contributing

We welcome contributions to the Intelligent Project Planning System! Here's how to get started:

1. **Fork the Repository**: Create your own fork of the project
2. **Create a Branch**: `git checkout -b feature/your-feature-name`
3. **Make Changes**: Implement your feature or bug fix
4. **Test Thoroughly**: Ensure all functionality works as expected
5. **Submit Pull Request**: Create a PR with a clear description of changes

### Development Guidelines

- Follow existing code style and conventions
- Update documentation for new features
- Ensure TypeScript types are properly defined
- Test both frontend and backend changes
- Update configuration files when adding new environment variables

### Code Style

- **Python**: Follow PEP 8 guidelines, use async/await patterns consistently
- **TypeScript**: Use strict type checking, follow React best practices
- **Configuration**: Use YAML for agent configuration, environment variables for secrets

## 📖 Documentation

### Architecture Deep Dive

- **Agent Configuration**: All AI agents are defined in `backend/app/config/agents.yaml`
- **Service Layer**: Business logic organized in `backend/app/services/`
- **Database Models**: SQLAlchemy models in `backend/app/models/`
- **API Endpoints**: RESTful API with WebSocket support in `backend/app/api/`

### Configuration Guide

The system uses a sophisticated configuration system:

- **Agent Definitions**: Roles, goals, and capabilities defined in YAML
- **Task Orchestration**: Sequential and parallel task execution
- **Environment Variables**: Dynamic configuration with `${VARIABLE_NAME}` syntax
- **Constraint Preservation**: Automatic project constraint respect during updates

## 🔐 Security

- **Input Validation**: All user inputs are validated and sanitized
- **API Security**: Rate limiting and authentication mechanisms
- **Data Protection**: Secure handling of uploaded documents and generated insights
- **Environment Isolation**: Clear separation between development and production configurations

## 🐛 Troubleshooting

### Common Issues

**Backend Won't Start**
- Verify Python version (3.9+)
- Check virtual environment activation
- Ensure all environment variables are set
- Validate database connection settings

**Frontend Build Errors**
- Verify Node.js version (18+)
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Check TypeScript configuration
- Ensure API URL is correctly configured

**Agent Analysis Fails**
- Verify Anthropic API key is valid
- Check internet connectivity
- Review agent configuration syntax in YAML
- Monitor backend logs for detailed error messages

**WebSocket Connection Issues**
- Ensure CORS settings allow WebSocket connections
- Check firewall and proxy configurations
- Verify WebSocket URL matches backend configuration

### Performance Optimization

- **Database**: Use PostgreSQL for production, enable connection pooling
- **Frontend**: Enable Next.js production optimizations
- **Caching**: Implement Redis for session management in high-traffic scenarios
- **Load Balancing**: Use reverse proxy for horizontal scaling

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **CrewAI**: Multi-agent framework enabling intelligent collaboration
- **Anthropic**: Claude language models powering agent intelligence  
- **FastAPI**: High-performance Python web framework
- **Next.js**: React framework enabling excellent developer experience
- **ChromaDB**: Vector database for semantic search capabilities

## 📞 Support

- **Issues**: Report bugs and request features via [GitHub Issues](https://github.com/your-username/intelligent-project-planning/issues)
- **Discussions**: Join community discussions for questions and ideas
- **Documentation**: Comprehensive guides available in the `/docs` directory

---

**Built with ❤️ for the future of human-AI collaboration in project management.**