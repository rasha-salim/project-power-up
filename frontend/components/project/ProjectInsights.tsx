'use client';

import { useState, useEffect } from 'react';
import { 
  ChartBarIcon, 
  ClockIcon, 
  ExclamationTriangleIcon, 
  DocumentTextIcon 
} from '@heroicons/react/24/outline';

interface ProjectInsightsProps {
  projectId: string;
  projectStatus: string;
}

export default function ProjectInsights({ projectId, projectStatus }: ProjectInsightsProps) {
  const [insights, setInsights] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState('technical');

  // Fetch project insights
  useEffect(() => {
    const fetchInsights = async () => {
      // Only fetch insights if project analysis is completed or in progress
      if (projectStatus === 'draft') {
        setLoading(false);
        return;
      }

      try {
        // Fetch insights from the API
        const response = await fetch(`/api/v1/projects/${projectId}/insights`);
        
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to load insights');
        }
        
        const data = await response.json();
        
        // If analysis is still in progress
        if (data.status === 'analyzing' || data.status === 'not_started') {
          setLoading(false);
          return;
        }
        
        // If we have insights, set them
        if (data.status === 'completed' && data.insights) {
          setInsights(data.insights);
        } else {
          // If no insights but status is completed, something went wrong
          setError('No insights available. The analysis may have encountered an error.');
        }
        
        setLoading(false);
      } catch (err) {
        console.error('Error fetching project insights:', err);
        setError(err instanceof Error ? err.message : 'Failed to load project insights. Please try again later.');
        setLoading(false);
      }
    };

    fetchInsights();
    
    // If project is analyzing, set up polling to check for completion
    let pollInterval: NodeJS.Timeout | null = null;
    
    if (projectStatus === 'analyzing') {
      pollInterval = setInterval(async () => {
        try {
          const response = await fetch(`/api/v1/projects/${projectId}/insights`);
          
          if (!response.ok) {
            console.error('Error polling for insights, will retry');
            return;
          }
          
          const data = await response.json();
          
          // If analysis is complete, update insights
          if (data.status === 'completed' && data.insights) {
            setInsights(data.insights);
            setLoading(false);
            if (pollInterval) clearInterval(pollInterval);
          }
        } catch (err) {
          console.error('Error polling for insights:', err);
        }
      }, 5000); // Poll every 5 seconds
    }
    
    // Clean up interval on unmount
    return () => {
      if (pollInterval) clearInterval(pollInterval);
    };
  }, [projectId, projectStatus]);

  if (projectStatus !== 'completed') {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Project Insights Dashboard</h3>
          <p className="text-gray-500 mb-4">
            Insights will be available after project analysis is complete.
          </p>
          <div className="bg-gray-100 p-4 rounded-lg">
            {projectStatus === 'analyzing' ? (
              <div className="flex items-center justify-center">
                <svg className="animate-spin h-5 w-5 mr-2 text-primary-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Analysis in progress...</span>
              </div>
            ) : (
              <span>Run an analysis to generate insights</span>
            )}
          </div>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <svg className="animate-spin h-10 w-10 text-primary-600 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <p className="text-gray-500">Loading project insights...</p>
        </div>
      </div>
    );
  }

  if (error || !insights) {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Error Loading Insights</h3>
          <p className="text-gray-500">{error || 'No insights available'}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden h-[600px] flex flex-col">
      <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">Project Insights Dashboard</h3>
        <p className="mt-1 text-sm text-gray-500">
          AI-generated insights and recommendations for your project
        </p>
      </div>
      
      {/* Tabs */}
      <div className="border-b border-gray-200 bg-gray-50">
        <nav className="flex">
          <button
            onClick={() => setActiveSection('technical')}
            className={`py-3 px-4 text-sm font-medium ${
              activeSection === 'technical'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center">
              <ChartBarIcon className="w-4 h-4 mr-1" />
              Technical Analysis
            </div>
          </button>
          <button
            onClick={() => setActiveSection('risk')}
            className={`py-3 px-4 text-sm font-medium ${
              activeSection === 'risk'
                ? 'border-b-2 border-amber-500 text-amber-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center">
              <ExclamationTriangleIcon className="w-4 h-4 mr-1" />
              Risk Assessment
            </div>
          </button>
          <button
            onClick={() => setActiveSection('plan')}
            className={`py-3 px-4 text-sm font-medium ${
              activeSection === 'plan'
                ? 'border-b-2 border-green-500 text-green-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center">
              <ClockIcon className="w-4 h-4 mr-1" />
              Project Plan
            </div>
          </button>
        </nav>
      </div>
      
      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {activeSection === 'technical' && (
          <div className="space-y-4">
            <div className="card p-4">
              <h4 className="text-lg font-medium text-gray-900 mb-2">Architecture</h4>
              <p className="text-gray-700">{insights.technical_analysis.architecture}</p>
            </div>
            
            <div className="card p-4">
              <h4 className="text-lg font-medium text-gray-900 mb-2">Technology Stack</h4>
              <p className="text-gray-700">{insights.technical_analysis.tech_stack}</p>
            </div>
            
            <div className="card p-4">
              <h4 className="text-lg font-medium text-gray-900 mb-2">Feasibility Assessment</h4>
              <p className="text-gray-700">{insights.technical_analysis.feasibility}</p>
            </div>
            
            <div className="bg-blue-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600 italic">
                Note: This is a placeholder for the Technical Analysis dashboard. In a complete implementation, 
                this would include interactive visualizations, architecture diagrams, and more detailed technical insights.
              </p>
            </div>
          </div>
        )}
        
        {activeSection === 'risk' && (
          <div className="space-y-4">
            <div className="card p-4">
              <h4 className="text-lg font-medium text-gray-900 mb-2">Key Risks</h4>
              <ul className="list-disc pl-5 space-y-2">
                {insights.risk_assessment.key_risks.map((risk: string, index: number) => (
                  <li key={index} className="text-gray-700">{risk}</li>
                ))}
              </ul>
            </div>
            
            <div className="card p-4">
              <h4 className="text-lg font-medium text-gray-900 mb-2">Mitigation Strategies</h4>
              <ul className="list-disc pl-5 space-y-2">
                {insights.risk_assessment.mitigation_strategies.map((strategy: string, index: number) => (
                  <li key={index} className="text-gray-700">{strategy}</li>
                ))}
              </ul>
            </div>
            
            <div className="bg-amber-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600 italic">
                Note: This is a placeholder for the Risk Assessment dashboard. In a complete implementation, 
                this would include risk matrices, impact vs. probability charts, and more detailed risk analysis.
              </p>
            </div>
          </div>
        )}
        
        {activeSection === 'plan' && (
          <div className="space-y-4">
            <div className="card p-4">
              <h4 className="text-lg font-medium text-gray-900 mb-2">Timeline</h4>
              <p className="text-gray-700">{insights.project_plan.timeline}</p>
            </div>
            
            <div className="card p-4">
              <h4 className="text-lg font-medium text-gray-900 mb-2">Key Milestones</h4>
              <ul className="list-disc pl-5 space-y-2">
                {insights.project_plan.milestones.map((milestone: string, index: number) => (
                  <li key={index} className="text-gray-700">{milestone}</li>
                ))}
              </ul>
            </div>
            
            <div className="card p-4">
              <h4 className="text-lg font-medium text-gray-900 mb-2">Resource Requirements</h4>
              <p className="text-gray-700">{insights.project_plan.resource_requirements}</p>
            </div>
            
            <div className="bg-green-50 p-4 rounded-lg">
              <p className="text-sm text-gray-600 italic">
                Note: This is a placeholder for the Project Plan dashboard. In a complete implementation, 
                this would include Gantt charts, resource allocation visualizations, and more detailed planning tools.
              </p>
            </div>
          </div>
        )}
      </div>
      
      {/* Footer */}
      <div className="px-4 py-3 bg-gray-50 text-right sm:px-6 border-t border-gray-200">
        <button className="btn btn-outline">
          <DocumentTextIcon className="w-4 h-4 mr-1" />
          Export Insights
        </button>
      </div>
    </div>
  );
}
