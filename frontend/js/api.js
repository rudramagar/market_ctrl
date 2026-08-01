const defaultHeaders = {
  Accept: "application/json",
};

export class ApiError extends Error {
  constructor(
    message,
    {
      status = 0,
      code = "request_failed",
      reason = null,
      body = null,
    } = {},
  ) {
    super(message);

    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.reason = reason;
    this.body = body;
  }
}

function getErrorDetails(
  responseBody,
  status,
) {
  const errorPayload =
    responseBody?.error;

  if (
    errorPayload &&
    typeof errorPayload === "object"
  ) {
    return {
      message:
        errorPayload.message ||
        `Request failed with HTTP ${status}`,
      code:
        errorPayload.code ||
        `http_${status}`,
      reason:
        errorPayload.reason || null,
    };
  }

  if (typeof errorPayload === "string") {
    return {
      message: errorPayload,
      code: `http_${status}`,
      reason: null,
    };
  }

  return {
    message:
      responseBody?.message ||
      `Request failed with HTTP ${status}`,
    code: `http_${status}`,
    reason: null,
  };
}

async function requestJson(
  url,
  options = {},
) {
  let response;

  try {
    response = await fetch(url, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    });
  } catch (error) {
    throw new ApiError(
      "Unable to connect to the backend.",
      {
        code: "network_error",
        body: error,
      },
    );
  }

  let responseBody = null;

  try {
    responseBody = await response.json();
  } catch {
    // Some responses may not contain JSON.
  }

  if (!response.ok) {
    const details = getErrorDetails(
      responseBody,
      response.status,
    );

    throw new ApiError(
      details.message,
      {
        status: response.status,
        code: details.code,
        reason: details.reason,
        body: responseBody,
      },
    );
  }

  return responseBody;
}

export async function getHealth() {
  return requestJson("/health");
}

export async function getUsers() {
  return requestJson("/api/v1/users");
}
