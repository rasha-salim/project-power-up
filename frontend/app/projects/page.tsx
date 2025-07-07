'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { PlusIcon, DocumentTextIcon, ChartBarIcon, ClockIcon } from '@heroicons/react/24/outline';
import { API_ENDPOINTS, apiRequest } from '../api/config';

// Types
interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  planning_status?: string;
  created_at: string;
  updated_at: string;
  document_count?: number;
}

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch projects
  useEffect(() => {
    const fetchProjects = async () => {
      try {
        // Fetch projects from the API
        console.log('🔵 Fetching projects list');
        console.log('🔵 Using API endpoint:', API_ENDPOINTS.PROJECTS.LIST);
        
        const data = await apiRequest(API_ENDPOINTS.PROJECTS.LIST);
        console.log('🟢 Projects fetched successfully:', data.length);
        
        // Add document count if available, or default to 0
        const projectsWithDocCount = data.map((project: any) => ({
          ...project,
          document_count: project.document_count || 0
        }));
        
        setProjects(projectsWithDocCount);
        setLoading(false);
      } catch (err: any) {
        console.error('🔴 Error fetching projects:', err);
        setError(err.message || 'Failed to load projects. Please try again later.');
        setLoading(false);
      }
    };

    fetchProjects();
  }, []);

  // Status badge component
  const StatusBadge = ({ status }: { status: string }) => {
    let bgColor = 'bg-gray-100 text-gray-800';
    
    if (status === 'completed') {
      bgColor = 'bg-green-100 text-green-800';
    } else if (status === 'analyzing') {
      bgColor = 'bg-blue-100 text-blue-800';
    } else if (status === 'draft') {
      bgColor = 'bg-gray-100 text-gray-800';
    }
    
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bgColor}`}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    );
  };

  // Planning status badge component
  const PlanningStatusBadge = ({ planningStatus }: { planningStatus?: string }) => {
    if (!planningStatus) return null;
    
    let bgColor = 'bg-gray-100 text-gray-600';
    let displayText = planningStatus;
    
    if (planningStatus === 'completed') {
      bgColor = 'bg-emerald-100 text-emerald-700';
      displayText = 'Planning Complete';
    } else if (planningStatus === 'in_progress') {
      bgColor = 'bg-amber-100 text-amber-700';
      displayText = 'Planning in Progress';
    } else if (planningStatus === 'not_started') {
      bgColor = 'bg-slate-100 text-slate-600';
      displayText = 'Planning Not Started';
    }
    
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${bgColor}`}>
        📋 {displayText}
      </span>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <h1 className="text-3xl font-bold text-gray-900">Projects</h1>
          <Link href="/projects/new" className="btn btn-primary">
            <PlusIcon className="w-5 h-5 mr-2" />
            New Project
          </Link>
        </div>
      </header>

      {/* Main content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
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

        {/* Loading state */}
        {loading ? (
          <div className="text-center py-12">
            <svg className="animate-spin h-10 w-10 text-primary-600 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <p className="text-gray-500">Loading projects...</p>
          </div>
        ) : (
          <>
            {/* Projects grid */}
            {projects.length === 0 ? (
              <div className="text-center py-12 bg-white rounded-lg shadow">
                <DocumentTextIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No projects yet</h3>
                <p className="text-gray-500 mb-6">Get started by creating your first project.</p>
                <Link href="/projects/new" className="btn btn-primary">
                  <PlusIcon className="w-5 h-5 mr-2" />
                  Create Project
                </Link>
              </div>
            ) : (
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {projects.map((project) => (
                  <Link 
                    key={project.id} 
                    href={`/projects/${project.id}`}
                    className="block group"
                  >
                    <div className="card hover:shadow-lg transition-shadow duration-200 h-full flex flex-col">
                      <div className="p-6 flex-grow">
                        <div className="flex justify-between items-start mb-4">
                          <h2 className="text-xl font-semibold text-gray-900 group-hover:text-primary-600 transition-colors duration-200">
                            {project.name}
                          </h2>
                          <div className="flex flex-col gap-2">
                            <StatusBadge status={project.status} />
                            <PlanningStatusBadge planningStatus={project.planning_status} />
                          </div>
                        </div>
                        <p className="text-gray-600 mb-6 line-clamp-3">
                          {project.description}
                        </p>
                        <div className="flex items-center text-sm text-gray-500">
                          <DocumentTextIcon className="h-5 w-5 mr-1" />
                          <span>{project.document_count} documents</span>
                        </div>
                      </div>
                      <div className="border-t border-gray-200 bg-gray-50 px-6 py-4 rounded-b-lg">
                        <div className="flex justify-between items-center text-sm">
                          <div className="flex items-center text-gray-500">
                            <ClockIcon className="h-4 w-4 mr-1" />
                            <span>
                              {new Date(project.updated_at).toLocaleDateString()}
                            </span>
                          </div>
                          <div className="text-primary-600 font-medium">View Details →</div>
                        </div>
                      </div>
                    </div>
                  </Link>
                ))}
                
                {/* New project card */}
                <Link href="/projects/new" className="block group h-full">
                  <div className="card border-2 border-dashed border-gray-300 hover:border-primary-500 transition-colors duration-200 h-full flex flex-col justify-center items-center p-6 text-center">
                    <div className="w-16 h-16 rounded-full bg-primary-100 flex items-center justify-center mb-4 group-hover:bg-primary-200 transition-colors duration-200">
                      <PlusIcon className="h-8 w-8 text-primary-600" />
                    </div>
                    <h3 className="text-lg font-medium text-gray-900 mb-1">Create New Project</h3>
                    <p className="text-gray-500">Start planning with AI assistance</p>
                  </div>
                </Link>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
