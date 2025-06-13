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
}

interface AgentConversationProps {
  projectId: string;
  onStartAnalysis: () => void;
}

export default function AgentConversation({ projectId, onStartAnalysis }: AgentConversationProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [currentAnalysisId, setCurrentAnalysisId] = useState<string | null>(null);
  const [analysisComplete, setAnalysisComplete] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const connectWebSocket = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.hostname}:8000/api/v1/ws/agent-conversation/${projectId}`;
    
    console.log('Connecting to WebSocket:', wsUrl);
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('WebSocket connected');
      setIsConnected(true);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        type: 'system',
        message: 'Connected to AI agent',
        timestamp: new Date().toISOString()
      }]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received message:', data);
        
        switch (data.type) {
          case 'user_message':
          case 'agent_message':
          case 'system_message':
            setMessages(prev => [...prev, {
              id: Date.now().toString(),
              type: data.type === 'agent_message' ? 'agent' : (data.type === 'user_message' ? 'user' : 'system'),
              sender: data.sender,
              senderName: data.sender_name,
              message: data.message,
              timestamp: new Date().toISOString()
            }]);
            break;

          case 'analysis_started':
            setCurrentAnalysisId(data.analysis_id);
            setIsAnalyzing(true);
            setAnalysisComplete(false);
            break;

          case 'analysis_complete':
            setMessages(prev => [...prev, {
              id: Date.now().toString(),
              type: 'result',
              sender: 'system',
              senderName: 'System',
              message: data.message || 'Analysis completed successfully!',
              timestamp: new Date().toISOString(),
              result: data.result
            }]);
            setIsAnalyzing(false);
            setAnalysisComplete(true);
            break;

          case 'analysis_saved':
            setMessages(prev => [...prev, {
              id: Date.now().toString(),
              type: 'system',
              sender: 'system',
              senderName: 'System',
              message: data.message || 'Analysis saved to insights!',
              timestamp: new Date().toISOString()
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
              id: Date.now().toString(),
              type: 'system',
              message: data.message || 'Analysis was cancelled',
              timestamp: new Date().toISOString()
            }]);
            break;

          case 'error':
            setMessages(prev => [...prev, {
              id: Date.now().toString(),
              type: 'error',
              message: data.message || 'An error occurred',
              timestamp: new Date().toISOString()
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
      console.error('WebSocket error:', error);
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        type: 'error',
        message: 'Connection error occurred',
        timestamp: new Date().toISOString()
      }]);
    };

    ws.onclose = () => {
      console.log('WebSocket disconnected');
      setIsConnected(false);
      wsRef.current = null;
      
      // Attempt to reconnect after 3 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('Attempting to reconnect...');
        connectWebSocket();
      }, 3000);
    };

    wsRef.current = ws;
  };

  useEffect(() => {
    connectWebSocket();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [projectId]);

  const sendMessage = () => {
    if (!input.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    // If analysis is complete, treat this as a question about the analysis
    if (analysisComplete && currentAnalysisId) {
      const message = {
        type: 'user_question',
        analysis_id: currentAnalysisId,
        question: input.trim()
      };

      wsRef.current.send(JSON.stringify(message));
      
      // Add user message to UI
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        type: 'user',
        message: input.trim(),
        timestamp: new Date().toISOString()
      }]);
    } else {
      // Regular message (not during analysis)
      const message = {
        type: 'user_message',
        message: input.trim()
      };

      wsRef.current.send(JSON.stringify(message));
    }

    setInput('');
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
            value={input}
            onChange={(e) => setInput(e.target.value)}
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
            disabled={!isConnected || !input.trim() || (isAnalyzing && !analysisComplete)}
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
