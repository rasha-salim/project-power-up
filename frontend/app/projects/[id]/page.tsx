'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import ProjectHeader from '@/components/project/ProjectHeader';
import DocumentManager from '@/components/project/DocumentManager';
import AgentConversation from '@/components/project/AgentConversation';
import ProjectInsights from '@/components/project/ProjectInsights';

// Types
interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
}

interface Document {
  id: string;
  filename: string;
  status: string;
  created_at: string;
  description?: string;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;
  
  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAnalysisRunning, setIsAnalysisRunning] = useState(false);
  const [activeTab, setActiveTab] = useState('conversation');

  // Fetch project data
  useEffect(() => {
    const fetchProjectData = async () => {
      try {
        // In a real implementation, this would fetch from the API
        // const response = await fetch(`/api/v1/projects/${projectId}`);
        // const data = await response.json();
        
        // For now, use mock data
        const mockProject = {
          id: projectId,
          name: 'E-Commerce Platform Redesign',
          description: 'Redesign the company\'s e-commerce platform with improved UX and mobile responsiveness.',
          status: 'draft',
          created_at: '2025-05-01T10:00:00Z',
          updated_at: '2025-05-20T15:30:00Z',
        };
        
        const mockDocuments = [
          {
            id: '1',
            filename: 'requirements.pdf',
            status: 'processed',
            created_at: '2025-05-01T10:30:00Z',
            description: 'Initial project requirements document'
          },
          {
            id: '2',
            filename: 'meeting_notes.docx',
            status: 'processed',
            created_at: '2025-05-05T14:20:00Z',
            description: 'Notes from kickoff meeting'
          },
          {
            id: '3',
            filename: 'technical_specs.pdf',
            status: 'processing',
            created_at: '2025-05-18T09:45:00Z',
          },
        ];
        
        setProject(mockProject);
        setDocuments(mockDocuments);
        setLoading(false);
      } catch (err) {
        console.error('Error fetching project data:', err);
        setError('Failed to load project data. Please try again later.');
        setLoading(false);
      }
    };

    fetchProjectData();
  }, [projectId]);

  // Handle starting analysis
  const handleStartAnalysis = () => {
    setIsAnalysisRunning(true);
    
    // In a real implementation, this would call the API to start the analysis
    // For now, just update the project status after a delay
    setTimeout(() => {
      setProject(prev => prev ? { ...prev, status: 'analyzing' } : null);
      
      // Simulate analysis completion after some time
      setTimeout(() => {
        setProject(prev => prev ? { ...prev, status: 'completed' } : null);
        setIsAnalysisRunning(false);
      }, 15000);
    }, 2000);
  };

  // Handle document upload
  const handleDocumentUpload = (files: File[]) => {
    // In a real implementation, this would call the API to upload the files
    // For now, just add them to the documents list
    const newDocuments = files.map((file, index) => ({
      id: `new-${Date.now()}-${index}`,
      filename: file.name,
      status: 'processing',
      created_at: new Date().toISOString(),
    }));
    
    setDocuments(prev => [...prev, ...newDocuments]);
    
    // Simulate processing completion after some time
    setTimeout(() => {
      setDocuments(prev => 
        prev.map(doc => 
          doc.id.startsWith('new-') 
            ? { ...doc, status: 'processed' } 
            : doc
        )
      );
    }, 3000);
  };

  // Handle document delete
  const handleDocumentDelete = (documentId: string) => {
    // In a real implementation, this would call the API to delete the document
    // For now, just remove it from the documents list
    setDocuments(prev => prev.filter(doc => doc.id !== documentId));
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <svg className="animate-spin h-10 w-10 text-primary-600 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <p className="text-gray-500">Loading project...</p>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md p-6 bg-white rounded-lg shadow">
          <svg className="h-12 w-12 text-red-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          <h3 className="text-lg font-medium text-gray-900 mb-2">Error Loading Project</h3>
          <p className="text-gray-500 mb-6">{error || 'Project not found'}</p>
          <Link href="/projects" className="btn btn-primary">
            Return to Projects
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Project header */}
      <ProjectHeader 
        project={project} 
        onStartAnalysis={handleStartAnalysis} 
      />

      {/* Main content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex">
              <button
                onClick={() => setActiveTab('conversation')}
                className={`py-4 px-6 text-sm font-medium ${
                  activeTab === 'conversation'
                    ? 'border-b-2 border-primary-500 text-primary-600'
                    : 'text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Agent Conversation
              </button>
              <button
                onClick={() => setActiveTab('insights')}
                className={`py-4 px-6 text-sm font-medium ${
                  activeTab === 'insights'
                    ? 'border-b-2 border-primary-500 text-primary-600'
                    : 'text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Project Insights
              </button>
            </nav>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column - Document Manager */}
          <div className="lg:col-span-1">
            <DocumentManager 
              projectId={projectId}
              documents={documents}
              onDocumentUpload={handleDocumentUpload}
              onDocumentDelete={handleDocumentDelete}
            />
          </div>

          {/* Right column - Agent Conversation or Insights */}
          <div className="lg:col-span-2">
            {activeTab === 'conversation' ? (
              <AgentConversation 
                projectId={projectId}
                isAnalysisRunning={isAnalysisRunning}
                onStartAnalysis={handleStartAnalysis}
              />
            ) : (
              <ProjectInsights 
                projectId={projectId}
                projectStatus={project.status}
              />
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
