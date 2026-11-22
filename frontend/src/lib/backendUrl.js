// Use the configured backend in production and same-origin Vite proxies locally.
function backendOrigin() {
  return import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "")
    || window.location.origin;
}

export function apiUrl(path) {
  return new URL(path, `${backendOrigin()}/`).toString();
}

export function wsUrl(path) {
  const url = new URL(path, `${backendOrigin()}/`);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}
