# Análisis comparativo — 3 modelos de lenguaje corriendo en local

Actividad 3 · *Aplicación de Apps de Inteligencia Artificial* · SENA Regional Tolima ·
Mediciones del **31 de julio de 2026**.

---

## 1. Metodología

### Equipo de prueba

| Componente | Especificación |
|---|---|
| CPU | AMD Ryzen 5 5600GT — 6 núcleos / 12 hilos |
| RAM | 14 GB utilizables |
| GPU | **Gráficos integrados AMD Radeon — sin GPU dedicada** |
| Sistema | Windows 11 Pro (build 26200) |
| Ollama | API local en `http://localhost:11434` |

> Toda la inferencia corre **en CPU**. En un equipo con GPU dedicada estos tiempos bajan
> mucho. Los números de abajo describen este PC, no los modelos en abstracto.

### Protocolo

- Los **mismos 3 prompts** en los 3 modelos, literalmente los que indica el material de
  apoyo (sección 5.1).
- Cada prompt se envía **sin contexto previo**, para que ninguna respuesta se beneficie de
  la conversación anterior.
- **Calentamiento previo que no se cuenta:** antes de medir, se envía un mensaje corto a
  cada modelo. Ollama tarda mucho más la primera vez porque tiene que cargar el modelo del
  disco a la RAM. Si ese tiempo se mezclara con el primer prompt, la comparación estaría
  midiendo la velocidad del disco, no la del modelo. El tiempo de carga se reporta aparte
  porque también es un dato útil.
- Medición con `time.perf_counter()` alrededor de la petición HTTP, en
  [`app/llm_client.py`](app/llm_client.py).
- Todo es reproducible: `python analisis/benchmark.py` y `python analisis/graficas.py`.
  Los datos crudos, incluidas las respuestas completas, quedan en
  [`analisis/resultados.json`](analisis/resultados.json).

### Los 3 prompts

| Nivel | Prompt |
|---|---|
| Simple | *Explica en una oración qué es Machine Learning.* |
| Medio | *Explica la diferencia entre una red neuronal de una capa y una red profunda con 10 capas.* |
| Complejo | *Escribe un código Python de 20 líneas que use requests para consumir la API de Ollama.* |

---

## 2. Tabla de registro de tiempos

| Modelo | Parámetros | Prompt simple | Prompt medio | Prompt complejo | Promedio | Calidad (1-5) |
|---|---|---|---|---|---|---|
| `gemma2:2b` | ~2B | **4.55 s** | 40.58 s | 39.69 s | **28.27 s** | 2.7 |
| `llama3.2:3b` | ~3.2B | 5.15 s | 57.63 s | **31.42 s** | 31.40 s | **3.0** |
| `llama3.1:8b` | ~8B | 13.45 s | 64.71 s | 101.03 s | 59.73 s | **3.0** |

Tiempo de carga inicial en RAM (medido aparte, no incluido arriba):

| Modelo | Carga inicial |
|---|---|
| `gemma2:2b` | 5.69 s |
| `llama3.2:3b` | 6.27 s |
| `llama3.1:8b` | 13.02 s |

Duración total del banco de pruebas: **383.2 segundos** (6 min 23 s).

---

## 3. Gráficas

### Gráfica 1 — Tiempo por modelo y complejidad del prompt

![Tiempos por modelo y prompt](analisis/grafica_tiempos.png)

> [!WARNING]
> **Ojo con esta gráfica: engaña.** En `gemma2:2b` y `llama3.2:3b`, el prompt
> *complejo* tardó **menos** que el *medio*. ¿El prompt difícil es más rápido que el fácil?
> No. La explicación está en la sección 5.

### Gráfica 2 — Parámetros vs tiempo promedio

![Parámetros vs tiempo promedio](analisis/grafica_dispersion.png)

Recta de tendencia: **5.43 segundos por cada mil millones de parámetros**.
Correlación: **r = 0.9950**.

### Gráfica 3 — Velocidad real de generación

![Velocidad de generación](analisis/grafica_velocidad.png)

---

## 4. Evaluación de la calidad (con evidencia)

