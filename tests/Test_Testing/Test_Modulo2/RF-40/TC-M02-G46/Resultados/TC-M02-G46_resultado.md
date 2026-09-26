# RESULTADO — TC-M02-G46

## 0. Resumen ejecutivo

| Dimensión | Resultado |
|---|---|
| VEREDICTO | **APROBADO** |
| Cobertura de actores | COMPLETA — Productor, Veterinario e Ingeniero de campo |
| Sub-casos | 2/2 |
| Peticiones oficiales | 6/6 |
| Persistencia indebida | NO — mismos IDs antes y después; Δ=0 en cada solicitud |
| Equipo responsable de defecto | No aplica; no se detectaron defectos |

Los tres actores recibieron rechazo por fecha incoherente y por ausencia de fase activa, con precondiciones verificadas y sin creación de eventos.

## 1. Identificación y alcance

- RF: **RF-40**, CU06; sub-casos TC-M02-087 y TC-M02-088. Responsable QA: Juan Esteban.
- Ubicación de entrega: `RF-410/TC-M02/G46`, conforme a la ruta literal reiterada por el usuario. La ficha propone `tests/Test_Testing/Test_Modulo2/RF-40/TC-M02-G46`; esta diferencia de ubicación no cambia el RF evaluado.
- Fuente del procedimiento: `C:/Users/yoloh/Downloads/INSTRUCCIONES_EJECUCION_TC-M02-G46.md`.
- Rama: `qa/juan-esteban-m02`.
- HEAD: `41369ea4ab3948eacb1ab9b2d0549310e285eeae`.
- Ambiente: TEST HTTPS; `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`.
- Ejecución oficial: 2026-09-10, 09:13:26–09:13:35 UTC (04:13:26–04:13:35 America/Bogota).
- Herramientas: Postman/Newman con reporteros CLI, JSON y htmlextra; Python/psycopg2 para SELECT y autenticación/GET previos.

## 2. Gate

| Verificación | Resultado |
|---|---|
| Repositorio | origin `https://github.com/Arekkazu/sgpmp-backend.git`, coincide |
| Rama | Coincide; no se cambió |
| Árbol inicial | Archivos sin seguimiento previos en G43, G44, G45, _datos_prueba y tests/openapi.json; sin diferencias en archivos versionados |
| HTTPS | GET OpenAPI → 200, también verificado en Newman |
| PostgreSQL | SELECT 1 → 1; sesión con `default_transaction_read_only=on` y `transaction_read_only=on` |
| Contrato | POST /activos-biologicos/{id_activo}/eventos/crecimiento; respuestas 201, 400, 401, 403, 404, 422 |

No se modificaron los trabajos previos. Se observaron cambios ajenos concurrentes en carpetas G45/G47 durante la ejecución; no forman parte de esta entrega.

### Correspondencias con el contrato vivo

La ficha denomina `fecha_evento` al dato; el DTO real acepta **`fecha` con formato date-time**. Se envió `fecha=2026-08-10T10:00:00Z` para conservar exactamente el día oficial. Enviar una propiedad desconocida `fecha_evento` no demostraría la validación temporal y por eso se utilizó el campo contractual, dejando explícita la correspondencia.

La ficha expresa `estado_fase=ACTIVA`; el esquema real representa la condición mediante **`modulo2.gestiones_fases.es_activa=true`**. Se contaron todas las fases con ese valor. Los activos del caso 088 no tenían ninguna fila de fase.

Campos obligatorios: tipo_medicion, valor_medicion, unidad_medida. El DTO no enumera combinaciones; los registros existentes de la misma especie y de los propios activos temporales confirman PESO / 250 / kg. Todos los recursos son INDIVIDUAL; se omite tipo_agregacion. No se fija un HTTP literal en la ficha: el 422 observado está declarado por OpenAPI.

## 3. Revisión previa de solo lectura

La inspección comenzó en BD, antes de cualquier login o POST. Se descubrieron tablas y columnas con information_schema; una búsqueda inicial restringida a public devolvió cero tablas y se amplió a todos los esquemas. Las tablas relevantes están en modulo1, modulo2 y modulo9.

**Escrituras de datos de negocio durante SETUP: 0.** Solo SELECT, GET y los tres logins expresamente permitidos. No se afirma ausencia de auditoría interna de sesiones generada por el servicio de autenticación.

### Actores y acceso legítimo

| Actor | Usuario | Correo vigente | Login | JWT sub | GET de recursos |
|---|---|---|---|---|---|
| Productor | 35 | m2m.nuevo@ejemplo.com | 200 | 35 | 291: 200, 297: 200 |
| Veterinario | 3 | juan.carlos.qa133@sgpmp-test.com | 200 | 3 | 325: 200, 330: 200 |
| Ingeniero | 4 | ingeniero@pecuaria.co | 200 | 4 | 332: 200, 331: 200 |

El correo de Veterinario indicado en la ficha, `juan.carlos@email.com`, no aparece en la consulta actual. Se empleó la cuenta existente del mismo rol, usuario 3, `juan.carlos.qa133@sgpmp-test.com`, sin modificarla. El login fue exitoso y su identidad se comprobó mediante el sub del token. La sección 7.5 permite buscar usuarios existentes del mismo rol. Esta deriva documental no bloquea la cobertura.

