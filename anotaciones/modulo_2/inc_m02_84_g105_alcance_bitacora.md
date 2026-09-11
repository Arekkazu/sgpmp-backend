# INC-M02-84-G105 — Alcance de consulta de la bitácora RF-52

## Desvío

`ConsultarBitacoraUseCase` no recibía al usuario autenticado y enviaba los
filtros directamente al repositorio. El permiso de lectura sobre el recurso 31
permitía consultar cualquier clasificación y cualquier activo.

Esto incumplía CA-8 en dos escenarios:

- un Productor podía consultar eventos `ACCESO_DATOS` de activos registrados
  por otro usuario;
- un Contador podía consultar clasificaciones distintas de
  `TRANSFORMACION_BIOLOGICA` y `SANITARIO`.

## Corrección

- El caso de uso recibe `UsuarioActual` y resuelve el nombre vigente del rol.
- Una consulta explícita no autorizada responde
  `403 / ALCANCE_BITACORA_DENEGADO`.
- Cada rechazo intenta registrar un evento `ACCESO_NO_AUTORIZADO`, con
  resultado `RECHAZADO`, usuario, activo, rol y clasificación solicitada.
- Las consultas generales del Contador se limitan en SQL a sus dos
  clasificaciones permitidas.
- Las consultas generales del Productor excluyen eventos `ACCESO_DATOS` de
  activos ajenos, evitando filtraciones por paginación o ausencia de filtro.
- Los demás roles con permiso conservan la consulta existente.

## Validación

- 11 pruebas unitarias y de contrato HTTP cubren Productor, Contador,
  Administrador, registro de rechazo y fallo de auditoría.
- Una prueba de integración con PostgreSQL verifica los filtros SQL, los tres
  rechazos de TC-M02-266 y la creación de los eventos de acceso no autorizado.
- La integración usa `pruebas-integrador` y el aislamiento transaccional del
  proyecto. Al finalizar quedaron cero activos y eventos del fixture.

## Base de datos

No requiere migraciones ni cambios de esquema. `sgpmp_dev` no fue modificada.
