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
  structured_data?: any; // Structured analysis data from backend
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
  onAnalysisComplete?: (insights: any) => void;
  existingInsights?: any;  // Add this prop for existing analysis
}

export default function AgentConversation({ projectId, onAnalysisComplete, existingInsights }: AgentConversationProps) {
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
      // Try to parse JSON first - handle both complete JSON objects and nested structures
      if (messageText.trim().startsWith('{') && messageText.trim().endsWith('}')) {
        try {
          const parsed = JSON.parse(messageText);
          console.log('🟢 Successfully parsed JSON response:', {
            hasTA: !!parsed.technical_analysis,
            hasRA: !!parsed.risk_assessment,
            hasPP: !!parsed.project_plan,
            hasRec: !!parsed.recommendations,
            topLevelKeys: Object.keys(parsed)
          });
          
          // Check if it's a structured analysis response
          if (parsed.technical_analysis || parsed.risk_assessment || parsed.project_plan || parsed.recommendations) {
            return parsed;
          }
          
          // Also check if the message itself contains the structure we need
          if (typeof parsed === 'object' && parsed !== null) {
            return parsed;
          }
        } catch (jsonError) {
          console.warn('🟡 JSON parse error:', jsonError);
          // Continue to markdown parsing if JSON fails
        }
      }
      
      // Try to detect structured markdown content (both old and new formats)
      if (messageText.includes('## Analysis Results:') || 
          messageText.includes('### Technical Analysis') ||
          messageText.includes('### Risk Assessment') ||
          messageText.includes('### Project Plan') ||
          messageText.includes('Technical Analysis:') ||
          messageText.includes('Architecture Overview') ||
          messageText.includes('Technology Stack')) {
        
        // Parse markdown-formatted analysis into structured data
        const result: any = {};
        
        // Extract Technical Analysis section (handle both ### and plain text formats)
        let techMatch = messageText.match(/### Technical Analysis([\s\S]*?)(?=###|\n\n|$)/);
        if (!techMatch) {
          // Try new format with "Technical Analysis:" header
          techMatch = messageText.match(/Technical Analysis:([\s\S]*?)(?=Risk Assessment|Project Plan|Recommendations|$)/);
        }
        
        if (techMatch) {
          const techContent = techMatch[1];
          result.technical_analysis = {
            architecture: extractArchitecture(techContent),
            tech_stack: extractTechStackFromNewFormat(techContent),
            complexity_score: extractScoreFromNewFormat(techContent, 'Complexity'),
            maintainability_score: extractScoreFromNewFormat(techContent, 'Maintainability'),
            scalability_score: extractScoreFromNewFormat(techContent, 'Scalability'),
            performance_score: extractScoreFromNewFormat(techContent, 'Performance'),
            security_score: extractScoreFromNewFormat(techContent, 'Security')
          };
        }
        
        // Extract Risk Assessment section
        let riskMatch = messageText.match(/### Risk Assessment([\s\S]*?)(?=###|\n\n|$)/);
        if (!riskMatch) {
          // For new format, provide default risk assessment based on complexity
          const complexityScore = extractScoreFromNewFormat(messageText, 'Complexity') || 8;
          result.risk_assessment = {
            overall_risk_score: Math.max(1, Math.min(10, complexityScore - 1)),
            key_risks: [],
            mitigation_strategies: []
          };
        } else {
          const riskContent = riskMatch[1];
          result.risk_assessment = {
            overall_risk_score: extractScore(riskContent, 'Overall Risk Score'),
            key_risks: extractRisks(riskContent),
            mitigation_strategies: []
          };
        }
        
        // Extract Project Plan section
        let planMatch = messageText.match(/### Project Plan([\s\S]*?)(?=###|\n\n|$)/);
        if (!planMatch) {
          // Try to extract timeline from the whole message if no formal project plan section
          const timeline = extractProjectTimeline(messageText);
          if (timeline) {
            result.project_plan = {
              timeline: timeline,
              estimated_cost: 0,
              phases: [],
              milestones: [],
              resource_requirements: {
                developers: 0,
                designers: 0,
                qa: 0,
                devops: 0,
                pm: 1
              }
            };
          }
        } else {
          const planContent = planMatch[1];
          result.project_plan = {
            timeline: extractValue(planContent, 'Timeline'),
            estimated_cost: extractCost(planContent),
            phases: extractPhases(planContent),
            milestones: [],
            resource_requirements: {
              developers: 0,
              designers: 0,
              qa: 0,
              devops: 0,
              pm: 1
            }
          };
        }
        
        // Extract Recommendations section
        let recMatch = messageText.match(/### Recommendations([\s\S]*?)(?=###|\n\n|$)/);
        if (!recMatch) {
          // For new format, provide default recommendations based on analysis
          result.recommendations = [
            "Implement comprehensive testing strategy",
            "Establish proper monitoring and logging",
            "Follow security best practices",
            "Plan for scalability from the start"
          ];
        } else {
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

  // New parsing functions for current agent output format
  const extractArchitecture = (content: string) => {
    // Look for "Architecture Overview" section or "Type:" field
    const typeMatch = content.match(/(?:Architecture Overview|Type):\s*([^\n]+)/);
    if (typeMatch) {
      return typeMatch[1].trim();
    }
    
    // Fallback to looking for "architecture" keyword
    const archMatch = content.match(/architecture[:\s]*([^\n]+)/i);
    return archMatch ? archMatch[1].trim() : '';
  };

  const extractTechStackFromNewFormat = (content: string) => {
    const stack: any = {};
    
    // Extract Frontend technologies
    const frontendMatch = content.match(/Frontend:\s*([\s\S]*?)(?=Backend:|Infrastructure:|$)/);
    if (frontendMatch) {
      const frontendContent = frontendMatch[1];
      const techs = frontendContent.match(/- ([^\n]+)/g);
      if (techs) {
        stack.frontend = techs.map(tech => tech.replace(/^- /, '').trim());
      }
    }
    
    // Extract Backend technologies
    const backendMatch = content.match(/Backend:\s*([\s\S]*?)(?=Frontend:|Infrastructure:|$)/);
    if (backendMatch) {
      const backendContent = backendMatch[1];
      const techs = backendContent.match(/- ([^\n]+)/g);
      if (techs) {
        stack.backend = techs.map(tech => tech.replace(/^- /, '').trim());
      }
    }
    
    // Extract Infrastructure technologies
    const infraMatch = content.match(/Infrastructure:\s*([\s\S]*?)(?=Frontend:|Backend:|Technical Considerations:|$)/);
    if (infraMatch) {
      const infraContent = infraMatch[1];
      const techs = infraContent.match(/- ([^\n]+)/g);
      if (techs) {
        stack.infrastructure = techs.map(tech => tech.replace(/^- /, '').trim());
      }
    }
    
    // Extract Tools (if mentioned)
    const toolsMatch = content.match(/Tools:\s*([\s\S]*?)(?=Frontend:|Backend:|Infrastructure:|$)/);
    if (toolsMatch) {
      const toolsContent = toolsMatch[1];
      const techs = toolsContent.match(/- ([^\n]+)/g);
      if (techs) {
        stack.tools = techs.map(tech => tech.replace(/^- /, '').trim());
      }
    }
    
    return stack;
  };

  const extractScoreFromNewFormat = (content: string, key: string) => {
    // Look for "Complexity Rating:", "Maintainability Score:", etc.
    const patterns = [
      new RegExp(`${key}\\s*(?:Rating|Score)?:\\s*(\\d+(?:\\.\\d+)?)`),
      new RegExp(`${key}\\s*(?:Rating|Score)?[:\\s]*(\\d+(?:\\.\\d+)?)/10`),
      new RegExp(`${key}[:\\s]*(\\d+(?:\\.\\d+)?)`),
    ];
    
    for (const pattern of patterns) {
      const match = content.match(pattern);
      if (match) {
        return parseFloat(match[1]);
      }
    }
    
    return 0;
  };

  const extractProjectTimeline = (content: string) => {
    // Look for "Project Timeline:" pattern
    const timelineMatch = content.match(/Project Timeline:\s*([^\n]+)/);
    return timelineMatch ? timelineMatch[1].trim() : '';
  };

  // Unified structured content rendering function - used for both agent messages and results
  const renderUnifiedStructuredContent = (analysisData: any) => {
    if (!analysisData) return null;
    
    return (
      <div className="space-y-4">
        {/* Technical Analysis Section */}
        {analysisData.technical_analysis && (
          <div>
            <h3 className="font-semibold text-base mb-2 text-gray-900">Technical Analysis</h3>
            <div className="text-sm space-y-2 text-gray-800">
              {analysisData.technical_analysis.architecture && (
                <p><span className="font-semibold">Architecture:</span> {analysisData.technical_analysis.architecture}</p>
              )}
              {analysisData.technical_analysis.tech_stack && (
                <div>
                  <span className="font-semibold">Tech Stack:</span>
                  <div className="ml-4 mt-1 space-y-1">
                    {analysisData.technical_analysis.tech_stack.frontend?.length > 0 && (
                      <div><span className="font-medium">Frontend:</span> {analysisData.technical_analysis.tech_stack.frontend.join(', ')}</div>
                    )}
                    {analysisData.technical_analysis.tech_stack.backend?.length > 0 && (
                      <div><span className="font-medium">Backend:</span> {analysisData.technical_analysis.tech_stack.backend.join(', ')}</div>
                    )}
                    {analysisData.technical_analysis.tech_stack.infrastructure?.length > 0 && (
                      <div><span className="font-medium">Infrastructure:</span> {analysisData.technical_analysis.tech_stack.infrastructure.join(', ')}</div>
                    )}
                    {analysisData.technical_analysis.tech_stack.tools?.length > 0 && (
                      <div><span className="font-medium">Tools:</span> {analysisData.technical_analysis.tech_stack.tools.join(', ')}</div>
                    )}
                  </div>
                </div>
              )}
              {(analysisData.technical_analysis.complexity_score || 
                analysisData.technical_analysis.maintainability_score || 
                analysisData.technical_analysis.scalability_score ||
                analysisData.technical_analysis.security_score) && (
                <div>
                  <span className="font-semibold">Scores:</span>
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
        
        {/* Risk Assessment Section */}
        {analysisData.risk_assessment && (
          <div>
            <h3 className="font-semibold text-base mb-2 text-gray-900">Risk Assessment</h3>
            <div className="text-sm space-y-2 text-gray-800">
              {analysisData.risk_assessment.overall_risk_score && (
                <p><span className="font-semibold">Overall Risk Score:</span> {analysisData.risk_assessment.overall_risk_score}/10</p>
              )}
              {analysisData.risk_assessment.key_risks?.length > 0 && (
                <div>
                  <span className="font-semibold">Key Risks:</span>
                  <div className="ml-4 mt-1 space-y-1">
                    {analysisData.risk_assessment.key_risks.map((risk: any, idx: number) => (
                      <div key={idx}>{risk.name} ({risk.level}) - {risk.description}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        
        {/* Project Plan Section */}
        {analysisData.project_plan && (
          <div>
            <h3 className="font-semibold text-base mb-2 text-gray-900">Project Plan</h3>
            <div className="text-sm space-y-2 text-gray-800">
              {analysisData.project_plan.timeline && (
                <p><span className="font-semibold">Timeline:</span> {analysisData.project_plan.timeline}</p>
              )}
              {analysisData.project_plan.estimated_cost && (
                <p><span className="font-semibold">Estimated Cost:</span> ${typeof analysisData.project_plan.estimated_cost === 'number' ? 
                  analysisData.project_plan.estimated_cost.toLocaleString() : 
                  analysisData.project_plan.estimated_cost}</p>
              )}
              {analysisData.project_plan.phases?.length > 0 && (
                <div>
                  <span className="font-semibold">Phases:</span>
                  <div className="ml-4 mt-1 space-y-1">
                    {analysisData.project_plan.phases.map((phase: any, idx: number) => (
                      <div key={idx}>
                        {phase.name} ({phase.duration} weeks) - {phase.description}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
        
        {/* Recommendations Section */}
        {analysisData.recommendations?.length > 0 && (
          <div>
            <h3 className="font-semibold text-base mb-2 text-gray-900">Recommendations</h3>
            <div className="text-sm space-y-1 text-gray-800">
              {analysisData.recommendations.map((rec: string, idx: number) => (
                <div key={idx} className="flex items-start">
                  <span className="font-medium mr-2">{idx + 1}.</span>
                  <span>{rec}</span>
                </div>
              ))}
            </div>
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
    const shouldShowSaveButton = analysisComplete && !analysisSaved && currentAnalysisId;
    console.log('🔘 Save button state evaluation:', {
      analysisComplete,
      analysisSaved,
      currentAnalysisId,
      isConnected,
      existingInsights: !!existingInsights,
      shouldShowSaveButton,
      condition1_analysisComplete: analysisComplete,
      condition2_notAnalysisSaved: !analysisSaved,
      condition3_hasCurrentAnalysisId: !!currentAnalysisId,
      allConditionsMet: analysisComplete && !analysisSaved && currentAnalysisId,
      buttonWillShow: shouldShowSaveButton && isConnected
    });
    
    if (!shouldShowSaveButton) {
      console.log('🚫 Save button NOT showing because:', {
        missingAnalysisComplete: !analysisComplete,
        alreadySaved: analysisSaved,
        missingAnalysisId: !currentAnalysisId,
        notConnected: !isConnected
      });
    } else {
      console.log('✅ Save button SHOULD be showing');
    }
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
              
              // Check if this is a Technical Analysis message (JSON or formatted text from agent)
              const isJsonStructuredResponse = data.message && data.message.trim().startsWith('{') && data.message.trim().endsWith('}');
              const isMarkdownAnalysisResponse = data.message && (
                data.message.includes('Technical Analysis:') || 
                data.message.includes('Technical Analysis\n') ||
                data.message.match(/Technical Analysis[:\s]/i) ||
                (data.message.includes('Architecture Overview') && data.message.includes('Technology Stack'))
              );
              
              if (isJsonStructuredResponse || isMarkdownAnalysisResponse) {
                console.log('🟡 Technical Analysis message detected, parsing structured content:', {
                  sender: data.sender,
                  messageLength: data.message.length,
                  hasAnalysisId: !!data.analysis_id,
                  currentAnalysisId: currentAnalysisId,
                  isJsonFormat: isJsonStructuredResponse,
                  isMarkdownFormat: isMarkdownAnalysisResponse,
                  messagePreview: data.message.substring(0, 200) + '...'
                });
                
                // Parse the formatted text into structured data
                const parsedStructuredData = parseStructuredContent(data.message);
                
                if (parsedStructuredData) {
                  console.log('🟡 Successfully parsed Technical Analysis, activating save button:', {
                    parsedKeys: Object.keys(parsedStructuredData),
                    technicalAnalysisKeys: parsedStructuredData.technical_analysis ? Object.keys(parsedStructuredData.technical_analysis) : [],
                    willActivateSave: true
                  });
                  
                  // Generate analysis ID if not provided
                  const analysisId = data.analysis_id || `analysis_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
                  
                  // Set analysis states to activate save button
                  setIsAnalyzing(false);
                  setAnalysisComplete(true);
                  setAnalysisSaved(false);
                  setCurrentAnalysisId(analysisId);
                  setIsAgentThinking(false);
                  
                  // Add the structured data to the message
                  data.structured_data = parsedStructuredData;
                  data.analysis_id = analysisId;
                  
                  console.log('🟡 Technical Analysis save button should now be active with:', {
                    analysisComplete: true,
                    analysisSaved: false,
                    currentAnalysisId: analysisId,
                    hasStructuredData: !!parsedStructuredData
                  });
                } else {
                  console.warn('🟡 Failed to parse Technical Analysis message');
                }
              }
            }
            
            // If this is an agent message, set isAgentThinking to false
            if (data.type === 'agent_message') {
              // Don't turn off thinking indicator if this is a thinking message
              if (!data.is_thinking) {
                console.log('Setting isAgentThinking to false - got final response');
                setIsAgentThinking(false);
              }
              
              // Check if this is a new analysis with structured data
              if (data.structured_data && data.analysis_id) {
                console.log('🟡 New structured analysis detected, activating save button:', {
                  analysis_id: data.analysis_id,
                  currentAnalysisId: currentAnalysisId,
                  willSetAnalysisId: !currentAnalysisId,
                  structured_data_keys: Object.keys(data.structured_data || {}),
                  currentStates: {
                    analysisComplete: analysisComplete,
                    analysisSaved: analysisSaved,
                    isConnected: isConnected
                  }
                });
                
                setAnalysisComplete(true);
                setAnalysisSaved(false);  // Reset saved state for new analysis
                
                // Always set the analysis ID for new analyses (remove conditional check)
                console.log('🟡 Setting currentAnalysisId from agent message:', data.analysis_id);
                setCurrentAnalysisId(data.analysis_id);
              }
              
              setMessages(prev => [...prev, {
                id: generateMessageId(),
                type: 'agent',
                sender: data.sender || 'agent',
                senderName: data.sender_name || 'Agent',
                message: data.message || '',
                timestamp: new Date().toISOString(),
                message_id: data.message_id,
                structured_data: data.structured_data  // Include structured data if available
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
              console.log('🟡 Setting currentAnalysisId from analysis_complete:', data.analysis_id);
              setCurrentAnalysisId(data.analysis_id);
            } else {
              console.warn('🟡 No analysis_id provided in analysis_complete message');
            }
            
            console.log('🟡 Analysis states set - save button should appear with:', {
              analysisComplete: true,
              analysisSaved: false,
              currentAnalysisId: data.analysis_id,
              expectedSaveButton: !!data.analysis_id
            });
            
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
    setAnalysisProgress('');
    
    // Add a message suggesting the user to retry via chat
    setMessages(prev => [...prev, {
      id: generateMessageId(),
      type: 'system',
      sender: 'system',
      message: '💡 To retry analysis, please send a message like "@technical please analyze" or "start analysis"',
      timestamp: new Date().toISOString()
    }]);
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
                    // First check if we have structured data directly from backend
                    let structuredData = message.structured_data;
                    
                    // If no structured data, try to parse from message text
                    if (!structuredData) {
                      structuredData = parseStructuredContent(message.message);
                    }
                    
                    // Force structured rendering for all agent types to ensure consistent formatting
                    const isAgentMessage = message.sender === 'technical_agent' || 
                                         message.sender === 'technical_analyst' ||
                                         message.sender === 'project_planner' ||
                                         message.sender === 'planner' ||
                                         message.sender === 'assistant' ||
                                         message.sender === 'project_assistant' ||
                                         message.sender === 'risk_analyst' ||
                                         message.sender === 'security_analyst' ||
                                         message.senderName?.includes('Agent') ||
                                         message.senderName?.includes('Technical') ||
                                         message.senderName?.includes('Planner') ||
                                         message.senderName?.includes('Assistant') ||
                                         message.senderName?.includes('Analysis');
                    
                    if (isAgentMessage) {
                      // Force unified structured rendering for all agent messages to ensure consistent formatting
                      return (
                        <div className="w-full">
                          <div className="mb-2">{structuredData ? 'Analysis completed successfully!' : 'Response received successfully!'}</div>
                          <div className="mt-2 pt-2 border-t border-gray-300">
                            <div className="text-sm font-semibold mb-3">{structuredData ? 'Analysis Results:' : 'Agent Response:'}</div>
                            <div className="bg-white bg-opacity-50 p-3 rounded">
                              {structuredData ? renderUnifiedStructuredContent(structuredData) : (
                                // Force structured format even without structured data
                                <div className="space-y-4">
                                  <div>
                                    <h3 className="font-semibold text-base mb-2 text-gray-900">
                                      {message.senderName?.includes('Technical') ? 'Technical Analysis' :
                                       message.senderName?.includes('Planner') ? 'Project Planning Response' :
                                       message.senderName?.includes('Risk') ? 'Risk Assessment' :
                                       message.senderName?.includes('Security') ? 'Security Analysis' :
                                       'Agent Response'}
                                    </h3>
                                    <div className="text-sm text-gray-800 space-y-2">
                                      {message.message.split('\n\n').map((paragraph, idx) => (
                                        <div key={idx} className="leading-relaxed">
                                          {paragraph.split('\n').map((line, lineIdx) => {
                                            // Apply structured formatting to common patterns
                                            if (line.match(/^\d+\.\s/)) {
                                              return (
                                                <div key={lineIdx} className="flex items-start mb-2">
                                                  <span className="font-medium mr-2 text-gray-700">{line.match(/^\d+\./)?.[0]}</span>
                                                  <span>{line.replace(/^\d+\.\s/, '')}</span>
                                                </div>
                                              );
                                            } else if (line.includes(':') && !line.includes('http')) {
                                              const [label, ...value] = line.split(':');
                                              return (
                                                <div key={lineIdx} className="mb-1">
                                                  <span className="font-semibold">{label}:</span> {value.join(':')}
                                                </div>
                                              );
                                            } else if (line.trim()) {
                                              return <div key={lineIdx} className="mb-1">{line}</div>;
                                            }
                                            return null;
                                          })}
                                        </div>
                                      ))}
                                    </div>
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    } else {
                      // Fallback to ReactMarkdown for non-analysis content
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
                  <div className="text-sm font-semibold mb-3">Analysis Results:</div>
                  <div className="bg-white bg-opacity-50 p-3 rounded">
                    {message.result.raw_analysis ? (
                      // Display raw analysis as markdown if available
                      <ReactMarkdown className="prose prose-sm max-w-none">
                        {message.result.raw_analysis}
                      </ReactMarkdown>
                    ) : message.result.technical_analysis || message.result.risk_assessment || message.result.project_plan ? (
                      // Use unified structured rendering for consistent formatting
                      renderUnifiedStructuredContent(message.result)
                    ) : (
                      // Fallback to JSON display
                      <pre className="text-xs whitespace-pre-wrap">{JSON.stringify(message.result, null, 2)}</pre>
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
