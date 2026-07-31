import logging
from threading import RLock, Thread

from werkzeug.serving import make_server


logger = logging.getLogger(__name__)


class HttpServer:
    """Run a WSGI application in a managed thread."""

    def __init__(
        self,
        application,
        host="0.0.0.0",
        port=8080,
        threaded=True,
    ):
        if application is None:
            raise ValueError(
                "HTTP application is required"
            )

        if not isinstance(host, str):
            raise TypeError(
                "HTTP host must be a string"
            )

        host = host.strip()

        if not host:
            raise ValueError(
                "HTTP host cannot be empty"
            )

        port = int(port)

        if port < 0 or port > 65535:
            raise ValueError(
                "invalid HTTP port: %d"
                % port
            )

        self.application = application
        self.host = host
        self.port = port
        self.threaded = bool(threaded)

        self._lock = RLock()
        self._server = None
        self._thread = None
        self._running = False
        self._last_error = None

    @property
    def running(self):
        with self._lock:
            return self._running

    @property
    def last_error(self):
        with self._lock:
            return self._last_error

    @property
    def bound_host(self):
        with self._lock:
            if self._server is None:
                return None

            return self._server.host

    @property
    def bound_port(self):
        with self._lock:
            if self._server is None:
                return None

            return self._server.port

    def start(self):
        """Create the listener and start its worker thread."""

        with self._lock:
            if self._running:
                raise RuntimeError(
                    "HTTP server is already running"
                )

            self._last_error = None

            server = make_server(
                host=self.host,
                port=self.port,
                app=self.application,
                threaded=self.threaded,
            )

            thread = Thread(
                target=self._serve,
                args=(server,),
                name="http-server",
            )
            thread.daemon = False

            self._server = server
            self._thread = thread
            self._running = True

            try:
                thread.start()

            except Exception:
                self._server = None
                self._thread = None
                self._running = False

                server.server_close()
                raise

        logger.info(
            "HTTP server started: host=%s port=%d",
            self.bound_host,
            self.bound_port,
        )

    def stop(
        self,
        timeout_seconds=5.0,
    ):
        """Stop the listener and wait for its thread."""

        with self._lock:
            server = self._server
            thread = self._thread

        if server is None:
            return True

        try:
            server.shutdown()

        finally:
            server.server_close()

        if thread is not None:
            thread.join(
                timeout_seconds
            )

        with self._lock:
            stopped = not (
                thread is not None
                and thread.is_alive()
            )

            if stopped:
                self._server = None
                self._thread = None
                self._running = False

        if stopped:
            logger.info(
                "HTTP server stopped"
            )

        return stopped

    def _serve(self, server):
        try:
            server.serve_forever()

        except Exception as exc:
            with self._lock:
                self._last_error = exc

            logger.exception(
                "HTTP server failed"
            )

        finally:
            with self._lock:
                self._running = False
