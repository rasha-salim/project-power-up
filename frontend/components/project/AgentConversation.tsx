import { useState, useEffect, useRef } from 'react';
import { PaperAirplaneIcon, XMarkIcon, CheckIcon } from '@heroicons/react/24/outline';

interface Message {
  id: string;
  type: 'user' | 'agent' | 'system' | 'error' | 'result';
  sender?: string;
  senderName?: string;
  message: string;
  timestamp: string;
  result?: any;
  message_id?: string; // Server-generated unique ID
}

interface AgentConversationProps {
  projectId: string;
  onStartAnalysis: () => void;
}

export default function AgentConversation({ projectId, onStartAnalysis }: AgentConversationProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentAnalysisId, setCurrentAnalysisId] = useState<string | null>(null);
  const [analysisComplete, setAnalysisComplete] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  // Track processed message IDs to prevent duplicates
  const processedMessageIds = useRef<Set<string>>(new Set());
  const messageCounter = useRef(0);

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
      setMessages(prev => [...prev, {
        id: generateMessageId(),
        type: 'system',
        message: 'Connected to AI agent',
        timestamp: new Date().toISOString()
      }]);
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
            break;

          case 'analysis_complete':
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'result',
              sender: 'system',
              senderName: 'System',
              message: data.message || 'Analysis completed successfully!',
              timestamp: new Date().toISOString(),
              result: data.result,
              message_id: data.message_id
            }]);
            setIsAnalyzing(false);
            setAnalysisComplete(true);
            break;

          case 'analysis_status':
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              message: data.message || 'Processing...',
              timestamp: new Date().toISOString(),
              message_id: data.message_id
            }]);
            break;

          case 'analysis_saved':
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              sender: 'system',
              senderName: 'System',
              message: data.message || 'Analysis saved to insights!',
              timestamp: new Date().toISOString(),
              message_id: data.message_id
            }]);
            setCurrentAnalysisId(null);
            setAnalysisComplete(false);
            onStartAnalysis(); // Update parent component
            break;

          case 'analysis_cancelled':
            setCurrentAnalysisId(null);
            setIsAnalyzing(false);
            setAnalysisComplete(false);
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'system',
              message: data.message || 'Analysis was cancelled',
              timestamp: new Date().toISOString(),
              message_id: data.message_id
            }]);
            break;

          case 'error':
            setMessages(prev => [...prev, {
              id: generateMessageId(),
              type: 'error',
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
      setMessages(prev => [...prev, {
        id: generateMessageId(),
        type: 'error',
        message: 'Connection error occurred',
        timestamp: new Date().toISOString()
      }]);
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
      
      setMessages(prev => [...prev, {
        id: generateMessageId(),
        type: 'system',
        message: 'Disconnected from server',
        timestamp: new Date().toISOString()
      }]);
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

  const sendMessage = () => {
    if (!inputMessage.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      // Try to reconnect if websocket is not open
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        connectWebSocket();
        // Retry sending after a short delay
        setTimeout(() => {
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && inputMessage.trim()) {
            sendMessage();
          }
        }, 1000);
      }
      return;
    }

    const userMessage: Message = {
      id: generateMessageId(),
      type: 'user',
      message: inputMessage,
      timestamp: new Date().toISOString()
    };

    setMessages(prev => [...prev, userMessage]);

    // Send message to WebSocket
    if (currentAnalysisId) {
      // If we have an active analysis, send as user_question
      wsRef.current.send(JSON.stringify({
        type: 'user_question',
        analysis_id: currentAnalysisId,
        question: inputMessage
      }));
    } else {
      // Otherwise, send as general chat message
      wsRef.current.send(JSON.stringify({
        type: 'chat_message',
        message: inputMessage
      }));
    }

    setInputMessage('');
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
            {!isAnalyzing && !analysisComplete && (
              <>
                <button
                  onClick={() => startAnalysis(false)}
                  disabled={!isConnected}
                  className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Start Analysis
                </button>
                <button
                  onClick={() => startAnalysis(true)}
                  disabled={!isConnected}
                  className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Force New Analysis
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
            {analysisComplete && (
              <button
                onClick={confirmAndSaveAnalysis}
                disabled={!isConnected || !currentAnalysisId}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                <CheckIcon className="h-5 w-5" />
                Save to Insights
              </button>
            )}
          </div>
        </div>
      </div>

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
              <div className="whitespace-pre-wrap">{message.message}</div>
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
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="bg-white border-t px-6 py-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            disabled={!isConnected || (isAnalyzing && !analysisComplete)}
            placeholder={
              !isConnected ? "Connecting..." : 
              isAnalyzing && !analysisComplete ? "Analysis in progress..." :
              analysisComplete ? "Ask questions about the analysis..." :
              "Type a message..."
            }
            className="flex-1 px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <button
            onClick={sendMessage}
            disabled={!isConnected || !inputMessage.trim() || (isAnalyzing && !analysisComplete)}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <PaperAirplaneIcon className="h-5 w-5" />
          </button>
        </div>
        {analysisComplete && (
          <p className="text-sm text-gray-600 mt-2">
            Ask questions about the analysis or click "Save to Insights" when you're ready.
          </p>
        )}
      </div>
    </div>
  );
}
