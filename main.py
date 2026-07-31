"""Punto de entrada del cliente de chat para Ollama.

Único archivo que conoce a los dos módulos y los conecta:

    python main.py
"""

from __future__ import annotations

import sys
import tkinter as tk

from app.llm_client import OllamaClient
from app.ui import ChatApp


def main() -> int:
    root = tk.Tk()
    cliente = OllamaClient()  # host y timeout por defecto: localhost:11434
    ChatApp(root, cliente).pack(fill="both", expand=True)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
