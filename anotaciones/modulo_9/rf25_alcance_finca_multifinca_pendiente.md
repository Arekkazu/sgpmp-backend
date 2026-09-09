# RF-25 — Alcance por finca: deuda de modelo multi-finca

## Contexto

RF-25 exige que cada usuario no administrador solo vea la información de la(s)
finca(s) que le corresponden. La implementación actual (rama
`feature/rf25-alcance-finca-todos-modulos`) aplica ese alcance en todos los
módulos operativos usando el mecanismo común `AlcanceFincaPort` /
`AlcanceFincaAdapter` (ver `src/shared/alcance_finca_*.py`).

## Regla de alcance implementada

- **Global**: el rol del usuario tiene permiso de gestión sobre el recurso
  `fincas` (acción `U` actualizar o `D` desactivar, `id_recurso=9`). Ve todas
  las fincas.
- **Restringido**: cualquier otro rol. Ve solo las fincas cuyo
  `modulo9.fincas.id_usuario` coincide con su `id_usuario`.

## Limitación (deuda técnica asumida)

El modelo actual es **1 finca = 1 dueño** (`modulo9.fincas.id_usuario` es una
FK a `modulo1.usuarios.id_usuario`). No existe una relación muchos-a-muchos
`usuario <-> finca` ni un concepto de "finca atendida sin ser dueño".

Consecuencia: roles que en la operación real atienden fincas de terceros —
**Veterinario, Ingeniero de Campo, Supervisor, Gestor de Granja, etc.** — no
verán fincas que no les pertenezcan, aunque les corresponda operarlas. Verán
listados vacíos (no un error) hasta que se les asigne la finca como dueños.

## Decisión tomada

Se mantiene el modelo 1:1 por ahora y se documenta esta deuda. Cuando se
necesite soporte multi-finca real, se debe:

1. Introducir una tabla de asignación `usuarios_fincas` (o equivalente) con la
   convención de nomenclatura de `anotaciones/convencion_nomenclatura_bd.md`.
2. Migrar `AlcanceFincaAdapter.listar_ids_fincas_permitidas` para resolver las
   fincas desde esa tabla en lugar de `fincas.id_usuario`.
3. Actualizar la asignación de fincas (`PUT /usuarios/{id_usuario}/fincas`) y
   la vista `modulo9.vw_rf25_contexto_usuario`.

## Módulos con alcance aplicado

| Módulo | Endpoints restringidos | Traza a finca |
|--------|------------------------|---------------|
| biological_assets | listar/consultar activos, historial, eventos, ficha, indicadores, consolidados, asociación | `activos_biologicos.id_infraestructura -> infraestructuras.id_finca` |
| telemetry | monitoreo (dashboard/historial), alertas, vinculaciones | `sensores_areas_asociadas.id_infraestructura -> infraestructuras.id_finca` (alertas también vía `id_activo_biologico`) |
| configuration | infraestructuras, dispositivos IoT, asociaciones de sensor | `infraestructuras.id_finca` / `dispositivos_iot.id_infraestructura` |
| supplies | historial de suministros (vía `AlcanceActivoPort`) | `activos_biologicos.id_infraestructura -> infraestructuras.id_finca` |
| prediction | historial diagnóstico | `activos_biologicos.id_infraestructura -> infraestructuras.id_finca` |

## Excluidos del alcance (catálogos globales)

Especies, patologías, tipos de área, tipos de dispositivo, variables
ambientales, umbrales ambientales, ciclos biológicos, tema/idioma/dashboard, y
todo `identity_access` (usuarios, roles, permisos, auditoría) son datos
compartidos o administrativos y no se filtran por finca.
