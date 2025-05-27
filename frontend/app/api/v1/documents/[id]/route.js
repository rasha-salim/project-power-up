import { API_ENDPOINTS, apiRequest } from '../../../config';

export async function GET(request, { params }) {
  try {
    const { id } = params;
    const data = await apiRequest(API_ENDPOINTS.DOCUMENTS.GET(id));
    return Response.json(data);
  } catch (error) {
    console.error(`Error fetching document ${params.id}:`, error);
    return Response.json(
      { detail: error.message || 'Failed to fetch document' },
      { status: 500 }
    );
  }
}

export async function DELETE(request, { params }) {
  try {
    const { id } = params;
    const data = await apiRequest(API_ENDPOINTS.DOCUMENTS.DELETE(id), {
      method: 'DELETE',
    });
    return Response.json(data);
  } catch (error) {
    console.error(`Error deleting document ${params.id}:`, error);
    return Response.json(
      { detail: error.message || 'Failed to delete document' },
      { status: 500 }
    );
  }
}
