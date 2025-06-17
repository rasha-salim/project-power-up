# Agent Service Merge Plan

## Analysis Summary

### Current State:
1. **agent_service.py** (old, 573 lines)
   - Contains basic CRUD operations for agents
   - Has methods: get_agents_status, get_agent, create_agent_task, execute_agent_task, get_task_result
   - Has crew analysis methods: start_crew_analysis, execute_crew_analysis, get_analysis_status
   - Uses old imports: `langchain.llms`, `langchain.chat_models`
   - Not actively used by frontend

2. **agent_service_v2.py** (new, 790 lines)
   - Contains the actual implementation being used
   - Has methods: start_analysis, get_analysis_status, ask_question, save_analysis, chat_with_agent
   - Uses updated imports: `langchain_anthropic`
   - Includes WebSocket integration
   - Has pending_analyses state management
   - Used by websocket.py (singleton instance)

### Endpoints Usage:
- Old endpoints (`/agents/status`, `/agents/task`, `/agents/crew/*`) - NOT used by frontend
- V2 endpoints (`/agents/analysis/v2/*`) - NOT directly used by frontend
- Frontend uses WebSocket exclusively for agent interactions

## Merge Strategy

Since the frontend only uses WebSocket and the old agent_service methods aren't being used, we can:

1. **Delete agent_service.py entirely**
2. **Rename agent_service_v2.py to agent_service.py**
3. **Update all imports**
4. **Clean up the agents.py endpoints**

## Implementation Steps

### Step 1: Update imports in websocket.py
- Change `from app.services.agent_service_v2 import AgentServiceV2`
- To `from app.services.agent_service import AgentService`

### Step 2: Update imports in agents.py
- Remove `from app.services.agent_service import AgentService`
- Change `from app.services.agent_service_v2 import AgentServiceV2`
- To `from app.services.agent_service import AgentService`

### Step 3: Clean up agents.py
- Remove unused endpoints that use the old service
- Keep only the v2 endpoints and rename them

### Step 4: Rename the service class
- Change `class AgentServiceV2:` to `class AgentService:`

### Step 5: Delete and rename files
- Delete agent_service.py
- Rename agent_service_v2.py to agent_service.py

## Benefits
- Removes 573 lines of unused code
- Eliminates confusion about which service to use
- Simplifies the codebase
- Maintains all current functionality
