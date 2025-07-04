# Project Power-Up Deployment Guide

## 🎯 Overview

This guide provides comprehensive instructions for deploying the **Project Power-Up** application on free tier resources. The application is an intelligent project planning system that uses AI agents to transform project briefs into actionable plans.

## 📋 Prerequisites

### Required Accounts (All Free Tier)
1. **Vercel Account** (for frontend hosting)
2. **Railway/Render Account** (for backend hosting)
3. **Anthropic Account** (for Claude API access)
4. **PostgreSQL Database** (free tier from Railway/Render or Neon)

### Required Software
- **Node.js 18+** 
- **Python 3.9+**
- **Git**

## 🏗️ Architecture Overview

```
Frontend (Next.js 15) → Vercel
     ↓
Backend (FastAPI) → Railway/Render
     ↓
Database (PostgreSQL) → Railway/Render/Neon
     ↓
AI Services (Anthropic Claude) → API
```

## 📁 Project Structure

```
Project Power-Up/
├── frontend/          # Next.js 15 application
├── backend/           # FastAPI Python application
├── docs/             # Documentation
├── CLAUDE.md         # Project instructions
└── DEPLOYMENT_GUIDE.md
```

## 🛠️ Step 1: Environment Setup

### 1.1 Clone the Repository

```bash
git clone <repository-url>
cd Project\ Power-Up
```

### 1.2 Get API Keys

#### Anthropic API Key
1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create account and navigate to API Keys
3. Create new API key and copy it
4. **Store securely** - you'll need this for deployment

#### Required Environment Variables
```bash
# Backend Environment Variables
ANTHROPIC_API_KEY=your_anthropic_api_key_here
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
DATABASE_TYPE=postgresql
POSTGRES_SERVER=your_postgres_host
POSTGRES_USER=your_postgres_user
POSTGRES_PASSWORD=your_postgres_password
POSTGRES_DB=your_postgres_database
POSTGRES_PORT=5432
CHROMA_PERSIST_DIRECTORY=./chroma_db
UPLOAD_DIRECTORY=./uploads
MAX_UPLOAD_SIZE=10485760

# Frontend Environment Variables
NEXT_PUBLIC_API_URL=your_backend_url_here
```

## 🚀 Step 2: Backend Deployment (Railway)

### 2.1 Prepare Backend for Deployment

1. **Create requirements.txt** (already exists):
```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
sqlalchemy==2.0.23
psycopg2-binary==2.9.9
anthropic==0.3.11
crewai==0.1.0
chromadb==0.4.15
python-multipart==0.0.6
pydantic==2.5.0
python-dotenv==1.0.0
aiofiles==23.2.1
```

2. **Create Procfile** in backend directory:
```
web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

3. **Create runtime.txt** in backend directory:
```
python-3.9.18
```

### 2.2 Deploy to Railway

1. **Sign up for Railway**: [railway.app](https://railway.app)

2. **Create New Project**:
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your GitHub account
   - Select the Project Power-Up repository

3. **Configure Backend Service**:
   - Set **Root Directory**: `backend`
   - Set **Build Command**: `pip install -r requirements.txt`
   - Set **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

4. **Add Environment Variables**:
   Go to your service → Variables tab and add:
   ```
   ANTHROPIC_API_KEY=your_anthropic_api_key
   ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
   DATABASE_TYPE=postgresql
   POSTGRES_SERVER=<will be auto-filled by Railway DB>
   POSTGRES_USER=<will be auto-filled by Railway DB>
   POSTGRES_PASSWORD=<will be auto-filled by Railway DB>
   POSTGRES_DB=<will be auto-filled by Railway DB>
   POSTGRES_PORT=5432
   CHROMA_PERSIST_DIRECTORY=./chroma_db
   UPLOAD_DIRECTORY=./uploads
   MAX_UPLOAD_SIZE=10485760
   ```

5. **Add PostgreSQL Database**:
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway will automatically set database environment variables
   - Copy the database connection details

6. **Deploy**:
   - Click "Deploy"
   - Wait for deployment to complete
   - Copy the generated Railway URL (e.g., `https://your-app.railway.app`)

### 2.3 Alternative: Deploy to Render

