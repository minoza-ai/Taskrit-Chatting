try:
    import websockets  # noqa: F401
except ImportError as err:
    raise RuntimeError(
        "Missing websocket runtime dependency. Run `pip install -r requirements.txt` "
        "and start the server with the project Python environment."
    ) from err

import uvicorn

from app.main import app


if __name__ == '__main__':
    uvicorn.run('app.main:app', host='0.0.0.0', port=8000, reload=True)
