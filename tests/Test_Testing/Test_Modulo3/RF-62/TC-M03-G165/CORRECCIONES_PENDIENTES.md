# CORRECCIONES PENDIENTES — TC-M03-G165 (RF-62 / RF-63)

Este documento registra de manera formal y detallada las correcciones técnicas, operativas y de configuración pendientes de aplicar antes de la primera ejecución autorizada contra el entorno **TEST**.

---

### C1. Aislamiento de Conftest: `--noconftest` vs `--confcutdir` y Registro del Banner D7

* **Problema:**  
  El uso de la bandera `--noconftest` desactiva **todos** los archivos `conftest.py`, incluyendo el [conftest.py local](conftest.py) del directorio del caso de prueba. Además, en Pytest el hook `pytest_sessionstart` **no se registra si está definido dentro de un módulo de test** (`test_tc_m03_g165.py`), pues Pytest solo carga hooks de ciclo de vida de sesión desde plugins formales o archivos `conftest.py`. Como consecuencia directa, con `--noconftest` el banner obligatorio de la Decisión D7 no se imprime en consola ni se inyecta en la metadata del reporte HTML.
* **Por qué importa:**  
  La Decisión D7 exige como principio normativo que el equipo visualice claramente el estado de los literales pendientes de análisis antes de cada ejecución. Asimismo, es imperativo bloquear la carga del `tests/conftest.py` raíz (que importa `main.py` y causa colisiones con dependencias de servidor local).
* **Corrección propuesta:**  
  1. Sustituir `--noconftest` por `--confcutdir=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165` en la línea de comandos oficial. Esto le indica a Pytest que corte la búsqueda jerárquica de `conftest.py` en este directorio, ignorando el `tests/conftest.py` raíz y cargando exclusivamente el `conftest.py` local.
  2. Mover la implementación del hook `pytest_sessionstart` y el hook `pytest_html_report_title` / inyección de metadata al archivo `conftest.py` local.
  3. Actualizar la documentación y ejemplos en `README_EJECUCION.md`.
* **Cómo verificar cuando se autorice:**  
  Ejecutar con `--collect-only --confcutdir=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165` y verificar que el banner de pre-ejecución D7 se imprima en consola al inicio de la sesión sin errores de importación de `main.py`.

---

### C2. Revisión de Configuración en `pytest.ini` e Incompatibilidades con Cobertura (`--cov`)

* **Problema:**  
  El archivo `pytest.ini` global del repositorio define `testpaths = tests` y el entorno virtual tiene instalado el plugin `pytest-cov`. Si se ejecutan comandos sin aislar opciones, plugins como `pytest-cov` pueden intentar instrumentar el código fuente de `src/`, lo cual genera lentitud innecesaria en pruebas de integración HTTP o errores al recolectar módulos no cubiertos.
* **Por qué importa:**  
  TC-M03-G165 es una suite de verificación de caja negra basada en peticiones HTTP con `requests` contra un entorno remoto (`api.inmero.co`); no mide cobertura de código local ni debe interactuar con los mecanismos de instrumentación de `pytest-cov`.
* **Corrección propuesta:**  
  Añadir explícitamente en la invocación oficial la opción `-o addopts=""` o `-p no:cov` para evitar que plugins de cobertura interfieran con la recolección o la medición de tiempos del sandbox.
* **Cómo verificar cuando se autorice:**  
  Correr con `-p no:cov` y confirmar que no se generen artefactos `.coverage` ni advertencias de módulos no medidos.

---

### C3. Robustez de la Fixture `auditoria_eventos_control` y Manejo de Delata

* **Problema:**  
  1. La fixture `auditoria_eventos_control` en `test_tc_m03_g165.py` no tiene configurado `autouse=True` ni es referenciada por las fixtures de clase, por lo que Pytest nunca la invoca.
  2. El endpoint `/test-control/query` en el servidor TEST podría rechazar peticiones que no incluyan el encabezado `X-Test-Run-Id` si el middleware de sandbox lo exige de forma estricta.
  3. Actualmente la fixture solo ejecuta un `print()` en consola (el cual es silenciado por Pytest si no se usa la bandera `-s`) y ante cualquier excepción deja `c_pre = None`, omitiendo la verificación silenciosamente.
  4. Si se detecta un delta mayor a cero, reportarlo como error automático podría generar falsos positivos si otro miembro del equipo o proceso batch está interactuando simultáneamente con el entorno TEST.
