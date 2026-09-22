import axios from "axios";

// Keep browser traffic on the Next.js origin. next.config.js proxies /api to
// FastAPI, so Docker-only hostnames never leak into a user's browser.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
  maxRedirects: 5,
});

// Request interceptor to attach JWT token
if (typeof window !== "undefined") {
  apiClient.interceptors.request.use(
    (config) => {
      const token = localStorage.getItem("token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    },
    (error) => Promise.reject(error)
  );

  // Response interceptor for token refresh
  let isRefreshing = false;
  let failedQueue = [];

  const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
      if (error) {
        prom.reject(error);
      } else {
        prom.resolve(token);
      }
    });
    failedQueue = [];
  };

  apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
      const originalRequest = error.config;

      if (error.response?.status === 401 && !originalRequest._retry) {
        if (isRefreshing) {
          return new Promise((resolve, reject) => {
            failedQueue.push({ resolve, reject });
          }).then(token => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            return apiClient(originalRequest);
          }).catch(err => Promise.reject(err));
        }

        originalRequest._retry = true;
        isRefreshing = true;

        const refreshToken = localStorage.getItem("refresh_token");

        if (!refreshToken) {
          processQueue(error, null);
          isRefreshing = false;
          localStorage.removeItem("token");
          localStorage.removeItem("refresh_token");
          if (typeof window !== "undefined") {
            window.location.href = "/login";
          }
          return Promise.reject(error);
        }

        try {
          const response = await axios.post(
            `${API_BASE_URL}/auth/refresh-token`,
            { refresh_token: refreshToken },
            { headers: { "Content-Type": "application/json" } }
          );

          const { access_token, refresh_token: new_refresh_token } = response.data;

          localStorage.setItem("token", access_token);
          localStorage.setItem("refresh_token", new_refresh_token);

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          processQueue(null, access_token);
          isRefreshing = false;

          return apiClient(originalRequest);
        } catch (refreshError) {
          processQueue(refreshError, null);
          isRefreshing = false;
          localStorage.removeItem("token");
          localStorage.removeItem("refresh_token");
          if (typeof window !== "undefined") {
            window.location.href = "/login";
          }
          return Promise.reject(refreshError);
        }
      }

      return Promise.reject(error);
    }
  );
}

export default apiClient;