// API configuration
const API_BASE_URL = 'http://localhost:8000/api/v1';

export const API_ENDPOINTS = {
  // Document endpoints
  DOCUMENTS: {
    UPLOAD: `${API_BASE_URL}/documents/upload`,
    LIST: `${API_BASE_URL}/documents`,
    GET: (id) => `${API_BASE_URL}/documents/${id}`,
    STATUS: (id) => `${API_BASE_URL}/documents/${id}/status`,
    DELETE: (id) => `${API_BASE_URL}/documents/${id}`,
    PROJECT: (projectId) => `${API_BASE_URL}/documents/project/${projectId}`,
  },
  
  // Project endpoints
  PROJECTS: {
    LIST: `${API_BASE_URL}/projects`,
    GET: (id) => `${API_BASE_URL}/projects/${id}`,
    CREATE: `${API_BASE_URL}/projects`,
    UPDATE: (id) => `${API_BASE_URL}/projects/${id}`,
    DELETE: (id) => `${API_BASE_URL}/projects/${id}`,
    INSIGHTS: (id) => `${API_BASE_URL}/projects/${id}/insights`,
  },
};

// Helper function for API requests
export const apiRequest = async (url, options = {}) => {
  try {
    console.log(`Making API request to: ${url}`);
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });
    
    console.log(`API response status: ${response.status} for ${url}`);
    
    if (!response.ok) {
      let errorDetail = 'API request failed';
      try {
        const errorJson = await response.json();
        errorDetail = errorJson.detail || errorJson.message || 'API request failed';
      } catch (parseError) {
        errorDetail = `API request failed with status ${response.status}`;
      }
      console.error(`API error (${response.status}): ${errorDetail} for ${url}`);
      throw new Error(errorDetail);
    }
    
    const data = await response.json();
    console.log(`API request successful for ${url}`);
    return data;
  } catch (error) {
    console.error(`API request failed for ${url}: ${error.message}`);
    throw error;
  }
};

// Helper function for file uploads
export const uploadFile = async (url, formData, options = {}) => {
  try {
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
      ...options,
      // Don't set Content-Type header for multipart/form-data
      // The browser will set it automatically with the boundary
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'File upload failed');
    }
    
    return await response.json();
  } catch (error) {
    console.error('File upload error:', error);
    throw error;
  }
};

export default {
  API_ENDPOINTS,
  apiRequest,
  uploadFile,
};
