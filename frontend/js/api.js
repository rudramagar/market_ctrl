const defaultHeaders = {
  Accept: "application/json",
};

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...options.headers,
    },
  });

  let responseBody = null;

  try {
    responseBody = await response.json();
  } catch {
    // Some responses may not contain JSON.
  }

  if (!response.ok) {
    const message =
      responseBody?.message ||
      responseBody?.error ||
      `Request failed with HTTP ${response.status}`;

    throw new Error(message);
  }

  return responseBody;
}

export async function getHealth() {
  return requestJson("/health");
}

export async function getUsers() {
  return requestJson("/api/v1/users");
}