* **Por qué importa:**  
  La auditoría en `modulo1.eventos` tiene disparadores de base de datos que impiden operaciones DML destructivas (`UPDATE`/`DELETE`); si una prueba contamina esta tabla, no se puede revertir fácilmente.
* **Corrección propuesta:**  
  1. Declarar la fixture con `scope="session", autouse=True`.
  2. Implementar una estrategia de consulta robusta: intentar primero la consulta sin `X-Test-Run-Id`; si el endpoint responde con 400/401/422 requiriendo el identificador, abrir un `run_id` efímero temporal (`test-audit-probe-<uuid>`), ejecutar el SELECT y cerrarlo de inmediato con DELETE.
  3. Inyectar el resultado de la medición (`conteo_inicial`, `conteo_final`, `delta` o `"NO MEDIDO: <motivo>"`) en la metadata visible de `pytest-html` (hook `pytest_metadata`).
  4. Documentar un delta positivo como advertencia: `"REVISAR: incremento detectado (puede ser actividad concurrente en TEST)"`.
* **Cómo verificar cuando se autorice:**  
  Ejecutar el escenario base con `-s` y verificar en la consola y en la cabecera del HTML el reporte claro del conteo inicial, final y delta de `modulo1.eventos`.

---

### C4. Preflight Dinámico del Sensor: Ventana Temporal en lugar de Cero Lecturas Totales

* **Problema:**  
  El preflight actual sugiere buscar un sensor con "cero lecturas totales" en la base de datos de pruebas. En un entorno compartido con 257 dispositivos y semanas de pruebas previas, es altamente probable que todos los sensores ambientales ya posean lecturas históricas, lo que provocaría que el preflight aborte erróneamente sin encontrar candidatos.
* **Por qué importa:**  
  Para que el cálculo de calidad de RF-62 sea determinista, lo que verdaderamente se requiere no es que el sensor sea nuevo de fábrica, sino que **no existan lecturas reales dentro de la ventana de tiempo específica que abarcará la serie de prueba** (desde $t_{\text{ref}} - 210\text{ min}$ hasta $t_{21} + 10\text{ min}$).
* **Corrección propuesta:**  
  Modificar la consulta del preflight para evaluar la ventana temporal:
  ```sql
  SELECT count(*) FROM modulo3.telemetrias 
  WHERE id_sensor = :id_sensor 
    AND timestamp_captura BETWEEN :ts_inicio_ventana AND :ts_fin_ventana
  ```
  Si el sensor seleccionado no tiene lecturas dentro de ese rango horario, es apto para la prueba. Si tiene colisiones, iterar sobre el catálogo de sensores activos descubiertos hasta encontrar uno libre, o abortar con un mensaje descriptivo sin exponer credenciales.
* **Cómo verificar cuando se autorice:**  
  Ejecutar el preflight contra TEST y confirmar que seleccione automáticamente un sensor ambiental disponible sin colisión de timestamps.

---

### C5. Coherencia en Timestamps, Cadencia y Modo de Ingesta (`BUFFER_LOCAL`)

* **Problema:**  
  La ingesta individual con `origen = "TIEMPO_REAL"` valida que el `timestamp_captura` no sea mayor a 300 segundos en el futuro y, según la implementación del use case de ingesta, puede aplicar restricciones sobre lecturas pasadas de más de ~200 minutos. Asimismo, una serie histórica de 20 lecturas espaciadas por 10 minutos retrocede más de 3 horas hacia el pasado.
* **Por qué importa:**  
  Si la ingesta rechaza una lectura por antigüedad (`ERROR_TIEMPO`), la serie no alcanzará las $N=20$ lecturas requeridas y el use case evaluará la calidad con clasificación `INDETERMINADA` (serie insuficiente).
* **Corrección propuesta:**  
  1. Configurar explícitamente `origen = "BUFFER_LOCAL"` para la ingesta de las 20 lecturas históricas de la serie previa (el use case tolera hasta 72 horas en el pasado para sincronización de buffers).
  2. Para la lectura evaluada (lectura 21), asegurar que su timestamp satisfaga estrictamente $t_{21} \le t_{\text{servidor}} + 300\text{ s}$.
  3. Fijar el campo `frecuencia_muestreo = 10` (coherente con los 10 minutos de cadencia) y formatear los valores decimales como `f"{val:.2f}"` (con dos decimales fijos) para evitar discrepancias en la comparación de cadenas que realiza el algoritmo de sensor congelado (`str(v)`).
