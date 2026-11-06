import { state } from './state.js';
import { showLogin } from './router.js';

export async function api(path, options = {}) {
  const response = await fetch('/api' + path, {
    credentials: 'same-origin',
    ...options,
    headers: {
      ...(options.body && !(typeof FormData !== 'undefined' && options.body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
      ...options.headers,
    },
  });
  const result = await response
    .json()
    .catch(() => ({ error: '서버에 연결할 수 없습니다. Docker 실행 상태를 확인해주세요.' }));
  if (!response.ok) {
    if (response.status === 401 && state.user) {
      state.user = null;
      showLogin();
    }
    throw Error(result.error || '요청을 처리하지 못했습니다.');
  }
  return result;
}

export const post = (path, data) => api(path, { method: 'POST', body: JSON.stringify(data) });

