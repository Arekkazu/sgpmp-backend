# INC-M03-175-G57A — Permisos sobre los umbrales ambientales (`/configuracion/umbrales`)

**Issue:** #754. **RF del endpoint:** RF-17 (M09), "Configuración de umbrales de monitoreo y niveles de
alerta ambiental". QA cita RF-57 (Restricción 3, CA-14 y CA-17).
**Estado:** **bloqueado por un conflicto entre requerimientos**, por decisión del equipo. El comportamiento
actual cumple RF-17, que es el RF del endpoint. Se pide a Análisis que unifique.

## Lo que reporta QA

| Rol | Lo que espera QA | Lo que pasa hoy |
|---|---|---|
| Administrador | Configura | Configura (200) |
| Ingeniero de Campo | Configura (crear, ver, editar y desactivar) | 403 `ACCESO_DENEGADO` |
| Veterinario | 403 | Configura (200 y 201; desactiva) |
| Productor | 403 | 403 |

## Lo que dicen los requerimientos

| Fuente | Texto | Qué implica |
|---|---|---|
| **RF-17 (M09)**, el RF de `/configuracion/umbrales` | "Solo los usuarios con rol **Administrador o Veterinario** podrán modificar estos parámetros". **Actores:** Administrador del sistema y Veterinario. Flujo de acceso denegado: "Solo los usuarios con rol Administrador o Veterinario están autorizados para modificar los umbrales de seguridad ambiental" | **Administrador y Veterinario**, que es lo que hay hoy |
| RF-57, actor 7 (Administrador) | "Configurar reglas y umbrales" | Administrador |
| RF-57 Fase 5 | Los **valores base de las reglas de RF-57** "pueden ser modificados por el administrador del sistema o ingeniero de campo" | Habla de las reglas de RF-57, no del endpoint de RF-17 |
| RF-57, Restricción 3 | "Las reglas y umbrales no deben estar codificados de forma rígida; deben poder modificarse sin despliegues" | No asigna roles |
| RF-57, CA-14 | Gestión de la tormenta de alertas | No trata roles sobre umbrales |
| RF-57, CA-17 | "Dado un usuario sin los permisos requeridos… rechazar la operación y registrar el intento" | Exige el rechazo, no dice quién tiene el permiso |

**Conclusión:**
- **RF-57:** ninguna de las cláusulas que cita QA asigna al Ingeniero ni le quita al Veterinario el permiso
  sobre `/configuracion/umbrales`. La única mención del Ingeniero ("valores base… administrador o ingeniero
  de campo") se refiere a las **reglas de RF-57**.
- **RF-17:** el RF dueño del endpoint lo asigna **explícitamente** a Administrador y Veterinario.
- **Sin cambios:** invertir los permisos contradiría RF-17, así que no se cambian sin una decisión de
  Análisis.

## Implementación vigente (referencia)

- `src/configuration/infrastructure/routers/umbral_router.py`: recurso **20** (`umbrales_ambientales`).
  Crear = acción 1, leer = 2, actualizar = 3, desactivar = 4, con `require_permission`.
- Los permisos por rol están en `modulo1.permisos` y son datos: el código no tiene roles quemados (regla RBAC
  del proyecto).

## Qué se necesita para cerrarlo

1. **Análisis:** unificar RF-17 y RF-57 sobre quién configura los umbrales ambientales (Administrador +
   Veterinario, Administrador + Ingeniero de Campo, o los tres).
2. **Si la decisión cambia los roles:** una migración de datos (DML) sobre `modulo1.permisos` del recurso 20
   (otorgar C/R/U/D al rol que corresponda y retirar C/U/D al que no), con la **aprobación formal del
   DBA**. Además, hay que actualizar el mensaje del flujo de acceso denegado de RF-17. No hace falta tocar el
   código: `require_permission` lee los permisos en cada request.
3. **QA:** reejecutar TC-M03-G57A con la matriz que defina Análisis.

## Cambios

Ninguno en código ni en datos. Solo esta anotación.
