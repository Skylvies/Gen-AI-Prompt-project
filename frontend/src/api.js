// Thin wrapper around fetch. All backend calls go through here.
const BASE = (import.meta.env.VITE_API_URL || "").replace(/\/+$/, "");

function describeError(detail, status) {
  if (!detail) return `Request failed (HTTP ${status}).`;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{loc: [...], msg: "..."}]
    return detail.map((e) => `${(e.loc || []).slice(1).join(".") || "input"}: ${e.msg}`).join("; ");
  }
  return JSON.stringify(detail);
}

async function request(path, { method = "GET", body, headers = {} } = {}) {
  let response;
  try {
    response = await fetch(`${BASE}${path}`, {
      method,
      headers: { ...(body ? { "Content-Type": "application/json" } : {}), ...headers },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Cannot reach the backend. Check that it is running and that VITE_API_URL is correct.");
  }
  if (!response.ok) {
    let detail = null;
    try {
      detail = (await response.json()).detail;
    } catch {
      /* body was not JSON */
    }
    throw new Error(describeError(detail, response.status));
  }
  return response.status === 204 ? null : response.json();
}

export const api = {
  config: () => request("/api/config"),
  preview: (task, techniques, target_words) =>
    request("/api/prompts/preview", { method: "POST", body: { task, techniques, target_words } }),
  run: (payload, accessCode) =>
    request("/api/experiments", {
      method: "POST",
      body: payload,
      headers: accessCode ? { "X-Access-Code": accessCode } : {},
    }),
  list: () => request("/api/experiments"),
  get: (id) => request(`/api/experiments/${id}`),
  rescore: (id, weights) => request(`/api/experiments/${id}/rescore`, { method: "POST", body: { weights } }),
  remove: (id) => request(`/api/experiments/${id}`, { method: "DELETE" }),
};

// Plain links: the server answers with "Content-Disposition: attachment", so the browser downloads the file.
export const exportUrl = (format, id = null) =>
  id === null
    ? `${BASE}/api/experiments/export?format=${format}`
    : `${BASE}/api/experiments/${id}/export?format=${format}`;
