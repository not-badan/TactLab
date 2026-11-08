"""Private loopback service for the Windows desktop launcher."""
import errno
import socket
import sys
import threading

import uvicorn

from app import app


def main():
    with socket.socket() as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", 18461))
        except OSError as error:
            if error.errno not in (errno.EADDRINUSE, 10048, 10013):
                raise
            listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        server = uvicorn.Server(uvicorn.Config(app, limit_concurrency=24, log_level="warning"))
        # An anonymous pipe belongs to the parent window. EOF also handles a launcher crash.
        def watch_window():
            sys.stdin.buffer.read(1)
            server.should_exit = True

        threading.Thread(target=watch_window, daemon=True).start()
        print(f"http://127.0.0.1:{listener.getsockname()[1]}/", flush=True)
        server.run(sockets=[listener])


if __name__ == "__main__":
    main()
