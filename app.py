"""Ponto de entrada Streamlit: streamlit run app.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from sfsc.ui.streamlit_app import *  # noqa: F401,F403