| Actor | 087 activo | Estado / fase | Último crecimiento UTC | 088 activo | Estado / fases | Finca / infraestructura |
|---|---|---|---|---|---|---|
| Productor | 291 | ACTIVO / 1 | 2026-08-20 10:00 | 297 | ACTIVO / 0 | 57 / 48 |
| Veterinario | 325 | ACTIVO / 1 | 2026-08-20 10:00 | 330 | ACTIVO / 0 | 64 / 60 |
| Ingeniero de campo | 332 | ACTIVO / 1 | 2026-08-20 10:00 | 331 | ACTIVO / 0 | 65 / 61 |

La pertenencia se confirmó por infraestructura → finca → contexto del usuario, y por GET 200 con el token de cada actor. Los seis activos son especie 40, INDIVIDUAL, con inicio de ciclo 2026-06-01; la fecha temporal negativa es posterior al inicio del ciclo y anterior al último crecimiento.

| Inventario | Resultado |
|---|---|
| D1 | 259 activos consultados; 208 en estado ACTIVO |
| D2 | 39 activos con fase activa |
| D3 | 220 activos sin fase activa |
| D4 | 14 activos con eventos de crecimiento |
| D5 | Máximos por activo en evidencia SQL inferior |
| D6 | Sí: 291, 325, 332 |
| D7 | Sí: 297, 330, 331 |
| D8 | Tres cuentas autenticadas; identificadores 35, 3, 4; correo de Veterinario actualizado |
| D9/D10 | Fincas 57, 64 y 65; pertenencia BD y GET 200 |
| D11 | PESO, 250, kg; INDIVIDUAL; fechas posteriores al inicio del ciclo |

## 4. Payloads utilizados

Los únicos POST de negocio fueron las seis solicitudes oficiales. El cuerpo exacto de cada una queda en el JSON Newman.

```json
{
  "tipo_medicion": "PESO",
  "valor_medicion": 250,
  "unidad_medida": "kg",
  "fecha": "2026-08-10T10:00:00Z",
  "descripcion": "TC-M02-087 <actor>"
}
```

```json
{
  "tipo_medicion": "PESO",
  "valor_medicion": 250,
  "unidad_medida": "kg",
  "fecha": "2026-09-10T08:00:00Z",
  "descripcion": "TC-M02-088 <actor>"
}
```

## 5. TC-M02-087 — fecha anterior

| Actor / recurso | HTTP | Código | Persistencia | Resultado |
|---|---|---|---|---|
| TC-M02-087 Productor activo 291 | 422 | FECHA_INCOHERENTE | NO; Δ=0 | APROBADO |
| TC-M02-087 Veterinario activo 325 | 422 | FECHA_INCOHERENTE | NO; Δ=0 | APROBADO |
| TC-M02-087 Ingeniero activo 332 | 422 | FECHA_INCOHERENTE | NO; Δ=0 | APROBADO |

Respuesta real representativa (el mismo código y mensaje para los tres actores):

```json
{
  "error_code": "FECHA_INCOHERENTE",
  "message": "La fecha del evento es inválida o inconsistente con el historial.",
  "fields": [],
  "timestamp": "2026-09-10T09:13:26.950390+00:00"
}
```

## 6. TC-M02-088 — sin fase activa

| Actor / recurso | HTTP | Código | Persistencia | Resultado |
|---|---|---|---|---|
| TC-M02-088 Productor activo 297 | 422 | SIN_FASE_ACTIVA | NO; Δ=0 | APROBADO |
| TC-M02-088 Veterinario activo 330 | 422 | SIN_FASE_ACTIVA | NO; Δ=0 | APROBADO |
| TC-M02-088 Ingeniero activo 331 | 422 | SIN_FASE_ACTIVA | NO; Δ=0 | APROBADO |

Respuesta real representativa (el mismo código y mensaje para los tres actores):

```json
{
  "error_code": "SIN_FASE_ACTIVA",
  "message": "El activo no tiene una fase productiva activa. Asocie el activo a un ciclo productivo antes de registrar eventos de crecimiento.",
  "fields": [],
  "timestamp": "2026-09-10T09:13:28.876468+00:00"
}
```

## 7. Verificación BD

SELECT ejecutado inmediatamente antes de cada solicitud y después de su respuesta. La comparación incluye todos los eventos_activos del recurso, no solo la vista de crecimiento, para detectar también eventos incompletos.

| Petición | IDs antes | IDs después | Conteos | Δ | Tiempo antes UTC | Tiempo después UTC |
|---|---|---|---|---|---|---|
| TC-M02-087 Productor activo 291 | [223] | [223] | 1 → 1 | 0 | 2026-09-10 09:13:27.116102+00:00 | 2026-09-10 09:13:28.246585+00:00 |
| TC-M02-088 Productor activo 297 | [] | [] | 0 → 0 | 0 | 2026-09-10 09:13:29.135537+00:00 | 2026-09-10 09:13:30.080502+00:00 |
| TC-M02-087 Veterinario activo 325 | [239] | [239] | 1 → 1 | 0 | 2026-09-10 09:13:30.928395+00:00 | 2026-09-10 09:13:31.795466+00:00 |
| TC-M02-088 Veterinario activo 330 | [] | [] | 0 → 0 | 0 | 2026-09-10 09:13:32.631912+00:00 | 2026-09-10 09:13:33.560522+00:00 |
| TC-M02-087 Ingeniero activo 332 | [240] | [240] | 1 → 1 | 0 | 2026-09-10 09:13:34.416860+00:00 | 2026-09-10 09:13:35.295508+00:00 |
| TC-M02-088 Ingeniero activo 331 | [] | [] | 0 → 0 | 0 | 2026-09-10 09:13:36.136090+00:00 | 2026-09-10 09:13:37.043731+00:00 |

