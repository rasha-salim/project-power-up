import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { PaperAirplaneIcon, XMarkIcon, CheckIcon, ArrowPathIcon, InformationCircleIcon, StopIcon } from '@heroicons/react/24/outline';
import { API_ENDPOINTS, apiRequest } from '@/app/api/config';

interface Message {
  id: string;
  type: 'user' | 'agent' | 'system' | 'error' | 'result';
  sender?: string;
  senderName?: string;
  message: string;
  timestamp: string;
  result?: any;
  message_id?: string; // Server-generated unique ID
  isLoading?: boolean; // Flag to indicate loading state
}

interface AgentInfo {
  id: string;
  name: string;
  mention_id: string;
  role: string;
  description: string;
  capabilities: string[];
  example_prompts: string[];
  avatar?: string;
  color?: string;
  is_available: boolean;
}

interface AgentConversationProps {
  projectId: string;
  onStartAnalysis: () => void;
  onAnalysisComplete?: (insights: any) => void;
  existingInsights?: any;  // Add this prop for existing analysis
}

export default function AgentConversation({ projectId, onStartAnalysis, onAnalysisComplete, existingInsights }: AgentConversationProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentAnalysisId, setCurrentAnalysisId] = useState<string | null>(null);
  const [analysisComplete, setAnalysisComplete] = useState(false);
  const [isAgentThinking, setIsAgentThinking] = useState(false);
  const [showAgentCatalog, setShowAgentCatalog] = useState(false);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [showAgentSuggestions, setShowAgentSuggestions] = useState(false);
  const [agentSearchTerm, setAgentSearchTerm] = useState('');
  const [analysisSaved, setAnalysisSaved] = useState(false);  
  const [analysisProgress, setAnalysisProgress] = useState<string>('');
  const [analysisError, setAnalysisError] = useState<{
    message: string;
    type: string;
    recoverable: boolean;
    analysisId?: string;
  } | null>(null);
  const [activeAgent, setActiveAgent] = useState<AgentInfo | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  // Track processed message IDs to prevent duplicates
  const processedMessageIds = useRef<Set<string>>(new Set());
  const messageCounter = useRef(0);
  const connectionMessageId = useRef<string | null>(null);

  const generateMessageId = () => {
    // Use a combination of timestamp and counter to ensure uniqueness
    messageCounter.current += 1;
    return `${Date.now()}-${messageCounter.current}`;
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Parse structured content from agent messages
  const parseStructuredContent = (messageText: string) => {
    try {
      // Try to parse JSON first
      if (messageText.trim().startsWith('{') && messageText.trim().endsWith('}')) {
        const parsed = JSON.parse(messageText);
        if (parsed.technical_analysis || parsed.risk_assessment || parsed.project_plan) {
          return parsed;
        }
      }
      
      // Try to detect structured markdown content
      if (messageText.includes('## Analysis Results:') || 
          messageText.includes('### Technical Analysis') ||
          messageText.includes('### Risk Assessment') ||
          messageText.includes('### Project Plan')) {
        
        // Parse markdown-formatted analysis into structured data
        const result: any = {};
        
        // Extract Technical Analysis section
        const techMatch = messageText.match(/### Technical Analysis([\s\S]*?)(?=###|\n\n|$)/);
        if (techMatch) {
          const techContent = techMatch[1];
          result.technical_analysis = {
            architecture: extractValue(techContent, 'Architecture'),
            tech_stack: extractTechStack(techContent),
            complexity_score: extractScore(techContent, 'Complexity'),
            maintainability_score: extractScore(techContent, 'Maintainability'),
            scalability_score: extractScore(techContent, 'Scalability'),
            security_score: extractScore(techContent, 'Security')
          };
        }
        
        // Extract Risk Assessment section
        const riskMatch = messageText.match(/### Risk Assessment([\s\S]*?)(?=###|\n\n|$)/);
        if (riskMatch) {
          const riskContent = riskMatch[1];
          result.risk_assessment = {
            overall_risk_score: extractScore(riskContent, 'Overall Risk Score'),
            key_risks: extractRisks(riskContent)
          };
        }
        
        // Extract Project Plan section
        const planMatch = messageText.match(/### Project Plan([\s\S]*?)(?=###|\n\n|$)/);
        if (planMatch) {
          const planContent = planMatch[1];
          result.project_plan = {
            timeline: extractValue(planContent, 'Timeline'),
            estimated_cost: extractCost(planContent),
            phases: extractPhases(planContent)
          };
        }
        
        // Extract Recommendations section
        const recMatch = messageText.match(/### Recommendations([\s\S]*?)(?=###|\n\n|$)/);
        if (recMatch) {
          result.recommendations = extractRecommendations(recMatch[1]);
        }
        
        return Object.keys(result).length > 0 ? result : null;
      }
      
      return null;
    } catch (error) {
      console.log('Failed to parse structured content:', error);
      return null;
    }
  };

  // Helper functions for parsing markdown content
  const extractValue = (content: string, key: string) => {
    const match = content.match(new RegExp(`\\*\\*${key}\\*\\*:?\\s*([^\n]+)`));
    return match ? match[1].trim() : '';
  };

  const extractScore = (content: string, key: string) => {
    const match = content.match(new RegExp(`${key}:?\\s*(\\d+)`));
    return match ? parseInt(match[1]) : 0;
  };

  const extractTechStack = (content: string) => {
    const stack: any = {};
    const stackMatch = content.match(/\*\*Tech Stack\*\*:([\s\S]*?)(?=\*\*|$)/);
    if (stackMatch) {
      const stackContent = stackMatch[1];
      
      const frontendMatch = stackContent.match(/Frontend:\s*([^\n]+)/);
      if (frontendMatch) stack.frontend = frontendMatch[1].split(',').map(s => s.trim());
      
      const backendMatch = stackContent.match(/Backend:\s*([^\n]+)/);
      if (backendMatch) stack.backend = backendMatch[1].split(',').map(s => s.trim());
      
      const infraMatch = stackContent.match(/Infrastructure:\s*([^\n]+)/);
      if (infraMatch) stack.infrastructure = infraMatch[1].split(',').map(s => s.trim());
      
      const toolsMatch = stackContent.match(/Tools:\s*([^\n]+)/);
      if (toolsMatch) stack.tools = toolsMatch[1].split(',').map(s => s.trim());
    }
    return stack;
  };

  const extractRisks = (content: string) => {
    const risks: any[] = [];
    const riskMatches = content.match(/\s{2,}([^(]+)\s*\(([^)]+)\)\s*-\s*([^\n]+)/g);
    if (riskMatches) {
      riskMatches.forEach(match => {
        const parsed = match.match(/\s{2,}([^(]+)\s*\(([^)]+)\)\s*-\s*([^\n]+)/);
        if (parsed) {
          risks.push({
            name: parsed[1].trim(),
            level: parsed[2].trim(),
            description: parsed[3].trim()
          });
        }
      });
    }
    return risks;
  };

  const extractCost = (content: string) => {
    const match = content.match(/\*\*Estimated Cost\*\*:?\s*\$?([\d,]+)/);
    return match ? parseInt(match[1].replace(/,/g, '')) : 0;
  };

  const extractPhases = (content: string) => {
    const phases: any[] = [];
    const phaseMatches = content.match(/\s{2,}Phase\s+([^(]+)\s*\(([^)]+)\)\s*-\s*([^\n]+)/g);
    if (phaseMatches) {
      phaseMatches.forEach(match => {
        const parsed = match.match(/\s{2,}Phase\s+([^(]+)\s*\(([^)]+)\)\s*-\s*([^\n]+)/);
        if (parsed) {
          phases.push({
            name: parsed[1].trim(),
            duration: parsed[2].replace(/weeks?/i, '').trim(),
            description: parsed[3].trim()
          });
        }
      });
    }
    return phases;
  };

  const extractRecommendations = (content: string) => {
    const recommendations: string[] = [];
    const recMatches = content.match(/^\d+\.\s*(.+)$/gm);
    if (recMatches) {
      recMatches.forEach(match => {
        const parsed = match.match(/^\d+\.\s*(.+)$/);
        if (parsed) {
          recommendations.push(parsed[1].trim());
        }
      });
    }
    return recommendations;
  };

  // Render structured analysis data using the same HTML structure as result messages
  const renderStructuredAnalysis = (analysisData: any) => {
    return (
      <div className="space-y-3">
        {analysisData.technical_analysis && (
          <div>
            <h4 className="font-semibold text-sm mb-1">Technical Analysis</h4>
            <div className="text-xs space-y-1">
              {analysisData.technical_analysis.architecture && (
                <p><strong>Architecture:</strong> {analysisData.technical_analysis.architecture}</p>
              )}
              {analysisData.technical_analysis.tech_stack && Object.keys(analysisData.technical_analysis.tech_stack).length > 0 && (
                <div>
                  <strong>Tech Stack:</strong>
                  <ul className="ml-4 mt-1">
                    {analysisData.technical_analysis.tech_stack.frontend?.length > 0 && (
                      <li>Frontend: {analysisData.technical_analysis.tech_stack.frontend.join(', ')}</li>
                    )}
                    {analysisData.technical_analysis.tech_stack.backend?.length > 0 && (
                      <li>Backend: {analysisData.technical_analysis.tech_stack.backend.join(', ')}</li>
                    )}
                    {analysisData.technical_analysis.tech_stack.infrastructure?.length > 0 && (
                      <li>Infrastructure: {analysisData.technical_analysis.tech_stack.infrastructure.join(', ')}</li>
                    )}
                    {analysisData.technical_analysis.tech_stack.tools?.length > 0 && (
                      <li>Tools: {analysisData.technical_analysis.tech_stack.tools.join(', ')}</li>
                    )}
                  </ul>
                </div>
              )}
              {(analysisData.technical_analysis.complexity_score || 
                analysisData.technical_analysis.maintainability_score || 
                analysisData.technical_analysis.scalability_score ||
                analysisData.technical_analysis.security_score) && (
                <div>
                  <strong>Scores:</strong>
                  {[
                    analysisData.technical_analysis.complexity_score && `Complexity: ${analysisData.technical_analysis.complexity_score}/10`,
                    analysisData.technical_analysis.maintainability_score && `Maintainability: ${analysisData.technical_analysis.maintainability_score}/10`,
                    analysisData.technical_analysis.scalability_score && `Scalability: ${analysisData.technical_analysis.scalability_score}/10`,
                    analysisData.technical_analysis.security_score && `Security: ${analysisData.technical_analysis.security_score}/10`
                  ].filter(Boolean).join(', ')}
                </div>
              )}
            </div>
          </div>
        )}
        
        {analysisData.risk_assessment && (
          <div>
            <h4 className="font-semibold text-sm mb-1">Risk Assessment</h4>
            <div className="text-xs space-y-1">
              {analysisData.risk_assessment.overall_risk_score && (
                <p><strong>Overall Risk Score:</strong> {analysisData.risk_assessment.overall_risk_score}/10</p>
              )}
              {analysisData.risk_assessment.key_risks?.length > 0 && (
                <div>
                  <strong>Key Risks:</strong>
                  <ul className="ml-4 mt-1">
                    {analysisData.risk_assessment.key_risks.map((risk: any, idx: number) => (
                      <li key={idx}>{risk.name} ({risk.level}) - {risk.description}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
        
        {analysisData.project_plan && (
          <div>
            <h4 className="font-semibold text-sm mb-1">Project Plan</h4>
            <div className="text-xs space-y-1">
              {analysisData.project_plan.timeline && (
                <p><strong>Timeline:</strong> {analysisData.project_plan.timeline}</p>
              )}
              {analysisData.project_plan.estimated_cost && (
                <p><strong>Estimated Cost:</strong> ${analysisData.project_plan.estimated_cost.toLocaleString?.() || analysisData.project_plan.estimated_cost}</p>
              )}
              {analysisData.project_plan.phases?.length > 0 && (
                <div>
                  <strong>Phases:</strong>
                  <ul className="ml-4 mt-1">
                    {analysisData.project_plan.phases.map((phase: any, idx: number) => (
                      <li key={idx}>
                        {phase.name} ({phase.duration} weeks) - {phase.description}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
        
        {analysisData.recommendations?.length > 0 && (
          <div>
            <h4 className="font-semibold text-sm mb-1">Recommendations</h4>
            <ul className="text-xs ml-4">
              {analysisData.recommendations.map((rec: string, idx: number) => (
                <li key={idx}>{rec}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  };

  // Only auto-scroll when messages are added and user is already near the bottom
  useEffect(() => {
    // Check if user is already near the bottom before auto-scrolling
    const shouldScrollToBottom = () => {
      if (!messagesEndRef.current) return false;
      
      const container = messagesEndRef.current.parentElement;
      if (!container) return false;
      
      // Calculate distance from bottom
      const distanceFromBottom = 
        container.scrollHeight - (container.scrollTop + container.clientHeight);
      
      // Only auto-scroll if user is already close to the bottom (within 100px)
      // or if this is the first message
      return distanceFromBottom < 100 || messages.length <= 1;
    };

    if (shouldScrollToBottom()) {
      scrollToBottom();
    }
  }, [messages]);

  useEffect(() => {
    console.log('🟡 isAgentThinking state changed:', {
      newState: isAgentThinking,
      timestamp: new Date().toISOString(),
      stackTrace: new Error().stack?.split('\n').slice(1, 5).join('\n')
    });
  }, [isAgentThinking]);

  useEffect(() => {
    console.log('Save button state:', {
      analysisComplete,
      analysisSaved,
      currentAnalysisId,
      isConnected,
      existingInsights: !!existingInsights,
      showButton: analysisComplete && !analysisSaved,
      hasNewAnalysis: analysisComplete && currentAnalysisId && !analysisSaved
    });
  }, [analysisComplete, analysisSaved, currentAnalysisId, isConnected, existingInsights]);

  // Timeout recovery for agent responses
  useEffect(() => {
    if (isAgentThinking) {
      const timeout = setTimeout(() => {
        console.log('Agent response timeout - resetting thinking state');
        setIsAgentThinking(false);
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          type: 'system',
          sender: 'system',
          senderName: 'System',
          message: '⏰ Response timeout - the agent may have encountered an issue. Please try your message again.',
          timestamp: new Date().toISOString()
        }]);
      }, 400000); // 6.5 minute timeout for analysis operations (accounts for API retry delays up to 300s)

      return () => clearTimeout(timeout);
    }
  }, [isAgentThinking]);

  const connectWebSocket = () => {
    // If there's already a connection that's open or connecting, don't create a new one
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      console.log('WebSocket already connected or connecting');
      return;
    }

    // Close any existing connection before creating a new one
    if (wsRef.current) {
      console.log('Closing existing WebSocket connection before creating a new one');
      wsRef.current.close();
      wsRef.current = null;
    }

    // Import the getApiBaseUrl function from config to ensure consistent URL handling
    const getApiBaseUrl = () => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      
      // Force HTTPS for Railway domains (production)
      if (apiUrl && apiUrl.includes('railway.app')) {
        if (apiUrl.startsWith('http://')) {
          return apiUrl.replace('http://', 'https://');
        } else if (!apiUrl.startsWith('https://')) {
          return `https://${apiUrl}`;
        }
        return apiUrl;
      }
      
      if (apiUrl && !apiUrl.startsWith('http://') && !apiUrl.startsWith('https://')) {
        return `https://${apiUrl}`;
      }
      
      return apiUrl;
    };

    // Get the API base URL and convert to WebSocket URL
    const httpApiUrl = getApiBaseUrl();
    let wsBaseUrl;
    
    if (httpApiUrl.includes('railway.app')) {
      // Railway deployment - use wss and the Railway domain
      wsBaseUrl = httpApiUrl.replace('https://', 'wss://').replace('http://', 'wss://');
    } else if (httpApiUrl.startsWith('http://localhost')) {
      // Local development - use ws
      wsBaseUrl = httpApiUrl.replace('http://', 'ws://');
    } else {
      // Default to secure WebSocket for production
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      wsBaseUrl = `${protocol}//${httpApiUrl.replace(/^https?:\/\//, '')}`;
    }
    
    const wsUrl = `${wsBaseUrl}/api/v1/ws/agent-conversation/${projectId}`;
    
    console.log('🔗 WebSocket connection details:', {
      originalApiUrl: process.env.NEXT_PUBLIC_API_URL,
      processedHttpUrl: httpApiUrl,
      websocketUrl: wsUrl,
      isRailway: httpApiUrl.includes('railway.app')
    });
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('🟢 WebSocket connected successfully');
      setIsConnected(true);
      
      // Update the connecting message if it exists
      if (connectionMessageId.current) {
        setMessages(prev => prev.map(msg => {
          if (msg.id === connectionMessageId.current) {
            return {
              ...msg,
              message: 'Connected to AI agents',
              isLoading: false // Remove the spinner
            };
          }
          return msg;
        }));
        
        // Clear the connection message ID after a delay so it can be removed from the UI
        setTimeout(() => {
          // Remove the connection message after 3 seconds
          setMessages(prev => prev.filter(msg => msg.id !== connectionMessageId.current));
          connectionMessageId.current = null;
        }, 3000);
      }
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('🔴 WebSocket message received:', {
          type: data.type,
          timestamp: new Date().toISOString(),
          analysisId: data.analysis_id,
          sender: data.sender,
          messageLength: data.message?.length || 0,
          hasResult: !!data.result,
          resultKeys: data.result ? Object.keys(data.result) : [],
          // Enhanced isThinking logging
          isThinkingField: data.isThinking,
          isThinkingType: typeof data.isThinking,
          hasIsThinkingField: data.hasOwnProperty('isThinking'),
          currentState: {
            isAnalyzing: isAnalyzing,
            isAgentThinking: isAgentThinking,
            messagesCount: messages.length,
            currentAnalysisId: currentAnalysisId
          },
          fullData: data
        });
        
        // Special logging for isThinking field changes
        if (data.hasOwnProperty('isThinking')) {
          console.log(`🟡 isThinking field detected: ${data.isThinking} (current UI state: ${isAgentThinking})`);
        }
        
        // Clear any previous errors when receiving new messages
        if (data.type !== 'error' && data.type !== 'analysis_failed') {
          setAnalysisError(null);
        }

        switch (data.type) {
          case 'user_message':
          case 'agent_message':
          case 'system_message':
            console.log('🟢 Processing message:', data.type, {
              sender: data.sender,
              messagePreview: data.message?.substring(0, 100) + '...',
              willBeFiltered: data.type === 'agent_message' && !data.analysis_id && data.sender !== 'project_planner'
            });
            // Filter out certain system messages to keep chat clean
            if (data.type === 'system_message' && 
                (data.message.includes('Connected to agent conversation') || 
                 data.message.includes('Connection established'))) {
              return; // Skip these messages
            }
            
            // Filter out preliminary agent messages since we have typing indicator
            // BUT don't filter if this is an analysis content message (has analysis_id)
            // OR if this is from project_planner or technical_analyst (never filter these responses)
            if (data.type === 'agent_message' && 
                !data.analysis_id &&  // Only filter if NOT an analysis message
                data.sender !== 'project_planner' &&  // Never filter project planner responses
                data.sender !== 'technical_analyst' &&  // Never filter technical analyst responses
                (data.message.includes('Let me analyze') || 
                 data.message.includes('thinking') ||
                 data.message.includes('Processing') ||
                 data.message.includes('Starting analysis') ||
                 data.message.includes('Analyzing your project'))) {
              console.log('Filtering out preliminary message:', data.message.substring(0, 100));
              return; // Skip these messages
            }
            
            // Enhanced logging for debugging
            if (data.type === 'agent_message') {
              console.log('Received agent message:', {
                sender: data.sender,
                sender_name: data.sender_name,
                message_length: data.message?.length,
                is_thinking: data.is_thinking,
                analysis_id: data.analysis_id,
                message_preview: data.message?.substring(0, 100)
              });
              
              // Special logging for project planner
              if (data.sender === 'project_planner') {
                console.log('Project Planner message received:', {
                  is_thinking: data.is_thinking,
                  planning_context: data.planning_context,
                  will_stop_thinking: !data.is_thinking
                });
              }
            }
            
            // If this is an agent message, set isAgentThinking to false
            if (data.type === 'agent_message') {
              // Don't turn off thinking indicator if this is a thinking message
              if (!data.is_thinking) {
                console.log('Setting isAgentThinking to false - got final response');
                setIsAgentThinking(false);
              }
              
              setMessages(prev => [...prev, {
                id: generateMessageId(),
                type: 'agent',
                sender: data.sender || 'agent',
                senderName: data.sender_name || 'Agent',
                message: data.message || '',
                timestamp: new Date().toISOString(),
                message_id: data.message_id
              }]);
            } else {
              setMessages(prev => [...prev, {
                id: generateMessageId(),
                type: data.type === 'user_message' ? 'user' : 'system',
                sender: data.sender,
                senderName: data.sender_name,
                message: data.message,
                timestamp: new Date().toISOString(),
                message_id: data.message_id
              }]);
            }
            break;

          case 'analysis_started':
            console.log('Received analysis_started message:', data);
            setCurrentAnalysisId(data.analysis_id);
            setIsAnalyzing(true);
            setAnalysisComplete(false);
            setAnalysisSaved(false);  // Reset saved state when new analysis starts
            setIsAgentThinking(true);  // Show thinking indicator during analysis
            
            // Add a system message about the analysis starting
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              sender: 'system',
              message: data.message || 'Starting technical analysis...',
              timestamp: new Date().toISOString()
            }]);
            break;

          case 'analysis_status':
            console.log('🟡 Processing analysis_status message:', {
              status: data.status,
              isThinking: data.isThinking,
              message: data.message,
              currentThinkingState: isAgentThinking
            });
            
            // Handle isThinking field explicitly
            if (data.hasOwnProperty('isThinking')) {
              console.log(`🟡 Setting isAgentThinking to: ${data.isThinking}`);
              setIsAgentThinking(data.isThinking);
            }
            
            if (data.status === 'analyzing') {
              setIsAgentThinking(true);
              setAnalysisProgress(data.message || 'Analyzing...');
            } else if (data.status === 'retrying') {
              setAnalysisProgress(data.message || 'Retrying analysis...');
            } else if (data.status === 'already_running') {
              setCurrentAnalysisId(data.analysis_id);
              setAnalysisProgress(data.message || 'Analysis in progress...');
            } else if (data.status === 'completed' || data.status === 'finished') {
              console.log('🟡 Analysis status indicates completion, stopping thinking indicator');
              setIsAgentThinking(false);
              setAnalysisProgress('');
            }
            break;

          case 'analysis_failed':
            console.log('Analysis failed:', data);
            setIsAgentThinking(false);
            setAnalysisProgress('');
            setAnalysisError({
              message: data.message || 'Analysis failed',
              type: data.error_details?.error_type || 'unknown',
              recoverable: data.error_details?.recoverable || false,
              analysisId: data.analysis_id
            });
            
            // Add system message about the failure
            const errorMessage: Message = {
              id: generateMessageId(),
              type: 'system',
              sender: 'system',
              message: data.message || 'Analysis failed due to an error',
              timestamp: new Date().toISOString(),
              senderName: 'System'
            };
            setMessages(prev => [...prev, errorMessage]);
            break;

          case 'analysis_complete':
            console.log('🟡 ANALYSIS_COMPLETE handler triggered:', {
              analysis_id: data.analysis_id,
              currentAnalysisId: currentAnalysisId,
              willSetAnalysisId: data.analysis_id && !currentAnalysisId,
              hasResult: !!data.result,
              resultKeys: data.result ? Object.keys(data.result) : [],
              resultData: data.result,
              currentState: {
                isAnalyzing: isAnalyzing,
                analysisComplete: analysisComplete,
                messagesLength: messages.length
              }
            });
            
            console.log('🟡 Setting analysis states...');
            setIsAnalyzing(false);
            setAnalysisComplete(true);
            setIsAgentThinking(false); // Reset typing indicator
            setAnalysisSaved(false); // Reset saved state for new analysis
            
            // Always set the analysis ID from the complete message
            if (data.analysis_id) {
              console.log('🟡 Setting currentAnalysisId:', data.analysis_id);
              setCurrentAnalysisId(data.analysis_id);
            }
            
            // Check if this is a regenerated analysis
            const isRegenerated = data.result?.version && data.result.version > 1;
            
            // If we have result data, show it; otherwise show a waiting message
            const messageText = data.result && Object.keys(data.result).length > 0
              ? (isRegenerated 
                  ? `Analysis has been updated based on your feedback (Version ${data.result?.version || 1})`
                  : 'Analysis completed successfully!')
              : 'Analysis completed! Waiting for detailed results...';
            
            console.log('🟡 Adding analysis complete message:', {
              messageText,
              hasResult: !!data.result,
              resultKeys: data.result ? Object.keys(data.result) : [],
              messageId: generateMessageId()
            });
            
            setMessages(prev => {
              const newMessage: Message = {
                id: generateMessageId(),
                type: 'result',
                sender: data.sender || 'technical_agent',
                senderName: data.sender_name || 'Technical Analysis Agent',
                message: messageText,
                timestamp: new Date().toISOString(),
                result: data.result,
                message_id: data.message_id
              };
              console.log('🟡 New message being added:', newMessage);
              console.log('🟡 Previous messages count:', prev.length);
              return [...prev, newMessage];
            });
            
            // Notify parent component
            console.log('🟡 Checking onAnalysisComplete callback:', {
              hasCallback: !!onAnalysisComplete,
              hasResult: !!data.result,
              resultKeys: data.result ? Object.keys(data.result) : [],
              willCallCallback: !!(onAnalysisComplete && data.result)
            });
            
            if (onAnalysisComplete && data.result) {
              console.log('🟡 Calling onAnalysisComplete with result:', data.result);
              onAnalysisComplete(data.result);
            } else if (onAnalysisComplete && !data.result) {
              console.warn('🟡 onAnalysisComplete available but no result data to pass');
            } else if (!onAnalysisComplete && data.result) {
              console.warn('🟡 Result data available but no onAnalysisComplete callback');
            }
            
            // Log if we're missing result data
            if (!data.result || Object.keys(data.result).length === 0) {
              console.warn('Analysis complete but no result data received. Expecting follow-up agent_message.');
            }
            break;

          case 'analysis_result':
            console.log('Handling analysis_result message');
            setIsAnalyzing(false);
            setAnalysisComplete(true);
            setIsAgentThinking(false); // Reset typing indicator
            
            // Set the analysis ID if we don't have one yet
            if (data.analysis_id && !currentAnalysisId) {
              setCurrentAnalysisId(data.analysis_id);
            }
            
            // Check if this is a regenerated analysis
            const isRegeneratedResult = data.result?.version && data.result.version > 1;
            
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'result',
              sender: data.sender || 'technical_agent',
              senderName: data.sender_name || 'Technical Analysis Agent',
              message: isRegeneratedResult 
                ? `Analysis has been updated based on your feedback (Version ${data.result?.version || 1})`
                : 'Analysis results are ready!',
              timestamp: new Date().toISOString(),
              result: data.result,
              message_id: data.message_id
            }]);
            
            // Notify parent component
            console.log('🟡 analysis_result - Checking onAnalysisComplete callback:', {
              hasCallback: !!onAnalysisComplete,
              hasResult: !!data.result,
              resultKeys: data.result ? Object.keys(data.result) : [],
              willCallCallback: !!(onAnalysisComplete && data.result)
            });
            
            if (onAnalysisComplete && data.result) {
              console.log('🟡 analysis_result - Calling onAnalysisComplete with result:', data.result);
              onAnalysisComplete(data.result);
            } else if (onAnalysisComplete && !data.result) {
              console.warn('🟡 analysis_result - onAnalysisComplete available but no result data to pass');
            } else if (!onAnalysisComplete && data.result) {
              console.warn('🟡 analysis_result - Result data available but no onAnalysisComplete callback');
            }
            break;


          case 'analysis_saved':
            console.log('Analysis saved successfully:', data);
            // The optimistic update already happened in confirmAndSaveAnalysis
            // This just confirms it was saved to the database
            break;

          case 'analysis_cancelled':
            setCurrentAnalysisId(null);
            setIsAnalyzing(false);
            setAnalysisComplete(false);
            setAnalysisSaved(false);  // Reset analysisSaved state
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              sender: data.sender || 'technical_agent',
              senderName: data.sender_name || 'Technical Analysis Agent',
              message: data.message || 'Analysis was cancelled',
              timestamp: new Date().toISOString(),
              message_id: data.message_id
            }]);
            break;

          case 'error':
            setIsAgentThinking(false); // Also reset thinking state on error
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'error',
              sender: data.sender || 'system',
              senderName: data.sender_name || 'System',
              message: data.message || 'An error occurred',
              timestamp: new Date().toISOString(),
              message_id: data.message_id
            }]);
            setIsAnalyzing(false);
            setAnalysisError({
              message: data.message || 'An error occurred',
              type: 'general',
              recoverable: data.error_details?.recoverable || false,
              analysisId: data.error_details?.analysis_id
            });
            break;

          case 'conversation_stopped':
            console.log('Conversation stopped:', data);
            setIsAgentThinking(false);
            setAnalysisProgress('');
            setIsAnalyzing(false);
            
            // Add system message about the stop
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              sender: 'system',
              message: data.message || '🛑 Conversation stopped',
              timestamp: new Date().toISOString()
            }]);
            break;

          case 'agent_context_changed':
            console.log('Agent context changed:', data);
            
            // Update active agent state
            if (data.active_agent) {
              // Find the agent info by ID
              const agentInfo = agents.find(agent => agent.id === data.active_agent);
              if (agentInfo) {
                setActiveAgent(agentInfo);
                console.log('Active agent set to:', agentInfo.name);
              } else {
                // If agent not found in local list, create a basic info object
                const basicAgentInfo: AgentInfo = {
                  id: data.active_agent,
                  name: data.active_agent_name || data.active_agent,
                  mention_id: data.active_agent,
                  role: 'Agent',
                  description: '',
                  capabilities: [],
                  example_prompts: [],
                  is_available: true
                };
                setActiveAgent(basicAgentInfo);
              }
            } else {
              setActiveAgent(null);
              console.log('Active agent cleared');
            }
            
            // Add system message about the context change
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              sender: 'system',
              senderName: 'System',
              message: data.message || 'Agent context changed',
              timestamp: new Date().toISOString()
            }]);
            break;

          case 'ping':
            // Ignore ping messages
            break;

          case 'api_retry':
            console.log('API retry message received:', data);
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              sender: 'system',
              senderName: 'System',
              message: data.message || `🔄 API error detected. Retrying in ${data.retry_delay || 'a few'} seconds...`,
              timestamp: new Date().toISOString()
            }]);
            break;

          case 'constraint_violation_retry':
            console.log('Constraint violation retry message received:', data);
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              sender: 'system',
              senderName: 'System',
              message: data.message || '🔄 Analysis violates constraints. Retrying with enhanced instructions...',
              timestamp: new Date().toISOString()
            }]);
            break;

          case 'constraint_violation':
            console.log('Constraint violation warning received:', data);
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              sender: 'system',
              senderName: 'System',
              message: data.message || '⚠️ Analysis may violate project constraints. Manual review recommended.',
              timestamp: new Date().toISOString()
            }]);
            break;

          default:
            console.warn('🔶 Unknown message type:', data.type, 'Full data:', data);
        }
      } catch (error) {
        console.error('🔴 Error parsing WebSocket message:', {
          error: error instanceof Error ? error.message : String(error),
          rawData: event.data,
          timestamp: new Date().toISOString()
        });
      }
    };

    ws.onerror = (error) => {
      // WebSocket error events don't contain much detail in browsers
      console.error('🔴 WebSocket error occurred:', error);
      
      // Only add the connecting message if we don't already have one
      if (!connectionMessageId.current) {
        const newId = generateMessageId();
        connectionMessageId.current = newId;
        
        setMessages(prev => [...prev, {
          id: newId,
          type: 'system',
          message: 'Connecting to AI agents...',
          isLoading: true, // Flag to indicate loading state
          timestamp: new Date().toISOString()
        }]);
      }
    };

    ws.onclose = (event) => {
      console.log('🔴 WebSocket disconnected:', {
        code: event.code,
        reason: event.reason,
        wasClean: event.wasClean,
        timestamp: new Date().toISOString()
      });
      setIsConnected(false);
      wsRef.current = null;
      
      // Only attempt to reconnect if the connection was not closed intentionally
      // Normal closure code is 1000, 1001 is going away (page unload)
      if (event.code !== 1000 && event.code !== 1001) {
        // Attempt to reconnect after 3 seconds
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
        }
        
        reconnectTimeoutRef.current = setTimeout(() => {
          console.log('Attempting to reconnect...');
          connectWebSocket();
        }, 3000);
      }
      
      // Don't add disconnection message to chat - show in header instead
    };

    wsRef.current = ws;
  };

  useEffect(() => {
    // Clear any existing connection and timeout when project ID changes
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close(1000, 'Project ID changed'); // Normal closure
      wsRef.current = null;
    }
    
    // Connect with the new project ID
    connectWebSocket();

    return () => {
      // Clean up on component unmount
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounting'); // Normal closure
        wsRef.current = null;
      }
    };
  }, [projectId]);

  // Fetch agent catalog on mount
  useEffect(() => {
    fetchAgentCatalog();
  }, []);

  const fetchAgentCatalog = async () => {
    try {
      const response = await fetch(API_ENDPOINTS.AGENTS.CATALOG);
      if (response.ok) {
        const data = await response.json();
        setAgents(data);
      }
    } catch (error) {
      console.error('Failed to fetch agent catalog:', error);
    }
  };

  const startAnalysis = (force: boolean = false) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    wsRef.current.send(JSON.stringify({
      type: 'start_analysis',
      force: force
    }));
  };

  const cancelAnalysis = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN || !currentAnalysisId) {
      return;
    }

    wsRef.current.send(JSON.stringify({
      type: 'cancel_analysis',
      analysis_id: currentAnalysisId
    }));
  };

  const stopAgentConversation = () => {
    // Stop any ongoing agent thinking/processing
    setIsAgentThinking(false);
    setAnalysisProgress('');
    
    // If there's an active analysis, cancel it
    if (currentAnalysisId && isAnalyzing) {
      cancelAnalysis();
    }
    
    // Send a stop message to interrupt any ongoing agent processing
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'stop_conversation'
      }));
    }
    
    // Add a system message indicating the conversation was stopped
    setMessages(prev => [...prev, {
      id: generateMessageId(),
      type: 'system',
      sender: 'system',
      message: '🛑 Conversation stopped by user',
      timestamp: new Date().toISOString()
    }]);
  };

  const confirmAndSaveAnalysis = async () => {
    if (!currentAnalysisId || !isConnected) {
      return;
    }

    try {
      console.log('Saving analysis to insights:', currentAnalysisId);
      
      // Send save request via WebSocket using the existing confirm_analysis message type
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'confirm_analysis',
          analysis_id: currentAnalysisId
        }));
        
        // Optimistically update UI
        setAnalysisSaved(true);
        
        // Show success message
        setMessages(prev => [...prev, {
          id: generateMessageId(),
          type: 'system',
          sender: 'system',
          message: 'Analysis saved to project insights successfully!',
          timestamp: new Date().toISOString()
        }]);
      }
    } catch (error) {
      console.error('Failed to save analysis:', error);
      setMessages(prev => [...prev, {
        id: generateMessageId(),
        type: 'system',
        sender: 'system',
        message: 'Failed to save analysis. Please try again.',
        timestamp: new Date().toISOString()
      }]);
    }
  };

  const sendMessage = () => {
    if (!inputMessage.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    const userMessage = inputMessage.trim();
    
    // Add user message to chat
    setMessages(prev => [...prev, {
      id: generateMessageId(),
      type: 'user',
      message: userMessage,
      timestamp: new Date().toISOString()
    }]);

    // Send message based on context
    if (currentAnalysisId) {
      // In analysis context
      console.log('Sending user_question with analysis_id:', currentAnalysisId);
      wsRef.current.send(JSON.stringify({
        type: 'user_question',
        analysis_id: currentAnalysisId,
        question: userMessage
      }));
      setIsAgentThinking(true); // Show typing indicator
    } else {
      // General chat
      console.log('Sending chat_message:', userMessage);
      
      // Reset analysis saved state in case this triggers a new analysis
      if (userMessage.toLowerCase().includes('analysis') || userMessage.includes('@technical')) {
        setAnalysisSaved(false);
        setAnalysisComplete(false);
      }
      
      wsRef.current.send(JSON.stringify({
        type: 'chat_message',
        message: userMessage
      }));
      setIsAgentThinking(true); // Show typing indicator
    }

    setInputMessage('');
    setShowAgentSuggestions(false);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInputMessage(value);
    
    // Check for @ symbol
    const lastAtIndex = value.lastIndexOf('@');
    if (lastAtIndex !== -1 && lastAtIndex === value.length - 1 || 
        (lastAtIndex !== -1 && value.substring(lastAtIndex).match(/^@\w*$/))) {
      setShowAgentSuggestions(true);
      setAgentSearchTerm(value.substring(lastAtIndex + 1));
    } else {
      setShowAgentSuggestions(false);
    }
  };

  const insertAgentMention = (agent: AgentInfo) => {
    const lastAtIndex = inputMessage.lastIndexOf('@');
    const newMessage = inputMessage.substring(0, lastAtIndex) + `@${agent.mention_id} `;
    setInputMessage(newMessage);
    setShowAgentSuggestions(false);
    inputRef.current?.focus();
  };

  const filteredAgents = agents.filter(agent => 
    agent.is_available && 
    (agentSearchTerm === '' || 
     agent.mention_id.toLowerCase().includes(agentSearchTerm.toLowerCase()) ||
     agent.name.toLowerCase().includes(agentSearchTerm.toLowerCase()))
  );

  useEffect(() => {
    // Load existing insights only once when component mounts
    if (existingInsights && !analysisComplete) {
      // Add the existing analysis as a message
      const analysisMessage: Message = {
        id: generateMessageId(),
        type: 'result',
        sender: 'technical_agent',
        senderName: 'Technical Analysis Agent',
        message: 'Here is the previous analysis for this project:',
        timestamp: new Date().toISOString(),
        result: existingInsights,
      };
      
      setMessages([analysisMessage]);
      setAnalysisComplete(true);
      setAnalysisSaved(true);  // Set analysisSaved state
      
      // Don't set currentAnalysisId from existing insights as this is from a previous session
      // and would prevent new chat messages from working properly
    }
  }, []); // Empty dependency array to run only once on mount

  const retryAnalysis = () => {
    if (!analysisError?.analysisId) return;
    
    setAnalysisError(null);
    setAnalysisProgress('Retrying analysis...');
    
    // Send retry message
    wsRef.current?.send(JSON.stringify({
      type: 'start_analysis',
      force: true // Force retry even if previous analysis exists
    }));
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-medium text-gray-900">AI Agent Conversation</h3>
              {activeAgent && (
                <div className="flex items-center gap-2 px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
                  <span className="w-2 h-2 bg-blue-500 rounded-full"></span>
                  Chatting with {activeAgent.name}
                  <button
                    onClick={() => {
                      // Send clear command to backend
                      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                        wsRef.current.send(JSON.stringify({
                          type: 'user_message',
                          message: '@clear'
                        }));
                      }
                    }}
                    className="ml-2 text-blue-600 hover:text-blue-800"
                    title="Clear agent context"
                  >
                    <XMarkIcon className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
            <p className="text-sm text-gray-500">
              {isConnected ? 'Connected' : 'Connecting...'} • 
              {isAnalyzing ? ' Analysis in progress' : 
               analysisComplete ? ' Review analysis and ask questions' : ' Ready'}
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowAgentCatalog(!showAgentCatalog)}
              className="px-3 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-md flex items-center gap-2"
              title="View available agents"
            >
              <InformationCircleIcon className="h-5 w-5" />
              Agents
            </button>
            {analysisComplete && !analysisSaved && currentAnalysisId && (
              <button
                onClick={confirmAndSaveAnalysis}
                disabled={!isConnected || !currentAnalysisId}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <CheckIcon className="h-5 w-5" />
                Save to Insights
              </button>
            )}
            {!isAnalyzing && !analysisComplete && !existingInsights && (
              <button
                onClick={() => startAnalysis()}
                disabled={!isConnected}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <ArrowPathIcon className="h-5 w-5" />
                Start Analysis
              </button>
            )}
            {isAnalyzing && (
              <button
                onClick={cancelAnalysis}
                disabled={!isConnected}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <XMarkIcon className="h-5 w-5" />
                Cancel Analysis
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Agent Catalog Sidebar */}
      {showAgentCatalog && (
        <div className="absolute right-0 top-16 w-96 h-full bg-white border-l shadow-lg z-40 overflow-y-auto">
          <div className="p-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Available Agents</h3>
              <button
                onClick={() => setShowAgentCatalog(false)}
                className="text-gray-500 hover:text-gray-700"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            </div>
            <div className="space-y-4">
              {agents.map(agent => (
                <div
                  key={agent.id}
                  className={`p-4 rounded-lg border ${
                    agent.is_available ? 'border-gray-200' : 'border-gray-100 opacity-60'
                  }`}
                  style={{ borderLeftColor: agent.color, borderLeftWidth: '4px' }}
                >
                  <div className="flex items-start gap-3">
                    <span className="text-2xl">{agent.avatar}</span>
                    <div className="flex-1">
                      <h4 className="font-semibold flex items-center gap-2">
                        {agent.name}
                        <span className="text-sm text-gray-500">@{agent.mention_id}</span>
                      </h4>
                      <p className="text-sm text-gray-600 mt-1">{agent.description}</p>
                      {agent.example_prompts.length > 0 && (
                        <div className="mt-2">
                          <p className="text-xs text-gray-500 mb-1">Example prompts:</p>
                          <ul className="text-xs text-gray-600 space-y-1">
                            {agent.example_prompts.slice(0, 2).map((prompt, idx) => (
                              <li key={idx} className="italic">"{prompt}"</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {/* Analysis Error Banner */}
        {analysisError && (
          <div className={`p-4 rounded-lg border-l-4 ${
            analysisError.recoverable 
              ? 'bg-yellow-50 border-yellow-400 text-yellow-800' 
              : 'bg-red-50 border-red-400 text-red-800'
          }`}>
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <h4 className="font-medium mb-1">
                  {analysisError.recoverable ? '⚠️ Analysis Issue' : '❌ Analysis Failed'}
                </h4>
                <p className="text-sm mb-2">{analysisError.message}</p>
                {analysisError.recoverable && (
                  <p className="text-xs opacity-75 mb-3">
                    This appears to be a temporary issue. You can try again.
                  </p>
                )}
              </div>
              <button
                onClick={() => setAnalysisError(null)}
                className="text-gray-400 hover:text-gray-600 ml-2"
              >
                ✕
              </button>
            </div>
            
            {analysisError.recoverable && (
              <div className="flex gap-2">
                <button
                  onClick={retryAnalysis}
                  className="px-3 py-1 bg-yellow-600 text-white text-sm rounded hover:bg-yellow-700 transition-colors"
                >
                  🔄 Retry Analysis
                </button>
                <button
                  onClick={() => setAnalysisError(null)}
                  className="px-3 py-1 bg-gray-500 text-white text-sm rounded hover:bg-gray-600 transition-colors"
                >
                  Dismiss
                </button>
              </div>
            )}
          </div>
        )}

        {/* Analysis Progress Indicator */}
        {analysisProgress && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="flex items-center gap-2">
              <div className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
              <span className="text-blue-700 text-sm">{analysisProgress}</span>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-3xl rounded-lg px-4 py-2 ${
                message.type === 'user'
                  ? 'bg-blue-600 text-white'
                  : message.type === 'error'
                  ? 'bg-red-100 text-red-800'
                  : (message.sender === 'technical_agent' || message.sender === 'technical_analyst') || message.type === 'result'
                  ? 'bg-green-100 text-green-800'
                  : (message.sender === 'planner' || message.sender === 'project_planner')
                  ? 'bg-blue-100 text-blue-800'
                  : (message.sender === 'assistant' || message.sender === 'project_assistant')
                  ? 'bg-yellow-100 text-yellow-800'
                  : (message.sender === 'risk_analyst' || message.sender === 'security_analyst')
                  ? 'bg-purple-100 text-purple-800'
                  : message.type === 'system'
                  ? 'bg-gray-100 text-gray-800'
                  : 'bg-gray-200 text-gray-900'
              }`}
            >
              {message.senderName && (
                <div className="font-semibold text-sm mb-1">
                  {message.senderName}
                </div>
              )}
              <div className="whitespace-pre-wrap flex items-center gap-2">
                {message.type === 'agent' ? (
                  (() => {
                    // Try to parse structured content from agent messages
                    const structuredData = parseStructuredContent(message.message);
                    
                    if (structuredData) {
                      // Render structured analysis using consistent HTML styling
                      return (
                        <div className="text-xs overflow-x-auto bg-white bg-opacity-50 p-2 rounded">
                          <div className="text-sm font-semibold mb-1">Analysis Results:</div>
                          {renderStructuredAnalysis(structuredData)}
                        </div>
                      );
                    } else {
                      // Fallback to ReactMarkdown for non-structured content
                      return (
                        <ReactMarkdown 
                          className="prose prose-sm max-w-none text-gray-700 leading-relaxed"
                          components={{
                            h1: ({node, ...props}) => <h1 className="text-xl font-bold mt-4 mb-3 text-gray-900 border-b border-gray-200 pb-1" {...props} />,
                            h2: ({node, ...props}) => <h2 className="text-lg font-bold mt-4 mb-2 text-gray-900" {...props} />,
                            h3: ({node, ...props}) => <h3 className="text-base font-semibold mt-3 mb-2 text-gray-800" {...props} />,
                            h4: ({node, ...props}) => <h4 className="text-sm font-semibold mt-2 mb-1 text-gray-800" {...props} />,
                            ul: ({node, ordered, ...props}) => 
                              ordered ? 
                                <ol className="list-decimal list-outside ml-4 mb-3 space-y-1" {...props} /> : 
                                <ul className="list-disc list-outside ml-4 mb-3 space-y-1" {...props} />,
                            ol: ({node, ...props}) => <ol className="list-decimal list-outside ml-4 mb-3 space-y-1" {...props} />,
                            li: ({node, ...props}) => <li className="mb-1 leading-relaxed" {...props} />,
                            p: ({node, ...props}) => <p className="mb-3 leading-relaxed" {...props} />,
                            strong: ({node, ...props}) => <strong className="font-semibold text-gray-900" {...props} />,
                            em: ({node, ...props}) => <em className="italic text-gray-600" {...props} />,
                            code: ({node, ...props}) => <code className="bg-gray-100 px-1 py-0.5 rounded text-sm font-mono text-gray-800" {...props} />,
                            blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-blue-200 pl-4 py-2 mb-3 bg-blue-50 rounded-r" {...props} />,
                            hr: ({node, ...props}) => <hr className="my-4 border-gray-300" {...props} />,
                            table: ({node, ...props}) => <table className="w-full border-collapse border border-gray-300 mb-3" {...props} />,
                            th: ({node, ...props}) => <th className="border border-gray-300 px-2 py-1 bg-gray-100 font-semibold text-left" {...props} />,
                            td: ({node, ...props}) => <td className="border border-gray-300 px-2 py-1" {...props} />
                          }}
                        >
                          {message.message}
                        </ReactMarkdown>
                      );
                    }
                  })()
                ) : (
                  message.message
                )}
                {message.isLoading && (
                  <span className="inline-block animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500"></span>
                )}
              </div>
              {message.result && (
                <div className="mt-2 pt-2 border-t border-gray-300">
                  <div className="text-sm font-semibold mb-1">Analysis Results:</div>
                  <div className="text-xs overflow-x-auto bg-white bg-opacity-50 p-2 rounded">
                    {message.result.raw_analysis ? (
                      // Display raw analysis as markdown if available
                      <ReactMarkdown className="prose prose-xs max-w-none">
                        {message.result.raw_analysis}
                      </ReactMarkdown>
                    ) : message.result.technical_analysis || message.result.risk_assessment || message.result.project_plan ? (
                      // Display structured analysis data
                      <div className="space-y-3">
                        {message.result.technical_analysis && (
                          <div>
                            <h4 className="font-semibold text-sm mb-1">Technical Analysis</h4>
                            <div className="text-xs space-y-1">
                              <p><strong>Architecture:</strong> {message.result.technical_analysis.architecture}</p>
                              <div>
                                <strong>Tech Stack:</strong>
                                <ul className="ml-4 mt-1">
                                  {message.result.technical_analysis.tech_stack?.frontend?.length > 0 && (
                                    <li>Frontend: {message.result.technical_analysis.tech_stack.frontend.join(', ')}</li>
                                  )}
                                  {message.result.technical_analysis.tech_stack?.backend?.length > 0 && (
                                    <li>Backend: {message.result.technical_analysis.tech_stack.backend.join(', ')}</li>
                                  )}
                                  {message.result.technical_analysis.tech_stack?.infrastructure?.length > 0 && (
                                    <li>Infrastructure: {message.result.technical_analysis.tech_stack.infrastructure.join(', ')}</li>
                                  )}
                                  {message.result.technical_analysis.tech_stack?.tools?.length > 0 && (
                                    <li>Tools: {message.result.technical_analysis.tech_stack.tools.join(', ')}</li>
                                  )}
                                </ul>
                              </div>
                              <div>
                                <strong>Scores:</strong> 
                                Complexity: {message.result.technical_analysis.complexity_score}/10, 
                                Maintainability: {message.result.technical_analysis.maintainability_score}/10, 
                                Scalability: {message.result.technical_analysis.scalability_score}/10
                              </div>
                            </div>
                          </div>
                        )}
                        
                        {message.result.risk_assessment && (
                          <div>
                            <h4 className="font-semibold text-sm mb-1">Risk Assessment</h4>
                            <div className="text-xs space-y-1">
                              <p><strong>Overall Risk Score:</strong> {message.result.risk_assessment.overall_risk_score}/10</p>
                              {message.result.risk_assessment.key_risks?.length > 0 && (
                                <div>
                                  <strong>Key Risks:</strong>
                                  <ul className="ml-4 mt-1">
                                    {message.result.risk_assessment.key_risks.map((risk: any, idx: number) => (
                                      <li key={idx}>{risk.name} ({risk.level}) - {risk.description}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                        
                        {message.result.project_plan && (
                          <div>
                            <h4 className="font-semibold text-sm mb-1">Project Plan</h4>
                            <div className="text-xs space-y-1">
                              <p><strong>Timeline:</strong> {message.result.project_plan.timeline}</p>
                              <p><strong>Estimated Cost:</strong> ${message.result.project_plan.estimated_cost?.toLocaleString()}</p>
                              {message.result.project_plan.phases?.length > 0 && (
                                <div>
                                  <strong>Phases:</strong>
                                  <ul className="ml-4 mt-1">
                                    {message.result.project_plan.phases.map((phase: any, idx: number) => (
                                      <li key={idx}>{phase.name} ({phase.duration} weeks) - {phase.description}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                        
                        {message.result.recommendations?.length > 0 && (
                          <div>
                            <h4 className="font-semibold text-sm mb-1">Recommendations</h4>
                            <ul className="text-xs ml-4">
                              {message.result.recommendations.map((rec: string, idx: number) => (
                                <li key={idx}>{rec}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ) : (
                      // Fallback to JSON display
                      <pre>{JSON.stringify(message.result, null, 2)}</pre>
                    )}
                  </div>
                </div>
              )}
              <div className="text-xs opacity-75 mt-1">
                {new Date(message.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>
        ))}
        
        {/* Typing indicator */}
        {isAgentThinking && (
          <div className="flex justify-start">
            <div className="max-w-3xl rounded-lg px-4 py-2 bg-gray-200 text-gray-900">
              <div className="font-semibold text-sm mb-1">
                {messages.length > 0 && messages[messages.length - 1].senderName ? messages[messages.length - 1].senderName : 'Technical Analysis Agent'}
              </div>
              <div className="flex items-center gap-2">
                <div className="flex space-x-1">
                  <div className="h-2 w-2 bg-blue-600 rounded-full animate-pulse"></div>
                  <div className="h-2 w-2 bg-blue-600 rounded-full animate-pulse" style={{ animationDelay: '200ms' }}></div>
                  <div className="h-2 w-2 bg-blue-600 rounded-full animate-pulse" style={{ animationDelay: '400ms' }}></div>
                </div>
                <span className="text-sm text-gray-600">Thinking...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="bg-white border-t px-6 py-4">
        <div className="relative">
          {/* Save to Insights button (bottom placement) */}
          {analysisComplete && !analysisSaved && currentAnalysisId && (
            <div className="mb-4 flex justify-end">
              <button
                onClick={confirmAndSaveAnalysis}
                disabled={!isConnected || !currentAnalysisId}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <CheckIcon className="h-5 w-5" />
                Save to Insights
              </button>
            </div>
          )}
          {/* Agent suggestions dropdown */}
          {showAgentSuggestions && filteredAgents.length > 0 && (
            <div className="absolute bottom-full mb-2 left-0 w-64 bg-white border rounded-lg shadow-lg">
              <div className="p-2">
                <p className="text-xs text-gray-500 mb-2">Available agents:</p>
                {filteredAgents.map(agent => (
                  <button
                    key={agent.id}
                    onClick={() => insertAgentMention(agent)}
                    className="w-full text-left p-2 hover:bg-gray-100 rounded flex items-center gap-2"
                  >
                    <span>{agent.avatar}</span>
                    <div>
                      <div className="font-medium text-sm">@{agent.mention_id}</div>
                      <div className="text-xs text-gray-500">{agent.name}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}
          
          <form onSubmit={(e) => { e.preventDefault(); sendMessage(); }} className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputMessage}
              onChange={handleInputChange}
              placeholder={
                activeAgent
                  ? `Ask ${activeAgent.name} anything... (or type '@clear' to change agents)`
                  : currentAnalysisId 
                    ? "Ask a question about the analysis or type '@' to mention an agent..." 
                    : "Type a message or '@' to mention an agent..."
              }
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={!isConnected || isAgentThinking}
            />
            {isAgentThinking ? (
              <button
                type="button"
                onClick={stopAgentConversation}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 flex items-center gap-2"
                title="Stop agent conversation"
              >
                <StopIcon className="h-5 w-5" />
                Stop
              </button>
            ) : (
              <button
                type="submit"
                disabled={!isConnected || !inputMessage.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <PaperAirplaneIcon className="h-5 w-5" />
                Send
              </button>
            )}
          </form>
        </div>
        {!isConnected && (
          <p className="text-sm text-red-500 mt-2">
            Connection lost. Attempting to reconnect...
          </p>
        )}
        {currentAnalysisId && (
          <p className="text-xs text-gray-500 mt-2">
            💡 Tip: You can update the analysis by saying "please update the analysis with..." or mention specific agents with @
          </p>
        )}
      </div>
    </div>
  );
}
