from pathlib import Path
import sys

import uvicorn

# Make python/app importable when running from the repository root.
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / 'python'))

from app.main import app  # noqa: E402


if __name__ == '__main__':
    uvicorn.run('server:app', host='0.0.0.0', port=8000, reload=True)
