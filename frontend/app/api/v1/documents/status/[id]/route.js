import { API_ENDPOINTS, apiRequest } from '../../../../../../config';

export async function GET(request, { params }) {
  try {
    const { id } = params;
    console.log(`Next.js API route: Fetching document status with ID: ${id}`);
    
    // Try direct backend call
    try {
      const response = await fetch(`http://localhost:8000/api/v1/documents/status/${id}`);
      
      if (!response.ok) {
        if (response.status === 404) {
          return Response.json(
            { error: 'Document not found' },
            { status: 404 }
          );
        }
        throw new Error(`Backend returned ${response.status}`);
      }
      
      const data = await response.json();
      console.log(`Next.js API route: Document status fetched successfully`);
      return Response.json(data);
    } catch (fetchError) {
      console.error(`Next.js API route: Failed to fetch document status ${id}:`, fetchError);
      throw fetchError;
    }
  } catch (error) {
    console.error(`Next.js API route: Error for document status ${params.id}:`, error);
    return Response.json(
      { error: 'Failed to fetch document status', details: error.message },
      { status: 500 }
    );
  }
}
