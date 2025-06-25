import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Alert, AlertDescription } from './ui/alert';
import { 
  Code2, 
  Shield, 
  TrendingUp, 
  AlertTriangle, 
  Calendar,
  Users,
  DollarSign,
  CheckCircle,
  Clock,
  Layers,
  Zap,
  Lock,
  BarChart3,
  Info
} from 'lucide-react';

interface InsightsTabProps {
  projectId: string;
}

interface TechnicalAnalysis {
  analysis_id: string;
  project_id: string;
  version: number;
  technical_analysis: {
    architecture: string;
    tech_stack: {
      frontend: string[];
      backend: string[];
      infrastructure: string[];
      tools: string[];
    };
    complexity_score: number;
    maintainability_score: number;
    scalability_score: number;
    performance_score: number;
    security_score: number;
  };
  risk_assessment: {
    key_risks: string[];
    overall_risk_score: number;
    mitigation_strategies: string[];
  };
  project_plan: {
    timeline: string;
    phases: string[];
    milestones: string[];
    resource_requirements: {
      developers: number;
      designers: number;
      qa: number;
      devops: number;
      pm: number;
      other: Record<string, number>;
    };
    estimated_cost: number;
    effort_distribution: string[];
  };
  recommendations: string[];
  created_at: string;
  updated_at: string;
}

