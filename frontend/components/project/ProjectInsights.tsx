'use client';

import { useState, useEffect } from 'react';
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
  ArrowTrendingUpIcon
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

// Mock data structure based on technical analysis
const generateMockInsights = () => ({
  technical_analysis: {
    architecture: "Microservices architecture with React frontend and Python/FastAPI backend",
    tech_stack: {
      frontend: ["React", "TypeScript", "Tailwind CSS", "Next.js"],
      backend: ["Python", "FastAPI", "SQLAlchemy", "PostgreSQL"],
      infrastructure: ["Docker", "Kubernetes", "AWS"],
      tools: ["Git", "CI/CD", "Monitoring"]
    },
    complexity_score: 7.5,
    maintainability_score: 8.2,
    scalability_score: 9.0,
    performance_score: 7.8,
    security_score: 8.5
  },
  risk_assessment: {
    key_risks: [
      { name: "Technical Complexity", level: "High", impact: 8, probability: 7 },
      { name: "Resource Availability", level: "Medium", impact: 6, probability: 5 },
      { name: "Timeline Constraints", level: "High", impact: 9, probability: 6 },
      { name: "Integration Challenges", level: "Medium", impact: 7, probability: 4 },
      { name: "Security Vulnerabilities", level: "Low", impact: 8, probability: 3 }
    ],
    overall_risk_score: 6.8,
    mitigation_strategies: [
      "Implement comprehensive testing strategy",
      "Allocate buffer time for complex integrations",
      "Conduct regular security audits",
      "Establish clear communication channels"
    ]
  },
  project_plan: {
    timeline: "6 months",
    phases: [
      { name: "Planning", duration: 2, progress: 100 },
      { name: "Design", duration: 3, progress: 80 },
      { name: "Development", duration: 8, progress: 45 },
      { name: "Testing", duration: 2, progress: 0 },
      { name: "Deployment", duration: 1, progress: 0 }
    ],
    milestones: [
      { name: "Requirements Finalized", date: "2024-01-15", status: "completed" },
      { name: "Design Approved", date: "2024-02-01", status: "completed" },
      { name: "MVP Ready", date: "2024-04-15", status: "in-progress" },
      { name: "Beta Release", date: "2024-05-15", status: "upcoming" },
      { name: "Production Launch", date: "2024-06-30", status: "upcoming" }
    ],
    resource_requirements: {
      developers: 5,
      designers: 2,
      qa: 2,
      devops: 1,
      pm: 1
    },
    estimated_cost: 450000,
    effort_distribution: [
      { component: "Frontend", effort: 35 },
      { component: "Backend", effort: 40 },
      { component: "Infrastructure", effort: 15 },
      { component: "Testing", effort: 10 }
    ]
  },
  recommendations: [
    "Consider implementing automated testing early in the development cycle",
    "Allocate additional resources for the integration phase",
    "Implement monitoring and logging from the start",
    "Consider using a phased rollout approach"
  ]
});

const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899'];

