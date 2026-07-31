"""Cliente HTTP para la API de Ollama.

Este módulo es la única puerta de salida hacia la red. No importa `tkinter`
ni sabe nada de ventanas: recibe texto, devuelve texto y tiempos. Así se puede
probar desde una terminal, reemplazar por otro backend o reutilizar en otra
interfaz sin tocar una línea de la UI.

Dependencia externa: solo `requests`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, Sequence

import requests

# --- Configuración -----------------------------------------------------------

HOST_POR_DEFECTO = "http://localhost:11434"
RUTA_GENERATE = "/api/generate"
RUTA_TAGS = "/api/tags"

#: Segundos máximos de espera. Un modelo de 8B en CPU puede tardar bastante.
TIMEOUT_POR_DEFECTO = 180

#: Modelos que ofrece el desplegable de la interfaz.
MODELOS_DISPONIBLES: tuple[str, ...] = ("gemma2:2b", "llama3.2:3b", "llama3.1:8b")


# --- Tipos del dominio -------------------------------------------------------


class OllamaError(RuntimeError):
    """Fallo al hablar con Ollama, ya traducido a un mensaje entendible.

    La UI solo tiene que mostrar `str(error)`; no necesita conocer `requests`
    ni los códigos HTTP.
    """


@dataclass(frozen=True)
class Respuesta:
    """Resultado de una generación."""

    texto: str
    #: Segundos de reloj medidos por el cliente (lo que espera el usuario).
    segundos: float
    modelo: str
    #: Tokens de contexto que devuelve Ollama para encadenar el próximo turno.
    contexto: Optional[list[int]] = None


# --- Cliente -----------------------------------------------------------------


class OllamaClient:
    """Envoltura mínima sobre la API REST de Ollama."""

    def __init__(
        self,
        host: str = HOST_POR_DEFECTO,
        timeout: int = TIMEOUT_POR_DEFECTO,
    ) -> None:
        self._host = host.rstrip("/")
        self._timeout = timeout
        # Una sesión reutiliza la conexión TCP entre mensajes.
        self._sesion = requests.Session()

    # -- API pública ----------------------------------------------------------

    def generar(
        self,
        modelo: str,
        prompt: str,
        contexto: Optional[Sequence[int]] = None,
    ) -> Respuesta:
        """Envía un mensaje al modelo y espera la respuesta completa.

        `contexto` son los tokens que devolvió la llamada anterior: es lo que
        le da memoria a la conversación usando `/api/generate` (que por sí solo
        no guarda estado). Es específico de cada modelo, por eso se descarta al
        cambiar de modelo.

        Lanza `OllamaError` con un mensaje listo para mostrar si algo falla.
        """
        payload: dict[str, object] = {
            "model": modelo,
            "prompt": prompt,
            "stream": False,
        }
        if contexto:
            payload["context"] = list(contexto)

        inicio = time.perf_counter()
        datos = self._post(RUTA_GENERATE, payload, modelo)
        segundos = time.perf_counter() - inicio

        texto = str(datos.get("response", "")).strip()
        if not texto:
            raise OllamaError(
                f"El modelo '{modelo}' respondió vacío. "
                "Probá de nuevo o cambiá de modelo."
            )

        nuevo_contexto = datos.get("context")
        return Respuesta(
            texto=texto,
            segundos=segundos,
            modelo=modelo,
            contexto=list(nuevo_contexto) if isinstance(nuevo_contexto, list) else None,
        )

    def modelos_instalados(self) -> tuple[str, ...]:
        """Nombres de los modelos descargados en la máquina (`/api/tags`).

        Sirve para avisar antes de tiempo que falta un `ollama pull`.
        """
        datos = self._get(RUTA_TAGS)
        modelos = datos.get("models")
        if not isinstance(modelos, list):
            return ()
        return tuple(
            str(m["name"]) for m in modelos if isinstance(m, dict) and "name" in m
        )

    # -- Interno --------------------------------------------------------------

    def _post(self, ruta: str, payload: dict, modelo: str) -> dict:
        try:
            respuesta = self._sesion.post(
                self._host + ruta, json=payload, timeout=self._timeout
            )
        except requests.exceptions.Timeout as exc:
            raise OllamaError(
                f"Ollama tardó más de {self._timeout} s en responder. "
                "Probá con un modelo más liviano."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(self._mensaje_sin_conexion()) from exc
        except requests.exceptions.RequestException as exc:
            raise OllamaError(f"Error de red hablando con Ollama: {exc}") from exc

        if respuesta.status_code == 404:
            raise OllamaError(
                f"El modelo '{modelo}' no está descargado.\n"
                f"Descargalo con:  ollama pull {modelo}"
            )
        if respuesta.status_code >= 400:
            raise OllamaError(
                f"Ollama devolvió HTTP {respuesta.status_code}: "
                f"{respuesta.text[:300]}"
            )

        return self._json(respuesta)

    def _get(self, ruta: str) -> dict:
        try:
            respuesta = self._sesion.get(self._host + ruta, timeout=10)
            respuesta.raise_for_status()
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(self._mensaje_sin_conexion()) from exc
        except requests.exceptions.RequestException as exc:
            raise OllamaError(f"Error de red hablando con Ollama: {exc}") from exc

        return self._json(respuesta)

    @staticmethod
    def _json(respuesta: requests.Response) -> dict:
        try:
            datos = respuesta.json()
        except ValueError as exc:
            raise OllamaError("Ollama respondió algo que no es JSON válido.") from exc
        if not isinstance(datos, dict):
            raise OllamaError("Ollama respondió un JSON con una forma inesperada.")
        return datos

    def _mensaje_sin_conexion(self) -> str:
        return (
            f"No pude conectarme a Ollama en {self._host}.\n"
            "Verificá que esté corriendo (abrí una terminal y ejecutá: ollama serve)."
        )
