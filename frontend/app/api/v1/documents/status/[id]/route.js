import { API_ENDPOINTS, apiRequest } from '../../../../../../config';

export async function GET(request, { params }) {
  try {
    const { id } = params;
    console.log(`Next.js API route: Fetching document status with ID: ${id}`);
    
    // Try direct backend call if apiRequest fails
    try {
      const data = await apiRequest(API_ENDPOINTS.DOCUMENTS.STATUS(id));
      console.log(`Next.js API route: Document status fetched successfully: ${JSON.stringify(data)}`);
      return Response.json(data);
    } catch (apiError) {
      console.error(`Next.js API route: apiRequest failed for document status ${id}:`, apiError);
      
      // Try direct fetch as fallback
      console.log(`Next.js API route: Trying direct fetch for document status ${id}`);
      const newEndpointResponse = await fetch(`http://localhost:8000/api/v1/documents/status/${id}`);
      
      if (!newEndpointResponse.ok) {
        console.log(`New endpoint failed with ${newEndpointResponse.status}, trying legacy endpoint`);
        const directResponse = await fetch(`http://localhost:8000/api/v1/documents/${id}/status`);
        
        if (!directResponse.ok) {
          throw new Error(`Both endpoints failed. Backend returned ${directResponse.status} for document status ${id}`);
        }
        
        const directData = await directResponse.json();
        console.log(`Next.js API route: Legacy endpoint successful: ${JSON.stringify(directData)}`);
        return Response.json(directData);
      }
      
      const newEndpointData = await newEndpointResponse.json();
      console.log(`Next.js API route: New endpoint successful: ${JSON.stringify(newEndpointData)}`);
      return Response.json(newEndpointData);
    }
  } catch (error) {
    console.error(`Next.js API route: All attempts failed for document status ${params.id}:`, error);
    // Return a default response instead of error to keep polling working
    return Response.json({
      id: params.id,
      filename: "Unknown",
      status: "processing",
      progress: "10",
      message: `Error retrieving status: ${error.message || 'Unknown error'}`,
      status_error: true
    });
  }
}