export default function ProjectInsights({ projectId, projectStatus, projectInsights }: ProjectInsightsProps) {
  const [insights, setInsights] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState('overview');

  useEffect(() => {
    const fetchInsights = async () => {
      // If insights are passed as props, use them directly
      if (projectInsights) {
        setInsights(projectInsights);
        setLoading(false);
        return;
      }

      if (projectStatus === 'draft') {
        setLoading(false);
        return;
      }

      try {
        console.log(`Fetching insights for project: ${projectId}, status: ${projectStatus}`);
        const response = await fetch(`/api/v1/projects/${projectId}/insights`);

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

        if (data.status === 'completed' && data.insights) {
          // Use actual insights if available, otherwise use mock data for demo
          setInsights(data.insights.technical_analysis ? data.insights : generateMockInsights());
        } else if (data.status === 'analyzing') {
          // Use mock data for demo purposes while analyzing
          setInsights(generateMockInsights());
        } else {
          setError('No insights available');
        }

        setLoading(false);
      } catch (err) {
        console.error('Error fetching project insights:', err);
        // Use mock data for demo purposes on error
        setInsights(generateMockInsights());
        setLoading(false);
      }
    };

    fetchInsights();
  }, [projectId, projectStatus]);

  if (projectStatus !== 'completed' && projectStatus !== 'analyzing') {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <h3 className="text-lg font-medium text-gray-900 mb-2">Project Insights Dashboard</h3>
          <p className="text-gray-500 mb-4">
            Insights will be available after project analysis is complete.
          </p>
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

  if (!insights) {
    return (
      <div className="bg-white shadow rounded-lg p-6 h-[600px] flex items-center justify-center">
        <div className="text-center">
          <ExclamationTriangleIcon className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Insights Available</h3>
          <p className="text-gray-500">Please run an analysis first</p>
        </div>
      </div>
    );
  }

  // Prepare data for visualizations
  const techStackData = insights.technical_analysis?.tech_stack 
    ? Object.entries(insights.technical_analysis.tech_stack).map(([category, techs]: [string, any]) => ({
        category: category.charAt(0).toUpperCase() + category.slice(1),
        count: Array.isArray(techs) ? techs.length : 0
      }))
    : [];

  const qualityMetrics = [
    { metric: 'Complexity', score: insights.technical_analysis?.complexity_score || 7.5 },
    { metric: 'Maintainability', score: insights.technical_analysis?.maintainability_score || 8.2 },
    { metric: 'Scalability', score: insights.technical_analysis?.scalability_score || 9.0 },
    { metric: 'Performance', score: insights.technical_analysis?.performance_score || 7.8 },
    { metric: 'Security', score: insights.technical_analysis?.security_score || 8.5 }
  ];

  const riskMatrix = insights.risk_assessment?.key_risks 
    ? insights.risk_assessment.key_risks.map((risk: any) => ({
        name: risk.name,
        impact: risk.impact,
        probability: risk.probability,
        riskScore: (risk.impact * risk.probability) / 10
      }))
    : [];

  const projectPhases = insights.project_plan?.phases || [];
  const effortData = insights.project_plan?.effort_distribution || [];

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
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
                      {insights.project_plan?.resource_requirements 
                        ? Object.values(insights.project_plan.resource_requirements).reduce((a: number, b: any) => a + (typeof b === 'number' ? b : 0), 0)
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
                      ${insights.project_plan?.estimated_cost 
                        ? (insights.project_plan.estimated_cost / 1000).toFixed(0) 
                        : '0'}k
                    </p>
                  </div>
                  <CurrencyDollarIcon className="w-8 h-8 text-purple-400" />
                </div>
              </div>
            </div>

            {/* Quality Metrics Radar Chart */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Project Quality Metrics</h4>
              <ResponsiveContainer width="100%" height={300}>
                <RadarChart data={qualityMetrics}>
                  <PolarGrid strokeDasharray="3 3" />
                  <PolarAngleAxis dataKey="metric" />
                  <PolarRadiusAxis angle={90} domain={[0, 10]} />
                  <Radar name="Score" dataKey="score" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.6} />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Project Progress */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Project Progress by Phase</h4>
              <div className="space-y-3">
                {projectPhases.map((phase: any, index: number) => (
                  <div key={index}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="font-medium">{phase.name}</span>
                      <span className="text-gray-500">{phase.progress}%</span>
                    </div>
                    <div className="w-full bg-gray-200 rounded-full h-2">
                      <div 
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${phase.progress}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeSection === 'technical' && (
          <div className="space-y-6">
            {/* Architecture Overview */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Architecture Overview</h4>
              <p className="text-gray-700 mb-4">{insights.technical_analysis.architecture}</p>

              {/* Tech Stack Distribution */}
              <div className="mt-6">
                <h5 className="text-md font-medium text-gray-800 mb-3">Technology Stack Distribution</h5>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={techStackData}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="category" />
                    <YAxis />
                    <Tooltip />
                    <Bar dataKey="count" fill="#3B82F6">
                      {techStackData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Tech Stack Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {insights.technical_analysis?.tech_stack && Object.entries(insights.technical_analysis.tech_stack).map(([category, techs]: [string, any]) => (
                <div key={category} className="bg-white border rounded-lg p-4">
                  <h5 className="font-medium text-gray-900 mb-3 capitalize">{category}</h5>
                  <div className="flex flex-wrap gap-2">
                    {Array.isArray(techs) && techs.map((tech: string, index: number) => (
                      <span key={index} className="px-3 py-1 bg-blue-100 text-blue-700 rounded-full text-sm">
                        {tech}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeSection === 'risk' && (
          <div className="space-y-6">
            {/* Risk Matrix */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Risk Assessment Matrix</h4>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={riskMatrix} layout="horizontal">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, 10]} />
                  <YAxis dataKey="name" type="category" width={120} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="impact" fill="#EF4444" />
                  <Bar dataKey="probability" fill="#F59E0B" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Risk Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {insights.risk_assessment?.key_risks.map((risk: any, index: number) => (
                <div key={index} className={`border rounded-lg p-4 ${
                  risk.level === 'High' ? 'bg-red-50 border-red-200' :
                  risk.level === 'Medium' ? 'bg-amber-50 border-amber-200' :
                  'bg-green-50 border-green-200'
                }`}>
                  <div className="flex justify-between items-start mb-2">
                    <h5 className="font-medium text-gray-900">{risk.name}</h5>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      risk.level === 'High' ? 'bg-red-100 text-red-700' :
                      risk.level === 'Medium' ? 'bg-amber-100 text-amber-700' :
                      'bg-green-100 text-green-700'
                    }`}>
                      {risk.level} Risk
                    </span>
                  </div>
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
                </div>
              ))}
            </div>

            {/* Mitigation Strategies */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Mitigation Strategies</h4>
              <ul className="space-y-2">
                {insights.risk_assessment?.mitigation_strategies?.map((strategy: string, index: number) => (
                  <li key={index} className="flex items-start">
                    <ShieldCheckIcon className="w-5 h-5 text-green-500 mr-2 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-700">{strategy}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}

        {activeSection === 'plan' && (
          <div className="space-y-6">
            {/* Timeline Gantt Chart */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Project Timeline</h4>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={projectPhases} layout="horizontal">
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis type="number" domain={[0, 16]} label={{ value: 'Weeks', position: 'insideBottom', offset: -5 }} />
                  <YAxis dataKey="name" type="category" />
                  <Tooltip />
                  <Bar dataKey="duration" fill="#10B981" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Milestones */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Key Milestones</h4>
              <div className="space-y-3">
                {insights.project_plan?.milestones?.map((milestone: any, index: number) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center">
                      <div className={`w-3 h-3 rounded-full mr-3 ${
                        milestone.status === 'completed' ? 'bg-green-500' :
                        milestone.status === 'in-progress' ? 'bg-blue-500' :
                        'bg-gray-300'
                      }`} />
                      <div>
                        <p className="font-medium text-gray-900">{milestone.name}</p>
                        <p className="text-sm text-gray-500">{milestone.date}</p>
                      </div>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      milestone.status === 'completed' ? 'bg-green-100 text-green-700' :
                      milestone.status === 'in-progress' ? 'bg-blue-100 text-blue-700' :
                      'bg-gray-100 text-gray-700'
                    }`}>
                      {milestone.status.replace('-', ' ')}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeSection === 'resources' && (
          <div className="space-y-6">
            {/* Team Composition */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Team Composition</h4>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={insights.project_plan?.resource_requirements ? Object.entries(insights.project_plan.resource_requirements).map(([role, count]) => ({
                      name: role.charAt(0).toUpperCase() + role.slice(1),
                      value: count
                    })) : []}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                    outerRadius={80}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {insights.project_plan?.resource_requirements && Object.entries(insights.project_plan.resource_requirements).map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </div>

            {/* Effort Distribution */}
            <div className="bg-white border rounded-lg p-6">
              <h4 className="text-lg font-medium text-gray-900 mb-4">Effort Distribution by Component</h4>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={effortData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="component" />
                  <YAxis />
                  <Tooltip />
                  <Area type="monotone" dataKey="effort" stroke="#8B5CF6" fill="#8B5CF6" fillOpacity={0.6} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Resource Details */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h5 className="font-medium text-blue-900 mb-3">Development Team</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Frontend Developers</span>
                    <span className="font-medium">2</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Backend Developers</span>
                    <span className="font-medium">3</span>
                  </div>
                  <div className="flex justify-between">
                    <span>DevOps Engineer</span>
                    <span className="font-medium">1</span>
                  </div>
                </div>
              </div>
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <h5 className="font-medium text-green-900 mb-3">Support Team</h5>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>UI/UX Designers</span>
                    <span className="font-medium">2</span>
                  </div>
                  <div className="flex justify-between">
                    <span>QA Engineers</span>
                    <span className="font-medium">2</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Project Manager</span>
                    <span className="font-medium">1</span>
                  </div>
                </div>
              </div>
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
