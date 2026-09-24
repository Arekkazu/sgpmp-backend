# TC-M01-71 — Paginación del historial de auditoría repite un evento entre páginas consecutivas

**Issue:** #287. **Endpoint:** `GET /auditoria/` (y `GET /auditoria/archivado/`, mismo use case).

## Qué reportó QA

Con `tamano=50` y 10.351 registros totales, se detectó solapamiento entre páginas consecutivas:

- Página 1 → Página 2: `id_evento = 10396` aparece en ambas.
- Página 2 → Página 3: `id_evento = 10347` aparece en ambas.

Se esperaba que cada evento apareciera una sola vez entre las páginas consultadas.

## Causa raíz

`ConsultarAuditoriaUseCase.execute()` ordena por `fecha_evento DESC, id_evento DESC` (más
reciente primero) — orden ya determinístico, sin ambigüedad de empates. El problema no es el
orden: es que **cada llamada al endpoint inserta un evento nuevo en la propia tabla que está
paginando**. El paso 5 del use case registra `TIPO_CONSULTA_AUDITORIA` (quién consultó la
auditoría) con `fecha_evento = datetime.now()`, y hace `commit()` antes de responder al cliente.

Como esa fila nueva siempre es la más reciente de toda la tabla, se cuela en la posición 0 del
orden en la SIGUIENTE consulta — desplazando una posición hacia abajo a todas las demás filas.
El evento que estaba en la última posición de la página N reaparece como el primero de la
página N+1. Esto ocurre en **cada** llamada (no solo con actividad concurrente de otros
usuarios), lo que explica el patrón exacto reportado: un evento repetido por cada salto de
página, de forma consistente.

Confirmado con un repro de fakes que simula el filtrado/orden real del repositorio y hace que
`registrar()` inserte una fila nueva igual que en producción
(`tests/identity_access/test_inc_m01_71_paginacion_auditoria_estable.py`): sin ancla, pedir
página 1 y luego página 2 sin más contexto reproduce el solapamiento; con el fix, no.

## Decisión de diseño

Se evaluaron tres enfoques (ver discusión con el equipo):

1. **Ancla temporal (`fecha_hasta`) fijada por el backend y devuelta al cliente** — elegido.
2. Paginación por cursor (`id_evento`) — más robusta a largo plazo, pero rompe el contrato
   actual (`pagina`/`tamano`) que ya consumen el frontend y la colección de pruebas de QA.
3. Orden ascendente por `id_evento` (más antiguo primero) — evita el desplazamiento porque las
   filas nuevas se agregan al final, no al inicio, pero cambia la UX esperada de un log de
   auditoría (se espera ver lo más reciente primero).

Se optó por (1) por ser el cambio de menor alcance que no rompe el contrato existente.

## Fix

`ConsultarAuditoriaUseCase.execute()`:

- Si el cliente no manda `fecha_hasta`, se fija `fecha_hasta_efectiva = now() - 50ms` (margen de
  seguridad; ver siguiente sección) **antes** de consultar y de autoauditar la consulta.
- `contar_eventos` y `listar_eventos` usan siempre `fecha_hasta_efectiva`, nunca el valor crudo
  del cliente.
- La respuesta (`AuditoriaPaginadaResponse.fecha_hasta`) devuelve ese ancla. El cliente debe
  reenviarlo como `fecha_hasta` en las siguientes páginas de la misma navegación para obtener un
  conjunto estable — documentado en la descripción del parámetro `fecha_hasta` en ambos
  endpoints (`/auditoria/` y `/auditoria/archivado/`).
- Si el cliente sí manda `fecha_hasta` explícito, se respeta tal cual (comportamiento de filtro
  existente, sin cambios).

**Margen de 50ms:** al escribir el test de reproducción se detectó que, en este entorno de
desarrollo (Windows), dos llamadas consecutivas a `datetime.now()` separadas por pocos
milisegundos pueden devolver **el mismo valor exacto** (resolución del reloj del sistema). Como
el filtro es `fecha_evento <= fecha_hasta` (inclusive, comportamiento ya existente y compartido
con el resto de filtros del endpoint, no se tocó), un empate entre el ancla y el evento de
auto-auditoría volvería a colarlo en la página siguiente — exactamente el bug original. Restar
50ms al ancla por defecto garantiza separación aunque el reloj empate.

## Alcance

- No cubre el caso de actividad **concurrente de otros usuarios** insertando eventos reales
  entre que un cliente pide la página 1 y la página 2 — para eso el cliente debe reenviar el
  `fecha_hasta` devuelto, tal como ahora exige la documentación del parámetro. Si el cliente
  (frontend o la colección de QA) no lo reenvía, seguirá viendo el mismo desplazamiento con
  actividad concurrente real (no autoinfligida). Migrar a paginación por cursor eliminaría esto
  por completo, pero es un cambio de contrato fuera de alcance de este fix.
- No se tocó el endpoint `/auditoria/exportar` ni las exportaciones diferidas: no paginan por
  página de cliente (traen todo el conjunto filtrado en una sola pasada), así que no sufren este
  problema.

## Pruebas

- `tests/identity_access/test_inc_m01_71_paginacion_auditoria_estable.py` (nuevo, 4 casos, fakes
  sin BD): ancla por defecto cercana a "ahora", `fecha_hasta` explícito se respeta sin
  modificar, `contar_eventos`/`listar_eventos` reciben siempre la misma ancla, y el escenario
  completo de 3 páginas (reproduce y corrige TC-M01-71) confirmando cero solapamiento pese a que
  cada página sigue autoauditándose.
- Suite completa `tests -m "not integration"`: 691 passed, mismos 2 fallos preexistentes en
  `test_registrar_transferencia_use_case.py` (no relacionados, ya documentados en el repo).
