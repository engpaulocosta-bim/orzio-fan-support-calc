"""Ponto de entrada Streamlit: streamlit run app.py

A UI vive em ``sfsc/ui/streamlit_app.py`` dentro de ``main()``. O Streamlit
re-executa este ficheiro a cada interação (rerun); como o módulo só corre o seu
corpo na primeira importação, a UI tem de estar numa função que é chamada a cada
run — caso contrário a página renderiza vazia nos reruns seguintes.
"""
import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from sfsc.ui.streamlit_app import main

main()
