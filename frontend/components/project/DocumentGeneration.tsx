'use client';

import { useState, useEffect } from 'react';
import { 
  DocumentTextIcon, 
  DocumentArrowDownIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';

interface DocumentGenerationProps {
  projectId: string;
  projectStatus: string;
}

interface GeneratedDocument {
  id: string;
  type: string;
  filename: string;
  file_size: number;
  generated_at: string;
  title: string;
}

export default function DocumentGeneration({ projectId, projectStatus }: DocumentGenerationProps) {
  const [documents, setDocuments] = useState<GeneratedDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDocuments();
  }, [projectId]);

  const fetchDocuments = async () => {
    try {
      const response = await fetch(`/api/v1/documents/generate/${projectId}/documents`);
      if (response.ok) {
        const data = await response.json();
        setDocuments(data.documents || []);
      }
    } catch (err) {
      console.error('Error fetching documents:', err);
    }
  };

  const generateDocument = async (type: 'brief' | 'analysis' | 'comprehensive') => {
    setGenerating(type);
    setError(null);

    try {
      const response = await fetch(`/api/v1/documents/generate/${projectId}/generate/${type}`, {
        method: 'POST',
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to generate document');
      }

      const data = await response.json();
      
      // Refresh documents list
      await fetchDocuments();
      
      setGenerating(null);
    } catch (err) {
      console.error(`Error generating ${type} document:`, err);
      setError(err instanceof Error ? err.message : 'Failed to generate document');
      setGenerating(null);
    }
  };

  const downloadDocument = async (documentId: string, filename: string) => {
    try {
      const response = await fetch(`/api/v1/documents/generate/${projectId}/documents/${documentId}/download`);
      
      if (!response.ok) {
        throw new Error('Failed to download document');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error('Error downloading document:', err);
      setError('Failed to download document');
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getDocumentTypeIcon = (type: string) => {
    switch (type) {
      case 'brief':
      case 'markdown':
        return '📋';
      case 'analysis_report':
        return '📊';
      case 'comprehensive_report':
        return '📑';
      default:
        return '📄';
    }
  };

  const getDocumentTypeLabel = (type: string) => {
    switch (type) {
      case 'brief':
      case 'markdown':
        return 'Project Brief';
      case 'analysis_report':
        return 'Analysis Report';
      case 'comprehensive_report':
        return 'Comprehensive Report';
      default:
        return 'Document';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">Document Generation</h2>
          <p className="text-gray-600 mt-1">Generate and download project documents</p>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border-l-4 border-red-400 p-4">
          <div className="flex">
            <ExclamationTriangleIcon className="h-5 w-5 text-red-400" />
            <div className="ml-3">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Generate Documents Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Generate New Documents</h3>
        
        <div className="grid gap-4 md:grid-cols-3">
          {/* Project Brief */}
          <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
            <div className="flex items-center mb-3">
              <span className="text-2xl mr-3">📋</span>
              <div>
                <h4 className="font-medium text-gray-900">Project Brief</h4>
                <p className="text-sm text-gray-600">Generate from planning data</p>
              </div>
            </div>
            <button
              onClick={() => generateDocument('brief')}
              disabled={generating === 'brief'}
              className={`w-full btn ${
                generating === 'brief' 
                  ? 'btn-secondary cursor-not-allowed' 
                  : 'btn-primary'
              }`}
            >
              {generating === 'brief' ? (
                <div className="flex items-center">
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full mr-2"></div>
                  Generating...
                </div>
              ) : (
                'Generate Brief'
              )}
            </button>
          </div>

          {/* Analysis Report */}
          <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
            <div className="flex items-center mb-3">
              <span className="text-2xl mr-3">📊</span>
              <div>
                <h4 className="font-medium text-gray-900">Analysis Report</h4>
                <p className="text-sm text-gray-600">Generate from analysis data</p>
              </div>
            </div>
            <button
              onClick={() => generateDocument('analysis')}
              disabled={generating === 'analysis' || projectStatus === 'draft'}
              className={`w-full btn ${
                generating === 'analysis' || projectStatus === 'draft'
                  ? 'btn-secondary cursor-not-allowed' 
                  : 'btn-primary'
              }`}
            >
              {generating === 'analysis' ? (
                <div className="flex items-center">
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full mr-2"></div>
                  Generating...
                </div>
              ) : projectStatus === 'draft' ? (
                'Requires Analysis'
              ) : (
                'Generate Report'
              )}
            </button>
          </div>

          {/* Comprehensive Report */}
          <div className="border rounded-lg p-4 hover:shadow-md transition-shadow">
            <div className="flex items-center mb-3">
              <span className="text-2xl mr-3">📑</span>
              <div>
                <h4 className="font-medium text-gray-900">Comprehensive Report</h4>
                <p className="text-sm text-gray-600">Combined brief & analysis</p>
              </div>
            </div>
            <button
              onClick={() => generateDocument('comprehensive')}
              disabled={generating === 'comprehensive'}
              className={`w-full btn ${
                generating === 'comprehensive' 
                  ? 'btn-secondary cursor-not-allowed' 
                  : 'btn-primary'
              }`}
            >
              {generating === 'comprehensive' ? (
                <div className="flex items-center">
                  <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full mr-2"></div>
                  Generating...
                </div>
              ) : (
                'Generate Report'
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Generated Documents List */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-semibold text-gray-900">Generated Documents</h3>
        </div>
        
        {documents.length === 0 ? (
          <div className="p-6 text-center">
            <DocumentTextIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No documents generated yet</h3>
            <p className="text-gray-500">Generate your first document using the options above.</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {documents.map((document) => (
              <div key={document.id} className="p-6 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <span className="text-2xl">{getDocumentTypeIcon(document.type)}</span>
                    <div>
                      <h4 className="text-lg font-medium text-gray-900">{document.title}</h4>
                      <div className="flex items-center space-x-4 text-sm text-gray-500">
                        <span className="flex items-center">
                          <ClockIcon className="h-4 w-4 mr-1" />
                          {formatDate(document.generated_at)}
                        </span>
                        <span>{formatFileSize(document.file_size)}</span>
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                          {getDocumentTypeLabel(document.type)}
                        </span>
                      </div>
                    </div>
                  </div>
                  <button
                    onClick={() => downloadDocument(document.id, document.filename)}
                    className="btn btn-secondary flex items-center"
                  >
                    <DocumentArrowDownIcon className="h-4 w-4 mr-2" />
                    Download
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}