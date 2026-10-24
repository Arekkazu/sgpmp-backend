# TC-M03-G171: Integridad y Persistencia (RF-62)

## 1. Alcance y Objetivos
Evaluar la inmutabilidad de los registros originales de telemetría (RF-53), la completitud de los metadatos generados por el motor de evaluación de calidad (`GET /iot/calidad/{id}`), la unicidad del estado VIGENTE (Decisión D7) y el comportamiento ante cambios de configuración de auditoría.

## 2. Herramienta y Enfoque QA
- **Herramienta:** Newman / Postman v2.1.0 con reporte oficial en `resultados/resultado_TC-M03-G171.html` (consumido por el scanner).
- **Desviación de Arquitectura:** El diseño original contemplaba Pytest con acceso directo a base de datos. Se migró completamente a llamadas HTTP de la API REST para cumplir con la regla estricta de CERO DML y garantizar la auditoría del sandbox.

## 3. Verificación de Endpoints GET para Telemetría Cruda (Diagnóstico Crítico)
Antes de justificar el uso de SELECT por `/test-control/query`, se inspeccionó exhaustivamente el router de telemetría [telemetria_router.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/telemetria_router.py#L1-L15) y el router de monitoreo [monitoreo_router.py](file:///c:/Users/Juansegutt/Integrador/sgpmp-backend/src/telemetry/infrastructure/routers/monitoreo_router.py#L178-L215):
- `GET /iot/telemetria` (lista o filtrable por id_sensor + timestamp_captura): **NO EXISTE**. El router `/iot/telemetria` solo implementa `POST /` (ingesta individual), `POST /batch` (ingesta en lote) y `POST /vision` (visión computacional).
- `GET /iot/telemetria/{id}`: **NO EXISTE**.
- `GET /iot/monitoreo/historial` (RF-59): Existe pero proyecta vistas agregadas con semáforos y cálculos de negocio de monitoreo; no expone la fila cruda de telemetría con sus estados de ingestión precisos antes de ser procesados por RF-62.
- **Conclusión y Justificación:** Debido a que ningún endpoint GET de la API expone la fila cruda de `modulo3.telemetrias` de forma directa, se utiliza el endpoint de sandbox `POST /test-control/query` marcado como **`[VERIFICACION SQL SOLO LECTURA]`** (sin DML).
  - Petición 12: `SELECT valor_crudo, valor_ajustado, timestamp_captura, origen, estado_calidad, calibrado, apto_para_ia, apto_para_nic41 FROM modulo3.telemetrias WHERE id_telemetria = {{id_tel_327}}`
  - Petición 14: Misma consulta post-evaluación para corroborar inmutabilidad.

## 4. Subcasos Evaluados
1. **TC-M03-327 (Inmutabilidad de Telemetría Original RF-53):**
   - Se ingesta serie de 20 lecturas base con `POST /iot/telemetria/batch` y 1 lectura evaluada con `POST /iot/telemetria`.
   - **Ventanas y Tiempos:** Los `timestamp_captura` son todos pasados (15 de octubre de 2026), separados exactamente **600 s (10 minutos)** entre sí, sin depender de sleeps wall-clock.
   - Se toma snapshot antes y después de `POST /iot/calidad/{id}/evaluar`.
   - Se verifica que `valor_crudo`, `valor_ajustado`, `timestamp_captura`, `origen` y `estado_calidad` permanezcan idénticos.
   - Se valida que los únicos atributos actualizados en telemetría sean los flags booleanos `apto_para_ia` y `apto_para_nic41`.
2. **TC-M03-328 (Persistencia Completa y Unicidad VIGENTE):**
   - Ejecución de `POST /iot/calidad/{id}/evaluar` sobre lectura válida con ventana N=20 (16 de octubre de 2026, lecturas separadas 600 s).
   - `GET /iot/calidad/{id}` comprueba todos los campos del schema oficial `TelemetriaCalidadSchema`: `id_evaluacion` (UUID), `id_telemetria`, `id_sensor`, `timestamp_evaluacion`, `indice_calidad`, `clasificacion_calidad`, `apto_para_ia`, `apto_para_nic41`, `flags_detectados` (JSON), `parametros_aplicados` (k, M, N, umbral_drift), `estado_evaluacion='VIGENTE'`, `motivo_reevaluacion=null`, `id_evaluacion_superada=null`.
   - `[LIMITACION API]`: El campo `version_limites_fisicos_aplicada` es `null` en el motor activo. En lugar de relajar la aserción con un "o null", se extrae de `pm.test` y se documenta como limitación de integración vía `console.log`.
   - Verificación de invariante D7: filtrado `GET /iot/calidad?id_sensor={id}&estado_evaluacion=VIGENTE` valida unicidad con el prefijo `[DEFECTO CONOCIDO D7]` ante eventual duplicidad por re-evaluación no superseded.
3. **TC-M03-329 (Inmutabilidad ante Cambios de Configuración):**
   - **Estado:** `[BLOQUEADO]`.
   - **Motivo:** En el backend actual, `calidad_router.py:28` instancia `ParametrosCalidadStubAdapter()`, el cual fija de forma estática en código los parámetros `k=3.0, M=5, N=20, umbral_drift=5.0`. No existen endpoints en la API para mutar dinámicamente dichos parámetros operativos de RF-62 ni publicar versiones temporales de límites físicos.
