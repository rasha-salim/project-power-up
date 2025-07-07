# Complete Project Power-Up Deployment Guide

**Project Power-Up is an AI-powered project planning system that transforms project briefs into comprehensive, actionable plans using collaborative AI agents.** This guide provides step-by-step instructions for deploying your Project Power-Up application using Netlify for frontend hosting and Railway for backend services.

## Project Overview

**Project Power-Up** features:
- **Frontend**: Next.js 15 with TypeScript and Tailwind CSS
- **Backend**: FastAPI with SQLAlchemy async and PostgreSQL
- **AI Agents**: CrewAI-powered specialized agents (Project Planner, Technical Analyst, Security Analyst)
- **Real-time Communication**: WebSocket-based agent conversations
- **Document Processing**: ChromaDB vector storage with document upload/analysis
- **Document Generation**: Markdown document creation system

## Getting Started with Project Power-Up Deployment

### Prerequisites

1. **GitHub Repository**: Your Project Power-Up code
2. **Netlify Account**: Free tier available at netlify.com
3. **Railway Account**: Free tier available at railway.app
4. **Anthropic API Key**: For Claude AI functionality

### Project Structure
```
Project Power-Up/
├── frontend/           # Next.js 15 application
│   ├── app/           # App Router pages
│   ├── components/    # React components
│   ├── lib/          # Utilities and services
│   ├── next.config.js
│   ├── netlify.toml  # Netlify configuration
│   └── package.json
├── backend/           # FastAPI application
│   ├── app/          # Python application
│   │   ├── api/      # API endpoints
│   │   ├── core/     # Configuration
│   │   ├── models/   # SQLAlchemy models
│   │   ├── services/ # Business logic
│   │   └── main.py   # FastAPI application
│   ├── requirements.txt
│   └── Procfile      # Railway deployment
├── docs/             # Documentation
└── DEPLOYMENT_GUIDE.md
```

## Step 1: Backend Deployment (Railway)

### 1.1 Prepare Backend for Railway

**Verify requirements.txt:**
```txt
fastapi>=0.95.0
uvicorn>=0.21.1
pydantic>=2.0.0
pydantic-settings>=2.0.0
python-multipart>=0.0.6
python-dotenv>=1.0.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.5
asyncpg>=0.28.0
crewai>=0.28.0
langchain>=0.0.267
anthropic>=0.8.0
langchain-anthropic>=0.1.0
chromadb>=0.4.6
websockets>=11.0.3
pytest>=7.3.1
httpx>=0.24.0
aiofiles>=23.2.1
pyyaml>=6.0.0
python-docx>=0.8.11
```

**Create Procfile in backend directory:**
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### 1.2 Deploy to Railway

1. **Sign up for Railway**: Visit [railway.app](https://railway.app)

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select your Project Power-Up repository

3. **Configure Backend Service**:
   - Set **Root Directory**: `backend`
   - Set **Build Command**: `pip install -r requirements.txt`
   - Set **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

4. **Add PostgreSQL Database**:
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway will automatically create and connect the database
   - Note: Railway provides resolved environment variables automatically

5. **Configure Environment Variables**:
   ```bash
   # Required for AI functionality
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
   
   # Database configuration (auto-provided by Railway)
   # DATABASE_URL=postgresql://... (auto-generated)
   # POSTGRES_USER=postgres (auto-generated)
   # POSTGRES_PASSWORD=... (auto-generated)
   # POSTGRES_DB=railway (auto-generated)
   
   # Application settings
   DATABASE_TYPE=postgresql
   CHROMA_PERSIST_DIRECTORY=./chroma_db
   UPLOAD_DIRECTORY=./uploads
   MAX_UPLOAD_SIZE=10485760
   ```

6. **Deploy**:
   - Click "Deploy"
   - Wait for deployment to complete
   - Copy the generated Railway URL (e.g., `https://your-app.railway.app`)

### 1.3 Railway-Specific Configuration Notes

Our Project Power-Up backend includes enhanced Railway support:

- **Template Variable Resolution**: Handles Railway's `${{...}}` template syntax
- **SSL Configuration**: Automatic SSL for Railway PostgreSQL
- **Environment Detection**: Automatically detects Railway deployment
- **Enhanced Debugging**: Detailed connection logging for troubleshooting

## Step 2: Frontend Deployment (Netlify)

### 2.1 Prepare Frontend for Netlify

**Update frontend/.env.local:**
```bash
NEXT_PUBLIC_API_URL=https://your-app.railway.app
```

**Verify netlify.toml configuration:**
```toml
[build]
  publish = ".next"
  command = "npm run build"

[build.environment]
  NODE_VERSION = "18"

[[redirects]]
  from = "/*"
  to = "/index.html"
  status = 200

# Security headers
[[headers]]
  for = "/*"
  [headers.values]
    X-Frame-Options = "DENY"
    X-XSS-Protection = "1; mode=block"
    X-Content-Type-Options = "nosniff"
    Referrer-Policy = "strict-origin-when-cross-origin"
```

**Update next.config.js for production:**
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  
  // Only include API rewrites for local development
  ...(process.env.NODE_ENV === 'development' && {
    async rewrites() {
      return [
        {
          source: '/api/:path*',
          destination: 'http://localhost:8000/api/:path*',
        },
      ];
    },
  }),
  
  // Enable image optimization
  images: {
    domains: ['localhost'],
  },
};

