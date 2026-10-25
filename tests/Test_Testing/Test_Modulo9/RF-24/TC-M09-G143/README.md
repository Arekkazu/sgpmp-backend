# TC-M09-G143 — RF-24 v2.0

Auditoría e integridad de la calibración por **visión** (CU05, Flujo F): disparo automático sin
observaciones, rechazo manual por área sin cámara y rollback cuando la auditoría de publicación no
puede escribirse.

- **Requisito:** RF-24 v2.0 · **Caso de uso:** CU05 — Gestionar Dispositivos IoT, Flujo F
- **Tipo:** Auditoría / Integridad · **Prioridad:** Alta
- **Informe:** `RESULTADOS/TC-M09-G143_resultado.md`

## Ejecución mixta: dos ambientes, dos RUN

| Caso | Ambiente | Objetivo |
|---|---|---|
| TC-M09-290 | TEST | disparo automático M02→M09 con 0 observaciones → auditoría FALLIDO, `usuario_id = null` |
| TC-M09-291 | TEST | POST manual VISION sobre área sin cámara → 422 + evento RF-10 FALLIDO con IP |
| TC-M09-292 | **LOCAL AISLADO** | `REVOKE INSERT` en la auditoría de publicación → rollback de L2, L1 sigue vigente |

TC-M09-292 es local porque exige denegar temporalmente una escritura de auditoría, y eso **no** puede
hacerse contra TEST, DEV, MAIN ni ninguna BD compartida.

El informe de resultado es **uno solo para todo el grupo**. Los RUN se separan por ambiente porque
las evidencias no deben mezclarse, pero no llevan informe propio: cada carpeta de RUN guarda su
evidencia cruda y la decisión de los tres casos se redacta en `RESULTADOS/TC-M09-G143_resultado.md`.

## Compuertas de ejecutabilidad

Antes de crear datos, disparar eventos o levantar infraestructura hay que demostrar que VISION
existe. Las dos compuertas están automatizadas y son de **solo lectura**:

```powershell
$env:G143_RUN_ID_TEST  = 'run-test-YYYYMMDD-HHMMSS'
$env:G143_RUN_ID_LOCAL = 'run-local-YYYYMMDD-HHMMSS'

python -m pytest test_tc_m09_g143_test.py -v --noconftest `
  --junitxml="RESULTADOS/$env:G143_RUN_ID_TEST/pytest.xml"
python -m pytest test_tc_m09_292_local.py -v --noconftest `
  --junitxml="RESULTADOS/$env:G143_RUN_ID_LOCAL/pytest.xml"
```

- **`test_tc_m09_g143_test.py`** ejecuta la colección con Newman (un único `GET /openapi.json`,
  público) y revalida el contrato desde Pytest. No autentica, no usa credenciales y no envía ningún
  POST: ni el lote M02 de TC-290 ni el manual de TC-291.
- **`test_tc_m09_292_local.py`** comprueba sobre `src/` y `alembic/` que el artefacto contiene VISION
  **y** que la auditoría obligatoria de publicación puede identificarse. Si falta cualquiera de las
  dos, no levanta Docker, no crea base, no migra, no siembra y no toca privilegios.

Ambas fallan a propósito mientras VISION no exista: ese fallo **es** la constancia del
bloqueo/rechazo, y dejan su `evidencia.json` escrito de todos modos.

### Las dos compuertas no deciden igual

Es la asimetría propia de este grupo y está en el paquete:

- La ausencia de ruta **manual** VISION **no** basta para bloquear TC-290 (§12), porque M02→M09
  podría ser una integración interna. TC-290 se bloquea por la **fuente de datos**: si no existe
  estructura VISION, no puede demostrarse una ventana con `count = 0`, y ausencia de tabla no es
  cero observaciones funcionales (§11).
- TC-291 **sí** exige la operación manual, y su matriz trata la ausencia como **RECHAZADO** con
  evidencia OpenAPI (§22), no como bloqueo.

### Cuidado con los falsos positivos

Buscar "vision" por subcadena da positivos que no acreditan nada. Aquí el riesgo no es solo montar
un laboratorio inútil: en TC-292 llevaría a **revocar INSERT sobre una tabla equivocada**, y el
resultado no diría nada sobre VISION.

