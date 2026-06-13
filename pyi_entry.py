"""PyInstaller entry point.

PyInstaller runs the entry *script* as the top-level ``__main__`` module, so the
package's own ``__main__.py`` (which uses relative imports like ``from .cli``)
can't be used directly — it raises "attempted relative import with no known
parent package". This shim imports the installed package absolutely instead.

``python -m d2aa`` still uses ``src/d2aa/__main__.py``; this file is only for the
frozen binary.
"""

import sys

from d2aa.cli import run

if __name__ == "__main__":
    sys.exit(run())
