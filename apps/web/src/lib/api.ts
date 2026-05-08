import axios from 'axios';

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3000';

export const api = axios.create({
  baseURL: BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'X-User-ID': '00000000-0000-0000-0000-000000000000',
  },
});

api.interceptors.response.use(
  r => r,
  err => {
    const msg = err.response?.data?.error || err.message;
    console.error('[AEGIS API]', msg);
    return Promise.reject(err);
  }
);
