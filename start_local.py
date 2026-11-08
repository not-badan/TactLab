"""Start the source distribution on loopback and open its actual local port."""
import errno
import socket
import webbrowser

import uvicorn

from app import app


def main():
    with socket.socket() as listener:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(("127.0.0.1", 8096))
        except OSError as error:
            if error.errno not in (errno.EADDRINUSE, 10048, 10013):
                raise
            listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        url = f"http://127.0.0.1:{listener.getsockname()[1]}/"
        print(f"TactLab: {url}   |   Ctrl+C to stop", flush=True)
        webbrowser.open(url)
        server = uvicorn.Server(uvicorn.Config(app, limit_concurrency=24, timeout_keep_alive=5))
        server.run(sockets=[listener])


if __name__ == "__main__":
    main()