const http = require("node:http");

const backendOrigin =
  process.env.BACKEND_ORIGIN || "http://127.0.0.1:8080";

function isBackendRequest(requestUrl) {
  return (
    requestUrl === "/health" ||
    requestUrl.startsWith("/api/")
  );
}

function proxyBackendRequest(request, response) {
  const backendUrl = new URL(
    request.url || "/",
    backendOrigin,
  );

  const proxyRequest = http.request(
    {
      hostname: backendUrl.hostname,
      port: backendUrl.port || 80,
      path: `${backendUrl.pathname}${backendUrl.search}`,
      method: request.method,
      headers: {
        ...request.headers,
        host: backendUrl.host,
      },
    },
    (backendResponse) => {
      response.writeHead(
        backendResponse.statusCode || 502,
        backendResponse.headers,
      );

      backendResponse.pipe(response);
    },
  );

  proxyRequest.on("error", function (error) {
    if (response.headersSent) {
      response.destroy();
      return;
    }

    response.writeHead(502, {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    });

    response.end(JSON.stringify({
      error: {
        code: "backend_unavailable",
        message: "Backend unreachable — retrying automatically…",
        reason: error.code || "connection_failed",
      },
    }));
  });

  request.pipe(proxyRequest);
}

module.exports = {
  backendOrigin,
  isBackendRequest,
  proxyBackendRequest,
};