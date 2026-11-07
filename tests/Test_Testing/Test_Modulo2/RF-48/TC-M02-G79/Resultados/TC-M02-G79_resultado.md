# RESULTADO — TC-M02-G79

## 0. Resumen ejecutivo

**RECHAZADO contra la ficha suministrada: ambos POST devolvieron 201 en lugar del 200 obligatorio.** El 201 coincide con OpenAPI. Las dos transferencias persistieron completas y las verificaciones V2–V10 resultaron correctas; no se observó persistencia parcial.

| Dimensión | Resultado |
|---|---|
| Subcaso | TC-M02-133, RF-48, CU10C |
| Cobertura actores | COMPLETA: Productor y Administrador del sistema |
| Ejecuciones oficiales | 2/2, una por activo independiente |
| C1/C2/C3 | VERIFICADAS antes de cada POST |
| Ubicación final | CORRECTA |
| Historial / contadores / auditoría | CORRECTOS en las capturas de esta ejecución |
| Newman | 21 requests; 38 aserciones: 36 aprobadas y 2 fallidas (V1 HTTP) |
| Responsable del desajuste HTTP | Desarrollo Backend; coordinación con QA/Análisis para resolver ficha frente a contrato |
| Hallazgo incidental | GET disponibles incluye destinos incompatibles y de otras fincas |

La conservación de eventos anteriores se comprobó por comparación íntegra. No se probó resistencia a una modificación maliciosa futura: no se ejecutaron PUT, DELETE ni SQL de escritura. No se presenta esta ejecución como garantía absoluta de inmutabilidad.

## 1. Identificación y gate