La calificación no es una impresión: está sostenida en lo que cada modelo escribió.
Las respuestas completas están en `analisis/resultados.json`.

### Prompt simple — *"Explica en una oración qué es Machine Learning"*

| Modelo | Calidad | Observación |
|---|---|---|
| `gemma2:2b` | 4 | Correcto en el fondo, pero traduce el término como *"La máquina de aprendizaje"*, un calco incorrecto: en español se dice *aprendizaje automático*. |
| `llama3.2:3b` | 5 | Definición correcta y bien redactada. |
| `llama3.1:8b` | 5 | Definición correcta, agrega la idea de adaptarse a situaciones nuevas. |

Los tres cumplieron. Para una tarea así, pagar 13.45 s del 8B en lugar de 4.55 s del 2B
**no compra nada**.

### Prompt medio — *"Diferencia entre red de una capa y red profunda"*

| Modelo | Calidad | Observación |
|---|---|---|
| `gemma2:2b` | 3 | Bien estructurado, pero afirma que una red de una capa sirve para *"clasificación básica de imágenes (perro o gato)"* — falso, ese es justamente el tipo de problema que una sola capa **no** resuelve. |
| `llama3.2:3b` | 3 | Estructura clara, pero se enreda: dice que en una red de una capa *"las neuronas se comunican directamente entre sí"*, lo cual no describe bien una capa densa. |
| `llama3.1:8b` | **2** | El peor de los tres. Afirma que *"las redes neuronales de una capa no pueden aprender ya que no tienen múltiples capas para aplicar retropropagación"* — **es falso**: un perceptrón de una capa se entrena perfectamente con descenso de gradiente. Además divaga antes de responder. |

**El modelo más grande dio la peor respuesta, y tardó 64.71 s en darla.**

### Prompt complejo — *"Código Python que consuma la API de Ollama"*

Este es el resultado más interesante de todo el trabajo. **Los tres modelos fallaron, y
fallaron igual.** Ninguno escribió `http://localhost:11434/api/generate`:

| Modelo | Calidad | Qué inventó |
|---|---|---|
| `gemma2:2b` | 1 | URL inventada `https://api.llama.cool/v1/completions`, con `Bearer YOUR_API_TOKEN`. Encima usa como modelo `facebook/bart-large`, que es de **HuggingFace**, no de Ollama. |
| `llama3.2:3b` | 1 | Escribe mal el nombre del producto (*"Olma"*) e inventa `https://api.olma.com/api/v1/your-endpoint` con token de acceso. |
| `llama3.1:8b` | 2 | Código más ordenado y coherente, pero inventa `https://api.ollama.io/conversations` con **login por email y contraseña**. Ollama no tiene cuentas ni login. |

Los tres alucinaron una API **en la nube y de pago** para describir una herramienta cuya
característica principal es **correr local y gratis**. Es exactamente lo contrario de la
realidad, expresado con total seguridad y sin ninguna señal de duda.

> [!IMPORTANT]
> **Ninguno de estos modelos habría podido escribir la app de este repositorio.**
> El código de `app/llm_client.py` lo generó Claude (modelo de nube, muchísimo más grande),
> tal como indica el material de apoyo en la sección 4.2.

---

## 5. Lo que el tiempo bruto esconde

En `gemma2:2b`, el prompt medio tardó 40.58 s y el complejo 39.69 s. En `llama3.2:3b` la
diferencia es aún más marcada: 57.63 s el medio contra 31.42 s el complejo. **El prompt
"difícil" fue más rápido que el "fácil".**

La razón: un LLM genera **un token por vez**. El tiempo depende casi por completo de
**cuántos tokens escribe**, no de lo "difícil" que sea la pregunta. El prompt medio provocó
respuestas largas (2364 y 2895 caracteres); el complejo, respuestas más cortas.

Dividiendo caracteres generados sobre segundos empleados se obtiene la velocidad real,
independiente del largo:

| Modelo | Caracteres totales | Segundos totales | **Caracteres por segundo** |
|---|---|---|---|
| `gemma2:2b` | 4433 | 84.82 s | **52.3** |
| `llama3.2:3b` | 4724 | 94.20 s | **50.1** |
| `llama3.1:8b` | 3398 | 179.19 s | **19.0** |

