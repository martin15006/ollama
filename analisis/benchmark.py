"""Banco de pruebas: mide el tiempo de respuesta de los 3 modelos.

Protocolo de la Actividad 3: el MISMO prompt en los 3 modelos, con tres niveles
de dificultad creciente. Los resultados quedan en `resultados.json` para que
`graficas.py` los dibuje.

Uso:
    python analisis/benchmark.py

Detalle metodológico importante: antes de medir cada modelo se hace una llamada
de calentamiento que NO se cuenta. Ollama tarda mucho más la primera vez porque
carga el modelo en RAM (medido: 26.76 s el primer mensaje contra 1.09 s el
segundo). Si ese tiempo se mezclara con el primer prompt, la comparación entre
modelos mediría la carga en disco, no la velocidad de generación. El tiempo de
carga se mide aparte, porque también es un dato interesante.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

# Permite ejecutar el script desde la raíz del proyecto (`python analisis/benchmark.py`)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm_client import MODELOS_DISPONIBLES, OllamaClient, OllamaError

PROMPTS = {
    "simple": "Explica en una oración qué es Machine Learning.",
    "medio": (
        "Explica la diferencia entre una red neuronal de una capa "
        "y una red profunda con 10 capas."
    ),
    "complejo": (
        "Escribe un código Python de 20 líneas que use requests "
        "para consumir la API de Ollama."
    ),
}

PARAMETROS_B = {"gemma2:2b": 2.0, "llama3.2:3b": 3.2, "llama3.1:8b": 8.0}

SALIDA = Path(__file__).resolve().parent / "resultados.json"


def medir(cliente: OllamaClient, modelo: str) -> dict:
    """Calienta el modelo y luego mide los tres prompts."""
    print(f"\n=== {modelo} ===")

    print("  calentando (carga en RAM, no se cuenta)…", end=" ", flush=True)
    calentamiento = cliente.generar(modelo, "Responde solo: ok")
    print(f"{calentamiento.segundos:.2f} s")

    fila = {
        "modelo": modelo,
        "parametros_B": PARAMETROS_B[modelo],
        "carga_inicial_s": round(calentamiento.segundos, 2),
        "tiempos": {},
        "respuestas": {},
    }

    for nivel, prompt in PROMPTS.items():
        print(f"  prompt {nivel}…", end=" ", flush=True)
        respuesta = cliente.generar(modelo, prompt)  # sin contexto: cada uno independiente
        fila["tiempos"][nivel] = round(respuesta.segundos, 2)
        fila["respuestas"][nivel] = respuesta.texto
        print(f"{respuesta.segundos:.2f} s ({len(respuesta.texto)} caracteres)")

    tiempos = fila["tiempos"].values()
    fila["promedio_s"] = round(sum(tiempos) / len(tiempos), 2)
    return fila


def main() -> int:
    cliente = OllamaClient(timeout=600)  # el 8B con prompt complejo puede tardar

    try:
        instalados = cliente.modelos_instalados()
    except OllamaError as exc:
        print(f"ERROR: {exc}")
        return 1

    faltantes = [m for m in MODELOS_DISPONIBLES if m not in instalados]
    if faltantes:
        print("Faltan modelos por descargar: " + ", ".join(faltantes))
        print("Ejecutá:  " + "  ".join(f"ollama pull {m}" for m in faltantes))
        return 1

    inicio = time.time()
    resultados = []
    for modelo in MODELOS_DISPONIBLES:
        try:
            resultados.append(medir(cliente, modelo))
        except OllamaError as exc:
            print(f"  ERROR con {modelo}: {exc}")
            return 1

    SALIDA.write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nTiempo total del banco de pruebas: {time.time() - inicio:.1f} s")
    print(f"Resultados guardados en {SALIDA}\n")

    # Tabla lista para pegar en ANALISIS.md
    print("| Modelo | Parámetros | Simple | Medio | Complejo | Promedio | Carga inicial |")
    print("|---|---|---|---|---|---|---|")
    for r in resultados:
        t = r["tiempos"]
        print(
            f"| `{r['modelo']}` | ~{r['parametros_B']}B | {t['simple']} s | "
            f"{t['medio']} s | {t['complejo']} s | **{r['promedio_s']} s** | "
            f"{r['carga_inicial_s']} s |"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
