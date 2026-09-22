import apiClient from './client';

export const applicationsApi = {
  createFromMatch: async (matchId) => {
    const response = await apiClient.post(`/applications/from-match/${matchId}`);
    return response.data;
  },

  list: async (statusFilter = null) => {
    const params = statusFilter ? { status: statusFilter } : {};
    const response = await apiClient.get('/applications', { params });
    return response.data;
  },

  getById: async (applicationId) => {
    const response = await apiClient.get(`/applications/${applicationId}`);
    return response.data;
  },

  approve: async (applicationId) => {
    const response = await apiClient.post(`/applications/${applicationId}/approve`);
    return response.data;
  },

  reject: async (applicationId, reason = null) => {
    const response = await apiClient.post(
      `/applications/${applicationId}/reject`,
      reason ? { reason } : null
    );
    return response.data;
  },

  runAgent: async (applicationId) => {
    const response = await apiClient.post(`/applications/${applicationId}/run-agent`);
    return response.data;
  },

  // Phase 3: Cover letter management
  getCoverLetter: async (applicationId) => {
    const response = await apiClient.get(`/applications/${applicationId}/cover-letter`);
    return response.data;
  },

  generateCoverLetter: async (applicationId) => {
    const response = await apiClient.post(`/applications/${applicationId}/cover-letter/generate`);
    return response.data;
  },

  updateCoverLetter: async (applicationId, coverLetterContent) => {
    const response = await apiClient.put(`/applications/${applicationId}/cover-letter`, {
      cover_letter: coverLetterContent
    });
    return response.data;
  },

  // Phase 3: ACTION_REQUIRED details & question answering
  getActionDetails: async (applicationId) => {
    const response = await apiClient.get(`/applications/${applicationId}/action-details`);
    return response.data;
  },

  answerQuestions: async (applicationId, answers) => {
    const response = await apiClient.post(`/applications/${applicationId}/answer-questions`, { answers });
    return response.data;
  },

  getSettings: async () => {
    const response = await apiClient.get('/applications/settings');
    return response.data;
  },

  updateSettings: async (settings) => {
    const response = await apiClient.put('/applications/settings', settings);
    return response.data;
  },

  checkEligibility: async (jobOfferId) => {
    const response = await apiClient.get(`/applications/eligibility/${jobOfferId}`);
    return response.data;
  },

  runAutoApplyCycle: async () => {
    const response = await apiClient.post('/applications/auto-apply-run');
    return response.data;
  },

  getActivity: async (limit = 20) => {
    const response = await apiClient.get('/applications/activity', { params: { limit } });
    return response.data;
  },
};
