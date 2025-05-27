import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { DocumentTextIcon, ArrowUpTrayIcon, XMarkIcon, CheckIcon, ExclamationTriangleIcon } from '@heroicons/react/24/outline';

interface Document {
  id: string;
  filename: string;
  status: string;
  created_at: string;
  description?: string;
}

interface DocumentManagerProps {
  projectId: string;
  documents: Document[];
  onDocumentUpload: (files: File[]) => void;
  onDocumentDelete: (documentId: string) => void;
}

export default function DocumentManager({ 
  projectId, 
  documents, 
  onDocumentUpload, 
  onDocumentDelete 
}: DocumentManagerProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [showUploadArea, setShowUploadArea] = useState(false);

  // Handle file drop
  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length === 0) return;
    
    // Simulate upload process
    setIsUploading(true);
    setUploadProgress(0);
    
    // In a real implementation, this would call the API to upload the files
    const interval = setInterval(() => {
      setUploadProgress((prev) => {
        if (prev >= 100) {
          clearInterval(interval);
          setIsUploading(false);
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
    <div className="bg-white shadow rounded-lg overflow-hidden">
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
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
