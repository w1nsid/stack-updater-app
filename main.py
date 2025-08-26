"""Entry point for running the Stack Updater application.

This file simply imports the ASGI application object from the internal
``app.main`` module so that tools like uvicorn can discover it without
requiring the ``app`` package to be on ``sys.path``. Running ``uvicorn
main:app`` from the project root will now correctly locate and load
the FastAPI application.
"""

"""
Entrypoint for the Stack Updater application.

This module ensures that the internal ``app`` package can be imported
correctly regardless of the current working directory. By adjusting
``sys.path`` to include the directory containing this file, Python will
successfully locate the ``app`` package nested alongside ``main.py``.

Running ``python main.py`` will launch a development server using
Uvicorn. If you wish to use the Uvicorn CLI instead, you can invoke
``uvicorn main:app --host 0.0.0.0 --port 8080 --app-dir .``
"""

import os
import sys

# Ensure the folder containing this script is on sys.path so that
# ``import app`` resolves to the local package even when executed
# from another directory. Without this, uvicorn may fail to locate
# the ``app`` package when imported via ``main:app``.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from app.main import app  # type: ignore  # noqa: E402,F401

if __name__ == "__main__":
    # When run directly, spin up a development server. This avoids
    # relying on uvicorn's module import behaviour which can be
    # sensitive to the working directory.
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
