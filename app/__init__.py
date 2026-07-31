"""Paquete de la app: cliente de chat de escritorio para Ollama.

Dos módulos con responsabilidades separadas:

- `llm_client`: habla HTTP con Ollama. No sabe qué es una ventana.
- `ui`: pinta la interfaz Tkinter. No sabe qué es HTTP.

`main.py` (en la raíz) es el único que conoce a los dos y los conecta.
"""

__version__ = "1.0.0"

__all__ = ["__version__"]
