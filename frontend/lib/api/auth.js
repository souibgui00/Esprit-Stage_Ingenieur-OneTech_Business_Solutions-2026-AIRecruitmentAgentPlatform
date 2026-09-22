import apiClient from './client';

export const authApi = {
  register: async (email, password, full_name) => {
    const response = await apiClient.post('/auth/register', {
      email,
      password,
      full_name,
    });
    return response.data;
  },

  login: async (email, password) => {
    const formData = new URLSearchParams();
    formData.append('username', email);
    formData.append('password', password);

    const response = await apiClient.post('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    return response.data;
  },

  logout: async () => {
    const response = await apiClient.post('/auth/logout');
    return response.data;
  },

  getMe: async () => {
    const response = await apiClient.get('/auth/me');
    return response.data;
  },

  refreshToken: async (refreshToken) => {
    const response = await apiClient.post('/auth/refresh-token', {
      refresh_token: refreshToken,
    });
    return response.data;
  },

  changePassword: async (currentPassword, newPassword) => {
    const response = await apiClient.post('/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
    return response.data;
  },

  getPreferences: async () => {
    const response = await apiClient.get('/auth/preferences');
    return response.data;
  },

  updatePreferences: async (preferences) => {
    const response = await apiClient.put('/auth/preferences', preferences);
    return response.data;
  },

  forgotPassword: async (email) => {
    const response = await apiClient.post('/auth/forgot-password', { email });
    return response.data;
  },

  resetPassword: async (token, newPassword) => {
    const response = await apiClient.post('/auth/reset-password', {
      token,
      new_password: newPassword,
    });
    return response.data;
  },

  getGoogleAuthUrl: async () => {
    const response = await apiClient.get('/auth/google/auth-url');
    return response.data; // { authorization_url: "..." }
  },

  getGithubAuthUrl: async () => {
    const response = await apiClient.get('/auth/github/auth-url');
    return response.data; // { authorization_url: "..." }
  },

  exchangeGoogleCode: async (code) => {
    const response = await apiClient.post('/auth/google/callback', { code });
    return response.data; // { access_token, refresh_token, token_type }
  },

  exchangeGithubCode: async (code) => {
    const response = await apiClient.post('/auth/github/callback', { code });
    return response.data; // { access_token, refresh_token, token_type }
  },
};
