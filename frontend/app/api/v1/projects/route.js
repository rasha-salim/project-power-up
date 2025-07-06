import { API_ENDPOINTS, apiRequest } from '../../config';

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const data = await apiRequest(API_ENDPOINTS.PROJECTS.LIST);
    return Response.json(data);
  } catch (error) {
    console.error('Error fetching projects:', error);
    return Response.json(
      { detail: error.message || 'Failed to fetch projects' },
      { status: 500 }
    );
  }
}

export async function POST(request) {
  try {
    const body = await request.json();
    const data = await apiRequest(API_ENDPOINTS.PROJECTS.CREATE, {
      method: 'POST',
      body: JSON.stringify(body),
    });
    return Response.json(data);
  } catch (error) {
    console.error('Error creating project:', error);
    return Response.json(
      { detail: error.message || 'Failed to create project' },
      { status: 500 }
    );
  }
}
