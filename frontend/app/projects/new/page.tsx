'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeftIcon, DocumentTextIcon, ArrowUpTrayIcon, XMarkIcon } from '@heroicons/react/24/outline';
import { useDropzone } from 'react-dropzone';
import { API_ENDPOINTS, apiRequest, uploadMultipleFiles } from '../../api/config';

export default function NewProjectPage() {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    goal: '',
    deadline: '',
    teamSize: '',
    industry: '',
    budget: '',
  });
  const [documents, setDocuments] = useState<File[]>([]);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [skipDocuments, setSkipDocuments] = useState(false);

  // Handle form input changes
  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  // Handle file drop
  const onDrop = (acceptedFiles: File[]) => {
    setDocuments(prev => [...prev, ...acceptedFiles]);
  };

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

  // Remove a document from the list
  const removeDocument = (index: number) => {
    setDocuments(prev => prev.filter((_, i) => i !== index));
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      // Validate form
      if (!formData.name.trim()) {
        throw new Error('Project name is required');
      }

      // Create the project via API
      const projectData = {
        name: formData.name,
        description: formData.description,
        status: 'draft',
        goal: formData.goal,
        deadline: formData.deadline,
        team_size: parseInt(formData.teamSize) || null,
        industry: formData.industry,
        budget: formData.budget,
        planning_status: skipDocuments ? 'not_started' : 'not_started'
      };

      console.log('Creating project with data:', projectData);
      console.log('Using API endpoint:', API_ENDPOINTS.PROJECTS.CREATE);
      
      const project = await apiRequest(API_ENDPOINTS.PROJECTS.CREATE, {
        method: 'POST',
        body: JSON.stringify(projectData),
      });
      
      console.log('Project created successfully:', project);
      const projectId = project.id;

      // Upload documents if there are any and user didn't skip
      if (documents.length > 0 && !skipDocuments) {
        await uploadDocuments(projectId);
      }

      // Redirect to the new project page
      if (skipDocuments) {
        // Add a query parameter to indicate planning mode
        router.push(`/projects/${projectId}?planning=true`);
      } else {
        router.push(`/projects/${projectId}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred');
      setLoading(false);
    }
  };

  // Upload documents to the API with progress tracking
  const uploadDocuments = async (projectId: string) => {
    setIsUploading(true);
    setUploadProgress(0);

    try {
      console.log('Uploading documents for project:', projectId);
      console.log('Number of documents:', documents.length);
      console.log('Using upload endpoint:', API_ENDPOINTS.DOCUMENTS.UPLOAD);
      
      // Use the configured uploadMultipleFiles function
      const result = await uploadMultipleFiles(documents, projectId, '');
      console.log('Upload completed successfully:', result);
      
      setIsUploading(false);
    } catch (err) {
      console.error('Upload failed:', err);
      setIsUploading(false);
      throw err;
    }
  };

  // Next step
  const goToNextStep = () => {
    if (step < 3) {
      setStep(prev => prev + 1);
      window.scrollTo(0, 0);
    }
  };

  // Previous step
  const goToPreviousStep = () => {
    if (step > 1) {
      setStep(prev => prev - 1);
      window.scrollTo(0, 0);
    }
  };

  // Industry options
  const industries = [
    'Technology',
    'Healthcare',
    'Finance',
    'Education',
    'Manufacturing',
    'Retail',
    'Construction',
    'Entertainment',
    'Transportation',
    'Energy',
    'Other'
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex items-center">
          <Link href="/projects" className="text-gray-500 hover:text-gray-700 mr-4">
            <ArrowLeftIcon className="w-5 h-5" />
          </Link>
          <h1 className="text-3xl font-bold text-gray-900">Create New Project</h1>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-3xl mx-auto py-10 px-4 sm:px-6 lg:px-8">
        {/* Progress steps */}
        <div className="mb-10">
          <div className="flex items-center justify-between">
            <div className="w-full flex items-center">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                step >= 1 ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-600'
              }`}>
                1
              </div>
              <div className={`h-1 flex-1 ${
                step > 1 ? 'bg-primary-600' : 'bg-gray-200'
              }`}></div>
            </div>
            <div className="w-full flex items-center">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                step >= 2 ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-600'
              }`}>
                2
              </div>
              <div className={`h-1 flex-1 ${
                step > 2 ? 'bg-primary-600' : 'bg-gray-200'
              }`}></div>
            </div>
            <div className="w-full flex items-center">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                step >= 3 ? 'bg-primary-600 text-white' : 'bg-gray-200 text-gray-600'
              }`}>
                3
              </div>
            </div>
          </div>
          <div className="flex justify-between mt-2 text-sm">
            <div className={`w-full text-center ${step >= 1 ? 'text-primary-600 font-medium' : 'text-gray-500'}`}>
              Project Details
            </div>
            <div className={`w-full text-center ${step >= 2 ? 'text-primary-600 font-medium' : 'text-gray-500'}`}>
              Upload Documents
            </div>
            <div className={`w-full text-center ${step >= 3 ? 'text-primary-600 font-medium' : 'text-gray-500'}`}>
              Review & Create
            </div>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-50 border-l-4 border-red-400 p-4 mb-6">
            <div className="flex">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-red-700">{error}</p>
              </div>
            </div>
          </div>
        )}

        <div className="bg-white shadow rounded-lg overflow-hidden">
          <form onSubmit={handleSubmit}>
            {/* Step 1: Project Details */}
            {step === 1 && (
              <div className="p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-6">Project Details</h2>
                
                <div className="space-y-6">
                  <div>
                    <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
                      Project Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      id="name"
                      name="name"
                      value={formData.name}
                      onChange={handleChange}
                      className="input w-full"
                      placeholder="E.g., E-Commerce Platform Redesign"
                      required
                    />
                  </div>
                  
                  <div>
                    <label htmlFor="description" className="block text-sm font-medium text-gray-700 mb-1">
                      Project Description
                    </label>
                    <textarea
                      id="description"
                      name="description"
                      value={formData.description}
                      onChange={handleChange}
                      rows={4}
                      className="input w-full"
                      placeholder="Describe the project's purpose and scope..."
                    />
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label htmlFor="industry" className="block text-sm font-medium text-gray-700 mb-1">
                        Industry
                      </label>
                      <select
                        id="industry"
                        name="industry"
                        value={formData.industry}
                        onChange={handleChange}
                        className="input w-full"
                      >
                        <option value="">Select an industry</option>
                        {industries.map((industry) => (
                          <option key={industry} value={industry}>
                            {industry}
                          </option>
                        ))}
                      </select>
                    </div>
                    
                    <div>
                      <label htmlFor="deadline" className="block text-sm font-medium text-gray-700 mb-1">
                        Target Completion Date
                      </label>
                      <input
                        type="date"
                        id="deadline"
                        name="deadline"
                        value={formData.deadline}
                        onChange={handleChange}
                        className="input w-full"
                      />
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div>
                      <label htmlFor="teamSize" className="block text-sm font-medium text-gray-700 mb-1">
                        Team Size
                      </label>
                      <input
                        type="number"
                        id="teamSize"
                        name="teamSize"
                        value={formData.teamSize}
                        onChange={handleChange}
                        min="1"
                        className="input w-full"
                        placeholder="Number of team members"
                      />
                    </div>
                    
                    <div>
                      <label htmlFor="budget" className="block text-sm font-medium text-gray-700 mb-1">
                        Budget (USD)
                      </label>
                      <input
                        type="text"
                        id="budget"
                        name="budget"
                        value={formData.budget}
                        onChange={handleChange}
                        className="input w-full"
                        placeholder="E.g., 50,000"
                      />
                    </div>
                  </div>
                  
                  <div>
                    <label htmlFor="goal" className="block text-sm font-medium text-gray-700 mb-1">
                      Project Goal
                    </label>
                    <textarea
                      id="goal"
                      name="goal"
                      value={formData.goal}
                      onChange={handleChange}
                      rows={3}
                      className="input w-full"
                      placeholder="What are the main objectives of this project?"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Step 2: Upload Documents */}
            {step === 2 && (
              <div className="p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-6">Upload Project Documents</h2>
                
                <div className="space-y-6">
                  <p className="text-gray-600">
                    Upload project briefs, requirements, meeting notes, or any other relevant documents. 
                    Our AI agents will analyze these documents to help create your project plan.
                  </p>
                  
                  <div className="bg-blue-50 border-l-4 border-blue-400 p-4">
                    <div className="flex">
                      <div className="flex-shrink-0">
                        <svg className="h-5 w-5 text-blue-400" viewBox="0 0 20 20" fill="currentColor">
                          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                        </svg>
                      </div>
                      <div className="ml-3">
                        <p className="text-sm text-blue-700">
                          <strong>Don't have project documents yet?</strong> No problem! You can skip this step and use our Project Planner agent to help you create comprehensive project documentation through guided conversations.
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  {!skipDocuments && (
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
                  )}
                  
                  {/* Document list */}
                  {documents.length > 0 && !skipDocuments && (
                    <div className="mt-4">
                      <h3 className="text-sm font-medium text-gray-700 mb-2">Uploaded Documents</h3>
                      <ul className="border rounded-lg divide-y divide-gray-200">
                        {documents.map((file, index) => (
                          <li key={index} className="px-4 py-3 flex items-center justify-between">
                            <div className="flex items-center">
                              <DocumentTextIcon className="w-5 h-5 text-gray-400 mr-2" />
                              <div>
                                <p className="text-sm font-medium text-gray-900">{file.name}</p>
                                <p className="text-xs text-gray-500">
                                  {(file.size / 1024).toFixed(1)} KB
                                </p>
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => removeDocument(index)}
                              className="text-gray-400 hover:text-red-500"
                              aria-label="Remove document"
                            >
                              <XMarkIcon className="w-5 h-5" />
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  
                  <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        id="skipDocuments"
                        checked={skipDocuments}
                        onChange={(e) => setSkipDocuments(e.target.checked)}
                        className="h-4 w-4 text-primary-600 focus:ring-primary-500 border-gray-300 rounded"
                      />
                      <label htmlFor="skipDocuments" className="ml-2 text-sm text-gray-700">
                        Skip documents and use Project Planner to create documentation
                      </label>
                    </div>
                    {skipDocuments && (
                      <span className="text-xs text-green-600 font-medium">📋 Planning Mode</span>
                    )}
                  </div>
                  
                  {!skipDocuments && (
                    <>
                      <div className="bg-blue-50 p-4 rounded-lg">
                        <p className="text-sm text-blue-700">
                          <strong>Tip:</strong> The more information you provide, the better our AI agents can analyze your project.
                          Consider uploading requirements documents, meeting notes, and any existing project plans.
                        </p>
                      </div>
                    </>
                  )}
                  
                  {skipDocuments && (
                    <div className="bg-purple-50 p-4 rounded-lg">
                      <p className="text-sm text-purple-700">
                        <strong>Planning Mode Enabled:</strong> After creating your project, you'll be guided through building comprehensive project documentation with our Project Planner agent (@planner). This interactive process will help you create a detailed project brief that our technical analysts can then analyze.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Step 3: Review & Create */}
            {step === 3 && (
              <div className="p-6">
                <h2 className="text-xl font-semibold text-gray-900 mb-6">Review & Create Project</h2>
                
                <div className="space-y-6">
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h3 className="text-md font-medium text-gray-900 mb-3">Project Details</h3>
                    <dl className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-2">
                      <div className="col-span-2">
                        <dt className="text-sm font-medium text-gray-500">Name</dt>
                        <dd className="text-sm text-gray-900">{formData.name || 'Not specified'}</dd>
                      </div>
                      <div className="col-span-2">
                        <dt className="text-sm font-medium text-gray-500">Description</dt>
                        <dd className="text-sm text-gray-900">{formData.description || 'Not specified'}</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Industry</dt>
                        <dd className="text-sm text-gray-900">{formData.industry || 'Not specified'}</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Target Completion Date</dt>
                        <dd className="text-sm text-gray-900">{formData.deadline || 'Not specified'}</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Team Size</dt>
                        <dd className="text-sm text-gray-900">{formData.teamSize || 'Not specified'}</dd>
                      </div>
                      <div>
                        <dt className="text-sm font-medium text-gray-500">Budget</dt>
                        <dd className="text-sm text-gray-900">
                          {formData.budget ? `$${formData.budget}` : 'Not specified'}
                        </dd>
                      </div>
                      <div className="col-span-2">
                        <dt className="text-sm font-medium text-gray-500">Project Goal</dt>
                        <dd className="text-sm text-gray-900">{formData.goal || 'Not specified'}</dd>
                      </div>
                    </dl>
                  </div>
                  
                  <div className="bg-gray-50 p-4 rounded-lg">
                    <h3 className="text-md font-medium text-gray-900 mb-3">Documents</h3>
                    {skipDocuments ? (
                      <div className="flex items-center text-sm text-purple-700">
                        <span className="mr-2">📋</span>
                        <span><strong>Planning Mode:</strong> Will use Project Planner agent to create documentation</span>
                      </div>
                    ) : documents.length > 0 ? (
                      <ul className="space-y-1">
                        {documents.map((file, index) => (
                          <li key={index} className="text-sm text-gray-900 flex items-center">
                            <DocumentTextIcon className="w-4 h-4 text-gray-400 mr-1" />
                            {file.name} ({(file.size / 1024).toFixed(1)} KB)
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-gray-500">No documents uploaded</p>
                    )}
                  </div>
                  
                  {skipDocuments ? (
                    <div className="bg-purple-50 p-4 rounded-lg">
                      <p className="text-sm text-purple-700">
                        <strong>What happens next?</strong> You'll be taken to your project where you can chat with the Project Planner agent (@planner). The agent will guide you through creating a comprehensive project brief by asking targeted questions about your project's scope, goals, requirements, and timeline. Once complete, you can proceed with technical analysis.
                      </p>
                    </div>
                  ) : (
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <p className="text-sm text-blue-700">
                        <strong>What happens next?</strong> After creating your project, our AI agents will analyze your 
                        project details and documents. You'll be able to interact with the agents to refine the project plan 
                        and get insights into technical requirements, risks, and timelines.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Navigation buttons */}
            <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-between">
              {step > 1 ? (
                <button
                  type="button"
                  onClick={goToPreviousStep}
                  className="btn btn-outline"
                  disabled={loading}
                >
                  Previous
                </button>
              ) : (
                <Link href="/projects" className="btn btn-outline">
                  Cancel
                </Link>
              )}
              
              {step < 3 ? (
                <button
                  type="button"
                  onClick={goToNextStep}
                  className="btn btn-primary"
                >
                  Next
                </button>
              ) : (
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={loading}
                >
                  {loading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Creating Project...
                    </>
                  ) : (
                    'Create Project'
                  )}
                </button>
              )}
            </div>
          </form>
        </div>

        {/* Upload progress */}
        {isUploading && (
          <div className="mt-6 bg-white shadow rounded-lg p-6">
            <h3 className="text-md font-medium text-gray-900 mb-3">Uploading Documents</h3>
            <div className="flex justify-between text-sm text-gray-600 mb-1">
              <span>Uploading {documents.length} document{documents.length !== 1 ? 's' : ''}...</span>
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
      </main>
    </div>
  );
}