module.exports = nextConfig;
```

### 2.2 Deploy to Netlify

1. **Sign up for Netlify**: Visit [netlify.com](https://netlify.com)

2. **Import Project**:
   - Click "New site from Git"
   - Choose "GitHub"
   - Select your Project Power-Up repository

3. **Configure Build Settings**:
   - **Base directory**: `frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `frontend/.next`

4. **Set Environment Variables**:
   Go to Site settings → Environment variables:
   ```bash
   NEXT_PUBLIC_API_URL=https://your-app.railway.app
   ```

5. **Deploy**:
   - Click "Deploy site"
   - Wait for deployment (usually 2-3 minutes)
   - Copy the generated Netlify URL

## Step 3: Application Configuration

### 3.1 Update CORS Settings

In your Railway backend, ensure CORS is configured for your Netlify domain:

```python
# backend/app/main.py (already configured)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
```

**For production, update to:**
```python
allow_origins=[
    "https://your-netlify-app.netlify.app",
    "https://deploy-preview-*.netlify.app",  # For preview deployments
    "http://localhost:3000"  # For local development
],
```

### 3.2 Test Core Features

1. **Project Creation**:
   - Visit your Netlify URL
   - Create a new project
   - Verify project appears in database

2. **AI Agent System**:
   - Test `@planner` conversations for project brief creation
   - Test `@technical` analysis with uploaded documents
   - Test `@security` security analysis

3. **Document Features**:
   - Upload sample documents (`.docx`, `.txt`)
   - Verify document processing and ChromaDB storage
   - Test document generation in "📄 Generate Documents" tab

4. **Real-time Communication**:
   - Test WebSocket connections for agent conversations
   - Verify message formatting and display

## Step 4: Project Power-Up Specific Features

### 4.1 AI Agent Configuration

Your Project Power-Up includes three specialized agents:

**Project Planner Agent (`@planner`)**:
- Creates comprehensive project briefs
- Saves incremental progress to database
- Resumes conversations from where you left off

**Technical Analyst Agent (`@technical`)**:
- Analyzes uploaded documents
- Provides technical recommendations
- Integrates with project brief data

**Security Analyst Agent (`@security`)**:
- Performs security assessments
- Identifies potential vulnerabilities
- Provides security recommendations

### 4.2 Document Generation System

The document generation feature creates three types of documents:

1. **Project Brief**: Summarizes project overview and requirements
2. **Analysis Report**: Detailed technical and security analysis
3. **Comprehensive Report**: Combined brief and analysis data

### 4.3 Constraint Preservation System

The application includes advanced constraint preservation:
- Original deadlines and budgets are maintained during analysis updates
- Real-time validation prevents constraint violations
- WebSocket notifications for constraint compliance issues

## Step 5: Advanced Configuration

### 5.1 Environment-Specific Settings

