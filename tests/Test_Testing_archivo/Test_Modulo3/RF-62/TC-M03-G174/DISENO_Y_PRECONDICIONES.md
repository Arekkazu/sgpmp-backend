# TC-M03-G174: BFLA Broken Function Level Authorization (RF-62 / OWASP API5:2023)

## 1. Alcance y Objetivos
Verificar la autorización granular por nivel de función sobre los endpoints del módulo de calidad de telemetría IoT (`/iot/calidad`):
- `POST /iot/calidad/reevaluar`: Operación crítica administrativa de re-evaluación masiva (Recurso 38, Acción 5).
- `GET /iot/calidad`: Consulta de evaluaciones de calidad (Recurso 38, Acción 2).
- `POST /iot/calidad/{id_telemetria}/evaluar`: Evaluación puntual de lecturas (Recurso 38, Acción 5).

## 2. Herramienta y Enfoque QA
- **Herramienta:** Newman / Postman v2.1.0 con reporte oficial en `resultados/resultado_TC-M03-G174.html` (leído por el scanner).
- **CERO DML:** No se ejecuta ninguna instrucción SQL de mutación. La telemetría de prueba se genera vía `POST /iot/telemetria`.
- **Aislamiento Sandbox:** Transaccional bajo cabeceras `X-Test-Run-Id` y `X-Sandbox-Secret`, con `DELETE /test-control/runs/{{run_id}}` como última petición.

## 3. Matriz de Roles y Permisos Evaluados (Recurso 38: `calidad_telemetria`)
Conforme a la definición de base de datos (`modulo1.permisos_roles`):
- **Rol 1 (ADMINISTRADOR):** Permisos 38.2 (Leer) y 38.5 (Ejecutar).
- **Rol 2 (PRODUCTOR):** Permiso 38.2 (Leer).
- **Rol 3 (VETERINARIO):** Permiso 38.2 (Leer).
- **Rol 4 (INGENIERO_CAMPO):** Permisos 38.2 (Leer) y 38.5 (Ejecutar).
- **Rol 5 (CONTADOR):** Permiso 38.2 (Leer).

## 4. Hallazgo Adicional BFLA: Evaluación Puntual (`POST /iot/calidad/{id}/evaluar`)
- El Administrador (Rol 1) e Ingeniero de Campo (Rol 4) poseen permiso 38.5, permitiéndoles disparar evaluaciones puntuales en campo.
- Productor (Rol 2), Veterinario (Rol 3) y Contador (Rol 5) son denegados con HTTP 403 Forbidden.