```sql
SELECT a.id_activo_biologico,s.nombre,a.tipo,a.fecha_inicio_ciclo,(SELECT count(*) FROM modulo2.gestiones_fases f WHERE f.id_activo_biologico=a.id_activo_biologico AND es_activa),array(SELECT id_eventos FROM modulo2.eventos_activos e WHERE e.id_activo_biologico=a.id_activo_biologico ORDER BY id_eventos),(SELECT max(fecha) FROM modulo2.vw_rf46_eventos_crecimiento e WHERE e.id_activo_biologico=a.id_activo_biologico) FROM modulo2.activos_biologicos a JOIN modulo2.estados_activos_biologicos s ON s.id_estado_activo_biologico=a.id_estado WHERE a.id_activo_biologico=ANY(ARRAY[291,297,325,330,332,331]) ORDER BY 1;
```

Columnas: activo, estado, tipo, inicio_ciclo, número de fases activas, IDs de todos los eventos, máximo de crecimiento. En las doce consultas, las filas de los seis recursos permanecieron iguales:

```json
[
  [
    291,
    "ACTIVO",
    "INDIVIDUAL",
    "2026-06-01",
    1,
    [
      223
    ],
    "2026-08-20 10:00:00+00:00"
  ],
  [
    297,
    "ACTIVO",
    "INDIVIDUAL",
    "2026-06-01",
    0,
    [],
    null
  ],
  [
    325,
    "ACTIVO",
    "INDIVIDUAL",
    "2026-06-01",
    1,
    [
      239
    ],
    "2026-08-20 10:00:00+00:00"
  ],
  [
    330,
    "ACTIVO",
    "INDIVIDUAL",
    "2026-06-01",
    0,
    [],
    null
  ],
  [
    331,
    "ACTIVO",
    "INDIVIDUAL",
    "2026-06-01",
    0,
    [],
    null
  ],
  [
    332,
    "ACTIVO",
    "INDIVIDUAL",
    "2026-06-01",
    1,
    [
      240
    ],
    "2026-08-20 10:00:00+00:00"
  ]
]
```

### SELECT de inventario y resultados

```sql
SELECT current_timestamp,current_setting('transaction_read_only'),current_setting('TimeZone');
```

| current_timestamp | current_setting | current_setting |
|---|---|---|
| 2026-09-10 09:11:08.838535+00:00 | on | Etc/UTC |

```sql
SELECT a.id_activo_biologico,a.identificador,a.tipo,s.nombre AS estado,a.id_usuario,a.id_infraestructura,a.fecha_inicio_ciclo,(SELECT count(*) FROM modulo2.gestiones_fases f WHERE f.id_activo_biologico=a.id_activo_biologico AND f.es_activa) AS fases_activas,count(e.id_eventos) AS eventos,max(e.fecha) AS ultimo_evento FROM modulo2.activos_biologicos a JOIN modulo2.estados_activos_biologicos s ON s.id_estado_activo_biologico=a.id_estado LEFT JOIN modulo2.vw_rf46_eventos_crecimiento e ON e.id_activo_biologico=a.id_activo_biologico GROUP BY a.id_activo_biologico,s.nombre ORDER BY a.id_activo_biologico;
```

