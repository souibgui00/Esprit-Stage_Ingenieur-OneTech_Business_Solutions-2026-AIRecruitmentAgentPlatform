import apiClient from './client';

export const cvApi = {
  list: async () => {
    const response = await apiClient.get('/cv');
    return response.data;
  },

  get: async (cvId) => {
    const response = await apiClient.get(`/cv/${cvId}`);
    return response.data;
  },

  upload: async (file) => {
    const formData = new FormData();
    formData.append('file', file);

    const response = await apiClient.post('/cv/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getStatus: async (cvId) => {
    const response = await apiClient.get(`/cv/${cvId}/status`);
    return response.data;
  },

  reparse: async (cvId) => {
    const response = await apiClient.post(`/cv/${cvId}/reparse`);
    return response.data;
  },

  updatePersonalInfo: async (cvId, data) => {
    const response = await apiClient.put(`/cv/${cvId}/personal-info`, data);
    return response.data;
  },

  delete: async (cvId) => {
    const response = await apiClient.delete(`/cv/${cvId}`);
    return response.data;
  },
};
