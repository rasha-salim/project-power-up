import { useState, useEffect, useRef } from 'react';
import { PaperAirplaneIcon, XMarkIcon, CheckIcon, ArrowPathIcon, InformationCircleIcon } from '@heroicons/react/24/outline';

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

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    console.log('isAgentThinking:', isAgentThinking); // Debug log
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

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8000/api/v1/ws/agent-conversation/${projectId}`;
    
    console.log('Connecting to WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
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
        console.log('Received message:', data);
        
        // Check if this message has already been processed
        if (data.message_id && processedMessageIds.current.has(data.message_id)) {
          console.log(`Skipping duplicate message with ID: ${data.message_id}`);
          return;
        }
        
        // Add to processed messages if it has an ID
        if (data.message_id) {
          processedMessageIds.current.add(data.message_id);
          
          // Keep the set from growing too large
          if (processedMessageIds.current.size > 100) {
            // Convert to array, remove oldest entries, convert back to set
            const idsArray = Array.from(processedMessageIds.current);
            processedMessageIds.current = new Set(idsArray.slice(-50));
          }
        }
        
        switch (data.type) {
          case 'user_message':
          case 'agent_message':
          case 'system_message':
            // Filter out certain system messages to keep chat clean
            if (data.type === 'system_message' && 
                (data.message.includes('Connected to agent conversation') || 
                 data.message.includes('Connection established'))) {
              return; // Skip these messages
            }
            
            // Filter out preliminary agent messages since we have typing indicator
            if (data.type === 'agent_message' && 
                (data.message.includes('Let me analyze') || 
                 data.message.includes('thinking') ||
                 data.message.includes('Processing'))) {
              console.log('Filtering out preliminary message:', data.message);
              return; // Skip these messages
            }
            
            // If this is an agent message, set isAgentThinking to false
            if (data.type === 'agent_message') {
              // Don't reset thinking state for preliminary messages
              // Only reset when we get a substantial response (more than 50 characters) or an error
              const isPreliminaryMessage = data.message.includes('Let me analyze') || 
                                           data.message.includes('thinking') ||
                                           data.message.includes('Processing') ||
                                           data.message.length < 50;
              
              if (!isPreliminaryMessage || data.message.includes('error') || data.message.includes('apologize')) {
                setIsAgentThinking(false);
                console.log('Setting isAgentThinking to false - got final response'); // Debug log
              } else {
                console.log('Keeping isAgentThinking true for preliminary message'); // Debug log
              }
            }
            
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: data.type === 'agent_message' ? 'agent' : (data.type === 'user_message' ? 'user' : 'system'),
              sender: data.sender,
              senderName: data.sender_name,
              message: data.message,
              timestamp: new Date().toISOString(),
              message_id: data.message_id
            }]);
            break;

          case 'analysis_started':
            setCurrentAnalysisId(data.analysis_id);
            setIsAnalyzing(true);
            setAnalysisComplete(false);
            setAnalysisSaved(false);  // Reset saved state when new analysis starts
            break;

          case 'analysis_complete':
            setIsAnalyzing(false);
            setAnalysisComplete(true);
            setIsAgentThinking(false); // Reset typing indicator
            
            // Set the analysis ID if we don't have one yet
            if (data.analysis_id && !currentAnalysisId) {
              setCurrentAnalysisId(data.analysis_id);
            }
            
            // Check if this is a regenerated analysis
            const isRegenerated = data.result?.version && data.result.version > 1;
            
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'result',
              sender: data.sender || 'technical_agent',
              senderName: data.sender_name || 'Technical Analysis Agent',
              message: isRegenerated 
                ? `Analysis has been updated based on your feedback (Version ${data.result?.version || 1})`
                : 'Analysis completed successfully!',
              timestamp: new Date().toISOString(),
              result: data.result,
              message_id: data.message_id
            }]);
            
            // Notify parent component
            if (onAnalysisComplete && data.result) {
              onAnalysisComplete(data.result);
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
            if (onAnalysisComplete && data.result) {
              onAnalysisComplete(data.result);
            }
            break;

          case 'analysis_status':
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              sender: data.sender || 'technical_agent',
              senderName: data.sender_name || 'Technical Analysis Agent',
              message: data.message || 'Processing...',
              timestamp: new Date().toISOString(),
              message_id: data.message_id
            }]);
            break;

          case 'analysis_saved':
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              message: data.message || 'Analysis saved successfully!',
              timestamp: new Date().toISOString()
            }]);
            
            // Also update parent when analysis is saved
            if (onAnalysisComplete && data.insights) {
              onAnalysisComplete(data.insights);
            }
            setAnalysisSaved(true);  // Update analysisSaved state
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
            break;

          case 'ping':
            // Ignore ping messages
            break;

          default:
            console.log('Unknown message type:', data.type);
        }
      } catch (error) {
        console.error('Error parsing WebSocket message:', error);
      }
    };

    ws.onerror = (error) => {
      // WebSocket error events don't contain much detail in browsers
      console.error('WebSocket error occurred');
      
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
      console.log(`WebSocket disconnected with code: ${event.code}, reason: ${event.reason}`);
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
      const response = await fetch('/api/v1/agents/catalog');
      if (response.ok) {
        const data = await response.json();
        setAgents(data);
      }
    } catch (error) {
      console.error('Failed to fetch agent catalog:', error);
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
      wsRef.current.send(JSON.stringify({
        type: 'chat_message',
        message: userMessage
      }));
      setIsAgentThinking(true); // Show typing indicator
    }

    setInputMessage('');
    setShowAgentSuggestions(false);
  };

  const startAnalysis = (force: boolean = false) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    const message = {
      type: 'start_analysis',
      force: force
    };

    wsRef.current.send(JSON.stringify(message));
    
    setIsAnalyzing(true);
    setAnalysisComplete(false);
    setAnalysisSaved(false);  // Reset analysisSaved state
    setIsAgentThinking(true);  // Show typing indicator
    
    setMessages(prev => [...prev, {
      id: generateMessageId(),
      type: 'system',
      message: 'Starting project analysis...',
      timestamp: new Date().toISOString()
    }]);
  };

  const cancelAnalysis = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN || !currentAnalysisId) {
      return;
    }

    const message = {
      type: 'cancel_analysis',
      analysis_id: currentAnalysisId
    };

    wsRef.current.send(JSON.stringify(message));
    
    setMessages(prev => [...prev, {
      id: generateMessageId(),
      type: 'system',
      message: 'Cancelling analysis...',
      timestamp: new Date().toISOString()
    }]);
  };

  const confirmAndSaveAnalysis = () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN || !currentAnalysisId) {
      return;
    }

    const message = {
      type: 'confirm_analysis',
      analysis_id: currentAnalysisId
    };

    wsRef.current.send(JSON.stringify(message));
    
    setMessages(prev => [...prev, {
      id: generateMessageId(),
      type: 'system',
      message: 'Saving analysis results...',
      timestamp: new Date().toISOString()
    }]);
  };

  // Handle @ mentions in input
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

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-medium text-gray-900">AI Agent Conversation</h3>
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
            {!isAnalyzing && !analysisComplete && (
              <>
                <button
                  onClick={() => startAnalysis(false)}
                  disabled={!isConnected}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Start Analysis
                </button>
              </>
            )}
            {isAnalyzing && (
              <button
                onClick={cancelAnalysis}
                disabled={!isConnected || !currentAnalysisId}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <XMarkIcon className="h-5 w-5" />
                Cancel Analysis
              </button>
            )}
            {analysisComplete && !analysisSaved && (
              <button
                onClick={confirmAndSaveAnalysis}
                disabled={!isConnected || !currentAnalysisId}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <CheckIcon className="h-5 w-5" />
                Save to Insights
              </button>
            )}
            {analysisComplete && analysisSaved && (
              <button
                onClick={() => startAnalysis(true)}
                disabled={!isConnected}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                New Analysis
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
                  : message.type === 'system'
                  ? 'bg-gray-100 text-gray-800'
                  : message.type === 'result'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-gray-200 text-gray-900'
              }`}
            >
              {message.senderName && (
                <div className="font-semibold text-sm mb-1">
                  {message.senderName}
                </div>
              )}
              <div className="whitespace-pre-wrap flex items-center gap-2">
                {message.message}
                {message.isLoading && (
                  <span className="inline-block animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500"></span>
                )}
              </div>
              {message.result && (
                <div className="mt-2 pt-2 border-t border-gray-300">
                  <div className="text-sm font-semibold mb-1">Analysis Results:</div>
                  <pre className="text-xs overflow-x-auto bg-white bg-opacity-50 p-2 rounded">
                    {typeof message.result.technical_analysis === 'string' 
                      ? message.result.technical_analysis 
                      : JSON.stringify(message.result, null, 2)}
                  </pre>
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
          {analysisComplete && !analysisSaved && (
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
                currentAnalysisId 
                  ? "Ask a question about the analysis or type '@' to mention an agent..." 
                  : "Type a message or '@' to mention an agent..."
              }
              className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={!isConnected || isAgentThinking}
            />
            <button
              type="submit"
              disabled={!isConnected || !inputMessage.trim() || isAgentThinking}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <PaperAirplaneIcon className="h-5 w-5" />
              Send
            </button>
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
