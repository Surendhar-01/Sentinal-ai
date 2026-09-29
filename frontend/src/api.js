const API=import.meta.env.VITE_API_URL||'http://localhost:8000';
export const token=()=>localStorage.getItem('sentinel_token');
export async function request(path,options={}){const headers={...(options.body instanceof FormData?{}:{'Content-Type':'application/json'}),...(token()?{Authorization:`Bearer ${token()}`}:{})};const r=await fetch(API+path,{...options,headers:{...headers,...options.headers}});if(!r.ok)throw new Error((await r.json().catch(()=>({}))).detail||`Request failed (${r.status})`);return r.json()}
export async function login(username,password){const body=new URLSearchParams({username,password});const data=await request('/api/auth/token',{method:'POST',body,headers:{'Content-Type':'application/x-www-form-urlencoded'}});localStorage.setItem('sentinel_token',data.access_token);return data}
export const WS=import.meta.env.VITE_WS_URL||API.replace(/^http/,'ws');