const InsightsTab: React.FC<InsightsTabProps> = ({ projectId }) => {
  const [insights, setInsights] = useState<TechnicalAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchInsights();
  }, [projectId]);

  const fetchInsights = async () => {
    try {
      setLoading(true);
      const response = await fetch(`/api/v1/insights/${projectId}`);
      if (!response.ok) throw new Error('Failed to fetch insights');
      const data = await response.json();
      setInsights(data.technical_analysis);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load insights');
    } finally {
      setLoading(false);
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 8) return 'text-green-600';
    if (score >= 6) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getScoreBgColor = (score: number) => {
    if (score >= 8) return 'bg-green-100';
    if (score >= 6) return 'bg-yellow-100';
    return 'bg-red-100';
  };

  const getRiskColor = (score: number) => {
    if (score <= 4) return 'text-green-600';
    if (score <= 7) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getRiskBgColor = (score: number) => {
    if (score <= 4) return 'bg-green-100';
    if (score <= 7) return 'bg-yellow-100';
    return 'bg-red-100';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error || !insights) {
    return (
      <Alert className="m-4">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>
          {error || 'No insights available for this project yet.'}
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <Tabs defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="technical">Technical</TabsTrigger>
          <TabsTrigger value="risks">Risks</TabsTrigger>
          <TabsTrigger value="planning">Planning</TabsTrigger>
          <TabsTrigger value="other">Other Insights</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6 mt-6">
          {/* Architecture Overview */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Layers className="h-5 w-5" />
                Architecture Overview
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-lg font-medium mb-4">{insights.technical_analysis.architecture}</p>
              
              {/* Score Cards */}
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mt-6">
                {[
                  { label: 'Complexity', score: insights.technical_analysis.complexity_score, icon: Code2 },
                  { label: 'Maintainability', score: insights.technical_analysis.maintainability_score, icon: Shield },
                  { label: 'Scalability', score: insights.technical_analysis.scalability_score, icon: TrendingUp },
                  { label: 'Performance', score: insights.technical_analysis.performance_score, icon: Zap },
                  { label: 'Security', score: insights.technical_analysis.security_score, icon: Lock }
                ].map((item) => (
                  <div key={item.label} className="text-center">
                    <div className={`rounded-lg p-4 ${getScoreBgColor(item.score)}`}>
                      <item.icon className={`h-8 w-8 mx-auto mb-2 ${getScoreColor(item.score)}`} />
                      <div className={`text-2xl font-bold ${getScoreColor(item.score)}`}>
                        {item.score}/10
                      </div>
                      <div className="text-sm text-gray-600 mt-1">{item.label}</div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Key Recommendations */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5" />
                Key Recommendations
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-3">
                {insights.recommendations.slice(0, 5).map((rec, index) => (
                  <li key={index} className="flex items-start gap-3">
                    <CheckCircle className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                    <span className="text-gray-700">{rec}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="technical" className="space-y-6 mt-6">
          {/* Tech Stack */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Code2 className="h-5 w-5" />
                Technology Stack
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {Object.entries(insights.technical_analysis.tech_stack).map(([category, technologies]) => (
                  <div key={category}>
                    <h4 className="font-semibold text-gray-700 mb-3 capitalize">{category}</h4>
                    <div className="flex flex-wrap gap-2">
                      {technologies.map((tech) => (
                        <Badge key={tech} variant="secondary" className="py-1 px-3">
                          {tech}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Technical Scores Detail */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <BarChart3 className="h-5 w-5" />
                Technical Assessment Details
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                { 
                  label: 'Complexity', 
                  score: insights.technical_analysis.complexity_score,
                  description: 'Overall system complexity and architectural sophistication'
                },
                { 
                  label: 'Maintainability', 
                  score: insights.technical_analysis.maintainability_score,
                  description: 'Ease of maintaining and updating the codebase'
                },
                { 
                  label: 'Scalability', 
                  score: insights.technical_analysis.scalability_score,
                  description: 'Ability to handle growth in users and data'
                },
                { 
                  label: 'Performance', 
                  score: insights.technical_analysis.performance_score,
                  description: 'System responsiveness and efficiency'
                },
                { 
                  label: 'Security', 
                  score: insights.technical_analysis.security_score,
                  description: 'Protection against vulnerabilities and threats'
                }
              ].map((item) => (
                <div key={item.label}>
                  <div className="flex justify-between items-center mb-2">
                    <div>
                      <span className="font-medium">{item.label}</span>
                      <p className="text-sm text-gray-600">{item.description}</p>
                    </div>
                    <span className={`font-bold ${getScoreColor(item.score)}`}>
                      {item.score}/10
                    </span>
                  </div>
                  <Progress value={item.score * 10} className="h-2" />
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="risks" className="space-y-6 mt-6">
          {/* Risk Overview */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <AlertTriangle className="h-5 w-5" />
                Risk Assessment
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className={`text-center p-6 rounded-lg mb-6 ${getRiskBgColor(insights.risk_assessment.overall_risk_score)}`}>
                <div className={`text-4xl font-bold ${getRiskColor(insights.risk_assessment.overall_risk_score)}`}>
                  {insights.risk_assessment.overall_risk_score}/10
                </div>
                <div className="text-gray-600 mt-2">Overall Risk Score</div>
              </div>

              <div className="space-y-4">
                <div>
                  <h4 className="font-semibold mb-3">Key Risks</h4>
                  <ul className="space-y-2">
                    {insights.risk_assessment.key_risks.map((risk, index) => (
                      <li key={index} className="flex items-start gap-3">
                        <AlertTriangle className="h-5 w-5 text-yellow-500 mt-0.5 flex-shrink-0" />
                        <span className="text-gray-700">{risk}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="mt-6">
                  <h4 className="font-semibold mb-3">Mitigation Strategies</h4>
                  <ul className="space-y-2">
                    {insights.risk_assessment.mitigation_strategies.map((strategy, index) => (
                      <li key={index} className="flex items-start gap-3">
                        <Shield className="h-5 w-5 text-green-500 mt-0.5 flex-shrink-0" />
                        <span className="text-gray-700">{strategy}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="planning" className="space-y-6 mt-6">
          {/* Timeline */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5" />
                Project Timeline
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4">
                <Badge variant="outline" className="text-sm">
                  {insights.project_plan.timeline}
                </Badge>
              </div>

              <div className="space-y-4">
                <div>
                  <h4 className="font-semibold mb-3">Project Phases</h4>
                  <div className="space-y-2">
                    {insights.project_plan.phases.map((phase, index) => (
                      <div key={index} className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary text-white flex items-center justify-center text-sm font-semibold">
                          {index + 1}
                        </div>
                        <span className="text-gray-700">{phase}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-6">
                  <h4 className="font-semibold mb-3">Key Milestones</h4>
                  <ul className="space-y-2">
                    {insights.project_plan.milestones.map((milestone, index) => (
                      <li key={index} className="flex items-start gap-3">
                        <Clock className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
                        <span className="text-gray-700">{milestone}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Resources */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Users className="h-5 w-5" />
                Resource Requirements
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
                {Object.entries(insights.project_plan.resource_requirements)
                  .filter(([key]) => key !== 'other')
                  .map(([role, count]) => (
                    <div key={role} className="text-center p-4 bg-gray-50 rounded-lg">
                      <div className="text-2xl font-bold text-primary">{count as number}</div>
                      <div className="text-sm text-gray-600 capitalize">{role}</div>
                    </div>
                  ))}
                {Object.entries(insights.project_plan.resource_requirements.other).map(([role, count]) => (
                  <div key={role} className="text-center p-4 bg-gray-50 rounded-lg">
                    <div className="text-2xl font-bold text-primary">{count}</div>
                    <div className="text-sm text-gray-600 capitalize">{role.replace(/_/g, ' ')}</div>
                  </div>
                ))}
              </div>

              <div className="flex items-center justify-between p-4 bg-blue-50 rounded-lg">
                <div className="flex items-center gap-2">
                  <DollarSign className="h-5 w-5 text-blue-600" />
                  <span className="font-semibold">Estimated Cost</span>
                </div>
                <span className="text-2xl font-bold text-blue-600">
                  ${insights.project_plan.estimated_cost.toLocaleString()}
                </span>
              </div>

              <div className="mt-6">
                <h4 className="font-semibold mb-3">Effort Distribution</h4>
                <div className="space-y-2">
                  {insights.project_plan.effort_distribution.map((item, index) => (
                    <div key={index} className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-primary"></div>
                      <span className="text-gray-700">{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="other" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Info className="h-5 w-5" />
                Additional Insights
              </CardTitle>
            </CardHeader>
            <CardContent>
              <Alert>
                <Info className="h-4 w-4" />
                <AlertDescription>
                  Additional insights from other specialized agents are currently in development. 
                  These will include:
                  <ul className="mt-2 ml-4 list-disc space-y-1">
                    <li>Business Analysis & ROI Projections</li>
                    <li>User Experience & Design Recommendations</li>
                    <li>Market Analysis & Competitive Landscape</li>
                    <li>Legal & Compliance Considerations</li>
                  </ul>
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Version Info */}
      <div className="text-sm text-gray-500 text-center">
        Analysis Version {insights.version} • 
        Last updated: {new Date(insights.updated_at).toLocaleString()}
      </div>
    </div>
  );
};

export default InsightsTab;
