# DISENO_Y_PRECONDICIONES — TC-M04-G091

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G091 (TC-M04-281, TC-M04-282, TC-M04-283, TC-M04-284)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de predicción — Resiliencia y Fallback)
- **Fase:** DISEÑO TÉCNICO Y AUTOMATIZACIÓN DE PRUEBAS (SOLO DISEÑO Y CONSTRUCCIÓN)
- **Estado Global:** [PENDIENTE_DEV / REQUIERE FASE DE INFRAESTRUCTURA]
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/back-sigab-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra (Sandbox transaccional con aislamiento por `run_id`).

---

## 2. Diagnóstico Técnico y Estado de Endpoints

| Subcaso | Nombre Técnico | Validación Requerida | Estado Técnico Actual | Clasificación |
|---|---|---|---|---|
| **TC-M04-281** | Fallback tras caída de BD | Eventos capturados en memoria/archivo con `origen_registro="FALLBACK"` | Filtro `origen_registro` no expuesto como query param en router REST | [PENDIENTE_DEV] |
| **TC-M04-282** | Sincronización post-recuperación | Orden cronológico monótono creciente (FIFO) en sincronización de eventos de fallback | Requiere caída de PostgreSQL y espera de 10 min | [FASE INFRAESTRUCTURA] |
| **TC-M04-283** | Preservación de timestamp original | `fecha_evento` tras sincronización es idéntica a la fecha original de captura del evento | Requiere eventos inyectados durante corte de BD | [FASE INFRAESTRUCTURA] |
| **TC-M04-284** | Fallback Edge diferido (72h) | Buffer local de persistencia en nodos Edge desconectados (`origen_registro="EDGE"`) | Buffer local y sincronizador diferido en desarrollo | [PENDIENTE_DEV] |

---

## 3. PENDIENTES DE DESARROLLO

| Subcaso | Endpoint Esperado | Contrato Esperado | Asignado A (Equipo/Área) |
|---|---|---|---|
| **TC-M04-281** | `GET /prediccion/auditoria?origen_registro=FALLBACK` | Exponer query param `origen_registro: Optional[str]` en router para filtrar eventos generados en contingencia | Equipo Backend Core / Módulo 4 |
| **TC-M04-282** | Mecanismo de reintento / flushing FIFO | Proceso background de vaciado ordenado de cola de contingencia hacia PostgreSQL | Equipo Infraestructura / Backend Core |
| **TC-M04-284** | Sincronización Edge -> Central | Endpoint receptor de lotes de auditoría diferida Edge con origen `EDGE` y validación de hash | Equipo AIoT Edge / Backend Core |

---

## 4. FASE DE EJECUCIÓN SEPARADA (Precondiciones de Infraestructura)

> [!WARNING]
> Los 4 subcasos de TC-M04-G091 son **inviables de ejecutar de forma autónoma dentro de un sandbox HTTP transaccional estándar**.
> La evaluación de estos requisitos exige orquestación a nivel de infraestructura en una fase de prueba separada:
> 1. **Caída controlada de PostgreSQL (TC-M04-281):** Detener el contenedor/servicio de base de datos (`docker stop postgres_test`), emitir eventos desde clientes y verificar buffer de contingencia.
> 2. **Espera de recuperación (TC-M04-282):** Esperar 10 minutos de ventana de caída, reanudar servicio (`docker start postgres_test`) y verificar vaciado FIFO.
> 3. **Preservación temporal (TC-M04-283):** Validar que `fecha_evento` mantenga la estampa temporal del incidente y no la estampa del momento de inserción a BD.
> 4. **Corte prolongado Edge (TC-M04-284):** Simular desconexión WAN durante hasta 72 horas en nodos Edge con posterior sincronización masiva.

---

## 5. Estrategia de Sandbox y Teardown
- Generación de `run_id` aleatorio en pre-request de colección (`test-{{$guid}}`).
- Inyección de cabeceras de aislamiento `X-Test-Run-Id` y `X-Sandbox-Secret`.
- Teardown con `DELETE /test-control/runs/{{run_id}}` (200 OK con `Rollback exitoso`).
- Cero escrituras directas SQL en base de datos.