* **Cómo verificar cuando se autorice:**  
  Verificar que las 20 llamadas de la serie previa retornen código HTTP 201 y que `SELECT count(*) ...` confirme las 20 filas persistidas en la ventana previa de evaluación.

---

### C6. Manejo Resiliente de Excepciones en Fixtures de Clase y Contabilización en Scanner

* **Problema:**  
  En las fixtures de clase `run_context`, si el llamado HTTP `POST /iot/calidad/{id}/evaluar` lanza una excepción o si el código hiciera un `assert resp.status_code == 201` dentro de la propia fixture, cualquier error del servidor (como un HTTP 500 ante $\sigma=0$ en S_318c) haría que la fixture falle en fase de **Setup**. Cuando una fixture falla en Setup, Pytest marca todos los tests de la clase como `ERROR` en lugar de `FAILED`.
* **Por qué importa:**  
  El `scanner.py` del QA Dashboard parsea los reportes computables (`pytest-html` / JSON) buscando específicamente los contadores de `passed` y `failed`. Los errores de Setup (`ERROR`) pueden no contabilizarse como fallos de aserción normativos, distorsionando la trazabilidad de los defectos.
* **Corrección propuesta:**  
  1. La fixture de clase no debe realizar aserciones de código de estado HTTP; debe capturar el objeto `response` y entregarlo en el diccionario de contexto (`ctx["resp_eval"]`), incluso si la API respondió con código 4xx o 5xx.
  2. Las aserciones deben ejecutarse exclusivamente dentro de las funciones de test (p. ej., `test_tc318c_no_error_5xx_con_sigma_cero` y `test_tc303_http_status_201`).
* **Cómo verificar cuando se autorice:**  
  Confirmar que un error de respuesta HTTP se traduzca limpiamente en un test fallido (`Failed`) en la tabla de resultados HTML y no en un fallo de infraestructura en el Setup.

---

### C7. Tolerancia Idempotente a Teardown Doble (Manejo de HTTP 404)

* **Problema:**  
  Cada clase de prueba incluye un test explícito al final (`test_teardown_rollback`) que llama a `DELETE /test-control/runs/{run_id}`. A su vez, la fixture `run_context` incluye un bloque `finally:` que vuelve a invocar `client.teardown_rollback()`. Si el test de teardown ya borró el run exitosamente, la segunda llamada en el bloque `finally` recibirá un código HTTP 404 (`RUN_NO_ENCONTRADO`).
* **Por qué importa:**  
  Si el método `teardown_rollback` considerara un código 404 como un fallo de infraestructura, la fase de Teardown de la fixture fallaría, ensuciando el reporte con errores posteriores a la ejecución de las pruebas.
* **Corrección propuesta:**  
  Asegurar en `SandboxClient.teardown_rollback` que tanto HTTP 200 como HTTP 404 sean considerados estados válidos de cierre exitoso (idempotencia). Si la respuesta es distinta de 200 y 404 (p. ej. HTTP 500 o error de conexión), el teardown debe registrarse y propagarse como fallo.
* **Cómo verificar cuando se autorice:**  
  Comprobar que tras la ejecución de `test_teardown_rollback`, la posterior limpieza del bloque `finally` culmine sin lanzar excepciones no controladas.

---

### C8. Mantenimiento del Formato `<NN>` en Títulos de Incidencias para Taiga

* **Problema:**  
  En versiones preliminares de documentación se numeraron manualmente incidencias como `INC-M03-01`, `INC-M03-02`, etc. La numeración secuencial de incidencias es responsabilidad exclusiva del equipo de QA al momento de crear formalmente los tickets en la plataforma Taiga.
* **Por qué importa:**  
  El estándar de control de calidad del proyecto estipula que los archivos versionados no deben autoasignar números de incidencia para evitar colisiones con defectos reportados por otros ingenieros en el módulo.
