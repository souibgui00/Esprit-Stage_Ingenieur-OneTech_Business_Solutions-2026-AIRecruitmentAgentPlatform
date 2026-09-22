import apiClient from './client';

export const jobsApi = {
  listSources: async () => {
    const response = await apiClient.get('/jobs/sources');
    return response.data;
  },

  createSource: async (sourceData) => {
    const response = await apiClient.post('/jobs/sources', sourceData);
    return response.data;
  },

  triggerCollection: async (sourceId, keywords) => {
    const response = await apiClient.post(
      `/jobs/sources/${sourceId}/collect`,
      null,
      { params: { keywords } }
    );
    return response.data;
  },

  listRuns: async () => {
    const response = await apiClient.get('/jobs/runs');
    return response.data;
  },

  /** Browse existing DB offers (no fresh discovery) */
  listOffers: async (filters = {}) => {
    const response = await apiClient.get('/jobs/offers', { params: filters });
    return response.data;
  },

  /**
   * Unified search: DB + real-time fresh discovery from all active sources.
   * Returns jobs with source_name and is_fresh labels.
   * Match scores included only when the user's CV has been evaluated.
   */
  searchJobs: async ({ keywords, contract_type, location, sort_by = 'best_match', limit = 40 } = {}) => {
    const response = await apiClient.post('/jobs/search', null, {
      params: {
        keywords,
        ...(contract_type ? { contract_type } : {}),
        ...(location      ? { location }      : {}),
        sort_by,
        limit,
      },
    });
    return response.data;
  },

  getOffer: async (offerId) => {
    const response = await apiClient.get(`/jobs/offers/${offerId}`);
    return response.data;
  },

  getStatus: async (params = {}) => {
    const response = await apiClient.get('/jobs/status', { params });
    return response.data;
  },
};
