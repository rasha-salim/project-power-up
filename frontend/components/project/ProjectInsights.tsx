'use client';

import { useState, useEffect } from 'react';
import { API_ENDPOINTS, apiRequest } from '@/app/api/config';
import { 
  ChartBarIcon, 
  ClockIcon, 
  ExclamationTriangleIcon, 
  DocumentTextIcon,
  CpuChipIcon,
  UserGroupIcon,
  CurrencyDollarIcon,
  ShieldCheckIcon,
  BoltIcon,
  ArrowTrendingUpIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, RadarChart, Radar,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  Cell, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Area, AreaChart
} from 'recharts';

interface ProjectInsightsProps {
  projectId: string;
  projectStatus: string;
  projectInsights?: any;
}

// Helper function to transform real analysis data for visualization
const transformAnalysisData = (analysisData: any) => {
  if (!analysisData) return null;
  
  console.log('Raw API data:', analysisData);
  
  // Check if data is already in the correct flat structure (from props)
  if (analysisData.technical_analysis && typeof analysisData.technical_analysis === 'object' && 
      analysisData.technical_analysis.architecture) {
    console.log('✅ Data is already in flat structure (from props)');
    return {
      technical_analysis: analysisData.technical_analysis,
      risk_assessment: analysisData.risk_assessment || {},
      project_plan: analysisData.project_plan || {},
      recommendations: analysisData.recommendations || [],
      analysis_id: analysisData.analysis_id || null,
      version: analysisData.version || 1,
      created_at: analysisData.created_at || null,
      updated_at: analysisData.updated_at || null
    };
  }
  
  // Handle the nested structure from the API response
  // API returns: { technical_analysis: { analysis_id, project_id, version, technical_analysis: {}, risk_assessment: {}, project_plan: {}, recommendations: [] } }
  const data = analysisData.technical_analysis || analysisData;
  
  console.log('🔄 Using nested structure, extracted data:', data);
  
  return {
    technical_analysis: data.technical_analysis || {},
    risk_assessment: data.risk_assessment || {},
    project_plan: data.project_plan || {},
    recommendations: data.recommendations || [],
    analysis_id: data.analysis_id || null,
    version: data.version || 1,
    created_at: data.created_at || null,
    updated_at: data.updated_at || null
  };
};

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];

