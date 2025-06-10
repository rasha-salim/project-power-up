import { useState, useCallback, useEffect } from 'react';
import { useDropzone } from 'react-dropzone';
import { DocumentTextIcon, ArrowUpTrayIcon, XMarkIcon, CheckIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

interface Document {
  id: string;
  filename: string;
  status: string;
  progress?: string;
  created_at: string;
  description?: string;
}

interface DocumentManagerProps {
  projectId: string;
  documents: Document[];
  onDocumentUpload: (files: File[]) => void;
  onDocumentDelete: (documentId: string) => void;
  onDocumentUpdate?: (documentId: string, updates: Partial<Document>) => void;
}

export default function DocumentManager({ 
  projectId, 
  documents, 
  onDocumentUpload, 
  onDocumentDelete,
  onDocumentUpdate = () => {} // Default no-op function
}: DocumentManagerProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [showUploadArea, setShowUploadArea] = useState(false);
  const [processingDocuments, setProcessingDocuments] = useState<string[]>([]);
  const [notifications, setNotifications] = useState<{id: string, message: string, type: string}[]>([]);

  // Effect to check for processing documents and poll their status
  useEffect(() => {
    // Find documents that are in processing state
    const docsInProcessing = documents.filter(doc => doc.status === 'processing');
    
    // Update the processing documents list
    setProcessingDocuments(docsInProcessing.map(doc => doc.id));
    
    // If there are documents in processing state, set up polling
    if (docsInProcessing.length > 0) {
      console.log(`Setting up polling for ${docsInProcessing.length} processing documents`);
      const pollInterval = setInterval(async () => {
        // For each processing document, check its status
        for (const doc of docsInProcessing) {
          try {
            console.log(`Polling document status for ${doc.id}`);
            // Use the dedicated status endpoint with the correct route structure
            const statusUrl = `/api/v1/documents/status/${doc.id}`;  // This routes through Next.js API route
            console.log(`Status URL: ${statusUrl}`);
            
            const response = await fetch(statusUrl);
            // If we get a 404, try direct backend call
            if (response.status === 404) {
              console.log(`Trying direct backend call for ${doc.id} due to 404 from Next.js API route`);
              try {
                // Try direct backend call to both possible endpoints
                const backendResponse = await fetch(`http://localhost:8000/api/v1/documents/status/${doc.id}`);
                if (backendResponse.ok) {
                  const updatedDoc = await backendResponse.json();
                  console.log(`Direct backend call successful for ${doc.id}: Status ${updatedDoc.status}, Progress ${updatedDoc.progress}`);
                  
                  // Update document data through parent component
                  onDocumentUpdate(doc.id, {
                    status: updatedDoc.status,
                    progress: updatedDoc.progress || doc.progress
                  });
                  
                  // Check if processing is complete
                  if (updatedDoc.status === 'processed' || updatedDoc.status === 'error') {
                    // Show notification that document is processed
                    console.log(`Document ${doc.id} processing complete with status: ${updatedDoc.status}`);
                  }
                  
                  // Skip the rest of this iteration as we've handled this document
                  continue;
                } else {
                  console.log(`Direct backend call failed with status ${backendResponse.status}`);
                  // Try the old endpoint format as last resort
                  const legacyResponse = await fetch(`http://localhost:8000/api/v1/documents/${doc.id}/status`);
                  if (legacyResponse.ok) {
                    const updatedDoc = await legacyResponse.json();
                    console.log(`Legacy endpoint call successful for ${doc.id}`);
                    
                    // Update document data through parent component
                    onDocumentUpdate(doc.id, {
                      status: updatedDoc.status,
                      progress: updatedDoc.progress || doc.progress
                    });
                    
                    // Skip the rest of this iteration
                    continue;
                  }
                }
              } catch (directError) {
                console.error(`Direct backend call failed for ${doc.id}:`, directError);
              }
            }
            console.log(`Poll response status for ${doc.id}: ${response.status}`);
            
            if (response.ok) {
              const updatedDoc = await response.json();
              console.log(`Updated doc status: ${updatedDoc.status}, progress: ${updatedDoc.progress}`);
              console.log('Full document data:', updatedDoc);
              
              // Update document data through parent component
              onDocumentUpdate(doc.id, {
                status: updatedDoc.status,
                progress: updatedDoc.progress || doc.progress
              });
              
              // If the document status has changed to processed, show notification
              if (updatedDoc.status === 'processed' && doc.status === 'processing') {
                console.log(`Document ${doc.id} processing completed!`);
                // Add notification
                setNotifications(prev => [
                  ...prev, 
                  {
                    id: doc.id,
                    message: `Document ${doc.filename} has been processed successfully!`,
                    type: 'success'
                  }
                ]);
                
                // Remove from processing list
                setProcessingDocuments(prev => prev.filter(id => id !== doc.id));
              }
              
              // If the document is still processing but progress has changed, update the UI
              // This will be handled by the parent component's state update on the next render
            } else {
              console.warn(`Error polling document ${doc.id}: ${response.status}`);
              // Don't remove from processing list on error, we'll try again next time
            }
          } catch (error) {
            console.error(`Error checking document status for ${doc.id}:`, error);
            // Continue polling even if there's an error for one document
          }
        }
      }, 5000); // Poll every 5 seconds
      
      // Clean up interval on unmount
      return () => clearInterval(pollInterval);
    }
  }, [documents]);
  
  // Handle notification dismissal
  const dismissNotification = (id: string) => {
    setNotifications(prev => prev.filter(notification => notification.id !== id));
  };
  
  // Handle file drop
  const onDrop = useCallback((acceptedFiles: File[]) => {
    // Create a copy of files to avoid issues with the FileList object
    const filesCopy = [...acceptedFiles];
    console.log('Files dropped:', filesCopy.length);
    
    // Simulate upload process
    setIsUploading(true);
    setUploadProgress(0);
    
    // In a real implementation, this would call the API to upload the files
    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsUploading(false);
          
          // Pass all files to the parent component for upload
          onDocumentUpload(acceptedFiles);
          setShowUploadArea(false);
          return 100;
        }
        return prev + 10;
      });
    }, 300);
    
  }, [onDocumentUpload]);

  // Set up dropzone
  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt']
    },
    maxSize: 10485760, // 10MB
    multiple: true
  });

  // Format date
  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Document status icon
  const DocumentStatusIcon = ({ status }: { status: string }) => {
    if (status === 'processed') {
      return <CheckIcon className="w-5 h-5 text-green-500" />;
    } else if (status === 'processing') {
      return (
        <svg className="animate-spin h-5 w-5 text-blue-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      );
    } else if (status === 'error') {
      return <ExclamationTriangleIcon className="w-5 h-5 text-red-500" />;
    } else {
      return <DocumentTextIcon className="w-5 h-5 text-gray-400" />;
    }
  };

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden relative">      
      {/* Notifications */}
      <div className="fixed top-4 right-4 z-50 space-y-2 w-80">
        {notifications.map((notification) => (
          <div 
            key={notification.id} 
            className={`p-4 rounded-lg shadow-lg flex items-center justify-between ${notification.type === 'success' ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}
          >
            <div className="flex items-center">
              {notification.type === 'success' ? (
                <CheckIcon className="w-5 h-5 mr-2 text-green-500" />
              ) : (
                <ExclamationTriangleIcon className="w-5 h-5 mr-2 text-red-500" />
              )}
              <p className="text-sm">{notification.message}</p>
            </div>
            <button 
              onClick={() => dismissNotification(notification.id)}
              className="text-gray-500 hover:text-gray-700"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
          </div>
        ))}
      </div>
      <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-medium text-gray-900">Project Documents</h3>
          <button 
            onClick={() => setShowUploadArea(!showUploadArea)} 
            className="btn btn-outline text-sm"
          >
            <ArrowUpTrayIcon className="w-4 h-4 mr-1" />
            Upload
          </button>
        </div>
      </div>
      
      {/* Upload area */}
      {showUploadArea && (
        <div className="p-4 bg-gray-50 border-b border-gray-200">
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              isDragActive ? 'border-primary-500 bg-primary-50' : 'border-gray-300 hover:border-primary-400'
            }`}
          >
            <input {...getInputProps()} />
            <ArrowUpTrayIcon className="w-8 h-8 mx-auto text-gray-400 mb-2" />
            {isDragActive ? (
              <p className="text-primary-600">Drop the files here...</p>
            ) : (
              <div>
                <p className="text-gray-600 mb-1">Drag and drop files here, or click to select files</p>
                <p className="text-xs text-gray-500">Supported formats: PDF, DOCX, TXT (Max 10MB)</p>
              </div>
            )}
          </div>
          
          {isUploading && (
            <div className="mt-4">
              <div className="flex justify-between text-sm text-gray-600 mb-1">
                <span>Uploading...</span>
                <span>{uploadProgress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-primary-600 h-2 rounded-full transition-all duration-300" 
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>
      )}
      
      {/* Document list */}
      <div className="overflow-hidden">
        {documents.length === 0 ? (
          <div className="text-center py-8">
            <DocumentTextIcon className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500 mb-4">No documents uploaded yet</p>
            <button 
              onClick={() => setShowUploadArea(true)} 
              className="btn btn-outline text-sm"
            >
              <ArrowUpTrayIcon className="w-4 h-4 mr-1" />
              Upload Documents
            </button>
          </div>
        ) : (
          <ul className="divide-y divide-gray-200">
            {Array.isArray(documents) && documents.map((doc) => (
              <li key={doc.id} className="px-4 py-4 sm:px-6 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <DocumentStatusIcon status={doc.status} />
                    <div className="ml-3">
                      <p className="text-sm font-medium text-gray-900">{doc.filename}</p>
                      <p className="text-xs text-gray-500">
                        Uploaded {formatDate(doc.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center">
                    <span className="text-xs text-gray-500 mr-4">
                      {doc.status.charAt(0).toUpperCase() + doc.status.slice(1)}
                      {doc.status === 'processing' && ` (${doc.progress || '10'}%)`}
                    </span>
                    <button 
                      onClick={() => onDocumentDelete(doc.id)} 
                      className="text-gray-400 hover:text-red-500"
                      aria-label="Delete document"
                    >
                      <XMarkIcon className="w-5 h-5" />
                    </button>
                  </div>
                </div>
                {doc.description && (
                  <p className="mt-1 text-sm text-gray-600 ml-8">{doc.description}</p>
                )}
                
                {/* Progress bar for documents in processing state */}
                {doc.status === 'processing' && (
                  <div className="mt-2 ml-8 mr-8">
                    <div className="w-full bg-gray-200 rounded-full h-1.5">
                      <div 
                        className="bg-blue-500 h-1.5 rounded-full transition-all duration-300" 
                        style={{ width: `${doc.progress || '10'}%` }}
                      ></div>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
