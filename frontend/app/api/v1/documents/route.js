import { API_ENDPOINTS, apiRequest, uploadFile } from '../../config';

export async function GET(request) {
  try {
    // Get project_id from query params if provided
    const { searchParams } = new URL(request.url);
    const projectId = searchParams.get('project_id');
    
    let url = API_ENDPOINTS.DOCUMENTS.LIST;
    if (projectId) {
      url = `${url}?project_id=${projectId}`;
    }
    
    const data = await apiRequest(url);
    return Response.json(data);
  } catch (error) {
    console.error('Error fetching documents:', error);
    return Response.json(
      { detail: error.message || 'Failed to fetch documents' },
      { status: 500 }
    );
  }
}

export async function POST(request) {
  try {
    // For file uploads, we need to handle FormData
    const formData = await request.formData();
    
    // Get project_id from FormData if provided
    const projectId = formData.get('project_id');
    
    // Upload the file(s)
    const data = await uploadFile(API_ENDPOINTS.DOCUMENTS.UPLOAD, formData);
    return Response.json(data);
  } catch (error) {
    console.error('Error uploading document:', error);
    return Response.json(
      { detail: error.message || 'Failed to upload document' },
      { status: 500 }
    );
  }
}
