import { API_ENDPOINTS, apiRequest } from '../../../../config';

export const dynamic = 'force-dynamic';

export async function GET(request, { params }) {
  try {
    const { id } = params;
    
    // Call the backend insights endpoint directly
    const insights = await apiRequest(API_ENDPOINTS.PROJECTS.INSIGHTS(id));
    
    // Return the insights data
    return Response.json(insights);
  } catch (error) {
    console.error(`Error fetching insights for project ${params.id}:`, error);
    
    // Handle specific error cases
    if (error.message.includes('404')) {
      return Response.json(
        { detail: 'No analysis found for this project. Please run an analysis first.' },
        { status: 404 }
      );
    }
    
    return Response.json(
      { detail: error.message || 'Failed to fetch project insights' },
      { status: 500 }
    );
  }
}
