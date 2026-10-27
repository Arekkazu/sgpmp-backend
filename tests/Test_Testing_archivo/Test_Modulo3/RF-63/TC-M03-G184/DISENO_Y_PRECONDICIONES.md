# TC-M03-G184: OWASP API5 BFLA en Auditoría IoT (RF-63)

## 1. Identificación y Objetivos
- **Caso Maestro:** TC-M03-G184
- **Vulnerabilidad Evaluada:** OWASP API5:2023 - Broken Function Level Authorization (BFLA) en RF-63
- **Endpoints Protegidos:**
  1. `GET /iot/auditoria` (Recurso 39, Acción 2)
  2. `GET /iot/auditoria/{id_evento}` (Recurso 39, Acción 2)
  3. `GET /iot/auditoria/exportar` (Recurso 39, Acción 5)
  4. `POST /iot/auditoria/verificar-integridad` (Recurso 39, Acción 5)
- **Roles Evaluados:**
  - `ADMINISTRADOR` (Rol 1, canónico dev)
  - `PRODUCTOR` (Rol 2)
  - `VETERINARIO` (Rol 3)
  - `INGENIERO_CAMPO` (Rol 4)
  - `CONTADOR` (Rol 5)
- **Herramienta de Ejecución:** Newman + reporter htmlextra.
- **Entorno de Ejecución:** Sandbox transaccional con regla CERO DML.

---

## 2. Diagnóstico Técnico de Permisos RBAC en Base de Datos
En `alembic/baseline/esquema_baseline.sql:47837-47841`, la matriz RBAC para el recurso 39 (`bitacora_auditoria_iot`) está configurada de la siguiente manera:

| Permiso ID | Código Interno | Recurso | Acción | Rol Asignado | Nombre Rol |
|---|---|---|---|---|---|
| **234** | `admin_leer_bitacora_auditoria_iot` | 39 | 2 (LEER) | 1 | Administrador |
| **235** | `admin_ejecutar_bitacora_auditoria_iot` | 39 | 5 (EJECUTAR) | 1 | Administrador |
| **236** | `ing_leer_bitacora_auditoria_iot` | 39 | 2 (LEER) | 4 | Ingeniero de Campo |
| **237** | `cont_leer_bitacora_auditoria_iot` | 39 | 2 (LEER) | 5 | Contador |
| **238** | `cont_ejecutar_bitacora_auditoria_iot` | 39 | 5 (EJECUTAR) | 5 | Contador |

---

## 3. Matriz BFLA: Rol vs. Endpoint y Resultado Esperado

| Rol | `GET /iot/auditoria` (39, 2) | `GET /auditoria/{id}` (39, 2) | `GET /exportar` (39, 5) | `POST /verificar` (39, 5) | DELETE / PUT / PATCH | Observación de Alcance de Datos |
|---|---|---|---|---|---|---|
| **ADMINISTRADOR** | 200 OK | 200 OK | 200 OK | 200 OK | 405 | Acceso total administrativo |
| **PRODUCTOR** | 403 Forbidden | 403 Forbidden | 403 Forbidden | 403 Forbidden | 405 / 403 | Sin permisos sobre auditoría técnica IoT |
| **VETERINARIO** | 403 Forbidden | 403 Forbidden | 403 Forbidden | 403 Forbidden | 405 / 403 | Sin permisos sobre auditoría técnica IoT |
| **INGENIERO_CAMPO** | 200 OK | 200 OK | 403 Forbidden | 403 Forbidden | 405 | Solo lectura; acción 5 denegada |
| **CONTADOR** | 200 OK | 200 OK | 200 OK | 200 OK | 405 | Lectura y ejecución financiera/NIC41 |

---

## 4. Supuestos Confirmados y Discrepancias

1. **[CONFIRMACION RBAC] Endpoint `POST /verificar-integridad`:**
   - Exige `require_permission(39, 5)`.
   - Según el baseline de BD, los roles con acción 5 son **ADMINISTRADOR** y **CONTADOR**.
   - El rol **INGENIERO_CAMPO** carece de la acción 5 y recibe legítimamente HTTP **403 Forbidden**.
2. **[DISCREPANCIA CON EL CASO] Alcance de datos por rol en `GET /iot/auditoria`:**
   - La especificación del caso asume que el Contador solo debe ver eventos clasificados como `NIC41` y el Ingeniero de Campo solo eventos de `RF-55`, `RF-60` y `RF-62`.
   - Sin embargo, la implementación de backend autoriza el acceso a nivel de endpoint (`require_permission(39, 2)`), sin aplicar filtros de fila por pertenencia de rol en `ConsultarBitacoraIotUseCase`. Se documenta como `[DISCREPANCIA CON EL CASO]`: el Contador y el Ingeniero reciben todos los registros si no se envían parámetros de filtro específicos en la URL.
