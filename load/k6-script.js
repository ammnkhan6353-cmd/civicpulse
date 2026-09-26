// Load test for the HPA demo.
//   k6 run load/k6-script.js --out csv=load/k6-results.csv
// Against the local k3d Ingress (port 8081) by default; override with -e BASE_URL=...
//
// Only GET traffic: POST /api/complaints is rate limited (by design) and would
// just return 429s. GETs exercise the backend CPU, which is what the HPA watches.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE_URL = __ENV.BASE_URL || "http://127.0.0.1:8081";

export const options = {
  // Ramp offered load up, hold it, then ramp down - long enough to see scale-out
  // AND the slow (300 s stabilisation) scale-in.
  stages: [
    { duration: "30s", target: 5 },
    { duration: "1m", target: 40 },
    { duration: "2m", target: 100 },
    { duration: "2m", target: 100 },
    { duration: "1m", target: 0 },
  ],
  thresholds: {
    http_req_failed: ["rate<0.01"],
  },
};

const CATEGORIES = ["water", "electricity", "sanitation", "roads", "streetlights", "other"];

export default function () {
  const category = CATEGORIES[Math.floor(Math.random() * CATEGORIES.length)];
  const page = 1 + Math.floor(Math.random() * 3);
  const list = http.get(`${BASE_URL}/api/complaints?category=${category}&page=${page}&page_size=20`, {
    tags: { name: "list" },
  });
  check(list, { "list 200": (r) => r.status === 200 });

  const stats = http.get(`${BASE_URL}/api/stats`, { tags: { name: "stats" } });
  check(stats, { "stats 200": (r) => r.status === 200 });

  sleep(0.2);
}