export default function ProjectInsights({ projectId, projectStatus, projectInsights }: ProjectInsightsProps) {
  const [insights, setInsights] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState('overview');

  useEffect(() => {
    const fetchInsights = async () => {
      console.log('🔍 Starting fetchInsights with:', { projectId, projectStatus, projectInsights });
      
      // If insights are passed as props, use them directly
      if (projectInsights) {
        console.log('📥 Using insights from props:', projectInsights);
        const transformedData = transformAnalysisData(projectInsights);
        console.log('🔄 Transformed props data:', transformedData);
        
        if (transformedData && transformedData.technical_analysis && Object.keys(transformedData.technical_analysis).length > 0) {
          setInsights(transformedData);
          console.log('✅ Insights set successfully from props:', transformedData);
        } else {
          console.log('❌ No valid analysis data found in props:', projectInsights);
          setError('No analysis data available in props.');
        }
        
        setLoading(false);
        return;
      }

      if (projectStatus === 'draft') {
        console.log('⏭️ Skipping fetch - project status is draft');
        setLoading(false);
        return;
      }

      try {
        console.log(`Fetching insights for project: ${projectId}, status: ${projectStatus}`);
        const response = await fetch(API_ENDPOINTS.PROJECTS.INSIGHTS(projectId));

        if (!response.ok) {
          console.error(`Insights API error: ${response.status} ${response.statusText}`);
          let errorMessage = 'Failed to load insights';
          try {
            const errorData = await response.json();
            errorMessage = errorData.detail || errorMessage;
          } catch (e) {
            // If JSON parsing fails, use default error message
          }
          throw new Error(errorMessage);
        }

        const data = await response.json();
        console.log('Insights API response:', data);

        // Transform the real data for visualization
        const transformedData = transformAnalysisData(data);
        
        console.log('Transformed data:', transformedData);
        
        if (transformedData && transformedData.technical_analysis && Object.keys(transformedData.technical_analysis).length > 0) {
          setInsights(transformedData);
          console.log('✅ Insights set successfully:', transformedData);
        } else {
          console.log('❌ No valid analysis data found in response:', data);
          setError('No analysis data available. Please run an analysis first.');
        }

        setLoading(false);
      } catch (err) {
        console.error('Error fetching project insights:', err);
        const errorMessage = err instanceof Error ? err.message : 'Failed to load insights';
        
        // Provide more specific error messages based on the error type
        if (errorMessage.includes('404')) {
          setError('No analysis found for this project. Please run an analysis first.');
        } else if (errorMessage.includes('403')) {
          setError('You do not have permission to view these insights.');
        } else if (errorMessage.includes('500')) {
          setError('Server error while loading insights. Please try again later.');
        } else if (errorMessage.includes('NetworkError') || errorMessage.includes('fetch')) {
          setError('Network error. Please check your connection and try again.');
        } else {
          setError(errorMessage);
        }
        
        setLoading(false);
      }
    };

    fetchInsights();
  }, [projectId, projectStatus]);

  console.log('🎯 Project status check:', { projectStatus, shouldShow: projectStatus === 'completed' || projectStatus === 'analyzing' });
  
  if (projectStatus !== 'completed' && projectStatus !== 'analyzing') {
    console.log('🚫 Hiding insights - project status not completed/analyzing:', projectStatus);
    return (
      <div className="bg-white shadow rounded-lg p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Project Insights Dashboard</h3>
          <p className="text-gray-500 mb-4">
            Insights will be available after project analysis is complete.
          </p>
          <p className="text-xs text-gray-400">
            Current status: {projectStatus}
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <svg className="animate-spin h-10 w-10 text-blue-600 mx-auto mb-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          <p className="text-gray-500 mb-2">Loading project insights...</p>
          <p className="text-sm text-gray-400">This may take a few moments</p>
        </div>
      </div>
    );
  }

  // Handle error state
  if (error) {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-[600px] flex items-center justify-center">
        <div className="text-center max-w-md">
          <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Error Loading Insights</h3>
          <p className="text-gray-500 mb-4">{error}</p>
          <button 
            onClick={() => {
              setError(null);
              setLoading(true);
              // Trigger a refetch by changing the key or calling the effect again
              window.location.reload();
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!insights) {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <DocumentTextIcon className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Insights Available</h3>
          <p className="text-gray-500 mb-4">
            {projectStatus === 'analyzing' 
              ? 'Analysis is in progress. Insights will appear here once complete.' 
              : 'No analysis has been run for this project yet.'}
          </p>
          {projectStatus !== 'analyzing' && (
            <p className="text-sm text-gray-400">
              Upload documents and run an analysis to see insights
            </p>
          )}
        </div>
      </div>
    );
  }

  // Prepare data for visualizations using real analysis data
  const techStackData = insights.technical_analysis?.tech_stack 
    ? Object.entries(insights.technical_analysis.tech_stack).map(([category, techs]: [string, any]) => ({
        category: category.charAt(0).toUpperCase() + category.slice(1),
        count: Array.isArray(techs) ? techs.length : 0,
        technologies: Array.isArray(techs) ? techs : []
      }))
    : [];

  const qualityMetrics = [
    { metric: 'Complexity', score: insights.technical_analysis?.complexity_score || 0 },
    { metric: 'Maintainability', score: insights.technical_analysis?.maintainability_score || 0 },
    { metric: 'Scalability', score: insights.technical_analysis?.scalability_score || 0 },
    { metric: 'Performance', score: insights.technical_analysis?.performance_score || 0 },
    { metric: 'Security', score: insights.technical_analysis?.security_score || 0 }
  ].filter(metric => metric.score > 0); // Only show metrics with actual scores

  const riskMatrix = insights.risk_assessment?.key_risks 
    ? insights.risk_assessment.key_risks.map((risk: any) => ({
        name: risk.name,
        level: risk.level,
        impact: risk.impact,
        probability: risk.probability,
        riskScore: (risk.impact * risk.probability) / 10,
        description: risk.description
      }))
    : [];

  const projectPhases = insights.project_plan?.phases || [];
  const effortData = insights.project_plan?.effort_distribution || [];
  const milestones = insights.project_plan?.milestones || [];
  const resourceRequirements = insights.project_plan?.resource_requirements || {};

  return (
    <div className="bg-white shadow rounded-lg overflow-hidden h-[800px] flex flex-col">
      <div className="px-4 py-5 sm:px-6 border-b border-gray-200">
        <h3 className="text-lg font-medium text-gray-900">Project Insights Dashboard</h3>
        <p className="mt-1 text-sm text-gray-500">
          Comprehensive analysis and recommendations for your project
        </p>
      </div>

      {/* Enhanced Tabs */}
      <div className="border-b border-gray-200 bg-gray-50">
        <nav className="flex overflow-x-auto">
          <button
            onClick={() => setActiveSection('overview')}
            className={`py-3 px-4 text-sm font-medium whitespace-nowrap ${
              activeSection === 'overview'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center">
              <ChartBarIcon className="w-4 h-4 mr-1" />
              Overview
            </div>
          </button>
          <button
            onClick={() => setActiveSection('technical')}
            className={`py-3 px-4 text-sm font-medium whitespace-nowrap ${
              activeSection === 'technical'
                ? 'border-b-2 border-blue-500 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center">
              <CpuChipIcon className="w-4 h-4 mr-1" />
              Technical Analysis
            </div>
          </button>
          <button
            onClick={() => setActiveSection('risk')}
            className={`py-3 px-4 text-sm font-medium whitespace-nowrap ${
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
            className={`py-3 px-4 text-sm font-medium whitespace-nowrap ${
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
          <button
            onClick={() => setActiveSection('resources')}
            className={`py-3 px-4 text-sm font-medium whitespace-nowrap ${
              activeSection === 'resources'
                ? 'border-b-2 border-purple-500 text-purple-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <div className="flex items-center">
              <UserGroupIcon className="w-4 h-4 mr-1" />
              Resources
            </div>
          </button>
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {activeSection === 'overview' && (
          <div className="space-y-6">
            {/* Key Metrics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-blue-600 font-medium">Project Duration</p>
                    <p className="text-2xl font-bold text-blue-900">{insights.project_plan?.timeline || 'TBD'}</p>
                  </div>
                  <ClockIcon className="w-8 h-8 text-blue-400" />
                </div>
              </div>
              <div className="bg-green-50 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-green-600 font-medium">Team Size</p>
                    <p className="text-2xl font-bold text-green-900">
                      {resourceRequirements && Object.keys(resourceRequirements).length > 0
                        ? Object.values(resourceRequirements).reduce((a: number, b: any) => {
                            if (typeof b === 'number') return a + b;
                            if (typeof b === 'object' && b !== null) {
                              return a + Object.values(b).reduce((sum: number, val: any) => sum + (typeof val === 'number' ? val : 0), 0);
                            }
                            return a;
                          }, 0)
                        : 0} people
                    </p>
                  </div>
                  <UserGroupIcon className="w-8 h-8 text-green-400" />
                </div>
              </div>
              <div className="bg-purple-50 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-purple-600 font-medium">Estimated Cost</p>
                    <p className="text-2xl font-bold text-purple-900">
                      {insights.project_plan?.estimated_cost 
                        ? insights.project_plan.estimated_cost >= 1000
                          ? `$${(insights.project_plan.estimated_cost / 1000).toFixed(1)}k`
                          : `$${insights.project_plan.estimated_cost}`
                        : '$0'}
                    </p>
                  </div>
                  <CurrencyDollarIcon className="w-8 h-8 text-purple-400" />
                </div>
              </div>
              <div className="bg-amber-50 rounded-lg p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-amber-600 font-medium">Risk Score</p>
                    <p className="text-2xl font-bold text-amber-900">
                      {insights.risk_assessment?.overall_risk_score 
                        ? insights.risk_assessment.overall_risk_score.toFixed(1)
                        : '0.0'}/10
                    </p>
                  </div>
                  <ExclamationTriangleIcon className="w-8 h-8 text-amber-400" />
                </div>
              </div>
            </div>

            {/* Quality Metrics Radar Chart */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Project Quality Metrics</h4>
              {qualityMetrics.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <RadarChart data={qualityMetrics}>
                    <PolarGrid strokeDasharray="3 3" />
                    <PolarAngleAxis dataKey="metric" />
                    <PolarRadiusAxis angle={90} domain={[0, 10]} />
                    <Radar name="Score" dataKey="score" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.6} />
                    <Tooltip />
                  </RadarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-60 text-gray-500">
                  <div className="text-center">
                    <ChartBarIcon className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                    <p>No quality metrics available</p>
                  </div>
                </div>
              )}
            </div>

            {/* Project Phases Overview */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Project Phases Overview</h4>
              {projectPhases.length > 0 ? (
                <div className="space-y-3">
                  {projectPhases.map((phase: any, index: number) => (
                    <div key={index}>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="font-medium">{phase.name}</span>
                        <span className="text-gray-500">
                          {phase.duration ? `${phase.duration} weeks` : `${phase.progress || 0}%`}
                        </span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${phase.progress || 0}%` }}
                        />
                      </div>
                      {phase.description && (
                        <p className="text-xs text-gray-600 mt-1">{phase.description}</p>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-center h-32 text-gray-500">
                  <div className="text-center">
                    <ClockIcon className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                    <p>No project phases defined</p>
                  </div>
                </div>
              )}
            </div>

            {/* Recent Recommendations */}
            {insights.recommendations && insights.recommendations.length > 0 && (
              <div className="bg-white border rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Key Recommendations</h4>
                <div className="space-y-3">
                  {insights.recommendations.slice(0, 5).map((recommendation: string, index: number) => (
                    <div key={index} className="flex items-start">
                      <BoltIcon className="w-5 h-5 text-yellow-500 mr-3 flex-shrink-0 mt-0.5" />
                      <p className="text-gray-700 text-sm">{recommendation}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeSection === 'technical' && (
          <div className="space-y-6">
            {/* Architecture Overview */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Architecture Overview</h4>
              {insights.technical_analysis?.architecture ? (
                <p className="text-gray-700 mb-4">{insights.technical_analysis.architecture}</p>
              ) : (
                <p className="text-gray-500 italic mb-4">No architecture description available</p>
              )}

              {/* Tech Stack Distribution */}
              {techStackData.length > 0 && (
                <div className="mt-6">
                  <h5 className="text-md font-medium text-gray-800 mb-3">Technology Stack Distribution</h5>
                  <ResponsiveContainer width="100%" height={250}>
                    <BarChart data={techStackData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="category" />
                      <YAxis />
                      <Tooltip formatter={(value, name) => [value, 'Count']} />
                      <Bar dataKey="count" fill="#3B82F6">
                        {techStackData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            {/* Quality Scores */}
            {qualityMetrics.length > 0 && (
              <div className="bg-white border rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Technical Quality Scores</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {qualityMetrics.map((metric, index) => (
                    <div key={metric.metric} className="bg-gray-50 rounded-lg p-4">
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-medium text-gray-700">{metric.metric}</span>
                        <span className="text-lg font-bold text-gray-900">{metric.score.toFixed(1)}/10</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div 
                          className="h-2 rounded-full transition-all duration-300"
                          style={{ 
                            width: `${(metric.score / 10) * 100}%`,
                            backgroundColor: metric.score >= 8 ? '#10B981' : metric.score >= 6 ? '#F59E0B' : '#EF4444'
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tech Stack Details */}
            {insights.technical_analysis?.tech_stack && Object.keys(insights.technical_analysis.tech_stack).length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {Object.entries(insights.technical_analysis.tech_stack).map(([category, techs]: [string, any]) => (
                  <div key={category} className="bg-white border rounded-lg p-4">
                    <h5 className="font-medium text-gray-900 mb-3 capitalize flex items-center">
                      <CpuChipIcon className="w-5 h-5 mr-2 text-blue-500" />
                      {category.replace('_', ' ')}
                    </h5>
                    <div className="flex flex-wrap gap-2">
                      {Array.isArray(techs) && techs.length > 0 ? (
                        techs.map((tech: string, index: number) => (
                          <span key={index} className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                            {tech}
                          </span>
                        ))
                      ) : (
                        <span className="text-gray-500 italic text-sm">No technologies specified</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-white border rounded-lg p-6">
                <div className="text-center text-gray-500">
                  <CpuChipIcon className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                  <p>No technology stack information available</p>
                </div>
              </div>
            )}
          </div>
        )}

        {activeSection === 'risk' && (
          <div className="space-y-6">
            {/* Risk Matrix */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Risk Assessment Matrix</h4>
              {riskMatrix.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={riskMatrix} layout="horizontal">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" domain={[0, 10]} />
                    <YAxis dataKey="name" type="category" width={120} />
                    <Tooltip formatter={(value, name) => [value, name === 'impact' ? 'Impact' : 'Probability']} />
                    <Legend />
                    <Bar dataKey="impact" fill="#EF4444" name="Impact" />
                    <Bar dataKey="probability" fill="#F59E0B" name="Probability" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-60 text-gray-500">
                  <div className="text-center">
                    <ExclamationTriangleIcon className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                    <p>No risk assessment data available</p>
                  </div>
                </div>
              )}
            </div>

            {/* Overall Risk Score */}
            {insights.risk_assessment?.overall_risk_score && (
              <div className="bg-white border rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Overall Risk Assessment</h4>
                <div className="flex items-center justify-center">
                  <div className="text-center">
                    <div className={`text-6xl font-bold mb-2 ${
                      insights.risk_assessment.overall_risk_score >= 8 ? 'text-red-600' :
                      insights.risk_assessment.overall_risk_score >= 6 ? 'text-amber-600' :
                      insights.risk_assessment.overall_risk_score >= 4 ? 'text-yellow-600' :
                      'text-green-600'
                    }`}>
                      {insights.risk_assessment.overall_risk_score.toFixed(1)}
                    </div>
                    <div className="text-gray-500 text-lg">out of 10</div>
                    <div className={`text-sm font-medium mt-2 ${
                      insights.risk_assessment.overall_risk_score >= 8 ? 'text-red-600' :
                      insights.risk_assessment.overall_risk_score >= 6 ? 'text-amber-600' :
                      insights.risk_assessment.overall_risk_score >= 4 ? 'text-yellow-600' :
                      'text-green-600'
                    }`}>
                      {insights.risk_assessment.overall_risk_score >= 8 ? 'High Risk' :
                       insights.risk_assessment.overall_risk_score >= 6 ? 'Medium Risk' :
                       insights.risk_assessment.overall_risk_score >= 4 ? 'Low-Medium Risk' :
                       'Low Risk'}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Risk Details */}
            {riskMatrix.length > 0 && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {riskMatrix.map((risk: any, index: number) => (
                  <div key={index} className={`border rounded-lg p-4 ${
                    risk.level === 'High' || risk.level === 'HIGH' ? 'bg-red-50 border-red-200' :
                    risk.level === 'Medium' || risk.level === 'MEDIUM' ? 'bg-amber-50 border-amber-200' :
                    'bg-green-50 border-green-200'
                  }`}>
                    <div className="flex justify-between items-start mb-2">
                      <h5 className="font-medium text-gray-900">{risk.name}</h5>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        risk.level === 'High' || risk.level === 'HIGH' ? 'bg-red-100 text-red-700' :
                        risk.level === 'Medium' || risk.level === 'MEDIUM' ? 'bg-amber-100 text-amber-700' :
                        'bg-green-100 text-green-700'
                      }`}>
                        {risk.level} Risk
                      </span>
                    </div>
                    {risk.description && (
                      <p className="text-sm text-gray-600 mb-3">{risk.description}</p>
                    )}
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <span className="text-gray-500">Impact:</span>
                        <span className="ml-2 font-medium">{risk.impact}/10</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Probability:</span>
                        <span className="ml-2 font-medium">{risk.probability}/10</span>
                      </div>
                    </div>
                    <div className="mt-2 text-sm">
                      <span className="text-gray-500">Risk Score:</span>
                      <span className="ml-2 font-medium">{risk.riskScore.toFixed(1)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Mitigation Strategies */}
            {insights.risk_assessment?.mitigation_strategies && insights.risk_assessment.mitigation_strategies.length > 0 && (
              <div className="bg-white border rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Mitigation Strategies</h4>
                <ul className="space-y-2">
                  {insights.risk_assessment.mitigation_strategies.map((strategy: string, index: number) => (
                    <li key={index} className="flex items-start">
                      <ShieldCheckIcon className="w-5 h-5 text-green-500 mr-2 flex-shrink-0 mt-0.5" />
                      <span className="text-gray-700">{strategy}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {activeSection === 'plan' && (
          <div className="space-y-6">
            {/* Project Timeline Overview */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Project Timeline</h4>
              {insights.project_plan?.timeline && (
                <div className="mb-4 p-3 bg-blue-50 rounded-lg">
                  <p className="text-blue-800 font-medium">{insights.project_plan.timeline}</p>
                </div>
              )}
              {projectPhases.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={projectPhases} layout="horizontal">
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis type="number" domain={[0, 'dataMax']} label={{ value: 'Weeks', position: 'insideBottom', offset: -5 }} />
                    <YAxis dataKey="name" type="category" width={120} />
                    <Tooltip formatter={(value) => [`${value} weeks`, 'Duration']} />
                    <Bar dataKey="duration" fill="#10B981" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-60 text-gray-500">
                  <div className="text-center">
                    <ClockIcon className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                    <p>No project timeline data available</p>
                  </div>
                </div>
              )}
            </div>

            {/* Milestones */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Key Milestones</h4>
              {milestones.length > 0 ? (
                <div className="space-y-3">
                  {milestones.map((milestone: any, index: number) => (
                    <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                      <div className="flex items-center">
                        <div className={`w-3 h-3 rounded-full mr-3 ${
                          milestone.status === 'completed' ? 'bg-green-500' :
                          milestone.status === 'in-progress' || milestone.status === 'in_progress' ? 'bg-blue-500' :
                          'bg-gray-300'
                        }`} />
                        <div>
                          <p className="font-medium text-gray-900">{milestone.name}</p>
                          <p className="text-sm text-gray-500">{milestone.date}</p>
                          {milestone.description && (
                            <p className="text-xs text-gray-600 mt-1">{milestone.description}</p>
                          )}
                        </div>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        milestone.status === 'completed' ? 'bg-green-100 text-green-700' :
                        milestone.status === 'in-progress' || milestone.status === 'in_progress' ? 'bg-blue-100 text-blue-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {milestone.status.replace('-', ' ').replace('_', ' ')}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center text-gray-500">
                  <CheckCircleIcon className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                  <p>No milestones defined</p>
                </div>
              )}
            </div>

            {/* Cost Information - Debug Version */}
            {(() => {
              console.log('💰 Cost Debug Info:');
              console.log('insights.project_plan:', insights.project_plan);
              console.log('estimated_cost value:', insights.project_plan?.estimated_cost);
              console.log('estimated_cost type:', typeof insights.project_plan?.estimated_cost);
              console.log('estimated_cost != null:', insights.project_plan?.estimated_cost != null);
              console.log('estimated_cost !== "":', insights.project_plan?.estimated_cost !== '');
              
              const shouldShow = insights.project_plan?.estimated_cost != null && insights.project_plan.estimated_cost !== '';
              console.log('Should show cost section:', shouldShow);
              
              return shouldShow ? (
                <div className="bg-white border rounded-lg p-6">
                  <h4 className="text-lg font-medium text-gray-900 mb-4">Cost Estimation</h4>
                  <div className="text-center">
                    <div className="text-4xl font-bold text-green-600 mb-2">
                      ${typeof insights.project_plan.estimated_cost === 'string' 
                        ? insights.project_plan.estimated_cost.replace(/\$|,/g, '').replace(/[^\d]/g, '') 
                          ? Number(insights.project_plan.estimated_cost.replace(/\$|,/g, '').replace(/[^\d]/g, '')).toLocaleString()
                          : insights.project_plan.estimated_cost
                        : insights.project_plan.estimated_cost.toLocaleString()}
                    </div>
                    <p className="text-gray-500">Total Estimated Cost</p>
                  </div>
                </div>
              ) : (
                <div className="bg-red-50 border border-red-200 rounded-lg p-6">
                  <h4 className="text-lg font-medium text-red-900 mb-4">Cost Debug Info</h4>
                  <div className="text-sm text-red-700">
                    <p>Cost value: {JSON.stringify(insights.project_plan?.estimated_cost)}</p>
                    <p>Type: {typeof insights.project_plan?.estimated_cost}</p>
                    <p>Project plan exists: {JSON.stringify(!!insights.project_plan)}</p>
                  </div>
                </div>
              );
            })()}
          </div>
        )}

        {activeSection === 'resources' && (
          <div className="space-y-6">
            {/* Team Composition */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Team Composition</h4>
              {resourceRequirements && Object.keys(resourceRequirements).length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <PieChart>
                    <Pie
                      data={Object.entries(resourceRequirements)
                        .filter(([role, count]) => typeof count === 'number' && count > 0)
                        .map(([role, count]) => ({
                          name: role.charAt(0).toUpperCase() + role.slice(1).replace('_', ' '),
                          value: count
                        }))}
                      cx="50%"
                      cy="50%"
                      labelLine={false}
                      label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                      outerRadius={80}
                      fill="#8884d8"
                      dataKey="value"
                    >
                      {Object.entries(resourceRequirements)
                        .filter(([role, count]) => typeof count === 'number' && count > 0)
                        .map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                    </Pie>
                    <Tooltip />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex items-center justify-center h-60 text-gray-500">
                  <div className="text-center">
                    <UserGroupIcon className="w-12 h-12 mx-auto mb-2 text-gray-300" />
                    <p>No resource requirements specified</p>
                  </div>
                </div>
              )}
            </div>

            {/* Effort Distribution */}
            {effortData.length > 0 && (
              <div className="bg-white border rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Effort Distribution by Component</h4>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={effortData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="component" />
                    <YAxis label={{ value: 'Effort %', angle: -90, position: 'insideLeft' }} />
                    <Tooltip formatter={(value) => [`${value}%`, 'Effort']} />
                    <Area type="monotone" dataKey="effort" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.6} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Resource Details */}
            {resourceRequirements && Object.keys(resourceRequirements).length > 0 && (
              <div className="bg-white border rounded-lg p-6">
                <h4 className="text-lg font-medium text-gray-900 mb-4">Resource Requirements</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  {Object.entries(resourceRequirements).map(([role, count]) => {
                    if (typeof count !== 'number' || count === 0) return null;
                    return (
                      <div key={role} className="bg-gray-50 rounded-lg p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-gray-600 capitalize">
                              {role.replace('_', ' ')}
                            </p>
                            <p className="text-2xl font-bold text-gray-900">{count as number}</p>
                          </div>
                          <UserGroupIcon className="w-8 h-8 text-gray-400" />
                        </div>
                      </div>
                    );
                  })}
                  
                  {/* Handle 'other' resources if they exist */}
                  {resourceRequirements.other && typeof resourceRequirements.other === 'object' && (
                    Object.entries(resourceRequirements.other).map(([role, count]) => (
                      <div key={role} className="bg-gray-50 rounded-lg p-4">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm text-gray-600 capitalize">
                              {role.replace('_', ' ')}
                            </p>
                            <p className="text-2xl font-bold text-gray-900">{count as number}</p>
                          </div>
                          <UserGroupIcon className="w-8 h-8 text-gray-400" />
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-3 bg-gray-50 flex justify-end items-center sm:px-6 border-t border-gray-200">
        <div className="text-sm text-gray-500">
          {insights?.analysis_id && (
            <span>Analysis ID: {insights.analysis_id}</span>
          )}
          {insights?.version && (
            <span className="ml-4">Version: {insights.version}</span>
          )}
          {insights?.updated_at && (
            <span className="ml-4">Updated: {new Date(insights.updated_at).toLocaleDateString()}</span>
          )}
        </div>
      </div>
    </div>
  );
}
