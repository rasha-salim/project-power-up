import { API_ENDPOINTS, apiRequest } from '../../../../config';

export async function POST(request, { params }) {
  try {
    const { id } = params;
    // Call the backend API to start the analysis
    const response = await fetch(`${API_ENDPOINTS.PROJECTS.GET(id)}/analyze`, {
      method: 'POST',
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Analysis request failed');
    }
    
    const data = await response.json();
    return Response.json(data);
  } catch (error) {
    console.error(`Error starting analysis for project ${params.id}:`, error);
    return Response.json(
      { detail: error.message || 'Failed to start project analysis' },
      { status: 500 }
    );
  }
}
