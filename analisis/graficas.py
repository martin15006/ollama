"""Genera las 2 gráficas del análisis comparativo a partir de `resultados.json`.

Uso (después de correr benchmark.py):
    python analisis/graficas.py

Produce:
    analisis/grafica_tiempos.png     — barras: tiempo por modelo y tipo de prompt
    analisis/grafica_dispersion.png  — dispersión: parámetros vs tiempo promedio

matplotlib se usa SOLO acá. La app en sí sigue dependiendo únicamente de
`requests` (ver requirements.txt vs requirements-analisis.txt).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin ventana: solo guardar archivos
import matplotlib.pyplot as plt
import numpy as np

CARPETA = Path(__file__).resolve().parent
DATOS = CARPETA / "resultados.json"


def cargar() -> list[dict]:
    if not DATOS.exists():
        print(f"No encuentro {DATOS}. Corré primero:  python analisis/benchmark.py")
        sys.exit(1)
    return json.loads(DATOS.read_text(encoding="utf-8"))


def grafica_barras(datos: list[dict]) -> Path:
    """Tiempo de respuesta (Y) vs modelo (X), 3 grupos de barras."""
    modelos = [d["modelo"] for d in datos]
    simple = [d["tiempos"]["simple"] for d in datos]
    medio = [d["tiempos"]["medio"] for d in datos]
    complejo = [d["tiempos"]["complejo"] for d in datos]

    x = np.arange(len(modelos))
    ancho = 0.25

    fig, ax = plt.subplots(figsize=(10, 6))
    barras = [
        ax.bar(x - ancho, simple, ancho, label="Prompt simple", color="#4c9f70"),
        ax.bar(x, medio, ancho, label="Prompt medio", color="#3d7ea6"),
        ax.bar(x + ancho, complejo, ancho, label="Prompt complejo", color="#b5651d"),
    ]
    for grupo in barras:
        ax.bar_label(grupo, fmt="%.1f", fontsize=8, padding=2)

    ax.set_xlabel("Modelo")
    ax.set_ylabel("Tiempo de respuesta (segundos)")
    ax.set_title("Tiempo de respuesta según modelo y complejidad del prompt")
    ax.set_xticks(x)
    ax.set_xticklabels(modelos)
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    salida = CARPETA / "grafica_tiempos.png"
    fig.savefig(salida, dpi=120)
    plt.close(fig)
    return salida


def grafica_dispersion(datos: list[dict]) -> Path:
    """Parámetros (X) vs tiempo promedio (Y), con la recta de tendencia."""
    parametros = np.array([d["parametros_B"] for d in datos], dtype=float)
    promedios = np.array([d["promedio_s"] for d in datos], dtype=float)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(parametros, promedios, s=140, color="#3d7ea6", zorder=3)

    for d in datos:
        ax.annotate(
            f"{d['modelo']}\n{d['promedio_s']} s",
            (d["parametros_B"], d["promedio_s"]),
            textcoords="offset points",
            xytext=(10, -6),
            fontsize=9,
        )

    # Recta de mínimos cuadrados: si los puntos se pegan a la recta, la relación
    # es lineal; si se despegan hacia arriba, crece más rápido que lineal.
    pendiente, corte = np.polyfit(parametros, promedios, 1)
    xs = np.linspace(parametros.min() - 0.5, parametros.max() + 1.5, 100)
    ax.plot(
        xs,
        pendiente * xs + corte,
        "--",
        color="#b5651d",
        label=f"Tendencia lineal: {pendiente:.2f} s por cada 1B de parámetros",
    )

    ax.set_xlabel("Parámetros del modelo (miles de millones)")
    ax.set_ylabel("Tiempo promedio de respuesta (segundos)")
    ax.set_title("¿Es lineal la relación entre tamaño del modelo y tiempo?")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()

    salida = CARPETA / "grafica_dispersion.png"
    fig.savefig(salida, dpi=120)
    plt.close(fig)
    return salida


def grafica_velocidad(datos: list[dict]) -> Path:
    """Velocidad real de generación: caracteres producidos por segundo.

    El tiempo bruto engaña, porque una respuesta más larga tarda más aunque el
    modelo sea igual de rápido. Dividir el largo de la respuesta por el tiempo
    aísla la velocidad de generación del modelo.
    """
    modelos = [d["modelo"] for d in datos]
    velocidades = []
    for d in datos:
        caracteres = sum(len(t) for t in d["respuestas"].values())
        segundos = sum(d["tiempos"].values())
        velocidades.append(caracteres / segundos)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    barras = ax.bar(modelos, velocidades, color=["#4c9f70", "#3d7ea6", "#b5651d"])
    ax.bar_label(barras, fmt="%.1f", fontsize=10, padding=3)
    ax.set_xlabel("Modelo")
    ax.set_ylabel("Caracteres generados por segundo")
    ax.set_title("Velocidad real de generación (independiente del largo de la respuesta)")
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    salida = CARPETA / "grafica_velocidad.png"
    fig.savefig(salida, dpi=120)
    plt.close(fig)
    return salida


def main() -> int:
    datos = cargar()
    print("Generada:", grafica_barras(datos))
    print("Generada:", grafica_dispersion(datos))
    print("Generada:", grafica_velocidad(datos))

    print("\n--- Velocidad de generación (lo que el tiempo bruto esconde) ---")
    print("| Modelo | Caracteres totales | Segundos totales | Caracteres/segundo |")
    print("|---|---|---|---|")
    for d in datos:
        caracteres = sum(len(t) for t in d["respuestas"].values())
        segundos = sum(d["tiempos"].values())
        print(
            f"| `{d['modelo']}` | {caracteres} | {segundos:.2f} s | "
            f"**{caracteres / segundos:.1f}** |"
        )

    # Dato útil para las conclusiones del análisis.
    parametros = np.array([d["parametros_B"] for d in datos], dtype=float)
    promedios = np.array([d["promedio_s"] for d in datos], dtype=float)
    pendiente, _ = np.polyfit(parametros, promedios, 1)
    correlacion = np.corrcoef(parametros, promedios)[0, 1]
    print(f"\nPendiente: {pendiente:.2f} s por cada mil millones de parámetros")
    print(f"Correlación (r): {correlacion:.4f}  (1.0 = línea perfecta)")

    base = promedios[0] / parametros[0]
    print("\nSi la relación fuera exactamente proporcional al tamaño:")
    for p, real in zip(parametros, promedios):
        print(f"  {p}B → esperado {base * p:.2f} s | real {real:.2f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
