const TOKEN_KEY = "framemind_token";

function getAuthHeaders() {
  const token = localStorage.getItem(TOKEN_KEY);
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseOrThrow(res) {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

async function fetchWithFriendlyErrors(url, options = {}) {
  try {
    const res = await fetch(url, options);
    return await parseOrThrow(res);
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error("Unable to reach the server. Please make sure the backend is running on port 8000.");
    }
    throw error;
  }
}

export function getStoredToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function register({ apiBase, email, password, name }) {
  const data = await fetchWithFriendlyErrors(`${apiBase}/api/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name }),
  });
  localStorage.setItem(TOKEN_KEY, data.access_token);
  return data;
}

export async function login({ apiBase, email, password }) {
  const data = await fetchWithFriendlyErrors(`${apiBase}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem(TOKEN_KEY, data.access_token);
  return data;
}

export async function getCurrentUser({ apiBase }) {
  return fetchWithFriendlyErrors(`${apiBase}/api/auth/me`, {
    headers: getAuthHeaders(),
  });
}

export async function createFrameSession({ apiBase }) {
  return fetchWithFriendlyErrors(`${apiBase}/api/public/frame-sessions`, {
    method: "POST",
    headers: getAuthHeaders(),
  });
}

export async function uploadSingleFrame({ apiBase, sessionId, frame }) {
  const form = new FormData();
  form.append("frame", frame);
  return fetchWithFriendlyErrors(`${apiBase}/api/public/frame-sessions/${sessionId}/frame`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: form,
  });
}

export async function getFrameSessionStatus({ apiBase, sessionId }) {
  return fetchWithFriendlyErrors(`${apiBase}/api/public/frame-sessions/${sessionId}`, {
    headers: getAuthHeaders(),
  });
}

export async function generateFromSession({ apiBase, sessionId, intermediateCount, fps }) {
  const form = new FormData();
  form.append("intermediate_count", String(intermediateCount));
  form.append("fps", String(fps));

  return fetchWithFriendlyErrors(`${apiBase}/api/public/frame-sessions/${sessionId}/generate`, {
    method: "POST",
    headers: getAuthHeaders(),
    body: form,
  });
}
