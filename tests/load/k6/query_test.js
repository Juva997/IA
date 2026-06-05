import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: __ENV.K6_VUS ? parseInt(__ENV.K6_VUS) : 50,
  duration: __ENV.K6_DURATION || '1m',
};

export default function () {
  const url = __ENV.TARGET_URL || 'http://localhost:8000/query';
  const payload = JSON.stringify({ goal: 'Qual é o resumo deste texto?' });
  const params = {
    headers: {
      'Content-Type': 'application/json',
      Authorization: __ENV.ASSISTENTE_API_KEY ? `Bearer ${__ENV.ASSISTENTE_API_KEY}` : '',
    },
    tags: { name: 'query' },
  };

  const res = http.post(url, payload, params);
  check(res, { 'status is 200 or 503': (r) => r.status === 200 || r.status === 503 });
  sleep(1);
}
