import { useState, useEffect, useRef } from 'react';
import { PaperAirplaneIcon, MicrophoneIcon, ArrowPathIcon } from '@heroicons/react/24/outline';

interface Message {
  id: string;
  type: 'user_message' | 'agent_message' | 'system_message';
  sender: string;
  sender_name?: string;
  message: string;
  timestamp: string;
}

interface AgentConversationProps {
  projectId: string;
  isAnalysisRunning: boolean;
  onStartAnalysis: () => void;
}

export default function AgentConversation({ 
  projectId, 
  isAnalysisRunning,
  onStartAnalysis 
}: AgentConversationProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Connect to WebSocket
  useEffect(() => {
    // In a real implementation, this would connect to the WebSocket server
    // For now, we'll simulate the connection
    
    const connectWebSocket = () => {
      setIsConnecting(true);
      
      // Simulate connection delay
      setTimeout(() => {
        setIsConnected(true);
        setIsConnecting(false);
        
        // Add welcome message
        setMessages([
          {
            id: '1',
            type: 'system_message',
            sender: 'system',
            message: 'Welcome to the Agent Conversation. You can ask questions or start an analysis to see the AI agents in action.',
            timestamp: new Date().toISOString()
          }
        ]);
      }, 1500);
      
      return {
        close: () => {
          setIsConnected(false);
        }
      };
    };
    
    wsRef.current = connectWebSocket() as any;
    
    return () => {
      wsRef.current?.close();
    };
  }, [projectId]);

  // Handle sending a message
  const handleSendMessage = () => {
    if (!newMessage.trim() || !isConnected) return;
    
    // Create new message
    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user_message',
      sender: 'user',
      message: newMessage,
      timestamp: new Date().toISOString()
    };
    
    // Add to messages
    setMessages((prev) => [...prev, userMessage]);
    
    // Clear input
    setNewMessage('');
    
    // In a real implementation, this would send the message to the WebSocket server
    // For now, we'll simulate the agent responses
    simulateAgentResponses(newMessage);
  };

  // Simulate agent responses
  const simulateAgentResponses = (userMessage: string) => {
    // Technical Agent response
    setTimeout(() => {
      const technicalResponse: Message = {
        id: Date.now().toString(),
        type: 'agent_message',
        sender: 'technical_agent',
        sender_name: 'Technical Analysis Agent',
        message: `I've analyzed the technical aspects of your question: "${userMessage}". Based on my analysis, I recommend considering a microservices architecture with the following components...`,
        timestamp: new Date().toISOString()
      };
      
      setMessages((prev) => [...prev, technicalResponse]);
    }, 1500);
    
    // Risk Agent response
    setTimeout(() => {
      const riskResponse: Message = {
        id: Date.now().toString(),
        type: 'agent_message',
        sender: 'risk_agent',
        sender_name: 'Risk Assessment Agent',
        message: `After reviewing the technical recommendations, I've identified several potential risk factors that should be considered. The main concerns are: 1) Integration complexity, 2) Scalability challenges, 3) Security considerations...`,
        timestamp: new Date().toISOString()
      };
      
      setMessages((prev) => [...prev, riskResponse]);
    }, 3500);
    
    // Planning Agent response
    setTimeout(() => {
      const planningResponse: Message = {
        id: Date.now().toString(),
        type: 'agent_message',
        sender: 'planning_agent',
        sender_name: 'Project Planning Agent',
        message: `Taking into account both the technical architecture and risk assessment, I've developed an initial project plan. The timeline would be approximately 12 weeks, with key milestones at weeks 4, 8, and 12. Resource requirements include...`,
        timestamp: new Date().toISOString()
      };
      
      setMessages((prev) => [...prev, planningResponse]);
    }, 6000);
  };

  // Simulate full analysis
  const simulateFullAnalysis = () => {
    // System message
    setMessages((prev) => [
      ...prev, 
      {
        id: Date.now().toString(),
        type: 'system_message',
        sender: 'system',
        message: 'Starting comprehensive project analysis...',
        timestamp: new Date().toISOString()
      }
    ]);
    
    // Technical Agent response
    setTimeout(() => {
      const technicalResponse: Message = {
        id: Date.now().toString(),
        type: 'agent_message',
        sender: 'technical_agent',
        sender_name: 'Technical Analysis Agent',
        message: `I've analyzed the project documents and identified the key technical requirements. Based on my analysis, I recommend a cloud-based architecture with the following components:
        
1. Frontend: React with Next.js for server-side rendering
2. Backend: Node.js microservices with Express
3. Database: PostgreSQL for structured data, MongoDB for unstructured data
4. Authentication: OAuth 2.0 with JWT tokens
5. Deployment: Docker containers orchestrated with Kubernetes

This architecture provides scalability, maintainability, and aligns with modern development practices.`,
        timestamp: new Date().toISOString()
      };
      
      setMessages((prev) => [...prev, technicalResponse]);
    }, 2000);
    
    // Risk Agent response
    setTimeout(() => {
      const riskResponse: Message = {
        id: Date.now().toString(),
        type: 'agent_message',
        sender: 'risk_agent',
        sender_name: 'Risk Assessment Agent',
        message: `Based on the technical architecture and project requirements, I've identified several key risks:

1. Integration Risk: The microservices architecture introduces complexity in service communication
   - Mitigation: Implement comprehensive API documentation and service contracts

2. Scalability Risk: High user load during peak periods may affect performance
   - Mitigation: Implement auto-scaling and load testing before launch

3. Security Risk: Multiple services increase the attack surface
   - Mitigation: Regular security audits and implementing zero-trust architecture

4. Timeline Risk: The proposed architecture may require specialized skills
   - Mitigation: Early hiring or training for key technical roles

The overall risk profile is moderate, but manageable with proper planning and monitoring.`,
        timestamp: new Date().toISOString()
      };
      
      setMessages((prev) => [...prev, riskResponse]);
    }, 5000);
    
    // Planning Agent response
    setTimeout(() => {
      const planningResponse: Message = {
        id: Date.now().toString(),
        type: 'agent_message',
        sender: 'planning_agent',
        sender_name: 'Project Planning Agent',
        message: `Taking into account both the technical architecture and risk assessment, I've developed a comprehensive project plan:

Timeline: 16 weeks total development time

Key Milestones:
1. Week 4: Architecture design complete, development environment set up
2. Week 8: Core functionality implemented, integration testing begins
3. Week 12: Feature complete, system testing and optimization
4. Week 16: Production deployment and handover

Resource Requirements:
- 2 Frontend Developers (React, Next.js)
- 3 Backend Developers (Node.js, microservices)
- 1 DevOps Engineer (Docker, Kubernetes)
- 1 QA Engineer
- 1 Project Manager

Critical Path Items:
- Database schema design (Weeks 1-2)
- API development (Weeks 3-8)
- Integration testing (Weeks 8-12)

This plan accounts for the identified risks and includes buffer time for addressing unexpected challenges.`,
        timestamp: new Date().toISOString()
      };
      
      setMessages((prev) => [...prev, planningResponse]);
    }, 9000);
    
    // System message - completion
    setTimeout(() => {
      setMessages((prev) => [
        ...prev, 
        {
          id: Date.now().toString(),
          type: 'system_message',
          sender: 'system',
          message: 'Analysis complete. You can view the detailed results in the Project Insights dashboard.',
          timestamp: new Date().toISOString()
        }
      ]);
      
      // Notify parent that analysis is complete
      // In a real implementation, this would be triggered by the WebSocket
    }, 11000);
  };

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden flex flex-col h-[600px]">
      <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">Agent Conversation</h3>
      </div>
      
      {/* Connection status */}
      {!isConnected && (
        <div className="flex-1 flex items-center justify-center p-6 bg-gray-50">
          {isConnecting ? (
            <div className="text-center">
              <svg className="animate-spin h-8 w-8 text-primary-600 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              <p className="text-gray-600">Connecting to agents...</p>
            </div>
          ) : (
            <div className="text-center">
              <div className="bg-red-100 text-red-700 p-3 rounded-lg mb-4">
                <p>Connection to agents lost</p>
              </div>
              <button 
                onClick={() => {
                  setIsConnecting(true);
                  setTimeout(() => {
                    setIsConnected(true);
                    setIsConnecting(false);
                  }, 1500);
                }} 
                className="btn btn-primary"
              >
                <ArrowPathIcon className="w-4 h-4 mr-1" />
                Reconnect
              </button>
            </div>
          )}
        </div>
      )}
      
      {/* Messages */}
      {isConnected && (
        <>
          <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
            {messages.map((message) => (
              <div key={message.id} className="mb-4">
                {message.type === 'user_message' && (
                  <div className="user-message">
                    <div className="flex items-center mb-1">
                      <span className="font-medium text-gray-900">You</span>
                      <span className="text-xs text-gray-500 ml-2">
                        {new Date(message.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <p>{message.message}</p>
                  </div>
                )}
                
                {message.type === 'agent_message' && (
                  <div className={`agent-message ${
                    message.sender === 'technical_agent' 
                      ? 'agent-message-technical' 
                      : message.sender === 'risk_agent'
                        ? 'agent-message-risk'
                        : 'agent-message-planning'
                  }`}>
                    <div className="flex items-center mb-1">
                      <span className="font-medium text-gray-900">{message.sender_name}</span>
                      <span className="text-xs text-gray-500 ml-2">
                        {new Date(message.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div className="whitespace-pre-line">{message.message}</div>
                  </div>
                )}
                
                {message.type === 'system_message' && (
                  <div className="bg-gray-100 p-3 rounded-lg text-sm text-gray-600 text-center">
                    {message.message}
                  </div>
                )}
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
          
          {/* Input area */}
          <div className="p-4 border-t border-gray-200">
            {isAnalysisRunning ? (
              <div className="bg-blue-50 p-3 rounded-lg text-blue-700 text-center">
                <div className="flex items-center justify-center mb-2">
                  <svg className="animate-spin h-5 w-5 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Analysis in progress...</span>
                </div>
                <p className="text-sm">Agents are analyzing your project. Please wait.</p>
              </div>
            ) : messages.length === 0 || (messages.length === 1 && messages[0].type === 'system_message') ? (
              <div className="text-center">
                <p className="text-gray-600 mb-4">Start a conversation with the AI agents or run a full project analysis</p>
                <button 
                  onClick={() => {
                    onStartAnalysis();
                    simulateFullAnalysis();
                  }} 
                  className="btn btn-primary w-full"
                >
                  Start Project Analysis
                </button>
              </div>
            ) : (
              <div className="flex items-center">
                <input
                  type="text"
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                  placeholder="Ask a question or provide additional information..."
                  className="input flex-1 mr-2"
                />
                <button 
                  onClick={handleSendMessage}
                  disabled={!newMessage.trim()}
                  className="btn btn-primary p-2"
                  aria-label="Send message"
                >
                  <PaperAirplaneIcon className="w-5 h-5" />
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
