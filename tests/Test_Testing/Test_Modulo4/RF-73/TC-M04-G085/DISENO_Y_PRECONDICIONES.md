# DISENO_Y_PRECONDICIONES — TC-M04-G085

## 1. Identificación y Metadatos
- **ID Caso / Grupo:** TC-M04-G085 (Subcasos TC-M04-262 y TC-M04-263)
- **Módulo:** Módulo 4 — Predicción e IA (RF-64 a RF-73)
- **Requisito Funcional:** RF-73 (Auditoría de eventos de inferencia y modelos) / RF-72 (Retroalimentación Clínica y Conflictos)
- **Estado Técnico:** REDISEÑADO — EJECUTABLE END-TO-END BAJO SANDBOX
- **Entorno Evaluado:** Backend TEST desplegado (`https://api.inmero.co/api-sgpmp-test`)
- **Herramienta de Ejecución:** Newman + reporter htmlextra bajo Sandbox transaccional SGPMP (`X-Test-Run-Id`, `X-Sandbox-Secret`).

---

## 2. Diagnóstico Técnico y Eliminación de Premisas Erróneas

El diseño preliminar de este caso asumía erróneamente que "no existen inferencias generables vía API y por tanto el caso está bloqueado". El diagnóstico empírico (.diagnostico/diagnostico_G085.md) demostró:
1. **Existencia de Inferencias en BD:** Existen **63 inferencias vigentes** en la base de datos de TEST dentro de la ventana reglamentaria de 90 días.
2. **Activo Biológico y Finca:** El activo biológico `876` (`IND-QA-M04-1792715755-1`) pertenece a la infraestructura `399`, asignada a la finca `184` (*"Finca Prueba Alfa"*). Sobre este activo existen 11 inferencias en `modulo4.resultados_inferencia`.
3. **Endpoint Productor Operativo:** `POST /prediccion/retroalimentacion` existe y está plenamente implementado.
4. **Control de Acceso (RBAC):** Protegido por `require_permission(45, 1)`. Requiere token Bearer de un usuario con rol **Veterinario** (`id_rol = 3`). Un token de Administrador (`id_rol = 1`) es rechazado con **HTTP 403 Forbidden (`ACCESO_DENEGADO`)**.
5. **Cuentas Veterinarias Configuradas:**
   - **Veterinario 1:** `juan.carlos@email.com` (`id_usuario = 97`), con acceso asignado y activo a la finca `184` (`id_usuario_finca = 264`).
   - **Veterinario 2:** `juanstesting@gmail.com`, igualmente asociado a la finca `184`.

---

## 3. Matriz de Subcasos y Tipos de Evento

| Subcaso | Tipo Evento Esperado | Endpoint Productor | Severidad | Tipo Actor | Veredicto Esperado |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-M04-262** | `RETROALIMENTACION_REGISTRADA` | `POST /prediccion/retroalimentacion` | `INFO` | `USUARIO` | **PASS** (Registro legítimo) |
| **TC-M04-263** | `CONFLICTO_RETROALIMENTACION` | `POST /prediccion/retroalimentacion` | `WARNING` | `SISTEMA` | **FAIL / BUG** (Evidencia INC-M04-151-G085) |

### 3.1 Subcaso 1: `RETROALIMENTACION_REGISTRADA` (TC-M04-262)
- Veterinario 1 (`juan.carlos@email.com`) emite feedback `estado_retroalimentacion = "CORRECTO"` sobre la Inferencia 1 de finca 184.
- El backend persiste la retroalimentación y emite el evento de auditoría `RETROALIMENTACION_REGISTRADA` con severidad `INFO`, `tipo_actor = "USUARIO"`, `id_usuario = 97` y `conflicto_retroalimentacion = false`.

### 3.2 Subcaso 2: `CONFLICTO_RETROALIMENTACION` (TC-M04-263) y Detección de Bug
- Sobre una segunda inferencia (Inferencia 2) de la misma finca 184:
  1. Veterinario 1 registra `CORRECTO` (perteneciente a `_GRUPO_SIN_PROBLEMA = {"CORRECTO", "SIN_EVENTO"}`).
  2. Veterinario 2 registra `INCORRECTO` con `diagnosticos_reales = [1]` (perteneciente a `_GRUPO_CON_PROBLEMA = {"PARCIAL", "INCORRECTO"}`).
- **Lógica de Dominio:** Al coexistir estados de grupos opuestos de distintos veterinarios, `_calcular_conflicto()` evalúa `True`.
- **Bug INC-M04-151-G085:** En `registrar_retroalimentacion_use_case.py:165`, el use case construye el payload con la clave `"total_retroalimentaciones"`, mientras que el repositorio `evento_auditoria_m04_repository.py:29` exige `"numero_retroalimentaciones"`.
- **Comportamiento en Backend:** Al faltar el campo obligatorio, el repositorio rechaza el evento legítimo y persiste en su lugar `tipo_evento = "AUDITORIA_EVENTO_INVALIDO"` con severidad `ERROR`.
- **Estrategia del Test:**
  - El item de aserción oficial (9b) falla honestamente al no encontrar `CONFLICTO_RETROALIMENTACION` (captura formal del bug).
  - El item diagnóstico (9c) consulta `AUDITORIA_EVENTO_INVALIDO` y extrae el payload que evidencia la discrepancia de nombres de campo, marcando `bug_reproducido = true` en el entorno.

---

## 4. Estructura de la Colección Newman (10 Items)

1. `01-Login-Admin`: Autentica admin y extrae `jwt_admin`.
2. `02-Login-Vet1`: Autentica Veterinario 1 (`juan.carlos@email.com`), extrae `jwt_vet1` e `id_vet1`.
3. `03-Login-Vet2`: Autentica Veterinario 2 (`juanstesting@gmail.com`), extrae `jwt_vet2` e `id_vet2`.
4. `04-Preparar-Sandbox-Inferencias`: Consulta en sandbox 2 inferencias vigentes sobre activo 876 (finca 184) sin retroalimentaciones previas.
5. `05-Subcaso-1-Post-Retroalimentacion-Vet1`: Emite `POST /prediccion/retroalimentacion` con estado `CORRECTO`.
6. `06-Subcaso-1-Verificar-Retroalimentacion-Registrada`: Verifica evento `RETROALIMENTACION_REGISTRADA` en bitácora M04.
7. `07-Subcaso-2-Post-Retroalimentacion-Vet1`: Veterinario 1 emite feedback `CORRECTO` sobre inferencia 2.
8. `08-Subcaso-2-Post-Retroalimentacion-Vet2`: Veterinario 2 emite feedback contradictorio `INCORRECTO` sobre inferencia 2.
9. `09-Subcaso-2-Verificar-Eventos-Conflicto`: Aserción de `CONFLICTO_RETROALIMENTACION` (9b) + verificación de flag de conflicto (9a) + captura diagnóstica de `AUDITORIA_EVENTO_INVALIDO` (9c).
10. `10-Teardown-Sandbox`: Ejecuta `DELETE /test-control/runs/{{run_id}}` para revertir completamente todos los datos insertados en la prueba.

---

## 5. Teardown y Aislamiento Transaccional
- La ejecución completa ocurre dentro de un único `run_id` transaccional.
- El cierre mediante `DELETE /test-control/runs/{{run_id}}` garantiza la reversión de las retroalimentaciones y los eventos de auditoría emitidos durante ambos subcasos, preservando la regla de CERO DML permanente.
