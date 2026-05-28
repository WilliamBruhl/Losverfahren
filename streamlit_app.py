# SPDX-License-Identifier: AGPL-3.0-or-later
"""Streamlit Community Cloud entry point.

Streamlit Cloud expects an importable ``streamlit_app.py`` at the repo root.
This module simply puts the bundled ``losverfahren`` package on ``sys.path``
and re-runs the actual app file, so no editable install is required on the
hosted environment.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PKG_SRC = ROOT / "03-gui-tool" / "src"
APP_PATH = PKG_SRC / "losverfahren" / "app.py"

if str(PKG_SRC) not in sys.path:
    sys.path.insert(0, str(PKG_SRC))

runpy.run_path(str(APP_PATH), run_name="__main__")