| id_activo_biologico | identificador | tipo | estado | id_usuario | id_infraestructura | fecha_inicio_ciclo | fases_activas | eventos | ultimo_evento |
|---|---|---|---|---|---|---|---|---|---|
| 1 | BOV-001 | INDIVIDUAL | ACTIVO | 1 | 2 | — | 0 | 4 | 2026-07-28 10:00:00+00:00 |
| 2 | BOV-002 | INDIVIDUAL | INACTIVO | 1 | 2 | — | 1 | 3 | 2026-05-04 00:44:34.715686+00:00 |
| 3 | BOV-003 | INDIVIDUAL | BAJA | 1 | 4 | — | 0 | 0 | — |
| 4 | BOV-004 | INDIVIDUAL | INACTIVO | 2 | 1 | — | 1 | 0 | — |
| 5 | BOV-0852 | INDIVIDUAL | ACTIVO | 2 | 1 | — | 1 | 8 | 2026-09-09 20:20:00+00:00 |
| 6 | — | POBLACIONAL | CERRADO | 1 | 3 | — | 0 | 1 | 2024-03-15 07:00:00+00:00 |
| 7 | — | POBLACIONAL | CERRADO | 2 | 3 | — | 0 | 0 | — |
| 8 | — | POBLACIONAL | CERRADO | 1 | 4 | — | 1 | 0 | — |
| 9 | — | POBLACIONAL | ACTIVO | 2 | 4 | — | 0 | 0 | — |
| 10 | BOV-006 | INDIVIDUAL | BAJA | 1 | 1 | — | 1 | 0 | — |
| 12 | BOV-001-2025 | INDIVIDUAL | CERRADO | 5 | 1 | — | 0 | 0 | — |
| 19 | ARETE-TEST-01 | INDIVIDUAL | ACTIVO | 1 | 1 | — | 0 | 0 | — |
| 20 | — | POBLACIONAL | ACTIVO | 1 | 1 | — | 0 | 0 | — |
| 36 | ABC-123 | INDIVIDUAL | ACTIVO | 1 | 1 | — | 0 | 0 | — |
| 38 | BOV-001-2026 | INDIVIDUAL | ACTIVO | 5 | 1 | — | 0 | 0 | — |
| 45 | — | POBLACIONAL | ACTIVO | 5 | 2 | — | 0 | 0 | — |
| 46 | A-001 | INDIVIDUAL | ACTIVO | 1 | 1 | — | 0 | 0 | — |
| 51 | TRU-001 | INDIVIDUAL | ACTIVO | 1 | 1 | 2026-01-15 | 0 | 0 | — |
| 53 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-03-01 | 0 | 0 | — |
| 57 | TEST-GESTOR-ACTIVO-1 | INDIVIDUAL | ACTIVO | 30 | 2 | 2026-01-01 | 0 | 0 | — |
| 58 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-04 | 0 | 0 | — |
| 59 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-04 | 0 | 0 | — |
| 60 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-04 | 0 | 0 | — |
| 61 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-04 | 0 | 0 | — |
| 62 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-05 | 0 | 0 | — |
| 63 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-05 | 0 | 0 | — |
| 64 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-05 | 0 | 0 | — |
| 65 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-05 | 0 | 0 | — |
| 66 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-05 | 0 | 0 | — |
| 67 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-05 | 0 | 0 | — |
| 68 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-09-05 | 0 | 0 | — |
| 69 | — | POBLACIONAL | ACTIVO | 2 | 1 | 2026-09-05 | 0 | 0 | — |
| 70 | — | POBLACIONAL | ACTIVO | 2 | 1 | 2026-09-05 | 0 | 0 | — |
| 71 | — | POBLACIONAL | ACTIVO | 2 | 1 | 2026-09-05 | 0 | 0 | — |
| 72 | — | POBLACIONAL | ACTIVO | 2 | 1 | 2026-09-05 | 0 | 0 | — |
| 73 | — | POBLACIONAL | ACTIVO | 2 | 1 | 2026-09-05 | 0 | 0 | — |
| 74 | — | POBLACIONAL | ACTIVO | 2 | 1 | 2026-09-05 | 0 | 0 | — |
| 75 | — | POBLACIONAL | BAJA | 1 | 8 | 2026-09-08 | 0 | 0 | — |
| 76 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 77 | — | POBLACIONAL | BAJA | 1 | 8 | 2026-09-08 | 0 | 0 | — |
| 78 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 79 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 80 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 81 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 82 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 83 | — | POBLACIONAL | ACTIVO | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 84 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 85 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 86 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 87 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 88 | — | POBLACIONAL | ACTIVO | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 89 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 90 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 91 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 92 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 93 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 94 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 95 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 96 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 97 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 98 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 99 | — | POBLACIONAL | ACTIVO | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 100 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 101 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 102 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 103 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 104 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 105 | — | POBLACIONAL | BAJA | 1 | 3 | 2026-09-08 | 0 | 0 | — |
| 108 | MADRE-G53-1788880748 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 109 | PADRE-G53-1788880748 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 110 | MADRE-G53-1788883766399 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 111 | PADRE-G53-1788883766399 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 112 | MADRE-G53-1788883784112 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 113 | PADRE-G53-1788883784112 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 114 | MADRE-G53-1788883796373 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 115 | PADRE-G53-1788883796373 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 116 | MADRE-G53-1788883860908 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 117 | PADRE-G53-1788883860908 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 118 | MADRE-G53-1788883874980 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 119 | PADRE-G53-1788883874980 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 120 | MADRE-G53-1788883887192 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 121 | PADRE-G53-1788883887192 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 122 | MADRE-G53-1788915920285 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 123 | PADRE-G53-1788915920285 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 124 | HEMBRA-G54-1788916672286 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 125 | — | POBLACIONAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 126 | HEMBRA-G55-1788917313347 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 127 | MADRE-G57-1788918275792 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 128 | PADRE-G57-1788918275792 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 129 | — | POBLACIONAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 130 | — | POBLACIONAL | ACTIVO | 1 | 1 | 2026-01-01 | 1 | 16 | 2026-09-09 20:50:00+00:00 |
| 131 | MADRE-G58-1788921090136 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 132 | MADRE-G58-1788921115838 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 133 | PBAJA-G58-1788921115838 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 134 | PADRE-G58-1788921115838 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 135 | H1-G59-1788921379533 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 136 | H2-G59-1788921379533 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 137 | H3-G59-1788921379533 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 138 | H1-G59-1788923979567 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 139 | H2-G59-1788923979567 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 140 | MADRE-G60-1788925209109 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 141 | PADRE-G60-1788925209109 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 142 | PROBE-1788926784234 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 143 | — | POBLACIONAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 144 | SAN-1788926923141 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 145 | — | POBLACIONAL | ACTIVO | 2 | 6 | 2026-09-08 | 0 | 0 | — |
| 146 | — | POBLACIONAL | ACTIVO | 2 | 6 | 2026-09-08 | 0 | 0 | — |
| 147 | — | POBLACIONAL | ACTIVO | 2 | 6 | 2026-09-08 | 0 | 0 | — |
| 149 | — | POBLACIONAL | ACTIVO | 2 | 6 | 2026-09-08 | 0 | 0 | — |
| 150 | TCM02-IND-1788940523267 | INDIVIDUAL | ACTIVO | 2 | 6 | 2026-09-08 | 0 | 0 | — |
| 151 | — | POBLACIONAL | ACTIVO | 2 | 6 | 2026-09-08 | 0 | 0 | — |
| 152 | CACHAMA-EXPLORE-001 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 153 | TIL-EXPLORE-FASE-001 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-08-01 | 0 | 0 | — |
| 154 | CG106-1788975551806 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 155 | CG112-1788975551806 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 156 | — | POBLACIONAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 157 | CG106-1788975890309 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 158 | CG112-1788975890309 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 159 | CG106-1788976377689 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 160 | CG112-1788976377689 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 161 | CG62-EXPL | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 162 | CG62-1788976862662 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 163 | CG63-1788979203482 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 164 | CG64-1788979672094 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 165 | TCM02-G13-015-1788980162 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 166 | — | POBLACIONAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 167 | TCM02-G13-021-1788980163 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 168 | CG65-1788980202006 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 169 | TCM02-G13-015-1788980669 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 170 | — | POBLACIONAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 171 | TCM02-G13-021-1788980670 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 172 | TCM02-G13-015-1788980746 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 173 | — | POBLACIONAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 174 | TCM02-G13-021-1788980747 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 175 | MADRE-G53-1788985099800 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 176 | PADRE-G53-1788985099800 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 177 | HEMBRA-G54-1788985437288 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 178 | MADRE-G60-1788985652891 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 179 | PADRE-G60-1788985652891 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 180 | TRF-1788986283664 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 181 | TRF-1788986490818 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-09-09 | 0 | 0 | — |
| 182 | — | POBLACIONAL | ACTIVO | 2 | 6 | 2026-09-09 | 0 | 0 | — |
| 183 | X1'OR'1 | INDIVIDUAL | ACTIVO | 2 | 6 | 2026-09-09 | 0 | 0 | — |
| 184 | X1'OR'1=1 | INDIVIDUAL | ACTIVO | 2 | 6 | 2026-09-09 | 0 | 0 | — |
| 185 | X1'-- | INDIVIDUAL | ACTIVO | 2 | 6 | 2026-09-09 | 0 | 0 | — |
| 186 | X1';DROP | INDIVIDUAL | ACTIVO | 2 | 6 | 2026-09-09 | 0 | 0 | — |
| 187 | X1<>' | INDIVIDUAL | ACTIVO | 2 | 6 | 2026-09-09 | 0 | 0 | — |
| 188 | X1$ne | INDIVIDUAL | ACTIVO | 2 | 6 | 2026-09-09 | 0 | 0 | — |
| 189 | X1$gt | INDIVIDUAL | ACTIVO | 2 | 6 | 2026-09-09 | 0 | 0 | — |
| 190 | TRF-SC-1788992405 | INDIVIDUAL | ACTIVO | 2 | 6 | 2026-09-09 | 0 | 0 | — |
| 191 | QA-G20-1788993931486 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-09 | 0 | 0 | — |
| 192 | QA-G20-CY-1788994009831 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-09 | 0 | 0 | — |
| 193 | QA-G21-PROBE-1788994482 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-09 | 0 | 0 | — |
| 194 | QA-G21-1788994538251 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-09 | 0 | 0 | — |
| 195 | QA-G22-PROBE-1788994728 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-09 | 0 | 0 | — |
| 196 | QA-G22-DIAG-1788994815 | INDIVIDUAL | EN_TRATAMIENTO | 47 | 6 | 2026-09-09 | 0 | 0 | — |
| 197 | QA-G22-1788995034825 | INDIVIDUAL | EN_TRATAMIENTO | 47 | 6 | 2026-09-09 | 0 | 0 | — |
| 198 | QA-G22-1788995207698 | INDIVIDUAL | EN_TRATAMIENTO | 47 | 6 | 2026-09-09 | 0 | 0 | — |
| 199 | G23A-97441 | INDIVIDUAL | ACTIVO | 47 | 14 | 2026-09-09 | 0 | 0 | — |
| 200 | G23B-98252 | INDIVIDUAL | ACTIVO | 47 | 15 | 2026-09-09 | 0 | 0 | — |
| 201 | G33-1789000204391 | INDIVIDUAL | ACTIVO | 47 | 1 | 2026-09-10 | 0 | 0 | — |
| 202 | G34A-00873 | INDIVIDUAL | ACTIVO | 47 | 1 | 2026-09-09 | 0 | 0 | — |
| 203 | G34B-00891 | INDIVIDUAL | ACTIVO | 47 | 1 | 2026-09-09 | 0 | 0 | — |
| 204 | G34A-1789001060151 | INDIVIDUAL | ACTIVO | 47 | 1 | 2026-09-10 | 0 | 0 | — |
| 205 | G34B-1789001060982 | INDIVIDUAL | ACTIVO | 47 | 1 | 2026-09-10 | 0 | 0 | — |
| 206 | G34C-02519 | INDIVIDUAL | ACTIVO | 47 | 1 | 2026-09-10 | 0 | 0 | — |
| 207 | G39-02987 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 208 | G39-1789003055263 | INDIVIDUAL | AISLADO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 209 | — | POBLACIONAL | AISLADO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 210 | — | POBLACIONAL | AISLADO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 211 | — | POBLACIONAL | AISLADO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 212 | — | POBLACIONAL | AISLADO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 213 | G40-04447 | INDIVIDUAL | CERRADO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 214 | G40B-04513 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 215 | G40B-1789004586056 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 216 | G41A-05105 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 217 | — | POBLACIONAL | ACTIVO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 218 | G41A-1789005168826 | INDIVIDUAL | ACTIVO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 219 | — | POBLACIONAL | ACTIVO | 47 | 6 | 2026-09-10 | 0 | 0 | — |
| 221 | QA-G05-SETUP-1789005437 | INDIVIDUAL | ACTIVO | 47 | 17 | 2026-01-01 | 0 | 0 | — |
| 222 | G78-06591 | INDIVIDUAL | ACTIVO | 47 | 18 | 2026-09-10 | 0 | 0 | — |
| 223 | — | POBLACIONAL | ACTIVO | 1 | 16 | 2026-09-09 | 0 | 0 | — |
| 224 | QA-G06-Unicode-1789007227 | INDIVIDUAL | ACTIVO | 47 | 19 | 2026-01-01 | 0 | 0 | — |
| 225 | — | POBLACIONAL | ACTIVO | 47 | 19 | 2026-01-01 | 0 | 0 | — |
| 226 | QA-G06-Unicode-1789007672 | INDIVIDUAL | ACTIVO | 47 | 20 | 2026-01-01 | 0 | 0 | — |
| 227 | — | POBLACIONAL | ACTIVO | 47 | 20 | 2026-01-01 | 0 | 0 | — |
| 228 | CG106-1789009331152 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 229 | CG112-1789009331152 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 230 | CG62-1789009482960 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 231 | QA-G35-Activo-1789009490 | INDIVIDUAL | ACTIVO | 47 | 21 | 2026-01-01 | 0 | 0 | — |
| 232 | CG65-1789009560111 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 233 | CG71-EXPL | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 234 | CG71-1789010025362 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 235 | QA-G36-ActivoA-1789010065 | INDIVIDUAL | ACTIVO | 47 | 22 | 2026-01-01 | 0 | 0 | — |
| 236 | QA-G36-ActivoB-1789010065 | INDIVIDUAL | ACTIVO | 47 | 22 | 2026-01-01 | 0 | 0 | — |
| 237 | MADRE-G98-1789010200977 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 238 | PADRE1-G98-1789010200977 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 239 | PADRE2-G98-1789010200977 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 240 | CG102-EXPL | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 241 | CG102-1789010454613 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 242 | CG102-1789011596586 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 243 | QA-G37-Activo-1789011841 | INDIVIDUAL | EN_TRATAMIENTO | 47 | 23 | 2026-01-01 | 0 | 0 | — |
| 244 | TIL-G107-EXPL | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 245 | CADENA-1789011991628 | INDIVIDUAL | ACTIVO | 1 | 6 | 2026-08-01 | 0 | 0 | — |
| 246 | CA10-1789011991628 | INDIVIDUAL | ACTIVO | 1 | 3 | 2026-01-15 | 0 | 0 | — |
| 247 | QA-G38-Activo-1789013214 | INDIVIDUAL | ACTIVO | 47 | 24 | 2026-01-01 | 0 | 0 | — |
| 248 | QA-G38-Activo-1789013694 | INDIVIDUAL | ACTIVO | 47 | 25 | 2026-01-01 | 0 | 0 | — |
| 249 | QA-G49-Activo-1789014310 | INDIVIDUAL | ACTIVO | 47 | 26 | 2026-01-01 | 0 | 0 | — |
| 250 | QA-G50-Activo-1789016141 | INDIVIDUAL | ACTIVO | 47 | 27 | 2026-01-01 | 0 | 0 | — |
| 251 | QA-G51-Activo-1789016821 | INDIVIDUAL | ACTIVO | 47 | 28 | 2026-01-01 | 0 | 0 | — |
| 252 | QA-G52-Activo-1789017395 | INDIVIDUAL | ACTIVO | 47 | 29 | 2026-01-01 | 0 | 0 | — |
| 253 | QA-DIAG-Activo-1789018110 | INDIVIDUAL | ACTIVO | 47 | 30 | 2026-01-01 | 0 | 0 | — |
| 254 | QA-G66-ActivoA-1789019155 | INDIVIDUAL | ACTIVO | 47 | 31 | 2026-01-01 | 0 | 0 | — |
| 255 | QA-G66-ActivoB-1789019157 | INDIVIDUAL | ACTIVO | 47 | 31 | 2026-01-01 | 0 | 0 | — |
| 256 | QA-G66B-Activo-1789019607 | INDIVIDUAL | ACTIVO | 47 | 39 | 2026-01-01 | 0 | 0 | — |
| 279 | QAJE-CREC-OK | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 4 | 2026-09-10 08:33:36+00:00 |
| 280 | QAJE-IND-OUTLIER | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 2 | 2026-08-02 10:00:00+00:00 |
| 281 | — | POBLACIONAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 282 | QAJE-CREC-XSS | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 283 | — | POBLACIONAL | ACTIVO | 1 | 47 | 2026-06-01 | 1 | 0 | — |
| 284 | QAJE-TRF-NOACT | INDIVIDUAL | INACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 285 | QAJE-IND-1MED | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 1 | 2026-07-20 10:00:00+00:00 |
| 286 | QAJE-IND-BAJA | INDIVIDUAL | BAJA | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 287 | QAJE-TRF-SINORIG | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 288 | QAJE-CREC-CERRADO | INDIVIDUAL | CERRADO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 289 | QAJE-DAT-INFRAINACT | INDIVIDUAL | ACTIVO | 1 | 49 | 2026-06-01 | 1 | 0 | — |
| 290 | QAJE-TRF-CONC | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 291 | QAJE-CREC-FECHA | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 1 | 2026-08-20 10:00:00+00:00 |
| 292 | QAJE-TRF-OK | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 293 | QAJE-CREC-VAL | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 294 | QAJE-TRF-REGLAS | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 295 | QAJE-DAT-COMPL | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 2 | 2026-08-15 10:00:00+00:00 |
| 296 | — | POBLACIONAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 297 | QAJE-CREC-SINFASE | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 0 | 0 | — |
| 298 | QAJE-DAT-VACIO | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 299 | QAJE-IND-MACHO | INDIVIDUAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 300 | — | POBLACIONAL | ACTIVO | 1 | 48 | 2026-06-01 | 1 | 0 | — |
| 301 | QA-G66-ActivoA-1789020509 | INDIVIDUAL | ACTIVO | 47 | 54 | 2026-01-01 | 0 | 0 | — |
| 302 | QA-G66-ActivoB-1789020510 | INDIVIDUAL | ACTIVO | 47 | 54 | 2026-01-01 | 0 | 0 | — |
| 303 | QA-G66-ActivoA-1789020553 | INDIVIDUAL | ACTIVO | 47 | 55 | 2026-01-01 | 0 | 0 | — |
| 304 | QA-G66-ActivoB-1789020555 | INDIVIDUAL | ACTIVO | 47 | 55 | 2026-01-01 | 0 | 0 | — |
| 305 | QA-G66-ActivoB-1789021069 | INDIVIDUAL | ACTIVO | 47 | 56 | 2026-01-01 | 0 | 0 | — |
| 306 | QA-G66-ActivoA-1789021070 | INDIVIDUAL | ACTIVO | 47 | 56 | 2026-01-01 | 0 | 0 | — |
| 307 | QA-G66-ActivoB-1789021468 | INDIVIDUAL | ACTIVO | 47 | 57 | 2026-01-01 | 0 | 0 | — |
| 308 | QA-G66-ActivoA-1789021468 | INDIVIDUAL | ACTIVO | 47 | 57 | 2026-01-01 | 0 | 0 | — |
| 311 | QAJE-CREC-OK-VET | INDIVIDUAL | ACTIVO | 1 | 60 | 2026-06-01 | 1 | 2 | 2026-09-10 08:33:36+00:00 |
| 312 | QAJE-CREC-OK-ING | INDIVIDUAL | ACTIVO | 1 | 61 | 2026-06-01 | 1 | 4 | 2026-09-10 08:33:36+00:00 |
| 325 | QAJE-RF40-FECHA-VET | INDIVIDUAL | ACTIVO | 1 | 60 | 2026-06-01 | 1 | 1 | 2026-08-20 10:00:00+00:00 |
| 326 | QAJE-RF40-VAL-VET | INDIVIDUAL | ACTIVO | 1 | 60 | 2026-06-01 | 1 | 0 | — |
| 327 | QAJE-RF40-XSS-VET | INDIVIDUAL | ACTIVO | 1 | 60 | 2026-06-01 | 1 | 0 | — |
| 328 | — | POBLACIONAL | ACTIVO | 1 | 60 | 2026-06-01 | 1 | 0 | — |
| 329 | QAJE-RF40-CERRADO-VET | INDIVIDUAL | CERRADO | 1 | 60 | 2026-06-01 | 1 | 0 | — |
| 330 | QAJE-RF40-SINFASE-VET | INDIVIDUAL | ACTIVO | 1 | 60 | 2026-06-01 | 0 | 0 | — |
| 331 | QAJE-RF40-SINFASE-ING | INDIVIDUAL | ACTIVO | 1 | 61 | 2026-06-01 | 0 | 0 | — |
| 332 | QAJE-RF40-FECHA-ING | INDIVIDUAL | ACTIVO | 1 | 61 | 2026-06-01 | 1 | 1 | 2026-08-20 10:00:00+00:00 |
| 333 | QAJE-RF40-XSS-ING | INDIVIDUAL | ACTIVO | 1 | 61 | 2026-06-01 | 1 | 0 | — |
| 334 | — | POBLACIONAL | ACTIVO | 1 | 61 | 2026-06-01 | 1 | 0 | — |
| 335 | QAJE-RF40-VAL-ING | INDIVIDUAL | ACTIVO | 1 | 61 | 2026-06-01 | 1 | 0 | — |
| 336 | QAJE-RF40-CERRADO-ING | INDIVIDUAL | CERRADO | 1 | 61 | 2026-06-01 | 1 | 0 | — |

