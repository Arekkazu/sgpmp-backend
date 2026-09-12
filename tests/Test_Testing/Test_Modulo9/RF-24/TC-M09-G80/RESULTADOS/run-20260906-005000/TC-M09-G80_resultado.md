# TC-M09-G80 — RESULTADO

## DECISIÓN GENERAL

### BLOCKED — ALCANCE DE AUDITORÍA CONTRADICTORIO

TC-M09-151 exige que D09 permita correlacionar operaciones de calibración
exitosas, rechazadas y fallidas. La evidencia de contrato y API demuestra que
D09 no define ni expone esos tres resultados para calibraciones. Por ello no es
posible completar las tres correlaciones sin inventar eventos o superar el
presupuesto seguro de POST.

| Caso | Resultado | Motivo | Categoría de error | Equipo responsable | Acción |
| --- | --- | --- | --- | --- | --- |
| TC-M09-151 | BLOCKED | D09 no tiene tipo de evento, filtro ni resultado para calibraciones; RF-24 solo mantiene auditoría local CREATE/GET ligada a una calibración persistida. | No aplica; discrepancia de alcance pendiente de decisión | Desarrollo | **REPORTAR A DESARROLLO PARA REVISIÓN HUMANA DE TRAZABILIDAD** entre D09, RF-24 y la matriz TC151. |

No se declara defecto de producto todavía. La matriz amplía la expectativa de
auditar rechazo y fallo, mientras el contrato actual no la define para RF-24.
Desarrollo debe confirmar el alcance: si D09 debe cubrir esos tres resultados,
la ausencia de eventos pasará a ser un defecto FLUJO; si no, TC151 debe
corregirse o reasignarse.

## EVENTOS DE AUDITORÍA

| Tipo | Fuente/TC | Usuario esperado | Sensor esperado | Operación esperada | Resultado esperado | Evento D09 encontrado | Coincide |
| --- | --- | --- | --- | --- | --- | --- |
| Exitosa | TC-M09-141 / G74, calibración ID 9 | Usuario 4 | Sensor 3 | Calibración CREATE | SUCCESS equivalente | No | No; D09 no modela calibración |
| Rechazada | TC-M09-144 / G75 | Actor de G75 | Sensor real de G75 | Calibración rechazada por rango | REJECTED equivalente | No | No; D09 no modela rechazo de calibración |
| Fallida | TC-M09-150 / G79 | Usuario 4 | Sensor 7 / 6 | Fallo transaccional controlado | FAILED equivalente | No | No; fue un harness y D09 no lo expone |

### EXITOSA

- Fuente funcional real: G74, calibración ID 9, sensor 3, usuario 4.
- Timestamp de la operación: 2026-09-06T04:13:05.499000Z.
- Resultado funcional: HTTP 201 y persistencia demostrada.
- Consulta D09 correlacionada: usuario 4, ventana 04:10:00Z a 04:20:00Z.
- Resultado: cinco eventos, todos MODULO1, tipos 4/19/3 y ninguno con texto de
  calibración. No existe audit event ID D09 correlacionable.

### RECHAZADA

- Fuente funcional real: G75 TC-M09-144, HTTP 400
  VALOR_FUERA_DE_RANGO, sin persistencia.
- El rechazo es una regla controlada, no un fallo técnico.
- D09 no define un resultado REJECTED de calibración ni ofrece filtro por
  sensor, calibración u operación. No existe correlación admisible.

### FALLIDA

- Fuente revisada: G79 TC-M09-150, HTTP 500
  AUDITORIA_CALIBRACION_FALLIDA y rollback completo.
- La evidencia fue creada mediante un harness controlado de repositorio de
  auditoría; no es un evento real emitido por D09 en TEST y no puede usarse
  como evento auditado de TC151.
- La arquitectura RF-24 hace rollback si falla su auditoría local, por lo que
  no existe una calibración persistida que la tabla local pueda referenciar.

## TRAZABILIDAD

| Criterio | Resultado |
| --- | --- |
| RF-24 exige trazabilidad de calibraciones persistidas | Sí |
| TC151 exige auditar éxito, rechazo y fallo | Sí |
| D09 define éxito para calibración | No |
| D09 define rechazo para calibración | No |
| D09 define fallo para calibración | No |
| D09 filtra por sensor, calibración u operación | No |
| Auditoría local RF-24 registra CREATE/GET | Sí |
| Auditoría local RF-24 representa rechazo/fallo sin calibración | No |
| Existe discrepancia documental | Sí |

El modelo local modulo9.auditorias_calibraciones acepta solamente CREATE y GET,
exige id_calibracion y no contiene resultado. El caso de uso registra CREATE
solo después de guardar una calibración; ante fallo de auditoría hace rollback.
La API D09, por su parte, expone un catálogo de 24 tipos de MODULO1 sin eventos
de calibración o sensor, y sus filtros no incluyen sensor, calibration ID,
operación ni resultado de calibración.

## EVIDENCIA NEWMAN Y API

- Administrador autenticado: usuario 1, rol Administrador.
- Login, identidad, catálogo D09 y consulta filtrada respondieron HTTP 200.
- Newman 6.2.2; htmlextra 1.23.1.
- Assertions: 8 ejecutadas, 0 fallidas.
- HTML Newman: newman/newman-TC-M09-151-auditoria-oraculo.html.
- JSON Newman sanitizado: audit-oracle.json.
- Análisis de alcance y fuentes reutilizadas: audit-scope.json.
- Escaneo de seguridad: seguridad-evidencias.json, sin hallazgos.
- POST de calibración generado por G80: 0 de 2 permitidos.
- POST directo a D09 y escrituras de base de datos: 0.

## ORIGEN DEL BLOQUEO

| Origen | Resultado |
| --- | --- |
| Producto | No determinado hasta resolver el alcance |
| Automatización/prueba | No |
| Entorno TEST | No |
| Bloqueo | Sí |
| Categoría | No aplica; oráculo de auditoría contradictorio |
| Equipo responsable | Desarrollo |
| Acción | **REPORTAR A DESARROLLO PARA REVISIÓN HUMANA DE TRAZABILIDAD** |

## ENTORNO

| Elemento | Valor |
| --- | --- |
| Fecha local | 2026-09-06 |
| Backend TEST | https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test |
| Endpoint D09 | GET /auditoria/ |
| Backend branch / SHA | qa/juan-esteban-m09 / adc3932b9f0293a76ebec7e89ed877274791b6a1 |
| Frontend branch / SHA | qa/juan-esteban-m09 / 966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56 |
| SHA desplegado en TEST | No confirmado |

## GIT FINAL

El cierre read-only registró 57 entradas en el estado del backend y 182
archivos sin seguimiento; ocho pertenecen a G80. No hubo diferencias de
archivos rastreados en backend. Frontend registró 11 entradas de estado y 31
archivos sin seguimiento; git diff --stat contiene únicamente el cambio externo
preexistente de G22. Ningún archivo G80 existe en frontend. Los cambios ajenos
se preservaron sin intervención.

## CONTROLES CUMPLIDOS

- No se modificaron producto, D09, auditorías, infraestructura, datos ni
  dependencias.
- No se creó, editó ni eliminó ningún evento de auditoría manualmente.
- No se ejecutó Cypress, SQL de escritura, un POST de calibración ni limpieza.
- No se almacenaron credenciales, tokens, cabeceras de autenticación ni datos
  de sesión en los artefactos.
- No se ejecutaron commit, push, pull, merge ni cambio de rama.

La ejecución queda detenida para revisión humana.
