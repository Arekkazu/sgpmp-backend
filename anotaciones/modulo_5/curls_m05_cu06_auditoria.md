# CURLs — M05 CU06: Auditar Operaciones del Módulo (RF-80)

Base URL (local, sin proxy): `http://localhost:8000`
(En producción el proxy antepone `/api`.)

Autenticación: header `Authorization: Bearer <TOKEN>` obtenido de `POST /sesiones/`
(`{"correo_electronico": "...", "contrasena": "..."}`). Sesión expira a los 30 min de
inactividad — reloguear si aparece `401 SESION_EXPIRADA_INACTIVIDAD`.

Roles en los ejemplos: `<ADMIN>` (1), `<CONT>` (5), `<REVFISCAL>` (8), `<PROD>` (2, sin permiso).

RBAC: recurso `bitacora_auditoria_suministros` = **57** — R=2 (listar/detalle) y E=5 (exportar) →
Administrador/Contador/Revisor Fiscal.

Todos los escenarios de este documento fueron ejecutados contra un servidor local real
(`uvicorn main:app`) y verificados end-to-end el 2026-07-31. Como no se contaba con las
contraseñas en texto plano de los usuarios de prueba, los tokens `<ADMIN>`/`<CONT>`/`<REVFISCAL>`/
`<PROD>` se generaron insertando sesión+token directamente vía MCP postgres para las cuentas
existentes (`admin@pecuaria.co`, `contador@pecuaria.co`, `revisor.fiscal.test@pecuaria.co`,
`productor@pecuaria.co`) y firmando el JWT con `src.shared.jwt.create_token` — equivalente en
efecto a un login real vía `POST /sesiones/`.

---

## Listar y filtrar la bitácora

### Escenario 1 — Listar sin filtros

```bash
curl http://localhost:8000/suministros/auditoria -H "Authorization: Bearer <ADMIN>"
```

Respuesta `200`:
```json
{"total": 87, "pagina": 1, "registros_por_pagina": 50, "items": [ /* ... */ ]}
```

### Escenario 2 — Filtrar por `tipo_operacion` y paginar

```bash
curl "http://localhost:8000/suministros/auditoria?tipo_operacion=SUMINISTRO_REGISTRADO&registros_por_pagina=5" \
  -H "Authorization: Bearer <CONT>"
```

Respuesta `200`: solo eventos `SUMINISTRO_REGISTRADO`, máximo 5 items. También soporta
`id_usuario`, `fecha_desde`/`fecha_hasta`, `entidad_afectada`, `id_activo_biologico`,
`id_ciclo_productivo`, `resultado` (`EXITOSO|FALLIDO|RECHAZADO`) y `clasificacion_registro`
(`NIC41|TECNICO`) combinables.

### Escenario 3 — Productor sin permiso (403)

```bash
curl http://localhost:8000/suministros/auditoria -H "Authorization: Bearer <PROD>"
```

Respuesta `403`:
```json
{"error_code":"ACCESO_DENEGADO","message":"Acceso denegado. Su rol no tiene permisos para realizar esta operación.","fields":[],"timestamp":"..."}
```

---

## Detalle de un evento

### Escenario 4 — Detalle de un evento existente

```bash
curl http://localhost:8000/suministros/auditoria/83 -H "Authorization: Bearer <ADMIN>"
```

Respuesta `200`:
```json
{"id_auditoria_suministro":83,"entidad_afectada":"registro_suministro","tipo_operacion":"SUMINISTRO_REGISTRADO","id_usuario":3,"resultado":"EXITOSO","fecha_evento":"2026-07-31T13:02:03.517066Z","id_activo_biologico":57,"id_ciclo_productivo":1,"costo_afectado":"80000.0000","origen_precio":"MANUAL","clasificacion_registro":"NIC41","retencion_aplicable":"5 años","hash_integridad":"5635ab0a3943f4cfb3debc5ba52772d86ff3eef69d8ff89e606597fa7a600e91", "...": "..."}
```

### Escenario 5 — Detalle de un evento inexistente (404)

```bash
curl http://localhost:8000/suministros/auditoria/999999 -H "Authorization: Bearer <REVFISCAL>"
```

Respuesta `404`:
```json
{"error_code":"AUDITORIA_SUMINISTRO_NO_ENCONTRADA","message":"No existe el evento de auditoría 999999.","fields":[],"timestamp":"..."}
```

---

## Exportación

### Escenario 6 — Exportar CSV

```bash
curl "http://localhost:8000/suministros/auditoria/exportar?formato=csv" \
  -H "Authorization: Bearer <ADMIN>" -o Auditoria_Suministros.csv
```

Respuesta `200`, `Content-Type: text/csv; charset=utf-8`,
`Content-Disposition: attachment; filename="Auditoria_Suministros.csv"`. Verificado: 88 líneas
(1 encabezado + 87 filas).

### Escenario 7 — Exportar Excel

```bash
curl "http://localhost:8000/suministros/auditoria/exportar?formato=xlsx" \
  -H "Authorization: Bearer <ADMIN>" -o Auditoria_Suministros.xlsx
```

Respuesta `200`, `Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`.
Verificado con `file`: `Microsoft Excel 2007+`.

### Escenario 8 — Exportar PDF

```bash
curl "http://localhost:8000/suministros/auditoria/exportar?formato=pdf" \
  -H "Authorization: Bearer <ADMIN>" -o Auditoria_Suministros.pdf
```

Respuesta `200`, `Content-Type: application/pdf`. Verificado con `file`: `PDF document, version
1.4, 4 page(s)` (título, fecha de generación, total de registros, tabla con todas las columnas).

### Escenario 9 — Formato inválido (400)

```bash
curl "http://localhost:8000/suministros/auditoria/exportar?formato=doc" -H "Authorization: Bearer <ADMIN>"
```

Respuesta `400` (rechazado por el patrón `^(csv|xlsx|pdf)$` del `Query` del router, antes de
llegar al use case):
```json
{"error_code":"VAL_ENTRADA","message":"Errores de validacion en la solicitud","fields":[{"field":"formato","message":"String should match pattern '^(csv|xlsx|pdf)$'"}],"timestamp":"..."}
```

---

## Verificación del cierre de gap RF-81 (auto-auditoría del historial)

### Escenario 10 — Consultar historial (RF-81) genera `CONSULTA_HISTORIAL_EJECUTADA`

```bash
curl "http://localhost:8000/suministros/historial?id_activo_biologico=57" -H "Authorization: Bearer <ADMIN>"
```

Respuesta `200` normal de RF-81. Efecto colateral verificado en `auditorias_suministros`: nueva
fila `id_auditoria_suministro=95`, `tipo_operacion=CONSULTA_HISTORIAL_EJECUTADA`,
`id_usuario=1`, `id_activo_biologico=57`.

### Escenario 11 — Exportar historial (RF-81) genera `EXPORTACION_HISTORIAL_GENERADA`

```bash
curl "http://localhost:8000/suministros/historial/exportar?id_activo_biologico=57" -H "Authorization: Bearer <ADMIN>"
```

Respuesta `200` normal de RF-81 (CSV). Efecto colateral verificado: nueva fila
`id_auditoria_suministro=96`, `tipo_operacion=EXPORTACION_HISTORIAL_GENERADA`.

Ambos eventos son visibles inmediatamente vía `GET /suministros/auditoria?tipo_operacion=CONSULTA_HISTORIAL_EJECUTADA`
(o `EXPORTACION_HISTORIAL_GENERADA`), confirmando el circuito completo: RF-81 escribe → CU-06 lee.
