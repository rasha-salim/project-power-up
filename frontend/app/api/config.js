// API configuration
const getApiBaseUrl = () => {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  // Add https:// if the URL doesn't have a protocol
  if (apiUrl && !apiUrl.startsWith('http://') && !apiUrl.startsWith('https://')) {
    return `https://${apiUrl}`;
  }
  return apiUrl;
};

const API_BASE_URL = `${getApiBaseUrl()}/api/v1`;

// Debug logging
console.log('API Configuration:', {
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  API_BASE_URL: API_BASE_URL
});

export const API_ENDPOINTS = {
  // Document endpoints
  DOCUMENTS: {
    UPLOAD: `${API_BASE_URL}/documents/upload`,
    UPLOAD_MULTIPLE: `${API_BASE_URL}/documents/upload-multiple`,
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
export const uploadFile = async (formData) => {
  try {
    console.log('Uploading file with FormData');
    
    // Log the number of entries in the FormData
    let entryCount = 0;
    let fileCount = 0;
    for (const [key, value] of formData.entries()) {
      entryCount++;
      if (key === 'file') {
        fileCount++;
        console.log(`FormData entry: ${key}, filename: ${value.name}`);
      } else {
        console.log(`FormData entry: ${key}, value: ${value}`);
      }
    }
    console.log(`Total FormData entries: ${entryCount}, File count: ${fileCount}`);
    
    const response = await fetch(API_ENDPOINTS.DOCUMENTS.UPLOAD, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let errorDetail = `Upload failed with status: ${response.status}`;
      try {
        const errorData = await response.json();
        if (errorData && errorData.detail) {
          errorDetail = errorData.detail;
        }
      } catch (e) {
        // If parsing JSON fails, try to get text
        try {
          const errorText = await response.text();
          if (errorText) {
            errorDetail += ` - ${errorText}`;
          }
        } catch (textError) {
          console.error('Error parsing error response:', textError);
        }
      }
      throw new Error(errorDetail);
    }

    // Try to parse the response as JSON
    try {
      const responseText = await response.text();
      return responseText ? JSON.parse(responseText) : {};
    } catch (parseError) {
      console.error('Error parsing upload response:', parseError);
      throw new Error('Invalid response from server');
    }
  } catch (error) {
    console.error('File upload error:', error);
    throw error;
  }
};

// Helper function for multiple file uploads
export const uploadMultipleFiles = async (files, projectId, description) => {
  try {
    console.log('uploadMultipleFiles: Starting upload of', files.length, 'files');
    console.log('File names:', files.map(f => f.name));
    
    // Check for duplicate files by name
    const fileNames = files.map(f => f.name);
    const fileNameCounts = {};
    fileNames.forEach(name => {
      fileNameCounts[name] = (fileNameCounts[name] || 0) + 1;
    });
    
    const duplicates = Object.entries(fileNameCounts)
      .filter(([_, count]) => count > 1)
      .map(([name, count]) => `${name} (${count} copies)`);
    
    if (duplicates.length > 0) {
      console.warn('WARNING: Duplicate files detected in upload request:', duplicates);
    }
    
    const formData = new FormData();
    
    // Add each file to FormData with parameter name 'file'
    files.forEach(file => {
      console.log(`Adding file to FormData: ${file.name} (${file.size} bytes)`);
      formData.append('file', file);
    });
    
    // Add other form data
    if (projectId) {
      formData.append('project_id', projectId);
    }
    if (description) {
      formData.append('description', description);
    }
    
    // Log FormData entries for debugging
    console.log('FormData entries:');
    for (const pair of formData.entries()) {
      if (pair[0] === 'file') {
        console.log(`- ${pair[0]}: ${pair[1].name} (${pair[1].size} bytes)`);
      } else {
        console.log(`- ${pair[0]}: ${pair[1]}`);
      }
    }
    
    // Send request to the upload endpoint
    console.log(`Sending request to ${API_ENDPOINTS.DOCUMENTS.UPLOAD}`);
    const response = await fetch(API_ENDPOINTS.DOCUMENTS.UPLOAD, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      let errorDetail = `File upload failed with status: ${response.status}`;
      try {
        const errorData = await response.json();
        errorDetail = errorData.detail || errorDetail;
      } catch (e) {
        console.error('Error parsing error response:', e);
      }
      throw new Error(errorDetail);
    }

    try {
      // Parse the response
      const result = await response.json();
      
      // The backend now consistently returns a MultipleDocumentResponse with a documents array
      return result;
    } catch (parseError) {
      console.error('Error parsing upload response:', parseError);
      throw new Error('Invalid response from server');
    }
  } catch (error) {
    console.error('Error in uploadMultipleFiles:', error);
    throw error;
  }
};

export default {
  API_ENDPOINTS,
  apiRequest,
  uploadFile,
  uploadMultipleFiles,
};