```sql
SELECT u.id_usuario,u.correo_electronico,u.id_rol,c.id_estado_cuenta,c.tiene_correo_verificado,v.nombre_rol,v.id_finca,v.finca_activa_estado FROM modulo1.usuarios u LEFT JOIN modulo1.cuentas_usuarios c USING(id_usuario) LEFT JOIN modulo9.vw_rf25_contexto_usuario v USING(id_usuario) WHERE u.correo_electronico IN ('m2m.nuevo@ejemplo.com','juan.carlos@email.com','ingeniero@pecuaria.co');
```

| id_usuario | correo_electronico | id_rol | id_estado_cuenta | tiene_correo_verificado | nombre_rol | id_finca | finca_activa_estado |
|---|---|---|---|---|---|---|---|
| 35 | m2m.nuevo@ejemplo.com | 2 | 2 | True | Productor | 57 | True |
| 4 | ingeniero@pecuaria.co | 4 | 2 | True | Ingeniero de Campo | 65 | True |

```sql
SELECT a.id_activo_biologico,a.id_especie,i.id_infraestructura,i.id_finca,i.es_activo,v.id_usuario,v.nombre_rol FROM modulo2.activos_biologicos a JOIN modulo9.infraestructuras i USING(id_infraestructura) JOIN modulo9.vw_rf25_contexto_usuario v USING(id_finca) WHERE a.id_activo_biologico IN (291,297,325,330,332,331) ORDER BY 1,5;
```

