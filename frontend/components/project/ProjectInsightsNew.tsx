'use client';

import InsightsTab from '../../src/components/InsightsTab';

interface ProjectInsightsProps {
  projectId: string;
  projectStatus: string;
  projectInsights?: any;
}

export default function ProjectInsights({ projectId, projectStatus, projectInsights }: ProjectInsightsProps) {
  return <InsightsTab projectId={projectId} />;
}
