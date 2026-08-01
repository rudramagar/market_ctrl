const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");

const host = "127.0.0.1";
const port = Number(process.env.PORT || 3000);
const frontendRoot = path.resolve(__dirname, "..");

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".ico": "image/x-icon",
};

function sendFile(response, filePath) {
  fs.stat(filePath, (error, stats) => {
    if (error || !stats.isFile()) {
      response.writeHead(404, {
        "Content-Type": "text/plain; charset=utf-8",
      });
      response.end("404 Not Found");
      return;
    }

    const extension = path.extname(filePath).toLowerCase();

    response.writeHead(200, {
      "Content-Type":
        contentTypes[extension] ||
        "application/octet-stream",
      "Cache-Control": "no-cache",
    });

    fs.createReadStream(filePath).pipe(response);
  });
}

const server = http.createServer((request, response) => {
  let requestPath;

  try {
    requestPath = decodeURIComponent(
      new URL(request.url, `http://${request.headers.host}`).pathname,
    );
  } catch {
    response.writeHead(400);
    response.end("Bad Request");
    return;
  }

  if (requestPath === "/") {
    requestPath = "/index.html";
  }

  const filePath = path.resolve(
    frontendRoot,
    `.${requestPath}`,
  );

  // Prevent access outside the frontend directory.
  if (
    filePath !== frontendRoot &&
    !filePath.startsWith(`${frontendRoot}${path.sep}`)
  ) {
    response.writeHead(403);
    response.end("Forbidden");
    return;
  }

  sendFile(response, filePath);
});

server.listen(port, host, () => {
  console.log(`Frontend: http://${host}:${port}`);
  console.log("Press Ctrl+C to stop");
});