| id_activo_biologico | id_especie | id_infraestructura | id_finca | es_activo | id_usuario | nombre_rol |
|---|---|---|---|---|---|---|
| 291 | 40 | 48 | 57 | True | 35 | Productor |
| 297 | 40 | 48 | 57 | True | 35 | Productor |
| 325 | 40 | 60 | 64 | True | 3 | Veterinario |
| 330 | 40 | 60 | 64 | True | 3 | Veterinario |
| 331 | 40 | 61 | 65 | True | 4 | Ingeniero de Campo |
| 332 | 40 | 61 | 65 | True | 4 | Ingeniero de Campo |

```sql
SELECT id_activo_biologico,id_eventos,fecha,tipo_medicion,valor_medicion,unidad_medida FROM modulo2.vw_rf46_eventos_crecimiento WHERE id_activo_biologico IN (291,297,325,330,332,331) ORDER BY 1,2;
```

| id_activo_biologico | id_eventos | fecha | tipo_medicion | valor_medicion | unidad_medida |
|---|---|---|---|---|---|
| 291 | 223 | 2026-08-20 10:00:00+00:00 | PESO | 250.00 | kg |
| 325 | 239 | 2026-08-20 10:00:00+00:00 | PESO | 250.00 | kg |
| 332 | 240 | 2026-08-20 10:00:00+00:00 | PESO | 250.00 | kg |

