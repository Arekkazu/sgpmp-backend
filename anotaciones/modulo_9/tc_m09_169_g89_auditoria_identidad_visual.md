# TC-M09-169-G89 (#307) — Consulta de auditoría de identidad visual

## Desvío confirmado

RF-26 exige registrar cada modificación con usuario, fecha/hora y valores anteriores y
nuevos. El `POST` y el `PATCH` ya persistían esa información en
`modulo9.auditorias_visuales`, pero no existía una API para recuperarla. `GET /auditoria/`
consulta exclusivamente `modulo1.eventos`, por lo que no era una alternativa equivalente.

## Corrección

Se agregó:

```text
GET /configuracion/identidad-visual/{id_finca}/auditoria
```

El endpoint requiere permiso `R` sobre `identidad_visual` (`id_recurso=23`) y devuelve:

- identificador de auditoría y finca;
- identificador y nombre del usuario;
- fecha/hora;
- operación `CREATE` o `UPDATE`;
- snapshots `valor_anterior` y `valor_nuevo`;
- total de registros.

Si la finca no tiene identidad visual, responde `404 IDENTIDAD_VISUAL_NO_ENCONTRADA`.

## Duplicidad encontrada durante la revisión

En `sgpmp_dev`, cada actualización generaba dos filas:

1. El trigger `trg_identidad_visual_audit` escribía un snapshot sin `id_finca`.
2. El caso de uso escribía el snapshot canónico con `id_finca` dentro de la misma
   transacción del cambio.

La migración Alembic `47038edfa2fc` (`v5.3.0`) elimina el trigger duplicador. No borra
historial. La API filtra por el `id_finca` del snapshot canónico, por lo que los duplicados
anteriores permanecen preservados pero no aparecen dos veces en la respuesta.

El trigger transversal `trg_auditoria`, que alimenta el esquema genérico `auditoria`, no se
modifica.

## Validación

- Pruebas enfocadas RF-26: `18 passed`.
- Consulta real de la finca 6: 10 operaciones canónicas, ordenadas de versión 10 a 1.
- Flujo real transaccional sobre `sgpmp_dev`:
  - `PATCH` identidad visual: `200`.
  - `GET .../auditoria`: `200`.
  - total visible: 10 → 11.
  - última operación: `UPDATE`, usuario `Admin Camila`, snapshots versión 10 → 11.
  - rollback externo verificado: identidad y auditoría quedaron exactamente como estaban.
