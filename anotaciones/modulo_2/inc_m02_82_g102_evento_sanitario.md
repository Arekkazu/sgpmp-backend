# INC-M02-82-G102 / RF-41 - Evento sanitario válido responde 500

Fecha de verificación: 2026-09-12

## Evidencia

`TC-M02-261` registra un activo individual y luego ejecuta:

```http
POST /activos-biologicos/{id_activo}/eventos/sanitario
```

```json
{
  "tipo": "CONTROL_PREVENTIVO",
  "observaciones": "TC-M02-G102 - revision rutinaria (prueba QA de clasificacion)"
}
```

El payload cumple RF-41, pero TEST respondió `500 / ERROR_INTERNO`. El intento
quedó auditado como `RF41`, clasificación `SANITARIO` y resultado `FALLIDO`.

## Causa raíz confirmada

La hipótesis inicial apuntaba a
`modulo2.trg_fn_evento_sanitario_secuencia()` y su SQLSTATE `P0219`. La
inspección de `sgpmp_dev` descartó ese camino: el trigger solo evalúa eventos
con medicamento y dosis, por lo que no interviene en `CONTROL_PREVENTIVO`.

La reproducción con el repositorio SQLAlchemy real obtuvo:

```text
SQLSTATE: P0215
INVALID_DATE: La fecha del evento no puede ser futura.
Contexto: modulo2.trg_fn_evento_fecha_coherente()
```

`CURRENT_TIMESTAMP`/`now()` de PostgreSQL representa el inicio de la
transacción. El caso de uso consultaba primero el activo y después construía la
fecha predeterminada con `datetime.now()`. Por ello, la fecha creada por Python
quedaba unos milisegundos por delante del tiempo congelado de la transacción y
el trigger de `modulo2.eventos_activos` rechazaba un evento válido como futuro.

El traductor no reconocía `P0215`, por lo que ocultaba el diagnóstico como
`500 / ERROR_INTERNO`.

## Corrección

- La migración `v5.2.0_rf41_reloj_eventos_activos` reemplaza `now()` por
  `clock_timestamp()` tanto en
  `trg_fn_evento_fecha_coherente()` como en
  `chk_eventos_fecha_no_futura`.
- El modelo SQLAlchemy queda alineado con la restricción versionada.
- `db_error_translator` reconoce `P0215` como regla de negocio y lo convierte
  en `422`, usando `FECHA_FUTURA` o `FECHA_ANTERIOR_REGISTRO` según el mensaje.

No se deshabilitó ninguna protección: las fechas realmente futuras y las
anteriores a la creación del activo continúan siendo rechazadas. La migración
es necesaria para corregir la función y el `CHECK` existentes en cada ambiente.

## Verificación de base de datos

La inspección de `sgpmp_dev` se realizó con `member_dev`, puerto 5447, sesión
forzada a solo lectura y rollback final.

- `eventos_sanitarios` admite `CONTROL_PREVENTIVO` y exige observaciones.
- El trigger sanitario `P0219` no aplica al payload reportado.
- El trigger real involucrado está en `eventos_activos` y usa `P0215`.
- La sesión terminó con `ROLLBACK_OK`.
- No se ejecutó DDL ni DML en la base oficial.

## Pruebas

- Pruebas unitarias del traductor de errores: 30 aprobadas.
- Regresión de `biological_assets`, `configuration`, `identity_access` y
  `shared`: 537 aprobadas.
- Integración HTTP/PostgreSQL en `pruebas-integrador`: 2 aprobadas.
- Se comprobó que `upgrade()` y `downgrade()` restauran de forma reversible
  tanto la función como la restricción temporal.
- La integración comprobó respuesta `201`, fila en `eventos_sanitarios` y
  auditoría `RF41/SANITARIO/EXITOSO`.
- También comprobó que una fecha realmente futura continúa disparando `P0215`.
- Rollback comprobado en las tres tablas:
  `eventos_activos (56→56)`, `eventos_sanitarios (16→16)` y
  `bitacora_auditoria_m02 (14→14)`.

Las advertencias observadas corresponden a la deprecación de `TestClient` y a
la falta de permiso para crear `.pytest_cache`; no son fallos funcionales.

## Alcance

La causa está en el evento base compartido y no en una regla sanitaria. Por eso
la corrección elimina el falso positivo temporal para todos los subtipos que se
insertan en `eventos_activos`, aunque el escenario validado por esta incidencia
es RF-41. No modifica las reglas ni los triggers específicos de RF-42 o RF-45,
que corresponden a incidencias separadas.

La rama de rechazos tempranos de RF-52 modifica el caso de uso sanitario. Esta
solución no lo toca: se limita a la migración, el modelo y el traductor, evitando
duplicación funcional y conflictos de merge con esa rama.

QA debe actualizar el paso sanitario de G102 para exigir `HTTP 201` y repetir
la verificación de las cinco clasificaciones después del despliegue en TEST.
