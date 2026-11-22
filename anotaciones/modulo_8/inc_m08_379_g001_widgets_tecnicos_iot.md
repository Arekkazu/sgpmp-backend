# INC-M08-379-G001 · RF-103 — Widgets técnicos de IoT fuera del dashboard del Productor

Incidencia [#1195](https://github.com/Arekkazu/sgpmp-backend/issues/1195) · TC-M08-G001, subcaso TC-M08-002. Rama basada en `origin/dev` `6cee5fc4`.

## Causa

El catálogo (`GET /configuracion/personalizacion/dashboard/widgets`), el `PATCH` del layout, `GET .../dashboard/datos` y los datos de cada widget de M08 filtran con `SqlAlchemyWidgetRepository.ids_legibles_por_rol`. Un widget queda disponible si el rol tiene Leer sobre su `id_recurso`. Los cuatro widgets técnicos dependían de recursos que también leen otras pantallas:

| Widget | Recurso anterior | Roles con Leer (antes) |
|---|---|---|
| `estado_iot` | `infraestructura_iot` | Administrador, Productor, Veterinario, Ingeniero de Campo |
| `cal_sensores` | `dispositivos_iot` | Administrador, Productor, Ingeniero de Campo |
| `cfg_pendiente` | `dispositivos_iot` | Administrador, Productor, Ingeniero de Campo |
| `dispositivos_sin_senal` | `infraestructura_iot` | Administrador, Productor, Veterinario, Ingeniero de Campo |

La tabla salió de una BD efímera con todas las migraciones aplicadas. QA solo reportó al Productor, pero el Veterinario también veía `estado_iot` y `dispositivos_sin_senal`.

## Decisión

RF-103: «las alertas técnicas de dispositivos IoT (SIN_SEÑAL, EN_MANTENIMIENTO) son de competencia del Ingeniero de Campo / Administrador (RF-60)». La acción correctiva pide un recurso que lean solo esos dos roles.

- **No se usa `datos_tecnicos_dashboard`**, aunque el ticket lo sugiere: `495a6545bdb1` le da Leer también al Veterinario (batería y RSSI de RF-58). Reutilizarlo dejaría los widgets al Veterinario y mezclaría dos permisos con propósitos distintos.
- **Recurso nuevo `widgets_tecnicos_iot`**, con Leer para Administrador (`admin_leer_widget_tecnico_iot`) e Ingeniero de Campo (`ing_leer_widget_tecnico_iot`). Si un rol creado después necesita esos widgets, se le asigna con `POST /roles/{id_rol}/permisos`.
- **Layouts guardados:** se quitan las celdas técnicas (y su clave en `active_widget`) de los layouts de usuarios cuyo rol no lee el recurso. Si se dejaran, el siguiente `PATCH` de ese usuario respondería `403 WIDGET_NO_AUTORIZADO` por un widget que ya tenía guardado. Se actualiza `fecha_actualizacion`, así que un editor abierto con la versión anterior recibe el aviso de concurrencia. Se aplica lo mismo a `dashboard_layouts_default`; los predeterminados del seed no cambian.
- **No hay cambios de código.**

## Migración `046abf6dbaa9` (v5.5.0, sobre `e84904d795fd`)

- Desactiva FORCE RLS en `modulo1.recursos`, `permisos`, `roles`, `acciones`, `usuarios` y `modulo9.dashboard_layouts`, y lo restaura en un `finally`. Con FORCE activo, el UPDATE de layouts solo vería los del actor declarado.
- Si falta un rol o uno de los cuatro widgets, falla con un mensaje en vez de terminar sin cambios.
- `downgrade()` devuelve los widgets a su recurso anterior y retira el permiso del Ingeniero. Conserva el recurso y el permiso del Administrador, que protege `trg_proteger_permisos_admin_delete`. Las celdas quitadas no se restauran.

## Evidencia local

Se usó una BD efímera en `sgpmp-db` (PostgreSQL 18), migrada hasta `e84904d795fd`. Se sembraron un Productor, un Veterinario y un Ingeniero, cada uno con layout guardado `semaforo_areas` + `estado_iot`. Después de `upgrade`:

- Los cuatro widgets quedan en `widgets_tecnicos_iot` y solo los leen Administrador e Ingeniero de Campo.
- Los layouts del Productor y del Veterinario quedan con `semaforo_areas`, conservan `frecuencia_actualizacion` y tienen `fecha_actualizacion` nueva. El del Ingeniero no cambia.
- El round-trip `downgrade -1` → `upgrade head` funciona y FORCE RLS queda activo en las seis tablas.
- `tests/integration/test_inc_m08_379_g001_widgets_tecnicos_iot.py`: 7 pruebas pasan con la migración. Sin ella fallan las del Productor y el Veterinario.
- `tests/configuration`, `tests/reporting` y la integración de M08 RF-104..107 pasan: 800 pruebas. La excepción es `test_escalamiento_auditoria_y_preferencias` (RF-105, `assert 1 == 4`), que también falla sin esta migración. Es previa a este cambio.

## Re-prueba

Después de que el DBA aplique la migración en TEST, repetir TC-M08-002:

- El catálogo del Productor no trae `estado_iot`, `cal_sensores`, `cfg_pendiente` ni `dispositivos_sin_senal`.
- El `PATCH` con `estado_iot` responde `403 WIDGET_NO_AUTORIZADO` y el layout no cambia.
- El catálogo del Ingeniero sigue trayendo los cuatro widgets.
- El catálogo del Veterinario tampoco trae `estado_iot` ni `dispositivos_sin_senal`.