1. **Sign up for Render**: [render.com](https://render.com)

2. **Create Web Service**:
   - Click "New" → "Web Service"
   - Connect GitHub repository
   - Select Project Power-Up repository

3. **Configure Service**:
   - **Name**: project-power-up-backend
   - **Environment**: Python 3
   - **Region**: Choose closest to your users
   - **Branch**: main
   - **Root Directory**: backend
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

4. **Add PostgreSQL Database**:
   - Create new PostgreSQL database on Render
   - Copy connection details

5. **Set Environment Variables**:
   Same as Railway setup above

## 🌐 Step 3: Frontend Deployment (Vercel)

### 3.1 Prepare Frontend

1. **Update API URL**:
   Create `frontend/.env.local`:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend-url.railway.app
   ```

2. **Verify Package.json**:
   ```json
   {
     "scripts": {
       "build": "next build",
       "start": "next start",
       "dev": "next dev",
       "lint": "next lint"
     }
   }
   ```

### 3.2 Deploy to Vercel

1. **Sign up for Vercel**: [vercel.com](https://vercel.com)

2. **Import Project**:
   - Click "New Project"
   - Import from GitHub
   - Select Project Power-Up repository

3. **Configure Project**:
   - **Framework Preset**: Next.js
   - **Root Directory**: frontend
   - **Build Command**: `npm run build`
   - **Output Directory**: `.next`
   - **Install Command**: `npm install`

4. **Environment Variables**:
   Add in Vercel dashboard:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend-url.railway.app
   ```

5. **Deploy**:
   - Click "Deploy"
   - Wait for deployment
   - Copy the generated Vercel URL

## 🗄️ Step 4: Database Setup

### 4.1 Database Migration

Your database will be automatically created by SQLAlchemy when the backend starts. The models are defined in:
- `backend/app/models/project.py`
- `backend/app/models/document.py`
- `backend/app/models/analysis.py`

### 4.2 Verify Database Connection

1. **Check Backend Logs**:
   - Go to Railway/Render dashboard
   - Check deployment logs for database connection success

2. **Test API Endpoints**:
   ```bash
   curl https://your-backend-url.railway.app/api/v1/projects
   ```

## 🔧 Step 5: Configuration & Testing

### 5.1 Update CORS Settings

The backend is configured for production CORS. If you need to update allowed origins, modify `backend/app/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://your-vercel-app.vercel.app",
        "http://localhost:3000"  # For local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 5.2 Test the Complete Application

1. **Open Frontend URL** (Vercel deployment URL)
2. **Create a New Project**:
   - Click "New Project"
   - Fill in project details
   - Verify project creation

3. **Test Document Upload**:
   - Upload a sample document
   - Check processing status

4. **Test AI Agents**:
   - Chat with `@planner` to create project brief
   - Use `@technical` to run analysis
   - Try `@security` for security analysis

5. **Test Document Generation**:
   - Go to "📄 Generate Documents" tab
   - Generate project brief
   - Download generated document

## 🛡️ Step 6: Security & Best Practices

### 6.1 Secure API Keys

- **Never commit API keys** to version control
- Use environment variables on deployment platforms
- Rotate API keys regularly

### 6.2 Database Security

- Use strong passwords
- Enable SSL connections
- Regularly backup data

### 6.3 Monitoring

1. **Railway/Render Monitoring**:
   - Monitor resource usage
   - Set up alerting
   - Check logs regularly

2. **Vercel Analytics**:
   - Enable Vercel Analytics
   - Monitor frontend performance

## 🔄 Step 7: Updates & Maintenance

### 7.1 Continuous Deployment

Both Railway/Render and Vercel support automatic deployments:
- Push to `main` branch triggers automatic deployment
- Monitor deployment status in dashboards

### 7.2 Database Migrations

For schema changes:
1. Update models in `backend/app/models/`
2. Deploy backend (SQLAlchemy will handle migrations)
3. Verify in production database

### 7.3 Scaling

#### Free Tier Limits:
- **Railway**: 500 hours/month, 1GB RAM, 1GB disk
- **Render**: 750 hours/month, 512MB RAM, temporary disk
- **Vercel**: 100GB bandwidth, 6000 function invocations
- **Anthropic**: Rate limits based on plan

#### Scaling Options:
- Upgrade to paid tiers for more resources
- Use database connection pooling
- Implement caching strategies
- Consider CDN for static assets

## 🐛 Troubleshooting

### Common Issues

#### 1. Backend Won't Start
```bash
# Check logs in Railway/Render
# Common issues:
- Missing environment variables
- Database connection failure
- Port binding issues
```

#### 2. Frontend Can't Connect to Backend
```bash
# Check CORS settings
# Verify NEXT_PUBLIC_API_URL
# Check network connectivity
```

#### 3. Database Connection Issues
```bash
# Verify PostgreSQL credentials
# Check database is running
# Verify SSL settings
```

#### 4. API Rate Limits
```bash
# Monitor Anthropic usage
# Implement rate limiting
# Add error handling for rate limits
```

### Debug Commands

#### Backend Health Check:
```bash
curl https://your-backend-url/health
```

#### Database Connection Test:
```bash
# SSH into Railway/Render container
python -c "from app.db.init_db_simple import get_async_db; print('DB OK')"
```

#### API Test:
```bash
curl -X GET https://your-backend-url/api/v1/projects \
  -H "Content-Type: application/json"
```

## 📊 Monitoring & Analytics

### 1. Application Monitoring

#### Railway/Render:
- CPU/Memory usage
- Request logs
- Error tracking
- Uptime monitoring

#### Vercel:
- Function execution time
- Error rate
- Traffic analytics
- Core Web Vitals

### 2. Custom Monitoring

Add monitoring endpoints in `backend/app/main.py`:

```python
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now()}

