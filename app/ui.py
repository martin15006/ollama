"""Interfaz gráfica (Tkinter) del cliente de chat.

Este módulo solo se ocupa de pintar y de reaccionar a eventos. Toda la
comunicación con Ollama vive en `app.llm_client`, así que acá no hay ni una
llamada HTTP.

Detalle importante: las peticiones se hacen en un hilo aparte para que la
ventana no se congele mientras el modelo piensa. Tkinter NO es thread-safe, así
que el hilo no toca widgets: deja el resultado en una `queue.Queue` y el hilo
principal la revisa cada 100 ms con `after()`.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Optional

from .llm_client import MODELOS_DISPONIBLES, OllamaClient, OllamaError, Respuesta

# --- Constantes de presentación ----------------------------------------------

MARGEN = 10
INTERVALO_COLA_MS = 100  # cada cuánto el hilo principal revisa la cola

FUENTE_TEXTO = ("Segoe UI", 10)
FUENTE_AUTOR = ("Segoe UI", 10, "bold")
FUENTE_META = ("Segoe UI", 8, "italic")

COLOR_USUARIO = "#1a4d8f"
COLOR_ASISTENTE = "#1f6f43"
COLOR_META = "#777777"
COLOR_ERROR = "#b00020"


class ChatApp(ttk.Frame):
    """Ventana principal: selector de modelo, historial, entrada y estado."""

    def __init__(self, master: tk.Misc, cliente: OllamaClient) -> None:
        super().__init__(master, padding=MARGEN)
        self._cliente = cliente

        # Estado de la conversación.
        self._contexto: Optional[list[int]] = None
        self._mensajes = 0

        # Puente hilo de red -> hilo de la UI.
        self._cola: "queue.Queue[tuple[str, object]]" = queue.Queue()
        self._esperando = False
        self._tick = 0

        master.title("Cliente de chat para Ollama")
        master.minsize(620, 460)

        self._construir()
        self._revisar_cola()
        self._comprobar_instalados()

    # -- Construcción de la interfaz -----------------------------------------

    def _construir(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)  # el historial es lo que se estira

        self._construir_barra_superior()
        self._construir_historial()
        self._construir_entrada()
        self._construir_barra_estado()

        self._entrada.focus_set()

    def _construir_barra_superior(self) -> None:
        barra = ttk.Frame(self)
        barra.grid(row=0, column=0, sticky="ew", pady=(0, MARGEN))
        barra.columnconfigure(2, weight=1)  # espaciador entre combo y botón

        ttk.Label(barra, text="Modelo:").grid(row=0, column=0, padx=(0, 6))

        self._modelo = tk.StringVar(value=MODELOS_DISPONIBLES[0])
        combo = ttk.Combobox(
            barra,
            textvariable=self._modelo,
            values=list(MODELOS_DISPONIBLES),
            state="readonly",
            width=16,
        )
        combo.grid(row=0, column=1)
        combo.bind("<<ComboboxSelected>>", self._al_cambiar_modelo)

        ttk.Button(
            barra, text="Limpiar historial", command=self.limpiar_historial
        ).grid(row=0, column=3, sticky="e")

    def _construir_historial(self) -> None:
        self._historial = ScrolledText(
            self,
            wrap="word",
            state="disabled",
            font=FUENTE_TEXTO,
            padx=10,
            pady=10,
            relief="solid",
            borderwidth=1,
            height=18,
        )
        self._historial.grid(row=1, column=0, sticky="nsew")

        self._historial.tag_configure(
            "autor_usuario", font=FUENTE_AUTOR, foreground=COLOR_USUARIO, spacing1=8
        )
        self._historial.tag_configure(
            "autor_asistente", font=FUENTE_AUTOR, foreground=COLOR_ASISTENTE, spacing1=8
        )
        self._historial.tag_configure("cuerpo", font=FUENTE_TEXTO, lmargin1=2, lmargin2=2)
        self._historial.tag_configure("meta", font=FUENTE_META, foreground=COLOR_META)
        self._historial.tag_configure(
            "error", font=FUENTE_TEXTO, foreground=COLOR_ERROR, spacing1=8
        )

        self._escribir_meta(
            "Escribí un mensaje y presioná Enter (o el botón Enviar) para empezar."
        )

    def _construir_entrada(self) -> None:
        zona = ttk.Frame(self)
        zona.grid(row=2, column=0, sticky="ew", pady=(MARGEN, 0))
        zona.columnconfigure(0, weight=1)

        self._entrada = ttk.Entry(zona, font=FUENTE_TEXTO)
        self._entrada.grid(row=0, column=0, sticky="ew", ipady=4)
        self._entrada.bind("<Return>", self._al_enviar)

        self._boton_enviar = ttk.Button(zona, text="Enviar", command=self._al_enviar)
        self._boton_enviar.grid(row=0, column=1, padx=(6, 0))

    def _construir_barra_estado(self) -> None:
        self._estado = tk.StringVar(value="Conectando con Ollama…")
        ttk.Label(
            self,
            textvariable=self._estado,
            anchor="w",
            foreground=COLOR_META,
            font=FUENTE_META,
        ).grid(row=3, column=0, sticky="ew", pady=(6, 0))

    # -- Acciones del usuario -------------------------------------------------

    def _al_enviar(self, evento: Optional[tk.Event] = None) -> str:
        """Toma el texto de la caja y dispara la generación en segundo plano."""
        if self._esperando:
            return "break"

        texto = self._entrada.get().strip()
        if not texto:
            return "break"

        self._entrada.delete(0, "end")
        self._escribir_mensaje("Tú", texto, "autor_usuario")
        self._bloquear(True)

        hilo = threading.Thread(
            target=self._trabajar,
            args=(self._modelo.get(), texto, self._contexto),
            daemon=True,
        )
        hilo.start()
        return "break"  # evita el "ding" de Windows al presionar Enter

    def limpiar_historial(self) -> None:
        """Borra la conversación en pantalla y la memoria del modelo."""
        self._historial.configure(state="normal")
        self._historial.delete("1.0", "end")
        self._historial.configure(state="disabled")

        self._contexto = None
        self._mensajes = 0
        self._escribir_meta("Historial limpio. El modelo ya no recuerda lo anterior.")
        self._estado.set("Historial limpio.")
        self._entrada.focus_set()

    def _al_cambiar_modelo(self, evento: Optional[tk.Event] = None) -> None:
        # El contexto son tokens del modelo anterior: no sirven para otro.
        self._contexto = None
        self._escribir_meta(
            f"Modelo cambiado a {self._modelo.get()}. "
            "Se descartó el contexto de la charla previa."
        )
        self._entrada.focus_set()

    # -- Hilo de red ----------------------------------------------------------

    def _trabajar(
        self, modelo: str, prompt: str, contexto: Optional[list[int]]
    ) -> None:
        """Corre en un hilo aparte. No toca widgets: solo escribe en la cola."""
        try:
            respuesta = self._cliente.generar(modelo, prompt, contexto)
        except OllamaError as exc:
            self._cola.put(("error", str(exc)))
        except Exception as exc:  # red de seguridad: nunca matar el hilo en silencio
            self._cola.put(("error", f"Error inesperado: {exc}"))
        else:
            self._cola.put(("respuesta", respuesta))

    def _comprobar_instalados(self) -> None:
        """Consulta en segundo plano qué modelos están descargados."""

        def tarea() -> None:
            try:
                self._cola.put(("instalados", self._cliente.modelos_instalados()))
            except OllamaError as exc:
                self._cola.put(("error_conexion", str(exc)))

        threading.Thread(target=tarea, daemon=True).start()

    def _revisar_cola(self) -> None:
        """Se ejecuta en el hilo de la UI cada 100 ms."""
        try:
            while True:
                tipo, dato = self._cola.get_nowait()
                if tipo == "respuesta" and isinstance(dato, Respuesta):
                    self._mostrar_respuesta(dato)
                elif tipo == "error":
                    self._mostrar_error(str(dato))
                elif tipo == "instalados" and isinstance(dato, tuple):
                    self._mostrar_instalados(dato)
                elif tipo == "error_conexion":
                    self._estado.set(f"⚠ {str(dato).splitlines()[0]}")
        except queue.Empty:
            pass

        self._animar_espera()
        self.after(INTERVALO_COLA_MS, self._revisar_cola)

    # -- Pintar resultados ----------------------------------------------------

    def _mostrar_respuesta(self, respuesta: Respuesta) -> None:
        self._contexto = respuesta.contexto
        self._escribir_mensaje(respuesta.modelo, respuesta.texto, "autor_asistente")
        self._escribir_meta(
            f"⏱ {respuesta.segundos:.2f} s · {respuesta.modelo}"
        )
        self._bloquear(False)
        self._estado.set(
            f"Última respuesta: {respuesta.segundos:.2f} s · "
            f"{self._mensajes} mensaje(s) en esta charla"
        )

    def _mostrar_error(self, mensaje: str) -> None:
        self._historial.configure(state="normal")
        self._historial.insert("end", f"⚠ {mensaje}\n", "error")
        self._historial.configure(state="disabled")
        self._historial.see("end")
        self._bloquear(False)
        self._estado.set("Error: revisá el mensaje en el historial.")

    def _mostrar_instalados(self, instalados: tuple) -> None:
        faltantes = [m for m in MODELOS_DISPONIBLES if m not in instalados]
        if not faltantes:
            self._estado.set("Ollama conectado · los 3 modelos están descargados.")
            return

        self._estado.set("Ollama conectado · falta descargar: " + ", ".join(faltantes))
        self._escribir_meta(
            "Estos modelos del desplegable todavía no están en tu equipo: "
            + ", ".join(faltantes)
            + ". Descargalos con «ollama pull <modelo>» si querés usarlos."
        )

        # Si el modelo preseleccionado no está, arrancar en uno que sí funcione.
        if self._modelo.get() in faltantes:
            usables = [m for m in MODELOS_DISPONIBLES if m in instalados]
            if usables:
                self._modelo.set(usables[0])
                self._contexto = None
                self._escribir_meta(f"Se preseleccionó {usables[0]}, que sí tenés.")

    # -- Utilidades de pintado ------------------------------------------------

    def _escribir_mensaje(self, autor: str, texto: str, tag_autor: str) -> None:
        self._mensajes += 1
        self._historial.configure(state="normal")
        self._historial.insert("end", f"{autor}\n", tag_autor)
        self._historial.insert("end", f"{texto}\n", "cuerpo")
        self._historial.configure(state="disabled")
        self._historial.see("end")

    def _escribir_meta(self, texto: str) -> None:
        self._historial.configure(state="normal")
        self._historial.insert("end", f"{texto}\n", "meta")
        self._historial.configure(state="disabled")
        self._historial.see("end")

    def _bloquear(self, esperando: bool) -> None:
        """Evita mandar dos mensajes a la vez mientras el modelo responde."""
        self._esperando = esperando
        self._tick = 0
        estado = "disabled" if esperando else "normal"
        self._boton_enviar.configure(state=estado)
        self._entrada.configure(state=estado)
        if not esperando:
            self._entrada.focus_set()

    def _animar_espera(self) -> None:
        """Puntitos en la barra de estado para que se note que está trabajando."""
        if not self._esperando:
            return
        self._tick += 1
        if self._tick % 4:  # ~cada 400 ms
            return
        puntos = "." * (1 + (self._tick // 4) % 3)
        self._estado.set(f"Pensando con {self._modelo.get()}{puntos}")