Esta métrica cambia la lectura por completo:

- `gemma2:2b` y `llama3.2:3b` son **prácticamente igual de rápidos** (52.3 vs 50.1 c/s),
  aunque el segundo tiene 60% más parámetros.
- El salto real está en el 8B: **2.7 veces más lento** que el 2B.
- El promedio de 28.27 s de `gemma2:2b` no significa que sea "casi tan lento" como el 3B:
  significa que en esta corrida le tocó escribir menos texto.

---

## 6. Preguntas de reflexión

### 6.1 ¿La relación entre parámetros y tiempo de respuesta fue lineal? ¿Qué sugiere sobre la complejidad computacional?

**Con el tiempo bruto parece lineal — pero es una conclusión frágil.**

La correlación entre parámetros y tiempo promedio da **r = 0.9950**, casi una recta
perfecta, con pendiente de **5.43 s por cada mil millones de parámetros**. Con eso solo,
uno concluiría "sí, es lineal" y cerraría el tema.

Hay tres razones para no quedarse ahí:

1. **Son solo 3 puntos.** Por tres puntos casi siempre se puede trazar una recta convincente.
   Un r alto con n = 3 no demuestra gran cosa.
2. **El tiempo promedio depende del largo de las respuestas**, que fue distinto en cada
   modelo (4433, 4724 y 3398 caracteres). La variable no está controlada.
3. **Con la métrica limpia, la recta se rompe.** Si el tiempo fuera estrictamente
   proporcional al tamaño, pasar de 2B a 3.2B debería costar 60% más tiempo. En la práctica
   la velocidad casi no cambió (52.3 → 50.1 c/s, apenas 4% más lento). Y de 2B a 8B —cuatro
   veces más parámetros— la velocidad cayó 2.7 veces, **menos** de lo que predice la
   proporción directa.

**Qué sugiere sobre la complejidad computacional:** la teoría dice que generar un token
cuesta aproximadamente el doble de operaciones que parámetros tiene el modelo, o sea que
debería ser lineal. Lo que se observa es que en este PC la relación es **sublineal en la
zona baja**: con modelos chicos el cuello de botella no es la cantidad de cálculos, sino
mover los pesos entre la RAM y la CPU. Por eso 2B y 3.2B rinden casi igual: ambos caben
cómodos y la CPU no llega a saturarse. El 8B sí pesa lo suficiente (~4.9 GB) para que el
costo real empiece a notarse.

**Conclusión honesta:** con los datos de esta actividad **no se puede afirmar** que la
relación sea lineal. Lo que sí se puede afirmar es que **crece de forma sostenida** y que
hay un salto claro al llegar al 8B. Para responder bien haría falta medir más modelos
(1B, 4B, 7B, 13B) y fijar el largo de la respuesta.

### 6.2 ¿El modelo más grande siempre dio la mejor respuesta? ¿Hubo casos donde el pequeño respondió mejor?

**No, y hay dos casos concretos donde el grande quedó peor.**

- **Prompt medio:** `llama3.1:8b` fue el **único** que afirmó algo abiertamente falso (que
  una red de una capa no puede aprender porque no se le puede aplicar retropropagación).
  Los dos modelos chicos, con imprecisiones menores, no dijeron nada tan grueso. Y el 8B
  tardó 64.71 s en producir esa respuesta, contra 40.58 s del 2B.
- **Prompt simple:** los tres respondieron bien. El 8B tardó **casi 3 veces más** (13.45 s
  contra 4.55 s) para llegar al mismo lugar.
- **Prompt complejo:** ninguno acertó. El 8B fue algo mejor en estructura, pero para eso
  gastó 101.03 s — **2.5 veces más** que el 2B, y el resultado sigue siendo código que no
  funciona.

**Conclusión:** más parámetros ≠ mejor respuesta garantizada. Sirven para tareas de
razonamiento largo; para preguntas de definición son plata tirada en tiempo. Y sobre datos
que el modelo no vio bien durante el entrenamiento (como una herramienta reciente),
**el modelo grande alucina con más elocuencia, no con más verdad**.