```sql
SELECT id_activo_biologico,id_gestion_fases,es_activa,fecha_inicio,fecha_finalizacion FROM modulo2.gestiones_fases WHERE id_activo_biologico IN (291,297,325,330,332,331) ORDER BY 1;
```

| id_activo_biologico | id_gestion_fases | es_activa | fecha_inicio | fecha_finalizacion |
|---|---|---|---|---|
| 291 | 70 | True | 2026-06-01 08:00:00+00:00 | — |
| 325 | 93 | True | 2026-06-01 08:00:00+00:00 | — |
| 332 | 98 | True | 2026-06-01 08:00:00+00:00 | — |

```sql
SELECT pg_get_viewdef('modulo2.vw_rf46_eventos_crecimiento'::regclass,true);
```

```sql
 SELECT 'CRECIMIENTO'::text AS categoria,
    ea.id_eventos,
    ea.fecha,
    ea.id_activo_biologico,
    ab.identificador,
    ea.descripcion,
    COALESCE(concat_ws(' '::text, u.nombre, u.apellidos), 'Sin usuario'::text) AS usuario,
    'modulo2'::text AS modulo_origen,
    ec.tipo_medicion,
    ec.valor_medicion,
    ec.unidad_medida,
    ec.tipo_agregacion,
    ec.frecuencia
   FROM modulo2.eventos_activos ea
     JOIN modulo2.activos_biologicos ab ON ab.id_activo_biologico = ea.id_activo_biologico
     JOIN modulo2.eventos_crecimeinto ec ON ec.id_evento = ea.id_eventos
     LEFT JOIN modulo1.usuarios u ON u.id_usuario = ea.id_usuario;
```