* **Corrección propuesta:**  
  Verificar que tanto en `TC-M03-G165_resultado.md` como en cualquier documentación técnica se mantenga estrictamente el formato normativo con comodín:
  ```text
  [INC-M03-<NN>-TC-M03-G165][RF-62] <resumen descriptivo <= 120 caracteres>
  ```
* **Cómo verificar cuando se autorice:**  
  Ejecutar un grep estático en la carpeta del caso y confirmar que no exista ningún identificador numérico estático (`INC-M03-01`, `INC-M03-02`, etc.).

---

### C9. Protocolo de Primera Corrida Recomendada (Aislamiento sin Reporte Parcial)

* **Problema:**  
  Si durante la primera corrida exploratoria contra TEST se ejecuta el comando completo con `--html=resultados/resultado_TC-M03-G165.html` limitando la ejecución a un único subcaso (p. ej. `-k "TestEscenarioBase"`), se generará un archivo HTML que contiene únicamente 16 de los 55 tests del grupo.
* **Por qué importa:**  
  El scanner del dashboard (`scanner.py`) inspecciona la carpeta `resultados/` y toma el reporte presente como la evaluación definitiva del grupo. Un reporte parcial indicaría métricas erróneas y podría marcar falsamente el caso como aprobado si solo corrió el Happy Path.
* **Corrección propuesta:**  
  Establecer como regla operativa en `README_EJECUCION.md`:
  1. La corrida de prueba/humo preliminar debe realizarse **sin la opción `--html`** (solo visualización por consola).
  2. La generación del archivo oficial `resultados/resultado_TC-M03-G165.html` solo debe dispararse cuando se ejecuten los **6 escenarios completos** en una única sesión.
* **Cómo verificar cuando se autorice:**  
  Confirmar que la carpeta `resultados/` permanezca limpia hasta que se ejecute la suite completa de los 55 tests.

---

## Tabla Resumen de Correcciones Pendientes

| ID | Resumen de la Corrección | Prioridad | Archivo Afectado | Estado |
|:---:|---|:---:|---|:---:|
| **C1** | Usar `--confcutdir` en vez de `--noconftest` y mover hooks del banner D7 a `conftest.py` local | **Alta** | `test_tc_m03_g165.py`, `conftest.py`, `README_EJECUCION.md` | **PENDIENTE (no aplicado)** |
| **C2** | Desactivar interferencias de `--cov` mediante `-p no:cov` en el comando oficial | **Media** | `README_EJECUCION.md` | **PENDIENTE (no aplicado)** |
| **C3** | Robustecer `auditoria_eventos_control` (autouse, soporte de run efímero, metadata HTML) | **Alta** | `test_tc_m03_g165.py`, `conftest.py` | **PENDIENTE (no aplicado)** |
| **C4** | Preflight del sensor filtrando por ventana de tiempo en lugar de cero lecturas históricas | **Alta** | `test_tc_m03_g165.py` | **PENDIENTE (no aplicado)** |
| **C5** | Asegurar modo `BUFFER_LOCAL` para serie previa y formato uniforme con dos decimales | **Alta** | `test_tc_m03_g165.py` | **PENDIENTE (no aplicado)** |
| **C6** | Fixtures de clase sin asserts HTTP (capturar response para que falle el test y no el Setup) | **Alta** | `test_tc_m03_g165.py` | **PENDIENTE (no aplicado)** |
| **C7** | Garantizar idempotencia en `teardown_rollback` ante respuesta HTTP 404 | **Media** | `helpers_tc_m03_g165.py` | **PENDIENTE (no aplicado)** |
| **C8** | Mantener placeholder `<NN>` en todos los títulos de incidencias para Taiga | **Baja** | `TC-M03-G165_resultado.md` | **PENDIENTE (no aplicado)** |
| **C9** | Protocolo de primera corrida de humo sin `--html` para evitar reportes parciales en scanner | **Media** | `README_EJECUCION.md` | **PENDIENTE (no aplicado)** |

---

> **Confirmación de Cumplimiento de Alcance:**  
> Se confirma por escrito que **no se ha modificado ningún archivo de código `.py`**, **no se ha realizado ninguna petición HTTP o de red**, y **no se ha ejecutado ningún comando contra el entorno TEST ni en local**. Únicamente se ha documentado este archivo normativo para su aplicación controlada cuando el equipo lo autorice.
