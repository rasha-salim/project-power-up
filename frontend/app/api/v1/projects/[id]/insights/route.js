import { API_ENDPOINTS, apiRequest } from '../../../../config';

export async function GET(request, { params }) {
  try {
    const { id } = params;
    
    // Get the project to check if it has insights
    const project = await apiRequest(API_ENDPOINTS.PROJECTS.GET(id));
    
    if (!project.insights) {
      // If no insights are available, check if there's an analysis in progress
      if (project.status === 'analyzing') {
        return Response.json({
          status: 'analyzing',
          message: 'Analysis in progress. Insights will be available when complete.'
        });
      } else if (project.status === 'draft') {
        return Response.json({
          status: 'not_started',
          message: 'No analysis has been started for this project.'
        });
      }
      
      // If status is completed but no insights, something went wrong
      return Response.json({
        status: 'error',
        message: 'No insights available. Please try running the analysis again.'
      });
    }
    
    // Return the insights
    return Response.json({
      status: 'completed',
      insights: project.insights
    });
  } catch (error) {
    console.error(`Error fetching insights for project ${params.id}:`, error);
    return Response.json(
      { detail: error.message || 'Failed to fetch project insights' },
      { status: 500 }
    );
  }
}