## 8. Diagnóstico

No fue necesario: las seis respuestas coinciden con la regla evaluada, sin 500, errores de acceso ni persistencia. No se repitieron POST con curl ni se inspeccionó o modificó código del producto.

Se descartó error de prueba mediante SELECT inmediato de las precondiciones, payload exacto en Newman, control del sub del token, GET autorizado y verificación de finca. La revisión final comprobó los códigos específicos FECHA_INCOHERENTE y SIN_FASE_ACTIVA, además de las assertions de mensaje de la colección.

## 9. Veredicto final

**APROBADO.** Cobertura 6/6 y 3/3 actores; ambos sub-casos rechazados por su causa prevista y Δ=0 en cada petición. Newman ejecutó 7 solicitudes (1 GET de contrato y 6 POST oficiales), 31 assertions, 0 fallos. Las comprobaciones SQL se ejecutaron mediante el orquestador externo y no forman parte del contador de assertions Newman.

## 10. Datos para Registro de Errores

No se detectaron fallos del producto; categoría, severidad, plazo y equipo corrector no aplican. Como mantenimiento documental, QA debe actualizar el correo de Veterinario y explicitar las correspondencias fecha_evento → fecha y estado_fase → es_activa. No se abrió ni envió un registro externo.

## 11. Cumplimiento y reutilización

No se modificó código del producto, no hubo commit/push/cambio de rama, SQL de escritura, migraciones, despliegues ni creación o modificación de precondiciones. No se eliminaron fases. Se cubrieron los tres actores usando recursos legítimos. No se ejecutaron escenarios de otros grupos ni se inventó evidencia.

La colección contiene 00-SETUP-LECTURA, 01-CASO-PRINCIPAL (por actor) y 02-DIAGNOSTICO vacío. Los logins y GET de acceso se ejecutaron antes mediante el orquestador; sus estados e identidades están consolidados en §3. Los tokens se entregaron a Newman en memoria y se eliminaron de los reportes exportados.

Para repetir la prueba, es obligatorio volver a ejecutar los SELECT de este informe en una conexión con default_transaction_read_only=on, comprobar recursos y alcance de los tres actores, autenticarlos e inyectar token_Productor, token_Veterinario y token_Ingeniero. Ejecutar SELECT antes/después de cada POST. La colección sola no verifica BD y su éxito no autoriza a concluir APROBADO sin dicha evidencia. No ejecutar si cambiaron las precondiciones. Los scripts transitorios del orquestador no son entregables permanentes.

Entregables: colección Postman, un reporte HTML Newman, un reporte JSON Newman y este informe consolidado. La revisión automatizada de la evidencia confirmó las seis respuestas específicas, las doce capturas SQL y la ausencia de cambios en los seis conjuntos de IDs.
