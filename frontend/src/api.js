const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function request(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });
  } catch (error) {
    const networkError = new Error("Couldn't reach the server - try again");
    networkError.kind = "network";
    throw networkError;
  }

  let payload = null;
  const text = await response.text();

  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { detail: text };
    }
  }

  if (!response.ok) {
    const error = new Error(readErrorMessage(payload, response.statusText));
    error.status = response.status;
    error.payload = payload;
    throw error;
  }

  return payload;
}

function readErrorMessage(payload, fallback) {
  if (!payload) {
    return fallback;
  }

  if (typeof payload.detail === "string") {
    return payload.detail;
  }

  if (payload.detail?.message) {
    return payload.detail.message;
  }

  if (payload.message) {
    return payload.message;
  }

  return fallback;
}

export function getHealth() {
  return request("/health");
}

export function getStrategies() {
  return request("/strategies");
}

export function sendChat(message) {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function updateRetrievalStrategy(retrievalStrategy) {
  return request("/strategy/retrieval", {
    method: "POST",
    body: JSON.stringify({ retrieval_strategy: retrievalStrategy }),
  });
}

export function startReindex(chunkingStrategy) {
  return request("/reindex", {
    method: "POST",
    body: JSON.stringify({ chunking_strategy: chunkingStrategy }),
  });
}

export function getReindexStatus() {
  return request("/reindex-status");
}
