import { API_ENDPOINTS, apiRequest } from '../../../../../config';

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
      
      // Try the new /status/{id} endpoint first
      try {
        console.log(`Next.js API route: Trying /status/${id} endpoint`);
        const newEndpointResponse = await fetch(`http://localhost:8000/api/v1/documents/status/${id}`);
        
        if (newEndpointResponse.ok) {
          const data = await newEndpointResponse.json();
          console.log(`Next.js API route: /status/${id} endpoint successful`); 
          return Response.json(data);
        }
        console.log(`Next.js API route: /status/${id} endpoint failed with status ${newEndpointResponse.status}`);
      } catch (e) {
        console.error(`Next.js API route: Error with /status/${id} endpoint:`, e);
      }
      
      // Fall back to the old endpoint format
      console.log(`Next.js API route: Trying /${id}/status endpoint as fallback`);
      const directResponse = await fetch(`http://localhost:8000/api/v1/documents/${id}/status`);
      
      if (!directResponse.ok) {
        throw new Error(`Backend returned ${directResponse.status} for document status ${id}`);
      }
      
      const directData = await directResponse.json();
      console.log(`Next.js API route: Direct fetch successful: ${JSON.stringify(directData)}`);
      return Response.json(directData);
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
