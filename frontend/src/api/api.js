import axios from 'axios'
const api=axios.create({baseURL:import.meta.env.VITE_API_URL||'http://localhost:5000/api',timeout:30000,headers:{'Content-Type':'application/json'}})
api.interceptors.request.use(config=>{const token=localStorage.getItem('token');if(token)config.headers.Authorization=`Bearer ${token}`;return config})
api.interceptors.response.use(r=>r,error=>{if(error.response?.status===401){localStorage.removeItem('token');localStorage.removeItem('user');if(window.location.pathname!='/login')window.location.assign('/login')}return Promise.reject(error)})
export const getApiError=(error,fallback='Something went wrong')=>{if(error?.code==='ECONNABORTED')return 'Request timed out. Make sure the FastAPI backend is running on port 5000.';if(error?.response?.status===502)return error.response.data?.detail||error.response.data?.message||'Upstream market service is temporarily unavailable.';return error?.response?.data?.detail||error?.response?.data?.message||error?.message||fallback}
export default api
