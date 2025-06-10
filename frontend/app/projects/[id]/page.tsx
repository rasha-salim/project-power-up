'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import ProjectHeader from '@/components/project/ProjectHeader';
import DocumentManager from '@/components/project/DocumentManager';
import AgentConversation from '@/components/project/AgentConversation';
import ProjectInsights from '@/components/project/ProjectInsights';
import { API_ENDPOINTS } from '@/app/api/config';

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
  progress?: string;
  created_at: string;
  description?: string;
}

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params?.id as string;
  
  if (!projectId) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md p-6 bg-white rounded-lg shadow">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Invalid Project ID</h3>
          <p className="text-gray-500 mb-6">No project ID was provided.</p>
          <Link href="/projects" className="btn btn-primary">
            Return to Projects
          </Link>
        </div>
      </div>
    );
  }
  
  const [project, setProject] = useState<Project | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAnalysisRunning, setIsAnalysisRunning] = useState(false);
  const [activeTab, setActiveTab] = useState('conversation');

  // Handle document updates from DocumentManager
  const handleDocumentUpdate = (documentId: string, updates: Partial<Document>) => {
    console.log(`Updating document ${documentId} with:`, updates);
    setDocuments(prevDocs => 
      prevDocs.map(doc => 
        doc.id === documentId ? { ...doc, ...updates } : doc
      )
    );
  };

  // Fetch documents function
  const fetchDocuments = async () => {
    if (!projectId) return;
    
    try {
      console.log(`Fetching documents for project: ${projectId}`);
      const url = API_ENDPOINTS.DOCUMENTS.PROJECT(projectId);
      console.log(`Using URL: ${url}`);
      
      const documentsResponse = await fetch(url);
      console.log(`Documents response status: ${documentsResponse.status}`);
      
      if (!documentsResponse.ok) {
        let errorMessage = `Error fetching documents: ${documentsResponse.status}`;
        try {
          const errorData = await documentsResponse.json();
          errorMessage = `${errorMessage} - ${errorData.detail || errorData.message || 'Unknown error'}`;
        } catch (parseError) {
          // If we can't parse the error response, just use the status code
        }
        console.error(errorMessage);
        setError(errorMessage);
        return;
      }
      
      const data = await documentsResponse.json();
      // Ensure data is an array
      const documentsData = Array.isArray(data) ? data : [];
      console.log('Documents loaded:', documentsData.length);
      console.log('Document data sample:', documentsData.length > 0 ? documentsData[0] : 'No documents');
      
      // Update documents state, preserving temp documents that aren't in the response
      setDocuments(prev => {
        const tempDocs = prev.filter(doc => doc.id.startsWith('temp-'));
        const serverDocs = documentsData.filter(doc => 
          !tempDocs.some(tempDoc => tempDoc.filename === doc.filename)
        );
        return [...serverDocs, ...tempDocs];
      });
    } catch (error) {
      console.error('Error fetching documents:', error);
    }
  };
  
  // Poll for document status updates
  useEffect(() => {
    // Check if there are any documents in processing state
    const hasProcessingDocuments = documents.some(doc => doc.status === 'processing');
    
    // If there are processing documents, set up polling
    if (hasProcessingDocuments) {
      const pollInterval = setInterval(() => {
        fetchDocuments();
      }, 5000); // Poll every 5 seconds
      
      return () => clearInterval(pollInterval);
    }
  }, [documents]);
  
  // Fetch project data
  useEffect(() => {
    const fetchProjectData = async () => {
      try {
        // Fetch project from the API
        const projectResponse = await fetch(`/api/v1/projects/${projectId}`);
        
        if (!projectResponse.ok) {
          const errorData = await projectResponse.json();
          throw new Error(errorData.detail || 'Failed to load project');
        }
        
        const projectData = await projectResponse.json();
        
        // Fetch documents for this project
        let documentsData = [];
        try {
          const documentsResponse = await fetch(API_ENDPOINTS.DOCUMENTS.PROJECT(projectId));
          
          if (!documentsResponse.ok) {
            console.error(`Error fetching documents: ${documentsResponse.status}`);
          } else {
            try {
              const data = await documentsResponse.json();
              // Ensure data is an array
              documentsData = Array.isArray(data) ? data : [];
              console.log('Documents loaded:', documentsData.length);
            } catch (parseErr) {
              console.error('Error parsing documents response:', parseErr);
            }
          }
        } catch (fetchErr) {
          console.error('Network error fetching documents:', fetchErr);
        }
        
        setProject(projectData);
        setDocuments(documentsData);
        setLoading(false);
        
        // If the project is in analyzing status, set the analysis running flag
        if (projectData.status === 'analyzing') {
          setIsAnalysisRunning(true);
        }
      } catch (err: any) {
        console.error('Error fetching project data:', err);
        setError(err.message || 'Failed to load project data. Please try again later.');
        setLoading(false);
      }
    };

    fetchProjectData();
  }, [projectId]);

  // Handle starting analysis
  const handleStartAnalysis = async () => {
    try {
      setIsAnalysisRunning(true);
      
      // Call the API to start the analysis
      const response = await fetch(`/api/v1/projects/${projectId}/analyze`, {
        method: 'POST',
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start analysis');
      }
      
      const data = await response.json();
      
      // Update the project status to analyzing
      setProject(prev => prev ? { ...prev, status: 'analyzing' } : null);
      
      // Set up polling to check analysis status
      const checkAnalysisStatus = async () => {
        try {
          const statusResponse = await fetch(`/api/v1/projects/${projectId}/insights`);
          
          if (!statusResponse.ok) {
            console.error('Error checking analysis status, will retry');
            return false;
          }
          
          const statusData = await statusResponse.json();
          
          // If analysis is complete, update the project
          if (statusData.status === 'completed') {
            setProject(prev => prev ? { 
              ...prev, 
              status: 'completed',
              insights: statusData.insights 
            } : null);
            setIsAnalysisRunning(false);
            return true;
          }
          
          return false;
        } catch (err) {
          console.error('Error checking analysis status:', err);
          return false;
        }
      };
      
      // Poll every 5 seconds for up to 5 minutes
      const maxAttempts = 60; // 5 minutes at 5-second intervals
      let attempts = 0;
      
      const pollInterval = setInterval(async () => {
        attempts++;
        const isComplete = await checkAnalysisStatus();
        
        if (isComplete || attempts >= maxAttempts) {
          clearInterval(pollInterval);
          if (!isComplete && attempts >= maxAttempts) {
            // If we've reached max attempts and it's still not complete,
            // we'll stop polling but leave the status as analyzing
            console.log('Analysis is taking longer than expected, stopped polling');
          }
        }
      }, 5000);
      
    } catch (err) {
      console.error('Error starting analysis:', err);
      setIsAnalysisRunning(false);
      // Show error to user
      alert(`Failed to start analysis: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  // Handle document upload
  const handleDocumentUpload = async (files: File[]) => {
    try {
      // Process each file individually to avoid issues with the backend
      for (const file of files) {
        // Create FormData for file upload
        const formData = new FormData();
        
        // Add project ID to FormData
        formData.append('project_id', projectId);
        
        // Add description if needed
        formData.append('description', `Uploaded for project ${projectId}`);
        
        // Add file to FormData - IMPORTANT: The key must be 'file' to match the backend
        formData.append('file', file);
        
        // Show processing state for new file
        const tempDocument = {
          id: `temp-${Date.now()}`,
          filename: file.name,
          status: 'processing',
          progress: '0',
          created_at: new Date().toISOString(),
        };
        
        setDocuments(prev => [...prev, tempDocument]);
        
        console.log(`Uploading file: ${file.name} for project: ${projectId}`);
        console.log('FormData contents:');
        // Log FormData contents without iterating through entries
        console.log(`project_id: ${projectId}`);
        console.log(`description: Uploaded for project ${projectId}`);
        console.log(`file: ${file.name}`);
        
        // Use the API configuration instead of hardcoded URL
        const uploadUrl = API_ENDPOINTS.DOCUMENTS.UPLOAD;
        console.log(`Uploading to: ${uploadUrl}`);
        
        // Upload file to the API
        console.log('Using fetch API to upload document');
        const response = await fetch(uploadUrl, {
          method: 'POST',
          body: formData,
          // Don't set Content-Type header for multipart/form-data
          // The browser will set it automatically with the boundary
        });
        
        // Log detailed information about the request
        console.log('Upload request completed');
        console.log('Response status:', response.status);
        console.log('Response status text:', response.statusText);
        
        console.log(`Upload response status: ${response.status}`);
        console.log(`Response headers:`, response.headers);
        
        // Get the response text first to debug
        const responseText = await response.text();
        console.log(`Response text: ${responseText}`);
        
        if (!response.ok) {
          let errorDetail = `Failed to upload document (Status: ${response.status})`;
          try {
            // Try to parse the response text as JSON
            if (responseText) {
              const errorData = JSON.parse(responseText);
              if (typeof errorData.detail === 'object') {
                // Handle structured error response
                errorDetail = errorData.detail.message || errorData.detail.error || errorDetail;
                console.error('Structured error details:', errorData.detail);
              } else {
                errorDetail = errorData.detail || errorDetail;
              }
            }
          } catch (e) {
            console.error('Error parsing error response:', e);
            // If we can't parse as JSON, use the response text directly
            if (responseText) {
              errorDetail += ` - ${responseText}`;
            }
          }
          console.error('Upload error details:', errorDetail);
          throw new Error(errorDetail);
        }
        
        // Parse the response text as JSON
        try {
          console.log('Attempting to parse response text:', responseText);
          const uploadedDocument = JSON.parse(responseText);
          console.log('Successfully parsed document:', uploadedDocument);
          
          // Add progress field if not present
          if (!uploadedDocument.progress) {
            uploadedDocument.progress = '0';
          }
          
          // Replace the temp document with the actual one
          setDocuments(prev => prev.map(doc => 
            doc.id === tempDocument.id ? uploadedDocument : doc
          ));
          
          // Start polling for document status updates
          fetchDocuments();
          
        } catch (e) {
          console.error('Error parsing success response:', e);
          // Handle the TypeScript error by checking if e is an Error object
          const errorMessage = e instanceof Error ? e.message : 'Unknown error';
          throw new Error(`Failed to parse server response: ${errorMessage}`);
        }
      }
    } catch (err) {
      console.error('Error uploading documents:', err);
      // Show error to user
      alert(`Failed to upload documents: ${err instanceof Error ? err.message : 'Unknown error'}`);
      
      // Remove temp documents on error
      setDocuments(prev => prev.filter(doc => !doc.id.startsWith('temp-')));
    }
  };

  // Handle document delete
  const handleDocumentDelete = async (documentId: string) => {
    try {
      // Call the API to delete the document
      const response = await fetch(`/api/v1/documents/${documentId}`, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to delete document');
      }
      
      // Remove the document from the list
      setDocuments(prev => prev.filter(doc => doc.id !== documentId));
    } catch (err) {
      console.error('Error deleting document:', err);
      // Show error to user
      alert(`Failed to delete document: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
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
              onDocumentUpdate={handleDocumentUpdate}
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
