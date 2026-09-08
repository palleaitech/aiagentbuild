
// Configure an Axios instance to point to your FastAPI server running on port 8000:

import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

export default apiClient;