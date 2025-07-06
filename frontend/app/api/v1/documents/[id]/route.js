import { API_ENDPOINTS, apiRequest } from '../../../config';

export const dynamic = 'force-dynamic';

export async function GET(request, { params }) {
  try {
    const { id } = params;
    console.log(`Next.js API route: Fetching document with ID: ${id}`);
    
    // Try direct backend call if apiRequest fails
    try {
      const data = await apiRequest(API_ENDPOINTS.DOCUMENTS.GET(id));
      console.log(`Next.js API route: Document fetched successfully: ${JSON.stringify(data)}`);
      return Response.json(data);
    } catch (apiError) {
      console.error(`Next.js API route: apiRequest failed for document ${id}:`, apiError);
      
      // Try direct fetch as fallback
      console.log(`Next.js API route: Trying direct fetch for document ${id}`);
      const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const directResponse = await fetch(`${backendUrl}/api/v1/documents/${id}`);
      
      if (!directResponse.ok) {
        throw new Error(`Backend returned ${directResponse.status} for document ${id}`);
      }
      
      const directData = await directResponse.json();
      console.log(`Next.js API route: Direct fetch successful: ${JSON.stringify(directData)}`);
      return Response.json(directData);
    }
  } catch (error) {
    console.error(`Next.js API route: All attempts failed for document ${params.id}:`, error);
    return Response.json(
      { detail: error.message || 'Failed to fetch document', status: 'error' },
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