- Responsable QA: Juan Esteban.
- Repositorio: https://github.com/Arekkazu/sgpmp-backend.git (fetch y push coinciden).
- Rama: `qa/juan-esteban-m02`.
- HEAD: `41369ea4ab3948eacb1ab9b2d0549310e285eeae`.
- Fecha: 2026-09-10; transferencias a las 15:03:44 y 15:03:49 America/Bogota (UTC−05).
- Ambiente: TEST HTTPS, `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Árbol inicial con archivos sin seguimiento en otros casos RF-40, RF-48 G80–G82, `_datos_prueba` y `tests/openapi.json`. Se conservaron. G79 contenía solamente `.gitkeep`.
- Herramientas: colección Postman v2.1 ejecutada con Newman; PostgreSQL mediante psycopg2/psql en modo de solo lectura; curl GET para diagnóstico.
- Últimos commits: `41369ea`, `a729fef`, `f707e8d`, `f51316f`, `d88af48`.

| Gate | Evidencia / resultado |
|---|---|
| Repositorio y rama | Correctos; sin cambio de rama |
| OpenAPI HTTPS | HTTP 200 con curl y Newman |
| PostgreSQL | SELECT 1 correcto; `transaction_read_only=on` |
| Contrato | GET disponibles y POST transferencias presentes |
| Body | Requiere origen, destino, fecha y motivo; usuario se obtiene del token |
| Éxito declarado | 201; discrepancia explícita con 200 de la ficha |

## 2. Revisión previa de datos y acceso

Los recursos ya existían antes del trabajo. El historial muestra ejecuciones anteriores de G79 y G82; se conservaron como línea base y no se contabilizaron como parte de estas dos transferencias. No se reubicaron activos para preparar el origen.

| Actor | Usuario / rol | Activo | Tipo / estado | Finca | Origen | Destino | C1 | C2 | Acceso |
|---|---|---:|---|---:|---:|---:|---|---|---|
| Productor | 35 / 2 | 292 QAJE-TRF-OK | INDIVIDUAL / ACTIVO | 57 | 51 | 48 | Destino sin restricción de especie; especie activo 40 | Bovino → Corral | Propietario finca 57; GET y token válidos |
| Administrador | 1 / 1 | 294 QAJE-TRF-REGLAS | INDIVIDUAL / ACTIVO | 57 | 47 | 51 | Especie 40 en ambos | Bovino → Corral | Rol Administrador con permiso; GET y token válidos |

Ambos orígenes y destinos están activos; cada destino es distinto del origen y pertenece a la misma finca. El destino elegido aparece en GET disponibles. No se infiere compatibilidad solamente por aparecer en ese GET: se revisan la especie, el tipo y la ocupación en BD. El Administrador tiene finca de contexto 34; su acceso administrativo legítimo a finca 57 se contrasta con rol, permisos y respuestas, sin fingir que es su propietario.

**Escrituras de preparación de datos: 0.** Solo SELECT, GET y login. Los GET/login pueden generar registros de sesión/auditoría internos del servicio; no se afirma que sus tablas permanezcan sin cambios. Las únicas mutaciones de negocio solicitadas fueron los dos POST oficiales.

### C3 y concurrencia

La fórmula real suma 1 por INDIVIDUAL y `cantidad_actual` por POBLACIONAL, excluyendo estados 5 y 6. No equivale al número de filas de activos. Corresponde a `InfraestructuraM09Adapter.calcular_ocupacion`.

| Actor | Capacidad destino | Ocupación destino ANTES inmediata | Cantidad | Proyección | C3 |
|---|---:|---:|---:|---:|---|
| Productor | 1000 | 220 | 1 | 221 | CUMPLE |
| Administrador | 200 | 0 | 1 | 1 | CUMPLE |

Se tomó una captura BD independiente inmediatamente antes y después de cada POST. El segundo ANTES ya incorpora la primera transferencia. Cada activo tenía exactamente una asociación vigente. `pg_locks` no mostró RowExclusiveLock/ExclusiveLock sobre activos en las capturas previas. El código revisado usa `SELECT ... FOR UPDATE NOWAIT` para concurrencia, no un estado persistido: `fecha_fin=NULL` en movimientos NO significa transferencia en progreso. La consulta de locks es una observación puntual; no se provocaron bloqueos ni concurrencia.


## 3. Ciclo productor

ANTES: 2026-09-10 20:03:43.072525+00:00. DESPUÉS: 2026-09-10 20:03:45.028608+00:00. Ambas sesiones BD `readonly=on`.

POST `/activos-biologicos/292/transferencias`

```json
{
  "infraestructura_origen_id": 51,
  "infraestructura_destino_id": 48,
  "fecha_transferencia": "2026-09-10",
  "motivo_transferencia": "TC-M02-G79 TC-M02-133 productor ejecucion 20260910T20 individual compatible"
}
```

Respuesta HTTP **201**:

```json
{
  "id_movimiento": 29,
  "id_activo_biologico": 292,
  "infraestructura_origen": "Corral QA JE Destino OK",
  "infraestructura_destino": "Corral QA JE Origen",
  "fecha_transferencia": "2026-09-10T00:00:00Z",
  "motivo_transferencia": "TC-M02-G79 TC-M02-133 productor ejecucion 20260910T20 individual compatible",
  "mensaje": "Transferencia registrada exitosamente. El activo fue transferido a Corral QA JE Origen en fecha 2026-09-10."
}
```


| Evidencia | ANTES | DESPUÉS |
|---|---|---|
| Ubicación activo | 51 | 48 |
| Ocupación origen 51 | 1 | 0 (−1) |
| Ocupación destino 48 | 220 | 221 (+1) |
| Movimientos | 1 | 2 |
| Asociación vigente | [284] | 290 |
| Evento movimiento nuevo | — | 29 |
| Auditoría RF48 nueva | — | 1079 |

| Verificación | Resultado |
|---|---|
| V1 | FALLA: 201 ≠ 200 de ficha |
| V2 | CORRECTO |
| V3 | CORRECTO |
| V4 | CORRECTO |
| V5 | CORRECTO |
| V6 | CORRECTO |
| V7 | CORRECTO |
| V8 | CORRECTO |
| V9 | CORRECTO |
| V10 | CORRECTO |

V2/V3/V10: BD más GET infraestructura. V4/V5: movimiento, respuesta POST e historial API. V6: comparación íntegra de movimientos, historial API y auditoría previos; la asociación antes abierta solo recibe fecha_fin para cerrar su vigencia. V7/V8: fórmula SQL real. V9: bitácora SQL y consulta API con Administrador para el evento del actor responsable.

<details><summary>SELECT ejecutados y resultados ANTES / DESPUÉS</summary>

Las consultas son las enviadas realmente; se conservan los resultados completos, incluidos eventos de lecturas previas.


### ANTES


```sql
SELECT current_timestamp, current_date, current_setting('transaction_read_only') AS readonly
```

```json
[
  {
    "current_timestamp": "2026-09-10 20:03:43.072525+00:00",
    "current_date": "2026-09-10",
    "readonly": "on"
  }
]
```


```sql
SELECT a.*,e.nombre AS estado FROM modulo2.activos_biologicos a JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico=a.id_estado WHERE id_activo_biologico=292
```

```json
[
  {
    "id_activo_biologico": 292,
    "id_especie": 40,
    "identificador": "QAJE-TRF-OK",
    "id_infraestructura": 51,
    "tipo": "INDIVIDUAL",
    "fecha_inicio_ciclo": "2026-06-01",
    "id_estado": 1,
    "descripcion": "QAJE-TRF-OK",
    "origen_financiero": "nacimiento",
    "costo_adquisicion": null,
    "atributos_dinamicos": null,
    "id_usuario": 1,
    "fecha_creacion": "2026-06-01 08:00:00+00:00",
    "id_dispositivo_iot": null,
    "soporte_documental": null,
    "detalles_procedencia": null,
    "estado": "ACTIVO"
  }
]
```


```sql
SELECT * FROM modulo9.infraestructuras WHERE id_infraestructura IN (51,48) ORDER BY id_infraestructura
```

```json
[
  {
    "id_infraestructura": 48,
    "descripcion": "Origen de todos los activos sembrados (RF-40/RF-48).",
    "nombre": "Corral QA JE Origen",
    "id_finca": 57,
    "superficie": "1000.00",
    "es_activo": true,
    "tipo": "Corral",
    "fecha_actualizacion": "2026-06-01 08:00:00+00:00",
    "capacidad_maxima": 1000,
    "id_especie": null
  },
  {
    "id_infraestructura": 51,
    "descripcion": "Destino compatible: TC-M02-133 y TC-M02-142.",
    "nombre": "Corral QA JE Destino OK",
    "id_finca": 57,
    "superficie": "500.00",
    "es_activo": true,
    "tipo": "Corral",
    "fecha_actualizacion": "2026-06-01 08:00:00+00:00",
    "capacidad_maxima": 200,
    "id_especie": 40
  }
]
```


```sql
SELECT i.id_infraestructura,COALESCE(SUM(CASE WHEN a.tipo='INDIVIDUAL' THEN 1 ELSE COALESCE(p.cantidad_actual,0) END) FILTER (WHERE a.id_activo_biologico IS NOT NULL),0) AS ocupacion FROM modulo9.infraestructuras i LEFT JOIN modulo2.activos_biologicos a ON a.id_infraestructura=i.id_infraestructura AND a.id_estado NOT IN (5,6) LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales p USING(id_activo_biologico) WHERE i.id_infraestructura IN (51,48) GROUP BY i.id_infraestructura ORDER BY 1
```

```json
[
  {
    "id_infraestructura": 48,
    "ocupacion": 220
  },
  {
    "id_infraestructura": 51,
    "ocupacion": 1
  }
]
```


```sql
SELECT * FROM modulo2.historial_infraestructura_activo WHERE id_activo_biologico=292 ORDER BY id_historial
```

```json
[
  {
    "id_historial": 239,
    "id_activo_biologico": 292,
    "id_infraestructura": 48,
    "fecha_inicio": "2026-06-01 08:00:00+00:00",
    "fecha_fin": "2026-09-10 09:47:24.706824+00:00",
    "id_usuario_registro": 1
  },
  {
    "id_historial": 284,
    "id_activo_biologico": 292,
    "id_infraestructura": 51,
    "fecha_inicio": "2026-09-10 09:47:24.706824+00:00",
    "fecha_fin": null,
    "id_usuario_registro": 35
  }
]
```


```sql
SELECT * FROM modulo2.movimientos WHERE id_activo_biologico=292 ORDER BY id_movimiento
```

```json
[
  {
    "id_movimiento": 23,
    "id_usuario": 35,
    "fecha_transferencia": "2026-09-10 00:00:00+00:00",
    "fecha_fin": null,
    "tipo": "salida",
    "id_activo_biologico": 292,
    "id_infraestructura_origen": 48,
    "id_infraestructura_destino": 51,
    "fecha_registro": "2026-09-10 09:47:24.712253+00:00",
    "motivo_transferencia": "TC-M02-G79 TC-M02-133 Productor transferencia individual compatible"
  }
]
```


```sql
SELECT * FROM modulo2.bitacora_auditoria_m02 WHERE id_activo_biologico=292 ORDER BY id_bitacora
```

```json
[
  {
    "id_bitacora": 984,
    "id_evento": "63cde01c-b84e-42f1-9167-8adaa42a16d8",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:44:02.798448+00:00",
    "timestamp_registro": "2026-09-10 09:44:02.798493+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "d6e12d138bf400c92af9fa3ec2a51993cbd014f98cabab8b55f767f22333d799",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 986,
    "id_evento": "82a59195-5146-46a8-8ac9-c9b9ccf2b846",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:44:29.774929+00:00",
    "timestamp_registro": "2026-09-10 09:44:29.774948+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "eaeadbacaa8b6276e98be0195967135de88e59e6abce227204ca8b06e66e5134",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 988,
    "id_evento": "fd677b00-a424-4613-9f18-f341ca074af7",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:23.171364+00:00",
    "timestamp_registro": "2026-09-10 09:47:23.171386+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ea53beaa48909ad34d59b2dc25043f81a419c804d7ab6db4c15dc9965c4ef8d3",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 989,
    "id_evento": "3c98b4e2-a4bf-47bd-82c4-9b63e33b6e9d",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:23.424580+00:00",
    "timestamp_registro": "2026-09-10 09:47:23.424600+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "a0f0e6a605d6e4a249c9aa0f4e77397c0e148e69568b1e509e62f6f4f76ec7a4",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 990,
    "id_evento": "199886fe-2df0-46e0-aa68-dfcfa87b39a7",
    "rf_origen": "RF48",
    "tipo_evento": "TRANSFERENCIA_REGISTRADA",
    "clasificacion_biologica": "GESTION_OPERATIVA",
    "id_activo_biologico": 292,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:47:24.720554+00:00",
    "timestamp_registro": "2026-09-10 09:47:24.720578+00:00",
    "resultado": "EXITOSO",
    "descripcion": "Transferencia: Corral QA JE Origen → Corral QA JE Destino OK",
    "detalle_tecnico": {
      "motivo": "TC-M02-G79 TC-M02-133 Productor transferencia individual compatible",
      "origen": 48,
      "destino": 51
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "9e76eece0ada760a40ad3c14781fc74a6dc0320b2665e906d809ba9f9130a98e",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 991,
    "id_evento": "06fa99ed-0e20-4f2c-a5f0-1880beb2d0ea",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:24.940507+00:00",
    "timestamp_registro": "2026-09-10 09:47:24.940524+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "f13db7baa07c6022f627e370ac25d916bb00c2b3770f531b496090e37e4c7546",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 992,
    "id_evento": "5f2cb208-94ad-4935-a91f-42533c7fc6e7",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:25.173287+00:00",
    "timestamp_registro": "2026-09-10 09:47:25.173301+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "7b8abea58f7f8ec5e691cbfb9537421ca9900214e81465eaedb0a41bd7707f22",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 998,
    "id_evento": "186147d9-e64a-4449-9265-f0caf86c598c",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:49:01.645581+00:00",
    "timestamp_registro": "2026-09-10 09:49:01.645609+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "60e6d59a73f66eacf7261c4728f9e72d7b687ba87c9c799a0371824fcae7301f",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1072,
    "id_evento": "1fad6935-9a19-4e09-9932-94846e2d150c",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:01:11.914316+00:00",
    "timestamp_registro": "2026-09-10 20:01:11.914366+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "efaa940f60b6aa76c19186e0a63dfc548205a1ce32ae1f56ed85835ee2eb2558",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1073,
    "id_evento": "fa7b3819-e177-45fd-bf6a-639dbe9ad81b",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:01:13.135003+00:00",
    "timestamp_registro": "2026-09-10 20:01:13.135022+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "8329f18e3bbd7a0898a64925bcc954b32ccd97a84dfce5b5d23c925ff5f93861",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1076,
    "id_evento": "ac879ba6-5d03-4ef0-aa0c-590f056e00bd",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:03:41.206297+00:00",
    "timestamp_registro": "2026-09-10 20:03:41.206315+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "2c075478cd7d6eb8965c1d2e531e54ae21dcad3ad6ec7e3fd094f9038f23e1dd",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1077,
    "id_evento": "9016f25a-696a-4d58-aaa8-30bb3ea3beab",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:03:41.422892+00:00",
    "timestamp_registro": "2026-09-10 20:03:41.422910+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "7eeaf37f6eb2330595c96a7cbe6962c351edc97045640dc3b487c77af4ce56f3",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1078,
    "id_evento": "efc3d90a-3a28-496a-9003-52ceb60c1765",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:03:41.648237+00:00",
    "timestamp_registro": "2026-09-10 20:03:41.648259+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "1aaca82304b3bb9ecf36158e983e84c762b0d0a30c17da6eeb9dbcb1eee09c2c",
    "registro_incompleto": false
  }
]
```


```sql
SELECT pid,mode,granted FROM pg_locks WHERE relation='modulo2.activos_biologicos'::regclass AND mode IN ('RowExclusiveLock','ExclusiveLock')
```

```json
[]
```


### DESPUÉS


```sql
SELECT current_timestamp, current_date, current_setting('transaction_read_only') AS readonly
```

```json
[
  {
    "current_timestamp": "2026-09-10 20:03:45.028608+00:00",
    "current_date": "2026-09-10",
    "readonly": "on"
  }
]
```


```sql
SELECT a.*,e.nombre AS estado FROM modulo2.activos_biologicos a JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico=a.id_estado WHERE id_activo_biologico=292
```

```json
[
  {
    "id_activo_biologico": 292,
    "id_especie": 40,
    "identificador": "QAJE-TRF-OK",
    "id_infraestructura": 48,
    "tipo": "INDIVIDUAL",
    "fecha_inicio_ciclo": "2026-06-01",
    "id_estado": 1,
    "descripcion": "QAJE-TRF-OK",
    "origen_financiero": "nacimiento",
    "costo_adquisicion": null,
    "atributos_dinamicos": null,
    "id_usuario": 1,
    "fecha_creacion": "2026-06-01 08:00:00+00:00",
    "id_dispositivo_iot": null,
    "soporte_documental": null,
    "detalles_procedencia": null,
    "estado": "ACTIVO"
  }
]
```


```sql
SELECT * FROM modulo9.infraestructuras WHERE id_infraestructura IN (51,48) ORDER BY id_infraestructura
```

```json
[
  {
    "id_infraestructura": 48,
    "descripcion": "Origen de todos los activos sembrados (RF-40/RF-48).",
    "nombre": "Corral QA JE Origen",
    "id_finca": 57,
    "superficie": "1000.00",
    "es_activo": true,
    "tipo": "Corral",
    "fecha_actualizacion": "2026-06-01 08:00:00+00:00",
    "capacidad_maxima": 1000,
    "id_especie": null
  },
  {
    "id_infraestructura": 51,
    "descripcion": "Destino compatible: TC-M02-133 y TC-M02-142.",
    "nombre": "Corral QA JE Destino OK",
    "id_finca": 57,
    "superficie": "500.00",
    "es_activo": true,
    "tipo": "Corral",
    "fecha_actualizacion": "2026-06-01 08:00:00+00:00",
    "capacidad_maxima": 200,
    "id_especie": 40
  }
]
```


```sql
SELECT i.id_infraestructura,COALESCE(SUM(CASE WHEN a.tipo='INDIVIDUAL' THEN 1 ELSE COALESCE(p.cantidad_actual,0) END) FILTER (WHERE a.id_activo_biologico IS NOT NULL),0) AS ocupacion FROM modulo9.infraestructuras i LEFT JOIN modulo2.activos_biologicos a ON a.id_infraestructura=i.id_infraestructura AND a.id_estado NOT IN (5,6) LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales p USING(id_activo_biologico) WHERE i.id_infraestructura IN (51,48) GROUP BY i.id_infraestructura ORDER BY 1
```

```json
[
  {
    "id_infraestructura": 48,
    "ocupacion": 221
  },
  {
    "id_infraestructura": 51,
    "ocupacion": 0
  }
]
```


```sql
SELECT * FROM modulo2.historial_infraestructura_activo WHERE id_activo_biologico=292 ORDER BY id_historial
```

```json
[
  {
    "id_historial": 239,
    "id_activo_biologico": 292,
    "id_infraestructura": 48,
    "fecha_inicio": "2026-06-01 08:00:00+00:00",
    "fecha_fin": "2026-09-10 09:47:24.706824+00:00",
    "id_usuario_registro": 1
  },
  {
    "id_historial": 284,
    "id_activo_biologico": 292,
    "id_infraestructura": 51,
    "fecha_inicio": "2026-09-10 09:47:24.706824+00:00",
    "fecha_fin": "2026-09-10 20:03:44.015034+00:00",
    "id_usuario_registro": 35
  },
  {
    "id_historial": 290,
    "id_activo_biologico": 292,
    "id_infraestructura": 48,
    "fecha_inicio": "2026-09-10 20:03:44.015034+00:00",
    "fecha_fin": null,
    "id_usuario_registro": 35
  }
]
```


```sql
SELECT * FROM modulo2.movimientos WHERE id_activo_biologico=292 ORDER BY id_movimiento
```

```json
[
  {
    "id_movimiento": 23,
    "id_usuario": 35,
    "fecha_transferencia": "2026-09-10 00:00:00+00:00",
    "fecha_fin": null,
    "tipo": "salida",
    "id_activo_biologico": 292,
    "id_infraestructura_origen": 48,
    "id_infraestructura_destino": 51,
    "fecha_registro": "2026-09-10 09:47:24.712253+00:00",
    "motivo_transferencia": "TC-M02-G79 TC-M02-133 Productor transferencia individual compatible"
  },
  {
    "id_movimiento": 29,
    "id_usuario": 35,
    "fecha_transferencia": "2026-09-10 00:00:00+00:00",
    "fecha_fin": null,
    "tipo": "salida",
    "id_activo_biologico": 292,
    "id_infraestructura_origen": 51,
    "id_infraestructura_destino": 48,
    "fecha_registro": "2026-09-10 20:03:44.021739+00:00",
    "motivo_transferencia": "TC-M02-G79 TC-M02-133 productor ejecucion 20260910T20 individual compatible"
  }
]
```


```sql
SELECT * FROM modulo2.bitacora_auditoria_m02 WHERE id_activo_biologico=292 ORDER BY id_bitacora
```

```json
[
  {
    "id_bitacora": 984,
    "id_evento": "63cde01c-b84e-42f1-9167-8adaa42a16d8",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:44:02.798448+00:00",
    "timestamp_registro": "2026-09-10 09:44:02.798493+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "d6e12d138bf400c92af9fa3ec2a51993cbd014f98cabab8b55f767f22333d799",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 986,
    "id_evento": "82a59195-5146-46a8-8ac9-c9b9ccf2b846",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:44:29.774929+00:00",
    "timestamp_registro": "2026-09-10 09:44:29.774948+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "eaeadbacaa8b6276e98be0195967135de88e59e6abce227204ca8b06e66e5134",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 988,
    "id_evento": "fd677b00-a424-4613-9f18-f341ca074af7",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:23.171364+00:00",
    "timestamp_registro": "2026-09-10 09:47:23.171386+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ea53beaa48909ad34d59b2dc25043f81a419c804d7ab6db4c15dc9965c4ef8d3",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 989,
    "id_evento": "3c98b4e2-a4bf-47bd-82c4-9b63e33b6e9d",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:23.424580+00:00",
    "timestamp_registro": "2026-09-10 09:47:23.424600+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "a0f0e6a605d6e4a249c9aa0f4e77397c0e148e69568b1e509e62f6f4f76ec7a4",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 990,
    "id_evento": "199886fe-2df0-46e0-aa68-dfcfa87b39a7",
    "rf_origen": "RF48",
    "tipo_evento": "TRANSFERENCIA_REGISTRADA",
    "clasificacion_biologica": "GESTION_OPERATIVA",
    "id_activo_biologico": 292,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:47:24.720554+00:00",
    "timestamp_registro": "2026-09-10 09:47:24.720578+00:00",
    "resultado": "EXITOSO",
    "descripcion": "Transferencia: Corral QA JE Origen → Corral QA JE Destino OK",
    "detalle_tecnico": {
      "motivo": "TC-M02-G79 TC-M02-133 Productor transferencia individual compatible",
      "origen": 48,
      "destino": 51
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "9e76eece0ada760a40ad3c14781fc74a6dc0320b2665e906d809ba9f9130a98e",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 991,
    "id_evento": "06fa99ed-0e20-4f2c-a5f0-1880beb2d0ea",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:24.940507+00:00",
    "timestamp_registro": "2026-09-10 09:47:24.940524+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "f13db7baa07c6022f627e370ac25d916bb00c2b3770f531b496090e37e4c7546",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 992,
    "id_evento": "5f2cb208-94ad-4935-a91f-42533c7fc6e7",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:25.173287+00:00",
    "timestamp_registro": "2026-09-10 09:47:25.173301+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "7b8abea58f7f8ec5e691cbfb9537421ca9900214e81465eaedb0a41bd7707f22",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 998,
    "id_evento": "186147d9-e64a-4449-9265-f0caf86c598c",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:49:01.645581+00:00",
    "timestamp_registro": "2026-09-10 09:49:01.645609+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "60e6d59a73f66eacf7261c4728f9e72d7b687ba87c9c799a0371824fcae7301f",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1072,
    "id_evento": "1fad6935-9a19-4e09-9932-94846e2d150c",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:01:11.914316+00:00",
    "timestamp_registro": "2026-09-10 20:01:11.914366+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "efaa940f60b6aa76c19186e0a63dfc548205a1ce32ae1f56ed85835ee2eb2558",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1073,
    "id_evento": "fa7b3819-e177-45fd-bf6a-639dbe9ad81b",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:01:13.135003+00:00",
    "timestamp_registro": "2026-09-10 20:01:13.135022+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "8329f18e3bbd7a0898a64925bcc954b32ccd97a84dfce5b5d23c925ff5f93861",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1076,
    "id_evento": "ac879ba6-5d03-4ef0-aa0c-590f056e00bd",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:03:41.206297+00:00",
    "timestamp_registro": "2026-09-10 20:03:41.206315+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "2c075478cd7d6eb8965c1d2e531e54ae21dcad3ad6ec7e3fd094f9038f23e1dd",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1077,
    "id_evento": "9016f25a-696a-4d58-aaa8-30bb3ea3beab",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:03:41.422892+00:00",
    "timestamp_registro": "2026-09-10 20:03:41.422910+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "7eeaf37f6eb2330595c96a7cbe6962c351edc97045640dc3b487c77af4ce56f3",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1078,
    "id_evento": "efc3d90a-3a28-496a-9003-52ceb60c1765",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 292,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:03:41.648237+00:00",
    "timestamp_registro": "2026-09-10 20:03:41.648259+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "1aaca82304b3bb9ecf36158e983e84c762b0d0a30c17da6eeb9dbcb1eee09c2c",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1079,
    "id_evento": "870112ec-85ef-4871-846c-89082ff1c529",
    "rf_origen": "RF48",
    "tipo_evento": "TRANSFERENCIA_REGISTRADA",
    "clasificacion_biologica": "GESTION_OPERATIVA",
    "id_activo_biologico": 292,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:03:44.026706+00:00",
    "timestamp_registro": "2026-09-10 20:03:44.026741+00:00",
    "resultado": "EXITOSO",
    "descripcion": "Transferencia: Corral QA JE Destino OK → Corral QA JE Origen",
    "detalle_tecnico": {
      "motivo": "TC-M02-G79 TC-M02-133 productor ejecucion 20260910T20 individual compatible",
      "origen": 51,
      "destino": 48
    },
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "7d89874acb1d854f99c39c37d6c3f9c8e823b81924731f83f45b9372d16b4b47",
    "registro_incompleto": false
  }
]
```


```sql
SELECT pid,mode,granted FROM pg_locks WHERE relation='modulo2.activos_biologicos'::regclass AND mode IN ('RowExclusiveLock','ExclusiveLock')
```

```json
[]
```


</details>


## 4. Ciclo admin

ANTES: 2026-09-10 20:03:49.015083+00:00. DESPUÉS: 2026-09-10 20:03:51.027606+00:00. Ambas sesiones BD `readonly=on`.

POST `/activos-biologicos/294/transferencias`

```json
{
  "infraestructura_origen_id": 47,
  "infraestructura_destino_id": 51,
  "fecha_transferencia": "2026-09-10",
  "motivo_transferencia": "TC-M02-G79 TC-M02-133 admin ejecucion 20260910T20 individual compatible"
}
```

Respuesta HTTP **201**:

```json
{
  "id_movimiento": 30,
  "id_activo_biologico": 294,
  "infraestructura_origen": "Corral QA JE Capacidad",
  "infraestructura_destino": "Corral QA JE Destino OK",
  "fecha_transferencia": "2026-09-10T00:00:00Z",
  "motivo_transferencia": "TC-M02-G79 TC-M02-133 admin ejecucion 20260910T20 individual compatible",
  "mensaje": "Transferencia registrada exitosamente. El activo fue transferido a Corral QA JE Destino OK en fecha 2026-09-10."
}
```


| Evidencia | ANTES | DESPUÉS |
|---|---|---|
| Ubicación activo | 47 | 51 |
| Ocupación origen 47 | 50 | 49 (−1) |
| Ocupación destino 51 | 0 | 1 (+1) |
| Movimientos | 2 | 3 |
| Asociación vigente | [289] | 291 |
| Evento movimiento nuevo | — | 30 |
| Auditoría RF48 nueva | — | 1086 |

| Verificación | Resultado |
|---|---|
| V1 | FALLA: 201 ≠ 200 de ficha |
| V2 | CORRECTO |
| V3 | CORRECTO |
| V4 | CORRECTO |
| V5 | CORRECTO |
| V6 | CORRECTO |
| V7 | CORRECTO |
| V8 | CORRECTO |
| V9 | CORRECTO |
| V10 | CORRECTO |

V2/V3/V10: BD más GET infraestructura. V4/V5: movimiento, respuesta POST e historial API. V6: comparación íntegra de movimientos, historial API y auditoría previos; la asociación antes abierta solo recibe fecha_fin para cerrar su vigencia. V7/V8: fórmula SQL real. V9: bitácora SQL y consulta API con Administrador para el evento del actor responsable.

<details><summary>SELECT ejecutados y resultados ANTES / DESPUÉS</summary>

Las consultas son las enviadas realmente; se conservan los resultados completos, incluidos eventos de lecturas previas.


### ANTES


```sql
SELECT current_timestamp, current_date, current_setting('transaction_read_only') AS readonly
```

```json
[
  {
    "current_timestamp": "2026-09-10 20:03:49.015083+00:00",
    "current_date": "2026-09-10",
    "readonly": "on"
  }
]
```


```sql
SELECT a.*,e.nombre AS estado FROM modulo2.activos_biologicos a JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico=a.id_estado WHERE id_activo_biologico=294
```

```json
[
  {
    "id_activo_biologico": 294,
    "id_especie": 40,
    "identificador": "QAJE-TRF-REGLAS",
    "id_infraestructura": 47,
    "tipo": "INDIVIDUAL",
    "fecha_inicio_ciclo": "2026-06-01",
    "id_estado": 1,
    "descripcion": "QAJE-TRF-REGLAS",
    "origen_financiero": "nacimiento",
    "costo_adquisicion": null,
    "atributos_dinamicos": null,
    "id_usuario": 1,
    "fecha_creacion": "2026-06-01 08:00:00+00:00",
    "id_dispositivo_iot": null,
    "soporte_documental": null,
    "detalles_procedencia": null,
    "estado": "ACTIVO"
  }
]
```


```sql
SELECT * FROM modulo9.infraestructuras WHERE id_infraestructura IN (47,51) ORDER BY id_infraestructura
```

```json
[
  {
    "id_infraestructura": 47,
    "descripcion": "Destino con capacidad al limite C3: TC-M02-137 (48 de 50).",
    "nombre": "Corral QA JE Capacidad",
    "id_finca": 57,
    "superficie": "100.00",
    "es_activo": true,
    "tipo": "Corral",
    "fecha_actualizacion": "2026-06-01 08:00:00+00:00",
    "capacidad_maxima": 50,
    "id_especie": 40
  },
  {
    "id_infraestructura": 51,
    "descripcion": "Destino compatible: TC-M02-133 y TC-M02-142.",
    "nombre": "Corral QA JE Destino OK",
    "id_finca": 57,
    "superficie": "500.00",
    "es_activo": true,
    "tipo": "Corral",
    "fecha_actualizacion": "2026-06-01 08:00:00+00:00",
    "capacidad_maxima": 200,
    "id_especie": 40
  }
]
```


```sql
SELECT i.id_infraestructura,COALESCE(SUM(CASE WHEN a.tipo='INDIVIDUAL' THEN 1 ELSE COALESCE(p.cantidad_actual,0) END) FILTER (WHERE a.id_activo_biologico IS NOT NULL),0) AS ocupacion FROM modulo9.infraestructuras i LEFT JOIN modulo2.activos_biologicos a ON a.id_infraestructura=i.id_infraestructura AND a.id_estado NOT IN (5,6) LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales p USING(id_activo_biologico) WHERE i.id_infraestructura IN (47,51) GROUP BY i.id_infraestructura ORDER BY 1
```

```json
[
  {
    "id_infraestructura": 47,
    "ocupacion": 50
  },
  {
    "id_infraestructura": 51,
    "ocupacion": 0
  }
]
```


```sql
SELECT * FROM modulo2.historial_infraestructura_activo WHERE id_activo_biologico=294 ORDER BY id_historial
```

```json
[
  {
    "id_historial": 241,
    "id_activo_biologico": 294,
    "id_infraestructura": 48,
    "fecha_inicio": "2026-06-01 08:00:00+00:00",
    "fecha_fin": "2026-09-10 09:47:28.975964+00:00",
    "id_usuario_registro": 1
  },
  {
    "id_historial": 285,
    "id_activo_biologico": 294,
    "id_infraestructura": 51,
    "fecha_inicio": "2026-09-10 09:47:28.975964+00:00",
    "fecha_fin": "2026-09-10 10:36:34.786394+00:00",
    "id_usuario_registro": 1
  },
  {
    "id_historial": 289,
    "id_activo_biologico": 294,
    "id_infraestructura": 47,
    "fecha_inicio": "2026-09-10 10:36:34.786394+00:00",
    "fecha_fin": null,
    "id_usuario_registro": 1
  }
]
```


```sql
SELECT * FROM modulo2.movimientos WHERE id_activo_biologico=294 ORDER BY id_movimiento
```

```json
[
  {
    "id_movimiento": 24,
    "id_usuario": 1,
    "fecha_transferencia": "2026-09-10 00:00:00+00:00",
    "fecha_fin": null,
    "tipo": "salida",
    "id_activo_biologico": 294,
    "id_infraestructura_origen": 48,
    "id_infraestructura_destino": 51,
    "fecha_registro": "2026-09-10 09:47:28.980645+00:00",
    "motivo_transferencia": "TC-M02-G79 TC-M02-133 Administrador transferencia individual compatible"
  },
  {
    "id_movimiento": 28,
    "id_usuario": 1,
    "fecha_transferencia": "2026-09-10 00:00:00+00:00",
    "fecha_fin": null,
    "tipo": "salida",
    "id_activo_biologico": 294,
    "id_infraestructura_origen": 51,
    "id_infraestructura_destino": 47,
    "fecha_registro": "2026-09-10 10:36:34.791548+00:00",
    "motivo_transferencia": "TC-M02-142 concurrencia B"
  }
]
```


```sql
SELECT * FROM modulo2.bitacora_auditoria_m02 WHERE id_activo_biologico=294 ORDER BY id_bitacora
```

```json
[
  {
    "id_bitacora": 985,
    "id_evento": "c39310bf-837f-4821-9c39-955112daa613",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:44:03.904222+00:00",
    "timestamp_registro": "2026-09-10 09:44:03.904238+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ad157535b0dee007455356992f10e24b04025083e340a709d86dad04f2d7b59d",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 987,
    "id_evento": "31d04340-2438-499c-956c-48f8f0b492a4",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:44:30.527595+00:00",
    "timestamp_registro": "2026-09-10 09:44:30.527613+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "87222efd8706d6cb34cd9d6ea815ad152746287f2441a5bf8c8a64c6c0bf8cdc",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 993,
    "id_evento": "b4392172-7ffb-4ada-8ddd-ef128c1fe5c6",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:27.416358+00:00",
    "timestamp_registro": "2026-09-10 09:47:27.416374+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "74e7f78664ef4b3d263003f1d6ca443de061dc8443b688a4f7444cfaa83bb788",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 994,
    "id_evento": "2d33abbf-4a97-44a9-9364-94a65363377e",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:27.624284+00:00",
    "timestamp_registro": "2026-09-10 09:47:27.624301+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "2d584434ca052206b5bf17591f91fa6ba11503dbcb5c8b499bc2f5c0078b0e63",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 995,
    "id_evento": "a2a1f7c0-c332-48b4-a455-81b43a3252c0",
    "rf_origen": "RF48",
    "tipo_evento": "TRANSFERENCIA_REGISTRADA",
    "clasificacion_biologica": "GESTION_OPERATIVA",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:47:28.983591+00:00",
    "timestamp_registro": "2026-09-10 09:47:28.983610+00:00",
    "resultado": "EXITOSO",
    "descripcion": "Transferencia: Corral QA JE Origen → Corral QA JE Destino OK",
    "detalle_tecnico": {
      "motivo": "TC-M02-G79 TC-M02-133 Administrador transferencia individual compatible",
      "origen": 48,
      "destino": 51
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "59f250bef324527fa415638cd0ba88f4f0cbcc8add5acce3c823e0c7bd08ed8b",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 996,
    "id_evento": "261e66b1-458e-426b-9867-b932615acbc8",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:29.206838+00:00",
    "timestamp_registro": "2026-09-10 09:47:29.206858+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "11a41a36b13d8572bcc6f18f1a752504b06a583f7b0f8f3e0aa9e113e9d4c44d",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 997,
    "id_evento": "9d609746-a6a0-40cd-8861-2e86651e9f13",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:29.428928+00:00",
    "timestamp_registro": "2026-09-10 09:47:29.428946+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "3dd5f1f8a87a2e6a0c3c4cf493214c193cff549e5ac29051cb0dcc6f7c96ed4e",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 999,
    "id_evento": "ef495601-3583-43b3-a933-6535349dfaa6",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:49:02.137100+00:00",
    "timestamp_registro": "2026-09-10 09:49:02.137116+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ad0d419341f51d316e5c9f3adb032a920d0177ce4acdb85b646779409d99fc90",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1000,
    "id_evento": "8c50a229-0d34-4e63-8b0c-cf268111cd7e",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:33.924668+00:00",
    "timestamp_registro": "2026-09-10 09:55:33.924708+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "15c98dc283db4590be031eca838237986b904076344bcd9baceb98d19d5bbee1",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1004,
    "id_evento": "72c2530e-e060-42d4-845a-6cc2bdca8198",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:36.094128+00:00",
    "timestamp_registro": "2026-09-10 09:55:36.094147+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "daccc3173d5b87df4ee1bae29a823e51bdd6f7c6262ba4295398f1493d45f27c",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1005,
    "id_evento": "c6d1c8ca-9997-4a3d-b74b-f89ed1b2b986",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:36.514087+00:00",
    "timestamp_registro": "2026-09-10 09:55:36.514101+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "e0decbcb8d195fd543665cc9a62b7c2f8698d12d664ada90704f9d65939815cf",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1009,
    "id_evento": "5e0e7dd4-f197-4c6c-81eb-7780ed0f501d",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:37.594981+00:00",
    "timestamp_registro": "2026-09-10 09:55:37.594995+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "226a04da5fea98fa4270e6920f2d5f535c69fba010d2e645c7562182922a0c51",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1011,
    "id_evento": "41180a23-d731-4c70-89cf-ffbb39e538ae",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:38.171239+00:00",
    "timestamp_registro": "2026-09-10 09:55:38.171253+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "5a6d4070741f67a50d2752ae92df8afec3ad6d07738328a3f0b23a1595edfae5",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1012,
    "id_evento": "af3f7bce-4eaa-40f1-a1d8-419a90d8c382",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:38.593780+00:00",
    "timestamp_registro": "2026-09-10 09:55:38.593797+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "9873d3622ff0e55c4d9eab3e45e777a251fbdd1f0f825d81c5ea0f5fdc90d077",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1020,
    "id_evento": "62edda4a-e628-4ec8-9baa-5dee02ce0d7a",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:09:57.924319+00:00",
    "timestamp_registro": "2026-09-10 10:09:57.924357+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "8fde357dff285b5f1f97fed8b01b5210c6827b65fcdb3df6d5d590b31b46c3a7",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1022,
    "id_evento": "b5d3eed2-8dbe-43b7-908a-aa7eba3d792d",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:09:58.822836+00:00",
    "timestamp_registro": "2026-09-10 10:09:58.822849+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "6038d4f2c8b1fb329bf47f6379e428e4251f102154304bff83cb9c7f7c44f00c",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1024,
    "id_evento": "d32b3f83-3feb-4f7b-8cef-92b5824038e9",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:11:53.456986+00:00",
    "timestamp_registro": "2026-09-10 10:11:53.456998+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "7c901618d4b6755a3882520c78f894ad0d976b9a1ee8d04939fe6491a8e4d6bf",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1026,
    "id_evento": "23b68119-c887-40bc-b34c-3138260100fe",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:11:54.539935+00:00",
    "timestamp_registro": "2026-09-10 10:11:54.539949+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ed19f7b10a80bb5ca94d7a714b73ef418c4f049a2485eff8995c4ddb9bf6005e",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1028,
    "id_evento": "080ec23c-4c6f-4558-a45d-b9e5e917792c",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:11:55.378499+00:00",
    "timestamp_registro": "2026-09-10 10:11:55.378513+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "c19e5e4968f5ccf9155bfe8d482eaf835e524b98fa0520a91b240fdc15c0f60f",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1030,
    "id_evento": "fce04a33-56b3-41ed-a6b0-5be70adc3020",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:12:45.609711+00:00",
    "timestamp_registro": "2026-09-10 10:12:45.609726+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "352757d55c2fde0901e6cc5f02dc7022114e1fff1064bca587b426839c180f5d",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1032,
    "id_evento": "103a62ed-9da7-431a-a0af-e553fa57e37d",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:12:46.945904+00:00",
    "timestamp_registro": "2026-09-10 10:12:46.945919+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "9db1f16de8fa3bd391240bae514d48dc2a8678286f59f4de973f4f9b31844db5",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1034,
    "id_evento": "733af6f8-54be-454b-b6ec-4f03493a7046",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:12:47.773418+00:00",
    "timestamp_registro": "2026-09-10 10:12:47.773432+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "b0294373412c9db204b9ff83c619741a3f333a952f2cc9f8f63a25a12f2e8cfa",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1044,
    "id_evento": "112ddd14-ed21-4e98-aecf-5dafd2b665e9",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:36:24.613365+00:00",
    "timestamp_registro": "2026-09-10 10:36:24.613378+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "593de8bece29ce278cd9494bbe67d0b787ee058c748b3e80ceb614da0fed4ca8",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1045,
    "id_evento": "9b7e4255-bb34-4bd8-bab9-c4df95b20bf5",
    "rf_origen": "RF48",
    "tipo_evento": "TRANSFERENCIA_REGISTRADA",
    "clasificacion_biologica": "GESTION_OPERATIVA",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:36:34.794321+00:00",
    "timestamp_registro": "2026-09-10 10:36:34.794347+00:00",
    "resultado": "EXITOSO",
    "descripcion": "Transferencia: Corral QA JE Destino OK → Corral QA JE Capacidad",
    "detalle_tecnico": {
      "motivo": "TC-M02-142 concurrencia B",
      "origen": 51,
      "destino": 47
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "5fbce0516680863ad9db8db5368e886b412351e6ee9650217b4da2170929b2d5",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1074,
    "id_evento": "ae9045bc-eb95-4535-8ca8-5d69bdc3a561",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:01:16.957799+00:00",
    "timestamp_registro": "2026-09-10 20:01:16.957816+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ebfb90e862c842eeb5af736b86d862b41be528bd6e1c09f9be3d9c44170344bc",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1075,
    "id_evento": "ee93d85e-bd93-4cfc-b1ee-93dbf307663c",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:01:17.729634+00:00",
    "timestamp_registro": "2026-09-10 20:01:17.729653+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "a09c277bc8aa5de9b6e5232a9164cbb603b5271761e949ed85603744c8e0e44b",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1083,
    "id_evento": "c4de022d-2b44-428a-a450-ebafdd93d4bb",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:03:47.442510+00:00",
    "timestamp_registro": "2026-09-10 20:03:47.442531+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "6130ad51d9fbe931ad9808e26fabcf3d7dc0ad6736fb8727976a2c5c9bd254c4",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1084,
    "id_evento": "04dd9c26-c484-48e8-9ae6-4774a15be7fb",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:03:47.634810+00:00",
    "timestamp_registro": "2026-09-10 20:03:47.634833+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ac8f5fea44806c92520435d952fe41dd72051ed9a59bae888c558f7f17561580",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1085,
    "id_evento": "3959ab9d-4347-4952-9e2e-6c6c149b40dd",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:03:47.859993+00:00",
    "timestamp_registro": "2026-09-10 20:03:47.860014+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "8fa54a612db27024b013b5d8fb32551829683ef06fc534677f70c25021ce85a6",
    "registro_incompleto": false
  }
]
```


```sql
SELECT pid,mode,granted FROM pg_locks WHERE relation='modulo2.activos_biologicos'::regclass AND mode IN ('RowExclusiveLock','ExclusiveLock')
```

```json
[]
```


### DESPUÉS


```sql
SELECT current_timestamp, current_date, current_setting('transaction_read_only') AS readonly
```

```json
[
  {
    "current_timestamp": "2026-09-10 20:03:51.027606+00:00",
    "current_date": "2026-09-10",
    "readonly": "on"
  }
]
```


```sql
SELECT a.*,e.nombre AS estado FROM modulo2.activos_biologicos a JOIN modulo2.estados_activos_biologicos e ON e.id_estado_activo_biologico=a.id_estado WHERE id_activo_biologico=294
```

```json
[
  {
    "id_activo_biologico": 294,
    "id_especie": 40,
    "identificador": "QAJE-TRF-REGLAS",
    "id_infraestructura": 51,
    "tipo": "INDIVIDUAL",
    "fecha_inicio_ciclo": "2026-06-01",
    "id_estado": 1,
    "descripcion": "QAJE-TRF-REGLAS",
    "origen_financiero": "nacimiento",
    "costo_adquisicion": null,
    "atributos_dinamicos": null,
    "id_usuario": 1,
    "fecha_creacion": "2026-06-01 08:00:00+00:00",
    "id_dispositivo_iot": null,
    "soporte_documental": null,
    "detalles_procedencia": null,
    "estado": "ACTIVO"
  }
]
```


```sql
SELECT * FROM modulo9.infraestructuras WHERE id_infraestructura IN (47,51) ORDER BY id_infraestructura
```

```json
[
  {
    "id_infraestructura": 47,
    "descripcion": "Destino con capacidad al limite C3: TC-M02-137 (48 de 50).",
    "nombre": "Corral QA JE Capacidad",
    "id_finca": 57,
    "superficie": "100.00",
    "es_activo": true,
    "tipo": "Corral",
    "fecha_actualizacion": "2026-06-01 08:00:00+00:00",
    "capacidad_maxima": 50,
    "id_especie": 40
  },
  {
    "id_infraestructura": 51,
    "descripcion": "Destino compatible: TC-M02-133 y TC-M02-142.",
    "nombre": "Corral QA JE Destino OK",
    "id_finca": 57,
    "superficie": "500.00",
    "es_activo": true,
    "tipo": "Corral",
    "fecha_actualizacion": "2026-06-01 08:00:00+00:00",
    "capacidad_maxima": 200,
    "id_especie": 40
  }
]
```


```sql
SELECT i.id_infraestructura,COALESCE(SUM(CASE WHEN a.tipo='INDIVIDUAL' THEN 1 ELSE COALESCE(p.cantidad_actual,0) END) FILTER (WHERE a.id_activo_biologico IS NOT NULL),0) AS ocupacion FROM modulo9.infraestructuras i LEFT JOIN modulo2.activos_biologicos a ON a.id_infraestructura=i.id_infraestructura AND a.id_estado NOT IN (5,6) LEFT JOIN modulo2.detalles_activos_biologicos_poblacionales p USING(id_activo_biologico) WHERE i.id_infraestructura IN (47,51) GROUP BY i.id_infraestructura ORDER BY 1
```

```json
[
  {
    "id_infraestructura": 47,
    "ocupacion": 49
  },
  {
    "id_infraestructura": 51,
    "ocupacion": 1
  }
]
```


```sql
SELECT * FROM modulo2.historial_infraestructura_activo WHERE id_activo_biologico=294 ORDER BY id_historial
```

```json
[
  {
    "id_historial": 241,
    "id_activo_biologico": 294,
    "id_infraestructura": 48,
    "fecha_inicio": "2026-06-01 08:00:00+00:00",
    "fecha_fin": "2026-09-10 09:47:28.975964+00:00",
    "id_usuario_registro": 1
  },
  {
    "id_historial": 285,
    "id_activo_biologico": 294,
    "id_infraestructura": 51,
    "fecha_inicio": "2026-09-10 09:47:28.975964+00:00",
    "fecha_fin": "2026-09-10 10:36:34.786394+00:00",
    "id_usuario_registro": 1
  },
  {
    "id_historial": 289,
    "id_activo_biologico": 294,
    "id_infraestructura": 47,
    "fecha_inicio": "2026-09-10 10:36:34.786394+00:00",
    "fecha_fin": "2026-09-10 20:03:49.983125+00:00",
    "id_usuario_registro": 1
  },
  {
    "id_historial": 291,
    "id_activo_biologico": 294,
    "id_infraestructura": 51,
    "fecha_inicio": "2026-09-10 20:03:49.983125+00:00",
    "fecha_fin": null,
    "id_usuario_registro": 1
  }
]
```


```sql
SELECT * FROM modulo2.movimientos WHERE id_activo_biologico=294 ORDER BY id_movimiento
```

```json
[
  {
    "id_movimiento": 24,
    "id_usuario": 1,
    "fecha_transferencia": "2026-09-10 00:00:00+00:00",
    "fecha_fin": null,
    "tipo": "salida",
    "id_activo_biologico": 294,
    "id_infraestructura_origen": 48,
    "id_infraestructura_destino": 51,
    "fecha_registro": "2026-09-10 09:47:28.980645+00:00",
    "motivo_transferencia": "TC-M02-G79 TC-M02-133 Administrador transferencia individual compatible"
  },
  {
    "id_movimiento": 28,
    "id_usuario": 1,
    "fecha_transferencia": "2026-09-10 00:00:00+00:00",
    "fecha_fin": null,
    "tipo": "salida",
    "id_activo_biologico": 294,
    "id_infraestructura_origen": 51,
    "id_infraestructura_destino": 47,
    "fecha_registro": "2026-09-10 10:36:34.791548+00:00",
    "motivo_transferencia": "TC-M02-142 concurrencia B"
  },
  {
    "id_movimiento": 30,
    "id_usuario": 1,
    "fecha_transferencia": "2026-09-10 00:00:00+00:00",
    "fecha_fin": null,
    "tipo": "salida",
    "id_activo_biologico": 294,
    "id_infraestructura_origen": 47,
    "id_infraestructura_destino": 51,
    "fecha_registro": "2026-09-10 20:03:49.988314+00:00",
    "motivo_transferencia": "TC-M02-G79 TC-M02-133 admin ejecucion 20260910T20 individual compatible"
  }
]
```


```sql
SELECT * FROM modulo2.bitacora_auditoria_m02 WHERE id_activo_biologico=294 ORDER BY id_bitacora
```

```json
[
  {
    "id_bitacora": 985,
    "id_evento": "c39310bf-837f-4821-9c39-955112daa613",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:44:03.904222+00:00",
    "timestamp_registro": "2026-09-10 09:44:03.904238+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ad157535b0dee007455356992f10e24b04025083e340a709d86dad04f2d7b59d",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 987,
    "id_evento": "31d04340-2438-499c-956c-48f8f0b492a4",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:44:30.527595+00:00",
    "timestamp_registro": "2026-09-10 09:44:30.527613+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "87222efd8706d6cb34cd9d6ea815ad152746287f2441a5bf8c8a64c6c0bf8cdc",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 993,
    "id_evento": "b4392172-7ffb-4ada-8ddd-ef128c1fe5c6",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:27.416358+00:00",
    "timestamp_registro": "2026-09-10 09:47:27.416374+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "74e7f78664ef4b3d263003f1d6ca443de061dc8443b688a4f7444cfaa83bb788",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 994,
    "id_evento": "2d33abbf-4a97-44a9-9364-94a65363377e",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:27.624284+00:00",
    "timestamp_registro": "2026-09-10 09:47:27.624301+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "2d584434ca052206b5bf17591f91fa6ba11503dbcb5c8b499bc2f5c0078b0e63",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 995,
    "id_evento": "a2a1f7c0-c332-48b4-a455-81b43a3252c0",
    "rf_origen": "RF48",
    "tipo_evento": "TRANSFERENCIA_REGISTRADA",
    "clasificacion_biologica": "GESTION_OPERATIVA",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:47:28.983591+00:00",
    "timestamp_registro": "2026-09-10 09:47:28.983610+00:00",
    "resultado": "EXITOSO",
    "descripcion": "Transferencia: Corral QA JE Origen → Corral QA JE Destino OK",
    "detalle_tecnico": {
      "motivo": "TC-M02-G79 TC-M02-133 Administrador transferencia individual compatible",
      "origen": 48,
      "destino": 51
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "59f250bef324527fa415638cd0ba88f4f0cbcc8add5acce3c823e0c7bd08ed8b",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 996,
    "id_evento": "261e66b1-458e-426b-9867-b932615acbc8",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:29.206838+00:00",
    "timestamp_registro": "2026-09-10 09:47:29.206858+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "11a41a36b13d8572bcc6f18f1a752504b06a583f7b0f8f3e0aa9e113e9d4c44d",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 997,
    "id_evento": "9d609746-a6a0-40cd-8861-2e86651e9f13",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:47:29.428928+00:00",
    "timestamp_registro": "2026-09-10 09:47:29.428946+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "3dd5f1f8a87a2e6a0c3c4cf493214c193cff549e5ac29051cb0dcc6f7c96ed4e",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 999,
    "id_evento": "ef495601-3583-43b3-a933-6535349dfaa6",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 09:49:02.137100+00:00",
    "timestamp_registro": "2026-09-10 09:49:02.137116+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ad0d419341f51d316e5c9f3adb032a920d0177ce4acdb85b646779409d99fc90",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1000,
    "id_evento": "8c50a229-0d34-4e63-8b0c-cf268111cd7e",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:33.924668+00:00",
    "timestamp_registro": "2026-09-10 09:55:33.924708+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "15c98dc283db4590be031eca838237986b904076344bcd9baceb98d19d5bbee1",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1004,
    "id_evento": "72c2530e-e060-42d4-845a-6cc2bdca8198",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:36.094128+00:00",
    "timestamp_registro": "2026-09-10 09:55:36.094147+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "daccc3173d5b87df4ee1bae29a823e51bdd6f7c6262ba4295398f1493d45f27c",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1005,
    "id_evento": "c6d1c8ca-9997-4a3d-b74b-f89ed1b2b986",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:36.514087+00:00",
    "timestamp_registro": "2026-09-10 09:55:36.514101+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "e0decbcb8d195fd543665cc9a62b7c2f8698d12d664ada90704f9d65939815cf",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1009,
    "id_evento": "5e0e7dd4-f197-4c6c-81eb-7780ed0f501d",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:37.594981+00:00",
    "timestamp_registro": "2026-09-10 09:55:37.594995+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "226a04da5fea98fa4270e6920f2d5f535c69fba010d2e645c7562182922a0c51",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1011,
    "id_evento": "41180a23-d731-4c70-89cf-ffbb39e538ae",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:38.171239+00:00",
    "timestamp_registro": "2026-09-10 09:55:38.171253+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "5a6d4070741f67a50d2752ae92df8afec3ad6d07738328a3f0b23a1595edfae5",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1012,
    "id_evento": "af3f7bce-4eaa-40f1-a1d8-419a90d8c382",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 09:55:38.593780+00:00",
    "timestamp_registro": "2026-09-10 09:55:38.593797+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "9873d3622ff0e55c4d9eab3e45e777a251fbdd1f0f825d81c5ea0f5fdc90d077",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1020,
    "id_evento": "62edda4a-e628-4ec8-9baa-5dee02ce0d7a",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:09:57.924319+00:00",
    "timestamp_registro": "2026-09-10 10:09:57.924357+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "8fde357dff285b5f1f97fed8b01b5210c6827b65fcdb3df6d5d590b31b46c3a7",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1022,
    "id_evento": "b5d3eed2-8dbe-43b7-908a-aa7eba3d792d",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:09:58.822836+00:00",
    "timestamp_registro": "2026-09-10 10:09:58.822849+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "6038d4f2c8b1fb329bf47f6379e428e4251f102154304bff83cb9c7f7c44f00c",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1024,
    "id_evento": "d32b3f83-3feb-4f7b-8cef-92b5824038e9",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:11:53.456986+00:00",
    "timestamp_registro": "2026-09-10 10:11:53.456998+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "7c901618d4b6755a3882520c78f894ad0d976b9a1ee8d04939fe6491a8e4d6bf",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1026,
    "id_evento": "23b68119-c887-40bc-b34c-3138260100fe",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:11:54.539935+00:00",
    "timestamp_registro": "2026-09-10 10:11:54.539949+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ed19f7b10a80bb5ca94d7a714b73ef418c4f049a2485eff8995c4ddb9bf6005e",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1028,
    "id_evento": "080ec23c-4c6f-4558-a45d-b9e5e917792c",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:11:55.378499+00:00",
    "timestamp_registro": "2026-09-10 10:11:55.378513+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "c19e5e4968f5ccf9155bfe8d482eaf835e524b98fa0520a91b240fdc15c0f60f",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1030,
    "id_evento": "fce04a33-56b3-41ed-a6b0-5be70adc3020",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:12:45.609711+00:00",
    "timestamp_registro": "2026-09-10 10:12:45.609726+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "352757d55c2fde0901e6cc5f02dc7022114e1fff1064bca587b426839c180f5d",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1032,
    "id_evento": "103a62ed-9da7-431a-a0af-e553fa57e37d",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:12:46.945904+00:00",
    "timestamp_registro": "2026-09-10 10:12:46.945919+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 35,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "9db1f16de8fa3bd391240bae514d48dc2a8678286f59f4de973f4f9b31844db5",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1034,
    "id_evento": "733af6f8-54be-454b-b6ec-4f03493a7046",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:12:47.773418+00:00",
    "timestamp_registro": "2026-09-10 10:12:47.773432+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "b0294373412c9db204b9ff83c619741a3f333a952f2cc9f8f63a25a12f2e8cfa",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1044,
    "id_evento": "112ddd14-ed21-4e98-aecf-5dafd2b665e9",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:36:24.613365+00:00",
    "timestamp_registro": "2026-09-10 10:36:24.613378+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "593de8bece29ce278cd9494bbe67d0b787ee058c748b3e80ceb614da0fed4ca8",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1045,
    "id_evento": "9b7e4255-bb34-4bd8-bab9-c4df95b20bf5",
    "rf_origen": "RF48",
    "tipo_evento": "TRANSFERENCIA_REGISTRADA",
    "clasificacion_biologica": "GESTION_OPERATIVA",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 10:36:34.794321+00:00",
    "timestamp_registro": "2026-09-10 10:36:34.794347+00:00",
    "resultado": "EXITOSO",
    "descripcion": "Transferencia: Corral QA JE Destino OK → Corral QA JE Capacidad",
    "detalle_tecnico": {
      "motivo": "TC-M02-142 concurrencia B",
      "origen": 51,
      "destino": 47
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "5fbce0516680863ad9db8db5368e886b412351e6ee9650217b4da2170929b2d5",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1074,
    "id_evento": "ae9045bc-eb95-4535-8ca8-5d69bdc3a561",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:01:16.957799+00:00",
    "timestamp_registro": "2026-09-10 20:01:16.957816+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ebfb90e862c842eeb5af736b86d862b41be528bd6e1c09f9be3d9c44170344bc",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1075,
    "id_evento": "ee93d85e-bd93-4cfc-b1ee-93dbf307663c",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:01:17.729634+00:00",
    "timestamp_registro": "2026-09-10 20:01:17.729653+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "a09c277bc8aa5de9b6e5232a9164cbb603b5271761e949ed85603744c8e0e44b",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1083,
    "id_evento": "c4de022d-2b44-428a-a450-ebafdd93d4bb",
    "rf_origen": "RF35",
    "tipo_evento": "ACTIVO_INDIVIDUAL_CONSULTA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:03:47.442510+00:00",
    "timestamp_registro": "2026-09-10 20:03:47.442531+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "6130ad51d9fbe931ad9808e26fabcf3d7dc0ad6736fb8727976a2c5c9bd254c4",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1084,
    "id_evento": "04dd9c26-c484-48e8-9ae6-4774a15be7fb",
    "rf_origen": "RF34",
    "tipo_evento": "INFRAESTRUCTURA_CONSULTADA",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:03:47.634810+00:00",
    "timestamp_registro": "2026-09-10 20:03:47.634833+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": {
      "tipo_consulta": "ACTIVA",
      "fecha_referencia": null
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "ac8f5fea44806c92520435d952fe41dd72051ed9a59bae888c558f7f17561580",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1085,
    "id_evento": "3959ab9d-4347-4952-9e2e-6c6c149b40dd",
    "rf_origen": "RF46",
    "tipo_evento": "HISTORIAL_CONSULTADO",
    "clasificacion_biologica": "ACCESO_DATOS",
    "id_activo_biologico": 294,
    "tipo_activo": null,
    "timestamp_evento": "2026-09-10 20:03:47.859993+00:00",
    "timestamp_registro": "2026-09-10 20:03:47.860014+00:00",
    "resultado": "EXITOSO",
    "descripcion": null,
    "detalle_tecnico": null,
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "8fa54a612db27024b013b5d8fb32551829683ef06fc534677f70c25021ce85a6",
    "registro_incompleto": false
  },
  {
    "id_bitacora": 1086,
    "id_evento": "e4d8d521-1506-4cb7-bcf7-40ba207d2dde",
    "rf_origen": "RF48",
    "tipo_evento": "TRANSFERENCIA_REGISTRADA",
    "clasificacion_biologica": "GESTION_OPERATIVA",
    "id_activo_biologico": 294,
    "tipo_activo": "INDIVIDUAL",
    "timestamp_evento": "2026-09-10 20:03:49.991208+00:00",
    "timestamp_registro": "2026-09-10 20:03:49.991224+00:00",
    "resultado": "EXITOSO",
    "descripcion": "Transferencia: Corral QA JE Capacidad → Corral QA JE Destino OK",
    "detalle_tecnico": {
      "motivo": "TC-M02-G79 TC-M02-133 admin ejecucion 20260910T20 individual compatible",
      "origen": 47,
      "destino": 51
    },
    "id_usuario_responsable": 1,
    "modulo_consumidor": "modulo2",
    "severidad_log": "INFO",
    "id_evento_correlacionado": null,
    "hash_integridad": "7aa54780234f085fb5175bb06a6b7959e9dcc30f7b346bef8781bf2ad7a2fdee",
    "registro_incompleto": false
  }
]
```


```sql
SELECT pid,mode,granted FROM pg_locks WHERE relation='modulo2.activos_biologicos'::regclass AND mode IN ('RowExclusiveLock','ExclusiveLock')
```

```json
[]
```


</details>


## 5. Diagnóstico y atribución

### H1 — Desajuste HTTP entre ficha y contrato

- Actores: Productor (292, 51→48) y Administrador (294, 47→51).
- Esperado por ficha: HTTP 200 y persistencia completa. Obtenido: HTTP 201 y persistencia completa; movimientos 29 y 30, auditorías 1079 y 1086.
- C1/C2/C3, tipo, estado, fecha, origen y permisos confirmados. El body contiene exactamente los cuatro campos requeridos por OpenAPI. La fecha se comparó con `current_date` del servidor.
- A1–A8: descartados mediante SELECT y GET de escenarios. A9: fecha 2026-09-10 no futura. A10: rol/permisos, sub del JWT y acceso correcto. A11: locks previos vacíos. A12: requests efectivos del JSON Newman coinciden con los IDs de BD. A13: ocupación recalculada con regla del adaptador. A14: tablas y endpoints concordantes. A15: la aserción refleja literalmente la ficha; OpenAPI exige 201. A16: 201 registrado en dos POST independientes y definido explícitamente por el router; no hay evidencia de defecto Newman.
- Causa técnica: `src/biological_assets/infrastructure/routers/activo_biologico_router.py:1071` declara `status_code=201` (véase ubicación real por búsqueda del decorador). Es coherente con el contrato vivo. No se puede decidir desde QA si debe corregirse el producto o la ficha: la discrepancia requiere resolución documental formal, sin cambiar silenciosamente el criterio de aceptación.
- Atribución: incumplimiento del criterio de la ficha / desalineación de especificación; **no demuestra fallo funcional de transferencia**. No se clasifica como error de payload ni se aprueba usando solo 2xx.
- Persistencia parcial: NO; se confirmó la operación completa para ambos actores. No se repitieron POST con curl porque producirían nuevas transferencias o un origen obsoleto. La evidencia HTTP está en los dos requests oficiales y en OpenAPI; la reproducción por curl del POST no se ejecutó.

### H2 — Hallazgo incidental: GET disponibles no filtra elegibilidad

En el SETUP, ambos actores recibieron infraestructura 1 (finca 1, Estanque) pese a que sus activos son bovinos de finca 57; también 52 (Estanque) y 53 (especie 41). Productor recibió 47 como disponible con ocupación 50/50. No se enviaron transferencias a esos destinos: no se ejecutaron casos negativos.

La reproducción con curl GET también devuelve 1, 52 y 53 para ambos actores. La infraestructura 47 dejó de estar llena después de la transferencia oficial del Administrador; esa diferencia temporal se distingue de la evidencia de SETUP.

El código local en `RegistrarTransferenciaUseCase.listar_infraestructuras_disponibles` solo llama `listar_activas(excluir_id=...)`; `InfraestructuraM09Adapter.listar_activas` filtra activo y exclusión del origen, sin finca, especie, tipo ni capacidad. Explica lo observado; no se afirma que el HEAD local sea el hash del despliegue. No se investigó ni afirmó que el POST permita transferencias entre fincas.

Este hallazgo no impidió construir los escenarios válidos y se reporta separado de G79. Atribución: defecto de filtrado del producto respecto a la selección de destinos compatibles. Categoría FLUJO / alcance de datos. Responsable: Desarrollo Backend.

### Conservación e inmutabilidad

Todos los movimientos históricos previos y registros previos de auditoría permanecieron idénticos. Los historiales API preservan todos los eventos anteriores. En los periodos de asociación se cerró solamente el periodo vigente, lo cual es el comportamiento esperado.

La lectura del catálogo de triggers encontró en movimientos un trigger de auditoría DML; no se encontró un trigger no interno que rechace cambios en las tres tablas examinadas. Esto por sí solo no demuestra que un usuario pueda modificar eventos: faltaría revisar todos los mecanismos de autorización. No se ejecutaron ataques de modificación ni se inventó una prueba de inmutabilidad absoluta. Esa garantía queda fuera de la evidencia dinámica obtenida.

## 6. Veredicto final y registro de errores

**RECHAZADO.** Cobertura 2/2 y V2–V10 correctas; V1 incumplida para ambos actores frente a la ficha recibida. No hay evidencia de pérdida de datos ni de persistencia parcial. La inmutabilidad futura no se certifica con esta ejecución.

| ID sugerido | Categoría | Severidad | Plazo máximo | Detección (Bogotá) | Fecha límite (Bogotá) | Responsable | Estado |
|---|---|---|---|---|---|---|---|
| QA-G79-H1 | HTTP_COM / especificación | Medio | 2 días hábiles | 2026-09-10 15:03:44 | 2026-09-14 15:03:44 | Desarrollo Backend + QA/Análisis para acuerdo contractual | Abierto |
| QA-G79-H2 | FLUJO / filtro de destinos | Medio | 2 días hábiles | 2026-09-10 15:01:10 | 2026-09-14 15:01:10 | Desarrollo Backend | Abierto |

Plazos calculados con jornada de lunes a viernes y exclusión del fin de semana, sin calendario adicional de feriados del proyecto. Severidad H1: impacto específico de contrato, con alternativa técnica de consumir 201; no bloquea la transferencia real. H2: selección parcial incorrecta con alternativa de validar compatibilidad y finca antes de elegir. No se confirma una brecha de escritura entre fincas.

Acción H1: acordar el código de éxito de RF-48 con QA/Análisis y alinear ficha/contrato/router según esa decisión; repetir la validación con nuevos ANTES. Acción H2: corregir filtrado de destinos y validar aislamiento de finca, C1, C2 y C3. Esta tarea QA no implementó correcciones ni envió tickets a terceros.

## 7. Artefactos y reproducción

- `../test_tc_m02_g79.json`: colección Postman, sin contraseñas ni tokens.
- `reporte_tc_m02_g79.json`: reporte Newman auténtico, con secretos redactados y evidencia complementaria bajo `qa_bd`; las estadísticas originales de Newman no se alteraron.
- `reporte_tc_m02_g79.html`: reporte Newman htmlextra, datos sensibles omitidos; incluye un resumen adicional de BD al final.
- Este informe consolida SQL y diagnóstico. No se crearon logs por consulta o por actor.

La colección contiene `00-SETUP-LECTURA`, `01-CASO-PRINCIPAL` con ambos actores y `02-DIAGNOSTICO` vacía; el diagnóstico realizado fue SELECT, curl GET y lectura de código, no requests negativos de Postman. Antes de reutilizarla deben renovarse los escenarios, fecha y SELECT: los activos ya están en destino. `password` se inyecta en un entorno privado y `bd_gate=validado` únicamente tras revisión BD fresca. En esta ejecución un hook síncrono de Newman ejecutó SELECT y validaciones antes de cada POST, y otra captura inmediatamente después. Ese hook fue una herramienta temporal de ejecución; la colección por sí sola no consulta PostgreSQL y el valor de gate no reemplaza la revisión. Las comprobaciones BD V2–V10 se evaluaron con Python sobre los snapshots y se incluyen separadas de las aserciones Newman.

## 8. Declaración de cumplimiento

- No se modificó código fuente del producto; no hubo commit, push, merge, rebase, reset ni cambio de rama.
- PostgreSQL se usó exclusivamente en modo read-only para SELECT; no se adquirieron locks de escritura para preparar el escenario.
- Preparación: cero mutaciones de datos de negocio. GET/login auditables por el servicio, según se explicó arriba.
- Exactamente dos POST oficiales de transferencia; ningún POST de reintento, preparación o diagnóstico.
- Activos independientes y legítimos por actor; orígenes reales, destinos activos de la misma finca y C1/C2/C3 verificados antes de enviar.
- No se fabricaron datos, compatibilidades, resultados ni una aprobación parcial.
- El diagnóstico no corrigió el producto ni rescató la discrepancia de aceptación.


## Anexo A. Gate, roles, contrato y diagnóstico de lectura


```json
{
  "gate": [
    {
      "current_timestamp": "2026-09-10 20:01:06.244449+00:00",
      "current_setting": "on"
    }
  ],
  "actores": [
    {
      "id_usuario": 1,
      "id_rol": 1,
      "nombre_rol": "Administrador",
      "id_finca": 34
    },
    {
      "id_usuario": 35,
      "id_rol": 2,
      "nombre_rol": "Productor",
      "id_finca": 57
    }
  ],
  "finca": [
    {
      "id_finca": 57,
      "id_usuario": 35,
      "es_activo": true
    }
  ],
  "especie": [
    {
      "id_especie": 40,
      "nombre": "Bovino Qa Je",
      "descripcion": "Especie de pruebas M02 (casos Juan Esteban). No usar en produccion.",
      "fecha_actualizacion": null,
      "fecha_creacion": "2026-06-01 08:00:00+00:00",
      "es_activo": true
    }
  ],
  "permisos_activos": [
    {
      "id_rol": 1,
      "nombre_rol": "Administrador",
      "modulo": "activos_biologicos",
      "accion": "Crear",
      "codigo_accion": "C",
      "id_permiso": 163,
      "permiso": "admin_crear_activo_biologico",
      "es_activo": true
    },
    {
      "id_rol": 1,
      "nombre_rol": "Administrador",
      "modulo": "activos_biologicos",
      "accion": "Leer",
      "codigo_accion": "R",
      "id_permiso": 164,
      "permiso": "admin_leer_activo_biologico",
      "es_activo": true
    },
    {
      "id_rol": 2,
      "nombre_rol": "Productor",
      "modulo": "activos_biologicos",
      "accion": "Crear",
      "codigo_accion": "C",
      "id_permiso": 165,
      "permiso": "prod_crear_activo_biologico",
      "es_activo": true
    },
    {
      "id_rol": 2,
      "nombre_rol": "Productor",
      "modulo": "activos_biologicos",
      "accion": "Leer",
      "codigo_accion": "R",
      "id_permiso": 166,
      "permiso": "prod_leer_activo_biologico",
      "es_activo": true
    },
    {
      "id_rol": 1,
      "nombre_rol": "Administrador",
      "modulo": "activos_biologicos",
      "accion": "Actualizar",
      "codigo_accion": "U",
      "id_permiso": 170,
      "permiso": "admin_actualizar_activo_biologico",
      "es_activo": true
    },
    {
      "id_rol": 2,
      "nombre_rol": "Productor",
      "modulo": "activos_biologicos",
      "accion": "Actualizar",
      "codigo_accion": "U",
      "id_permiso": 171,
      "permiso": "prod_actualizar_activo_biologico",
      "es_activo": true
    },
    {
      "id_rol": 1,
      "nombre_rol": "Administrador",
      "modulo": "activos_biologicos",
      "accion": "Ejecutar",
      "codigo_accion": "E",
      "id_permiso": 173,
      "permiso": "admin_ejecutar_cambio_fase",
      "es_activo": true
    },
    {
      "id_rol": 2,
      "nombre_rol": "Productor",
      "modulo": "activos_biologicos",
      "accion": "Ejecutar",
      "codigo_accion": "E",
      "id_permiso": 174,
      "permiso": "prod_ejecutar_cambio_fase",
      "es_activo": true
    },
    {
      "id_rol": 1,
      "nombre_rol": "Administrador",
      "modulo": "activos_biologicos",
      "accion": "Eliminar",
      "codigo_accion": "D",
      "id_permiso": 178,
      "permiso": "admin_desactivar_activo_biologico",
      "es_activo": true
    },
    {
      "id_rol": 2,
      "nombre_rol": "Productor",
      "modulo": "activos_biologicos",
      "accion": "Eliminar",
      "codigo_accion": "D",
      "id_permiso": 179,
      "permiso": "prod_desactivar_activo_biologico",
      "es_activo": true
    }
  ],
  "schema_body": {
    "properties": {
      "infraestructura_origen_id": {
        "type": "integer",
        "title": "Infraestructura Origen Id"
      },
      "infraestructura_destino_id": {
        "type": "integer",
        "title": "Infraestructura Destino Id"
      },
      "fecha_transferencia": {
        "type": "string",
        "format": "date",
        "title": "Fecha Transferencia"
      },
      "motivo_transferencia": {
        "type": "string",
        "title": "Motivo Transferencia"
      }
    },
    "type": "object",
    "required": [
      "infraestructura_origen_id",
      "infraestructura_destino_id",
      "fecha_transferencia",
      "motivo_transferencia"
    ],
    "title": "RegistrarTransferenciaDTO"
  },
  "respuestas_POST": [
    "201",
    "401",
    "403",
    "404",
    "409",
    "422",
    "500"
  ]
}
```


```sql
SELECT n.nspname,c.relname,t.tgname,pg_get_triggerdef(t.oid) AS definition FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='modulo2' AND c.relname IN ('movimientos','bitacora_auditoria_m02','historial_infraestructura_activo') AND NOT t.tgisinternal
```

```json
[
  {
    "nspname": "modulo2",
    "relname": "movimientos",
    "tgname": "trg_auditoria",
    "definition": "CREATE TRIGGER trg_auditoria AFTER INSERT OR DELETE OR UPDATE ON modulo2.movimientos FOR EACH ROW EXECUTE FUNCTION auditoria.fn_auditoria_dml()"
  }
]
```


```sql
SELECT id_infraestructura,id_finca,tipo,id_especie,capacidad_maxima FROM modulo9.infraestructuras WHERE id_infraestructura IN (1,47,52,53) ORDER BY 1
```

```json
[
  {
    "id_infraestructura": 1,
    "id_finca": 1,
    "tipo": "Estanque",
    "id_especie": null,
    "capacidad_maxima": null
  },
  {
    "id_infraestructura": 47,
    "id_finca": 57,
    "tipo": "Corral",
    "id_especie": 40,
    "capacidad_maxima": 50
  },
  {
    "id_infraestructura": 52,
    "id_finca": 57,
    "tipo": "Estanque",
    "id_especie": null,
    "capacidad_maxima": 100
  },
  {
    "id_infraestructura": 53,
    "id_finca": 57,
    "tipo": "Galpón",
    "id_especie": 41,
    "capacidad_maxima": 100
  }
]
```

Reproducción de lectura: `curl -H "Authorization: Bearer <token privado>" <base>/activos-biologicos/{292|294}/transferencias/disponibles`.

```json
{
  "productor": {
    "HTTP": 200,
    "curl_exit": 0,
    "destinos_incompatibles_observados": [
      {
        "id_infraestructura": 1,
        "nombre": "Estanque-01",
        "tipo": "Estanque",
        "capacidad_maxima": null,
        "id_especie": null
      },
      {
        "id_infraestructura": 52,
        "nombre": "Estanque QA JE Piscicola",
        "tipo": "Estanque",
        "capacidad_maxima": 100,
        "id_especie": null
      },
      {
        "id_infraestructura": 53,
        "nombre": "Galpon QA JE Aves",
        "tipo": "Galpón",
        "capacidad_maxima": 100,
        "id_especie": 41
      }
    ]
  },
  "admin": {
    "HTTP": 200,
    "curl_exit": 0,
    "destinos_incompatibles_observados": [
      {
        "id_infraestructura": 1,
        "nombre": "Estanque-01",
        "tipo": "Estanque",
        "capacidad_maxima": null,
        "id_especie": null
      },
      {
        "id_infraestructura": 52,
        "nombre": "Estanque QA JE Piscicola",
        "tipo": "Estanque",
        "capacidad_maxima": 100,
        "id_especie": null
      },
      {
        "id_infraestructura": 53,
        "nombre": "Galpon QA JE Aves",
        "tipo": "Galpón",
        "capacidad_maxima": 100,
        "id_especie": 41
      }
    ]
  }
}
```

### Consultas de identificaci?n y permisos

```sql
SELECT id_usuario,id_rol,nombre_rol,id_finca FROM modulo9.vw_rf25_contexto_usuario WHERE id_usuario IN (1,35);
SELECT id_finca,id_usuario,es_activo FROM modulo9.fincas WHERE id_finca=57;
SELECT * FROM modulo9.especies WHERE id_especie=40;
SELECT * FROM modulo9.vw_rf25_permisos_roles WHERE id_rol IN (1,2);
```

Resultados relevantes de estas consultas en el bloque del Anexo A; para permisos se muestra el subconjunto de activos_biologicos. Ambos roles tienen acci?n Ejecutar habilitada (permisos 173 y 174).