**Production Environment Variables (Railway)**:
```bash
# AI Configuration
ANTHROPIC_API_KEY=your_production_api_key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Database (auto-configured by Railway)
DATABASE_TYPE=postgresql

# File Upload
UPLOAD_DIRECTORY=./uploads
MAX_UPLOAD_SIZE=10485760

# Vector Database
CHROMA_PERSIST_DIRECTORY=./chroma_db
```

**Frontend Environment Variables (Netlify)**:
```bash
NEXT_PUBLIC_API_URL=https://your-app.railway.app
```

### 5.2 Performance Optimization

**Backend Optimizations (already included)**:
- Async SQLAlchemy for database operations
- Connection pooling for PostgreSQL
- Efficient ChromaDB vector storage
- WebSocket connection management

**Frontend Optimizations**:
- Next.js 15 with automatic optimizations
- Code splitting for large components
- Static asset optimization
- Tailwind CSS for minimal bundle size

## Step 6: Monitoring and Troubleshooting

### 6.1 Health Checks

**Backend Health Check**:
```bash
curl https://your-app.railway.app/
# Should return: {"message": "Intelligent Project Planning System API is running"}
```

**API Endpoint Test**:
```bash
curl https://your-app.railway.app/api/v1/projects
# Should return project list or empty array
```

### 6.2 Common Issues and Solutions

**Issue: Railway PostgreSQL Connection Errors**
```bash
# Check Railway logs for:
# ✅ Railway environment detected
# ✅ Using Railway's resolved POSTGRES_* environment variables
# ✅ Basic connection test successful
```

**Issue: Netlify Build Failures**
```bash
# Solution: Ensure package.json build script works locally
cd frontend
npm run build
# Should complete without errors
```

**Issue: CORS Errors**
```bash
# Solution: Update Railway CORS settings
# Ensure Netlify domain is included in allow_origins
```

**Issue: AI Agent Not Responding**
```bash
# Check ANTHROPIC_API_KEY is set in Railway
# Verify API key has sufficient credits
# Check Railway logs for Anthropic API errors
```

### 6.3 Performance Monitoring

**Railway Monitoring**:
- Monitor CPU/Memory usage in Railway dashboard
- Check request logs for errors
- Monitor database connection pool usage

**Netlify Monitoring**:
- Monitor build performance and duration
- Check Core Web Vitals in Netlify Analytics
- Monitor bandwidth usage

## Step 7: Maintenance and Updates

### 7.1 Continuous Deployment

Both Railway and Netlify support automatic deployments:
- Push to `main` branch triggers automatic deployment
- Monitor deployment status in respective dashboards
- Use branch deployments for testing changes

### 7.2 Database Maintenance

**PostgreSQL on Railway**:
- Regular backups are handled automatically
- Monitor database size and performance
- Use Railway's database management tools

**ChromaDB Vector Storage**:
- Monitor vector collection sizes
- Clean up old document embeddings if needed
- Backup important vector collections

### 7.3 Security Updates

- Regularly update dependencies (especially AI libraries)
- Monitor security advisories for FastAPI and Next.js
- Rotate API keys periodically
- Review and update CORS settings

## Conclusion

Your Project Power-Up application is now deployed on free-tier infrastructure:

- ✅ **Railway Backend**: FastAPI with PostgreSQL database
- ✅ **Netlify Frontend**: Next.js 15 with Tailwind CSS
- ✅ **AI Functionality**: Three specialized agents with CrewAI
- ✅ **Document Processing**: ChromaDB vector storage
- ✅ **Real-time Features**: WebSocket agent conversations
- ✅ **Document Generation**: Markdown export capabilities

**Estimated Monthly Costs**: $2-5 for AI usage (Anthropic Claude), $0 for infrastructure (free tiers)

This deployment is ready for sharing with selected users and can scale as your project grows!

---

**Quick Reference URLs**:
- Frontend: `https://your-netlify-app.netlify.app`
- Backend API: `https://your-app.railway.app`
- Health Check: `https://your-app.railway.app/`
- API Docs: `https://your-app.railway.app/docs`

**Support Resources**:
- Railway Documentation: [docs.railway.app](https://docs.railway.app)
- Netlify Documentation: [docs.netlify.com](https://docs.netlify.com)
- Project Power-Up Repository: Your GitHub repository