# INC-M08-380-G002 · RF-103 — «Valor del inventario» del Productor en $0

Incidencia [#1196](https://github.com/Arekkazu/sgpmp-backend/issues/1196) · TC-M08-G002, subcaso TC-M08-003. Rama basada en `origin/dev` `6cee5fc4`.

## Causa

El widget `valor_inventario` le abre la puerta al Productor con el permiso `indicadores_valor_inventario`. Los datos, en cambio, se leían con la sesión del usuario a través de `SqlAlchemyValoracionRepository.activos_valorados()`, que parte de `modulo6.reconocimientos_iniciales`. La política SELECT de esa tabla (`4fa0e24ea021_rls_modulo_06`) es `fn_tiene_permiso('reconocimiento_inicial', 'R')`, y lo mismo pasa con `calculos_valor_razonable` y `valoraciones_por_costos`. El Productor no tiene esos permisos, la consulta le devolvía cero filas y el widget le mostraba «Todavía no hay animales con valor reconocido.» con $0.

Esa RLS de M06 filtra **por permiso, no por finca**. Al Contador lo acotaban a sus fincas los joins con `modulo2.activos_biologicos` y `modulo9.infraestructuras`/`fincas`, que sí tienen RLS por finca.

## Corrección

La que propone el ticket, con el mismo patrón de #1154 (`como_sistema`):

- `SqlAlchemyDatosWidgetRepository.activos_valorados(id_finca, fincas_permitidas)` lee los activos valorados **como sistema** y los filtra por la finca pedida y por `fincas_permitidas`.
- `fincas_permitidas` sale de `AlcanceFincaAdapter.listar_ids_fincas_permitidas`. Es `None` solo para el rol protegido (Administrador) y, para los demás, `modulo9.usuarios_fincas` activas, que es la misma regla de `fn_fincas_del_usuario`. Hay que aplicarla explícitamente porque, como sistema, los joins ya no acotan nada.
- El caso de uso ya validaba la finca (finca ajena → `403 FINCA_NO_AUTORIZADA`) y ahora le pasa `permitidas` al repositorio.
- El widget solo devuelve agregados (`valor_total`, `activos`, desglose por método). El Productor no recibe permisos de Finanzas ni ve el detalle de la valoración.
- `como_sistema` restaura la identidad del usuario al salir; la prueba lo comprueba.

No requiere migración ni cambios de permisos.

## Evidencia local

Se usó una BD efímera en `sgpmp-db` (PostgreSQL 18) con `alembic upgrade head`. A `sgpmp_app` se le dieron los GRANT de USAGE/SELECT que tiene en DEV, porque las migraciones no los crean. `tests/integration/test_inc_m08_380_g002_valor_inventario_productor.py` corre como `sgpmp_app` con la identidad de un Productor asignado a una finca:

- Con su sesión, `activos_valorados()` de M06 devuelve `[]`, que es la premisa del ticket.
- El widget responde `OK`, `valor_total = 1365472.3` y `activos = 1`.
- Sin finca activa suma solo sus fincas; no incluye otra finca del mismo titular.
- Una finca ajena responde `403`.
- **Sin el arreglo** falla con `assert 'SIN_DATOS' == 'OK'`, el mismo resultado que en TEST.

Suites `tests/reporting`, `tests/configuration`, `tests/financial_valuation` y las integraciones de M06 (flujo NIC 41) y M08: 1073 pasan. La excepción es `test_escalamiento_auditoria_y_preferencias` (RF-105), que ya fallaba antes de este cambio.

## Re-prueba

Repetir TC-M08-003 en TEST:

- El Productor (176) y el Contador (178) piden `GET /dashboard/widgets/valor_inventario?id_finca=494` y ambos reciben `valor_total 1365472.3` y `activos 3`.
- El Productor con una finca que no tiene asignada recibe `403`.