- **`provisión`** y **`revisión`** contienen "vision". Por eso se cuenta la palabra como token.
  Esto incluye `EventoAuditoriaSuministro(… PROVISION_INCREMENTAL_ENTREGADA …)`: ese fue el falso
  positivo que invalidó el primer RUN local, documentado en su `EJECUCION_INVALIDA.md`.
- **`CAMARA_VISION`** y **`ATRIBUTOS_VISION`** son el tipo de dispositivo cámara y sus atributos
  (resolución, fps, área de cobertura): el hardware, no la operación de calibración.
- **`modulo9.auditorias_visuales`** es la auditoría de **identidad visual** de RF-26 (logo, colores
  de marca). "Visual" no es "visión por computador".
- **`integridad_baseline`** y "línea base de integridad" son el baseline de **RF-10**.

La compuerta local descarta explícitamente estos casos y los registra en la evidencia en lugar de
silenciarlos.

## Reglas que la automatización hace cumplir

- **TEST decide TC-290 y TC-291; el laboratorio local decide TC-292.**
- **No se escribe en TEST:** sin siembra de observaciones por SQL, sin auditorías insertadas a mano,
  sin línea base creada por SQL. Solo lectura.
- **No se inventa la ruta VISION** ni se modifica código productivo para obtener un PASS.
- **No se crean datos para un caso bloqueado:** sin fuente VISION demostrable no se registra el lote
  de TC-290 (§14), y confirmada la ausencia de la operación no se crea A2 (§22).
- **No se revocan tablas al azar** (§32). La tabla objetivo debe derivarse de una publicación VISION
  positiva de control; si no puede identificarse, el caso queda bloqueado y no se ejecuta ningún
  `REVOKE`. Los privilegios quedan en `null`, no en `false`.
- **Presupuesto:** 1 `POST /activos-biologicos`, 1 POST manual VISION, 1 POST VISION de setup y 1
  POST VISION objetivo. Sin reintentos automáticos.
- **STOP_ALL en TEST** si un escenario que debía rechazar produjera una línea base; en LOCAL, si el
  fault injection alterara una superficie no prevista, se invalida el RUN y se restauran permisos.
- **Un bloqueo de precondición no se convierte en defecto sin evidencia** (§10). Lo inalcanzable se
  reporta como inalcanzable.

## Estado actual

VISION no existe ni en el contrato de TEST (0 ocurrencias como palabra en 210 rutas) ni en el
artefacto de la rama (0/6 piezas). **TC-M09-291 queda RECHAZADO** —su matriz trata esa ausencia como
incumplimiento— y **TC-M09-290 y TC-M09-292 quedan BLOQUEADOS / NO VERIFICABLES**, de modo que el
grupo es **RECHAZADO**. No se ejecutó ningún POST, ningún `REVOKE` y no se levantó ningún
laboratorio. El detalle está en `RESULTADOS/TC-M09-G143_resultado.md`.

Los nombres del laboratorio quedan reservados para cuando VISION esté disponible: proyecto
`sgpmp-g143-292`, base `sgpmp_g143_292`, PostgreSQL en 55443, backend en `127.0.0.1:18043`, volumen
`sgpmp_g143_292_pgdata`. No se reutilizan los de G79 ni G136.

## Archivos

```text
TC-M09-G143/
├── README.md
├── TC-M09-G143.postman_collection.json   un único GET público, sin credenciales
├── test_tc_m09_g143_test.py              compuerta en TEST (TC-290 / TC-291) + Newman
├── test_tc_m09_292_local.py              compuerta previa al laboratorio local (TC-292)
└── RESULTADOS/
    ├── TC-M09-G143_resultado.md          informe ÚNICO del grupo: los tres casos y ambos RUN
    ├── run-test-20261007-152405/         evidencia.json · newman.html · pytest.xml
    ├── run-local-20261007-153512/        evidencia.json · pytest.xml
    └── run-local-20261007-152405/        RUN invalidado · EJECUCION_INVALIDA.md
```