@app.get("/metrics")
async def metrics():
    # Add custom metrics
    return {"projects": project_count, "uptime": uptime}
```

## 💰 Cost Estimation

### Free Tier Resources:

#### Infrastructure:
- **Railway**: Free (500 hours/month)
- **Vercel**: Free (100GB bandwidth)
- **PostgreSQL**: Free (Railway/Render included)

#### AI Services:
- **Anthropic Claude**: Pay-per-use
  - Claude-3.5-Sonnet: ~$3 per 1M input tokens
  - Typical project analysis: 5-10K tokens
  - Estimated cost: $0.02-0.05 per analysis

#### Monthly Estimates (100 projects):
- Infrastructure: $0 (free tier)
- AI Usage: ~$2-5 (depending on usage)
- **Total: $2-5/month**

## 🎉 Deployment Checklist

### Pre-Deployment:
- [ ] Anthropic API key obtained
- [ ] Repository cloned and reviewed
- [ ] Environment variables prepared

### Backend Deployment:
- [ ] Railway/Render account created
- [ ] PostgreSQL database created
- [ ] Backend service deployed
- [ ] Environment variables configured
- [ ] Health check successful

### Frontend Deployment:
- [ ] Vercel account created
- [ ] Frontend deployed
- [ ] API URL configured
- [ ] Frontend connects to backend

### Testing:
- [ ] Project creation works
- [ ] Document upload works
- [ ] AI agents respond correctly
- [ ] Document generation works
- [ ] All tabs function properly

### Production Ready:
- [ ] CORS configured correctly
- [ ] Error monitoring set up
- [ ] Backup strategy implemented
- [ ] Documentation updated

## 📞 Support & Resources

### Documentation:
- **FastAPI**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **Next.js**: [nextjs.org/docs](https://nextjs.org/docs)
- **Railway**: [docs.railway.app](https://docs.railway.app)
- **Vercel**: [vercel.com/docs](https://vercel.com/docs)
- **Anthropic**: [docs.anthropic.com](https://docs.anthropic.com)

### Community:
- **Railway Discord**: [railway.app/discord](https://railway.app/discord)
- **Vercel Discord**: [vercel.com/discord](https://vercel.com/discord)
- **FastAPI Discord**: [discord.gg/VQjSZaeJmf](https://discord.gg/VQjSZaeJmf)

### Emergency Contacts:
- Check deployment platform status pages
- Review application logs
- Consult troubleshooting section above

---

## 🔄 Quick Start Summary

For experienced developers who want to deploy quickly:

```bash
# 1. Get API key from Anthropic
# 2. Deploy backend to Railway:
#    - Root dir: backend
#    - Add PostgreSQL
#    - Set environment variables
# 3. Deploy frontend to Vercel:
#    - Root dir: frontend
#    - Set NEXT_PUBLIC_API_URL
# 4. Test the application
```

**That's it!** Your Project Power-Up application should now be running on free tier resources and ready to share with your selected users.

---

*Last updated: January 2025*
*Version: 1.0*