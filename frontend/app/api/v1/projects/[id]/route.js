import { API_ENDPOINTS, apiRequest } from '../../../config';

export async function GET(request, { params }) {
  try {
    const { id } = params;
    const data = await apiRequest(API_ENDPOINTS.PROJECTS.GET(id));
    return Response.json(data);
  } catch (error) {
    console.error(`Error fetching project ${params.id}:`, error);
    return Response.json(
      { detail: error.message || 'Failed to fetch project' },
      { status: 500 }
    );
  }
}

export async function PUT(request, { params }) {
  try {
    const { id } = params;
    const body = await request.json();
    const data = await apiRequest(API_ENDPOINTS.PROJECTS.UPDATE(id), {
      method: 'PUT',
      body: JSON.stringify(body),
    });
    return Response.json(data);
  } catch (error) {
    console.error(`Error updating project ${params.id}:`, error);
    return Response.json(
      { detail: error.message || 'Failed to update project' },
      { status: 500 }
    );
  }
}

export async function DELETE(request, { params }) {
  try {
    const { id } = params;
    const data = await apiRequest(API_ENDPOINTS.PROJECTS.DELETE(id), {
      method: 'DELETE',
    });
    return Response.json(data);
  } catch (error) {
    console.error(`Error deleting project ${params.id}:`, error);
    return Response.json(
      { detail: error.message || 'Failed to delete project' },
      { status: 500 }
    );
  }
}
