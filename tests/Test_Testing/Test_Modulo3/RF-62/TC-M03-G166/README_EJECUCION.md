# GUÍA DE EJECUCIÓN: TC-M03-G166 (RF-62 / RF-57 / RF-63)
**Caso:** Detección de Sensor Congelado y Fronteras de Severidad  
**Casos originales agrupados:** TC-M03-309, TC-M03-310, TC-M03-311  
**Entorno objetivo:** TEST (`https://www.api.inmero.co/api-sgpmp-test`)  
**Fallback secundario:** `https://api.inmero.co/api-sgpmp-test`  

---

## 1. Variables de Entorno Requeridas

Configure las siguientes variables en `.env.test` en la raíz del proyecto o expórtelas en su shell:

```bash
TEST_BASE_URL="https://www.api.inmero.co/api-sgpmp-test"
ENABLE_TEST_SANDBOX="true"
TEST_SANDBOX_SECRET="377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff"
TEST_ADMIN_EMAIL="administador.dev@gmail.com"
TEST_ADMIN_PASSWORD="<password-admin>"
```

> **IMPORTANTE (Política Anti-Hardcode y Seguridad):**
> - Prohibido usar `admin@pecuaria.co`.
> - Confirmar conectividad con `GET /health` antes de ejecutar; si la URL principal no responde, utilizar el fallback `https://api.inmero.co/api-sgpmp-test`.
> - Prohibido escribir contraseñas reales en archivos de repositorio o documentación.
> - Si falta alguna variable requerida, el test aborta inmediatamente con `SandboxConfigError` sin exponer secretos.

---

## 2. Comando Oficial de Ejecución (Fase 3)

Para ejecutar el caso de prueba aislando los archivos de configuración globales (`conftest.py` raíz que importa `main.py`) y generando los reportes computables reconocidos por el Scanner del Dashboard de QA (JUnit XML y pytest-html):

```powershell
$env:PYTHONPATH="."
$env:TEST_BASE_URL="https://www.api.inmero.co/api-sgpmp-test"
$env:ENABLE_TEST_SANDBOX="true"
$env:TEST_SANDBOX_SECRET="377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff"

pytest tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G166/ `
  --confcutdir=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G166 `
  -p no:cov `
  -v --tb=short `
  --html=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G166/resultados/resultado_TC-M03-G166.html --self-contained-html `
  --junitxml=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G166/resultados/resultado_TC-M03-G166.xml
```

---

## 3. Banner D7 (Ciclo de Vida de Evaluación - RESUELTO)

En cumplimiento de la Decisión D7 (RESUELTO por respuesta de análisis; RFC de aclaración de RF-62 en trámite), el hook `pytest_report_header` en [conftest.py](conftest.py) emite la siguiente línea informativa:

```text
==============================================================================
 [BANNER D7 RESUELTO] TC-M03-G166 -- ESTADO DE EVALUACION DE CALIDAD
==============================================================================
 * D7 RESUELTO: literal VIGENTE; catálogo {VIGENTE, SUPERADA}; RFC de aclaración en trámite.
 * Estado Superado Normativo : SUPERADA (RF-62 restriccion 9)
 * Estado Vigente Definido   : VIGENTE
 * Catalogo de Estados       : ['VIGENTE', 'SUPERADA']
 * Estados Definidos (D7)    : True
 * Regla canónica            : Máximo UNA evaluación VIGENTE por lectura.
 * Defecto conocido          : /evaluar duplica VIGENTES (invariante debe fallar hoy).
