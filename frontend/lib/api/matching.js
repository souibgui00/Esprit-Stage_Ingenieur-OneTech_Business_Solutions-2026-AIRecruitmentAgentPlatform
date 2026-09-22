import apiClient from './client';

export const matchingApi = {
  computeMatch: async (cvId, jobOfferId) => {
    const response = await apiClient.post(
      `/matching/cv/${cvId}/job/${jobOfferId}`
    );
    return response.data;
  },

  /**
   * GET /matching/cv/{cv_id}/best-matches
   * Returns top N scored opportunities sorted by compatibility DESC.
   * Backend auto-computes missing matches via pgvector + LLM.
   * Each item is: { match: MatchResponse, job_offer: JobOffer }
   * OR: MatchResponse with nested job_offer field.
   */
  getBestMatches: async (cvId, limit = 20, offset = 0) => {
    const response = await apiClient.get(`/matching/cv/${cvId}/best-matches`, {
      params: { limit, offset },
    });
    return response.data;
  },

  getExplanation: async (cvId, jobId) => {
    const response = await apiClient.get(`/matching/cv/${cvId}/job/${jobId}`);
    return response.data;
  },

  getAutoRecommendations: async (cvId, limit = 10, offset = 0) => {
    const response = await apiClient.get(
      `/matching/cv/${cvId}/auto-recommendations`,
      { params: { limit, offset } }
    );
    return response.data;
  },

  getConfig: async () => {
    const response = await apiClient.get('/matching/config');
    return response.data;
  },

  updateConfig: async (config) => {
    const response = await apiClient.put('/matching/config', config);
    return response.data;
  },

  triggerSourcing: async (cvId) => {
    const response = await apiClient.post(`/matching/cv/${cvId}/trigger-sourcing`);
    return response.data;
  },
};
