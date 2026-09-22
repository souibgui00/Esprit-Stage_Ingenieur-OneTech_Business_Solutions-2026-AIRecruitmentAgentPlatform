import apiClient from './client';
export const homeApi={summary:async()=>{const response=await apiClient.get('/home/summary');return response.data;}};
