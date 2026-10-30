# README_EJECUCION.md — Guía Operativa para Ejecución de TC-M03-G165

Este documento define las instrucciones para ejecutar el caso de prueba **TC-M03-G165** (RF-62 / RF-63) cuando el equipo de QA autorice la ejecución contra el entorno desplegado de **TEST**.

---

## 1. 📋 Variables de Entorno Requeridas

Las variables deben configurarse en el entorno o en el archivo `.env.test` en la raíz del repositorio:

| Variable | Descripción | Ejemplo / Valor |
|---|---|---|
| `TEST_BASE_URL` | URL base del backend en TEST | `https://api.inmero.co/back-sigab-test` |
| `ENABLE_TEST_SANDBOX` | Habilitación de aislamiento transaccional | `true` |
| `TEST_SANDBOX_SECRET` | Secreto del middleware de testing | `[SECRETO_CONFIGURADO]` |
| `TEST_ADMIN_EMAIL` | Cuenta administrativa autorizada | `administador.dev@gmail.com` |
| `TEST_ADMIN_PASSWORD` | Contraseña administrativa de TEST | `[PASSWORD_CONFIGURADO]` |

> ⚠️ **Regla de Seguridad:** Está estrictamente prohibido usar `admin@pecuaria.co`.

---

## 2. 🚀 Comando de Ejecución Oficial

Para ejecutar la suite completa (5 escenarios: `TestEscenarioBase`, `TestEscenario318a`, `TestEscenario318b`, `TestEscenario318c`, `TestEscenario320`) generando los reportes HTML y JUnit XML para el reintento correspondiente:

```powershell
# Desde la raíz del repositorio sgpmp-backend:
& ".\.venv\Scripts\python.exe" -m pytest --noconftest `
  tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165/test_tc_m03_g165.py `
  --html=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165/resultados/resultado_TC-M03-G165_reintento1.html `
  --self-contained-html `
  --junitxml=tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165/resultados/resultado_TC-M03-G165_reintento1.xml `
  -v
```

### 💡 Recomendación Operativa: Primera Corrida Solo con S_BASE
Antes de ejecutar los 5 escenarios completos, se recomienda validar la conectividad, descubrimiento dinámico y rollback corriendo únicamente el escenario base:

```powershell
& ".\.venv\Scripts\python.exe" -m pytest --noconftest `
  tests/Test_Testing/Test_Modulo3/RF-62/TC-M03-G165/test_tc_m03_g165.py -k "TestEscenarioBase" -v
```

---

## 3. 🔍 Supuestos "NO VERIFICADO" a Confirmar en la Primera Corrida

Durante la primera ejecución contra el entorno real de TEST se deben verificar los siguientes puntos:

1. **Enum real de `estado_evaluacion` en OpenAPI vivo**: Verificar si el schema expone un enum explícito o si permanece como `string` genérico.
2. **Ausencia de lecturas previas en la ventana del sensor**: Confirmar mediante SELECT dinámico que el sensor ambiental descubierto no tenga lecturas preexistentes en la base de datos de testing que contaminen la ventana $N=20$.
3. **Inocuidad de auditoría en `modulo1.eventos`**: Confirmar que antes y después de cada escenario el delta de filas en `modulo1.eventos` sea exactamente **0** (ningún evento de login o control persistido).
4. **Respuesta de `/test-control/query`**: Confirmar que devuelva el formato esperado `{"data": [...]}` y que vea los datos no confirmados del mismo `run_id`.
5. **Coexistencia de evaluaciones vigentes**: Confirmar si tras evaluar manualmente quedan 2 evaluaciones con `estado_evaluacion = 'VIGENTE'` para la misma lectura (la autoevaluación de la ingesta y la manual).

---

## 4. Banner Normativo D7 (`estado_evaluacion` - RESUELTO)

Al iniciar la sesión de Pytest, se imprime en consola la siguiente notificación informativa tras la resolución oficial de análisis (RFC de aclaración de RF-62 en trámite):

```text
==============================================================================
 [BANNER D7 RESUELTO] TC-M03-G165 -- ESTADO DE EVALUACION DE CALIDAD
==============================================================================
 * D7 RESUELTO: literal 'VIGENTE'; catálogo {'VIGENTE', 'SUPERADA'}; RFC de aclaración en trámite.
 * Regla canónica: máximo UNA evaluación VIGENTE por lectura.
 * Defecto conocido: /evaluar duplica VIGENTES (invariante debe fallar hoy).
==============================================================================
```

---

## 5. Correcciones de Diseño Aplicadas (Post Fix `#632` y `#685`)

1. **Eliminación de `TestEscenario318cBis`:**  
   `TestEscenario318cBis` fue retirado porque no forma parte de la especificación de `TC-M03-G165` (`TC-M03-303`, `TC-M03-318a/b/c`, `TC-M03-319`, `TC-M03-320`), tras desplegarse el fix `#632` (`INC-M03-104-G165`), `TestEscenario318c` ya cubre la saturación aritmética en `0` con $\sigma=0$, y además en `TEST` el rango físico de `TEMPERATURA_AMBIENTAL` en `modulo9.variables_ambientales` es `[-10.0, 50.0]`, por lo que `65.0 °C` se rechaza en Fase 5 de ingesta (`422 ERROR_SENSOR`) antes de llegar a `POST /iot/calidad/{id_telemetria}/evaluar`.
2. **Autoridad de `apto_para_ia` y `apto_para_nic41` (`DEV-02`, alembic `9eb3ce1ec3e8`):**  
   `modulo3.telemetrias` es inmutable tras la ingesta; `test_tc303_actualizacion_flags_telemetria_calidad_vigente` verifica `apto_para_ia` y `apto_para_nic41` en la fila `VIGENTE` de `modulo3.telemetria_calidad`.
3. **Contexto RLS en `/test-control/query`:**  
   `SandboxClient.query_sql` envuelve toda consulta en un `CROSS JOIN LATERAL` que invoca `set_config('app.current_role', 'Administrador', true)` y `set_config('app.current_user_id', ...)`.
4. **Offset positivo de calibración y `frecuencia_muestreo=10` dentro del sandbox:**  
   `calcular_offset_para_drift` calcula un offset positivo $(d \cdot \mu)/(1 - d) \in [0, 45]$, y cada escenario fija `frecuencia_muestreo=10` min mediante `PATCH /configuracion/parametros/{id}` dentro de su `X-Test-Run-Id`.

---

## ⚠️ Riesgo de latencia (INC-M03-G166-LATENCY)

La suite realiza ~105 POST secuenciales de ingesta (21 lecturas × 5 escenarios).
En horarios de alta carga de RDS TEST, un escenario puede superar los 20-30 s.
Mitigación en Fase 3: ejecutar primero por clase (`-k TestEscenarioBase`, etc.)
o con `--timeout=300` para evitar abortos prematuros.