==============================================================================
```

- **Aserción normativa activa:** Valida que `estado_evaluacion == 'VIGENTE'` en la respuesta de evaluación y pertenezca al catálogo `{'VIGENTE', 'SUPERADA'}` (sin skips).
- **Nuevo test del invariante:** `test_g166_invariante_una_sola_vigente` y `test_g166_transicion_superada` verifican que exista un máximo de una evaluación VIGENTE por lectura tras evaluar.

---

## 4. Supuestos "NO VERIFICADO" a Validar en Primera Ejecución en TEST

Los siguientes elementos no pueden validarse en modo estático y se verifican dinámicamente en los preflights del script:

1. **Catálogo OpenAPI en vivo:** Confirmar que los routers de `/iot/telemetria`, `/iot/calidad`, `/iot/alertas` y `/iot/auditoria` se encuentren publicados y funcionales en TEST (el archivo estático local `openapi-test.json` solo incluye M01).
2. **Formato de respuesta de `/test-control/query`:** Validar que las consultas devuelvan `{"rows": [...]}` o `{"data": [...]}`.
3. **Sensor Ambiental Activo:** Descubrimiento dinámico de un sensor de `TEMPERATURA_AMBIENTAL` (id=9) activo con serial como `access_key`.
4. **Ventana Temporal Sin Intrusas:** Validación mediante consulta de que el sensor no tenga telemetrías registradas entre $T_0 - 410\text{ min}$ y $T_0$.
5. **Calibración Nominal del Sensor:** Confirmación de que el sensor opera con factor ganancia=1 y offset=0 (o sin calibración previa activa).
6. **Inocuidad en `modulo1.eventos`:** Medición de delta de eventos en modulo1 antes y después de la suite (conteo reportado en consola y metadata).
   - *Análisis Estático de Aislamiento Transaccional (`test_control_router.py:42-87`, `testing_sandbox.py:48-56` y `testing_middlaware.py:17-27`):*
     El endpoint `/test-control/query` exige obligatoriamente la cabecera `X-Test-Run-Id` y el secreto de sandbox `X-Sandbox-Secret`. Cada `run_id` efímero abre una conexión con nivel de aislamiento estándar `READ COMMITTED`. Por tanto, una consulta ejecutada dentro de un run efímero nuevo **ve el estado confirmado real (COMMITTED) de la base de datos**. Al cerrarse el run efímero de medición mediante `DELETE /test-control/runs/{run_id}`, se ejecuta `rollback()`, garantizando que la consulta fue de lectura estricta y reflejó fielmente las filas consolidadas sin interferir con la transacción de los tests funcionales.

---

## 5. Defectos Probables y Discrepancias Documentadas

1. **[INC-M03-<NN>-TC-M03-G166][RF-62] POST /iot/calidad/{id}/evaluar deja mas de una evaluacion VIGENTE por lectura:**  
   El backend no realiza transición canónica a `SUPERADA` al evaluar una lectura ya evaluada (la autoevaluación de la ingesta y el POST manual coexisten como `VIGENTE`). `test_g166_invariante_una_sola_vigente` y `test_g166_transicion_superada` fallarán reportando este defecto reconocido por Desarrollo.
   - *OBSERVACIÓN:* El plan de pruebas original mencionaba el literal `ACTIVA`; por Decisión de Análisis (D7 RESUELTO) se confirmó que el literal canónico en uso es `VIGENTE` y el catálogo es `{"VIGENTE", "SUPERADA"}`.
2. **Alerta Técnica RF-57 Desconectada (`evaluar_calidad_telemetria_use_case.py:223-225`):**  
   El backend no invoca el caso de uso de alertas técnicas en la Fase 8 de calidad. La aserción normativa en `TestEfectosColaterales` es estricta (sin `skip` ni `xfail`) y **fallará reportando este defecto**.
3. **Discrepancia del Plan en Conteo de Repeticiones ($R-1$ vs $R$):**  
   El repositorio excluye la lectura evaluada (`timestamp_captura < ts`). Si se envían $R$ lecturas en total y se evalúa la última, el historial solo tiene $R-1$. La receta se ajustó normativamente a $R$ lecturas idénticas previas + lectura evaluada ($I_5, I_6, I_{10}, I_{11}, I_{20}, I_{21}$).
4. **Escala Decimal en `valor_repetido` (`evaluar_calidad_telemetria_use_case.py:146`):**  
   PostgreSQL almacena `Numeric(10, 4)` y el motor retorna `str(ultimas_m[0])` dando `'25.4000'`. El plan especifica `'25.40'`. Se compara numéricamente vía `Decimal`.
5. **Ausencia del campo `ventana_temporal`:**  
   El plan de pruebas lo menciona, pero no existe en la especificación de schemas del backend. No se aserta en el dict de flags.