### 6.3 ¿Qué problemas concretos de mi contexto podría resolver una app así?

El valor está en que funciona **sin internet y sin mandar los datos a nadie**:

- **Zonas rurales del Tolima con mala conectividad:** un asistente que funciona con el
  cable desconectado sirve donde una herramienta de nube simplemente no carga.
- **Documentos con datos personales** (historias clínicas, hojas de vida, contratos): se
  pueden resumir o redactar sin que el texto salga del equipo. Con una herramienta de nube,
  eso es un problema legal y ético.
- **Apoyo al estudio en instituciones sin presupuesto:** cero costo por consulta. Un
  laboratorio con 20 equipos puede tener 20 asistentes sin pagar suscripciones.
- **Micronegocios:** redactar descripciones de productos, responder mensajes, ordenar
  inventario — sin cuota mensual.

Un límite que este análisis deja claro: para **generar código** estos modelos locales todavía
no alcanzan. Para redactar, resumir, traducir y explicar, sí.

### 6.4 ¿Hay diferencia entre usar Claude (nube) vs LLaMA local en privacidad?

**Sí, y es una diferencia de fondo, no de grado.**

| | Claude / nube | LLaMA local |
|---|---|---|
| Dónde viaja el texto | A servidores de la empresa, por internet | No sale de la RAM del PC |
| Quién puede leerlo | La empresa, según su política; y quien intercepte o vulnere el servicio | Solo quien tenga acceso físico al equipo |
| Retención | Según los términos del servicio, fuera de mi control | Solo lo que yo guarde en disco |
| Si mañana cambian los términos | Me afecta | No me afecta: el modelo ya está descargado |
| Funciona sin internet | No | Sí |
| Costo por consulta | Sí | No |

Con Ollama, la conversación va a `localhost` — nunca cruza la tarjeta de red. Con una
herramienta de nube, **cada palabra sale del equipo**.

**El matiz honesto:** la privacidad se paga en capacidad. Este mismo análisis muestra que
los tres modelos locales inventaron una API que no existe, mientras que la app de este
repositorio la escribió un modelo de nube. La decisión correcta no es "local siempre" ni
"nube siempre", sino **según el dato**: información sensible o personal → local, aunque la
respuesta sea peor; problema difícil con datos públicos → nube.

---

## 7. Conclusiones

1. **El tamaño cuesta tiempo, y se nota.** El 8B fue **2.1 veces más lento en promedio** y
   **2.7 veces más lento generando texto** que el 2B. En un PC sin GPU es una diferencia
   que se siente en cada mensaje.

2. **`llama3.2:3b` es la mejor opción para este equipo.** Genera a 50.1 caracteres por
   segundo —prácticamente lo mismo que el 2B— con respuestas mejor redactadas. El 8B no
   compensa lo que cobra.

3. **Más parámetros no garantizan mejor respuesta.** El modelo grande dio la peor
   explicación del prompt medio, con un error conceptual claro.

4. **Los tres alucinaron la API de Ollama.** Ninguno mencionó `localhost:11434`; los tres
   inventaron un servicio de nube con token de pago. Es la lección más valiosa de la
   actividad: **un LLM afirma con la misma seguridad lo que sabe y lo que inventa**. Sin
   verificar contra la documentación real, el error pasa desapercibido.

5. **La métrica cruda engaña.** El tiempo por respuesta mezcla velocidad del modelo con
   largo de la respuesta. Sin normalizar por caracteres generados, la conclusión "el prompt
   complejo es más rápido que el medio" habría quedado escrita como si tuviera sentido.

6. **El costo de arranque importa en la experiencia de uso.** Cargar el 8B en RAM toma
   13.02 s antes de escribir la primera letra. Por eso la app avisa `Pensando…` y no se
   congela: sin eso, el usuario cree que el programa se colgó.

---

## Autor

**Juan Sebastián Martín Moncada**
Aprendiz — *Aplicación de Apps de Inteligencia Artificial*
SENA Regional Tolima · Centro de Industria y Construcción · 2026
