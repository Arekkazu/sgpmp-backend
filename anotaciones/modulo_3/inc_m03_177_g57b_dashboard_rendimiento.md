# INC-M03-177-G57B — Rendimiento del dashboard de monitoreo (RF-58, CA-13)

**RF:** RF-57 CA-13 / RF-58: "el dashboard debe actualizarse en 500 ms". **Issue:** #756.
**Rama:** desde `dev`, sin dependencias. **Sin migración.**

## Lo que reportó QA

En TEST (431 sensores), `GET /iot/monitoreo/dashboard`:
1. Respondió **500 ERROR_INTERNO tras 3 min 21 s**.
2. Al reintentar, respondió **200 tras 1 min 34 s** (45 KB).

## Causa

**1. El aviso E7 corría dentro del GET (causa principal).**
- Por cada sensor de la página en GRIS "Sin umbral configurado" y sin aviso en 24 h,
  `AvisoSinUmbralEmailAdapter`:
  - escribía la bitácora `VARIABLE_SIN_UMBRAL`, con un commit por sensor;
  - enviaba **un correo por Administrador**, de forma síncrona.
- `send_email` tiene un timeout SMTP de 8 s. Con unas 25 conexiones que no responden, eso da
  8 s × 25 ≈ **201 s**, justo los 3 min 21 s de QA.
- Si una excepción ocurría a mitad, el adaptador hacía `rollback()` y descartaba la bitácora
  de los sensores aún sin commit. Por eso el reintento volvió a avisar a una parte de ellos:
  ~12 timeouts, que son los 94 s de la segunda llamada.
- El 500 encaja con que la conexión del request quedara inservible tras minutos de espera
  (por ejemplo, por un timeout de sesión del servidor o del proxy). Esa parte no se pudo
  reproducir sin acceso a TEST.

**2. El conteo del semáforo repetía la consulta pesada.**
- `contar_semaforos` (M3-08) volvía a ejecutar `_SQL_ESTADOS` completo sobre los 431 sensores,
  con sus laterales sobre `telemetrias`, solo para contar colores.
- Con 431 sensores y estadísticas, costaba ~150 ms de los ~300 ms del GET.

**Lo que no es la causa:**
- Con estadísticas, la consulta de la página (50 sensores) toma ~25 ms. Los índices existentes
  bastan:
  - `idx_telemetria_sensor_captura`;
  - `uq_telemetria_sensor_variable_captura_origen`, para la última lectura válida;
  - `idx_bitacora_iot_tipo_evento_entidad_afectada_id`, para "ya avisado en 24 h".
- **No hace falta un índice nuevo ni una migración.**

## Cambios

- **`aviso_sin_umbral_background_adapter.py` (nuevo):** implementa `AvisoSinUmbralPort` agendando
  el aviso con `BackgroundTasks`.
  - Corre después de responder, con su propia sesión de sistema (`sesion_sistema()`), igual que
    `NotificacionSesionBackgroundAdapter` (QA M01 2.2).
  - Mientras un aviso está en curso, sus sensores no se agendan de nuevo, así que un refresco no
    duplica correos. La bitácora sigue evitando repetir el aviso en 24 h.
  - El contenido del aviso (bitácora, destinatarios, correo) no cambia:
    `AvisoSinUmbralEmailAdapter` es el mismo.
- **`monitoreo_router.py`:** los dos GET del dashboard inyectan el adaptador en segundo plano.
- **`SemaforoBaseSensor` (entidad) y `MonitoreoRepository.obtener_semaforos_sensores` (puerto y
  `_SQL_SEMAFOROS`):**
  - Devuelven el semáforo base de todos los sensores del alcance, sin laterales sobre
    `telemetrias`.
  - El alcance es el mismo que el de la vista: sensores visibles (RLS), área vigente y fincas.
- **`ObtenerDashboardUseCase.contar_semaforos`:** cuenta con el semáforo base y la misma regla del
  semáforo efectivo (CA-4 y CA-5).
- **`test_dev39_rf58_dashboard.py`:** el doble de M3-08 ahora responde `obtener_semaforos_sensores`.
  La prueba mantiene su intención: contar todo el alcance, no la página.

## Evidencia

**Pruebas unitarias:** `tests/telemetry/test_inc_m03_177_g57b_dashboard_rendimiento.py`, sin BD.
- El aviso se agenda y no corre dentro del request.
- Un refresco no duplica el aviso en curso.
- Al terminar, los sensores se liberan aunque el SMTP falle.
- El router ya no usa el adaptador síncrono.
- El conteo no pide la consulta completa de estados (CA-4 y CA-5 se mantienen).

**Integración:** `tests/integration/test_inc_m03_177_g57b_dashboard_rendimiento.py`, con
PostgreSQL efímero, migraciones al día y el rol `sgpmp_app` (con RLS).
- Escenario sembrado:
  - 431 sensores en 9 áreas, con 150 lecturas cada uno (64 650 en total).
  - Un tercio sin umbral (GRIS, E7).
  - Uno de cada cinco con lecturas `ERROR_CALIBRACION` recientes.
  - SMTP simulado con 0,5 s por correo.
- `ANALYZE` al sembrar, como en TEST con autovacuum.

| | Antes (`dev`) | Después |
|---|---|---|
| Primera llamada | **9,2 s** (17 correos dentro del GET) | 0,36–0,76 s, sin correos dentro del GET |
| Refrescos | 0,28–0,31 s | **0,18–0,30 s** (≤ 500 ms) |

- La primera llamada de un proceso nuevo incluye la compilación de SQLAlchemy y de las funciones
  de RLS, que ocurre una vez por proceso y conexión. En el contenedor varía entre 0,4 y 1,6 s y
  la prueba solo la imprime. La prueba acota los refrescos, que es lo que pide CA-13.
- Una segunda prueba ejecuta el aviso diferido:
  - escribe la bitácora de cada sensor;
  - envía un correo por Administrador;
  - libera los sensores;
  - un refresco posterior no repite el correo.

**Regresión:**
- Suite completa: 4 failed y 25 errors, los mismos de la base. Ninguno nuevo.
- Integración del dashboard (G87 y G57B): 10 passed.

## Fuera de alcance

- **Medición en TEST:** el número final debe tomarlo QA en TEST. Allí `telemetrias` y la
  bitácora son más grandes y el SMTP es real.
- **Índice parcial para la última lectura válida** (`(id_sensor, id_variable, timestamp_captura
  DESC) WHERE estado_calidad = 'LECTURA_VALIDA'`):
  - No hace falta con los datos medidos.
  - Si en TEST un sensor acumula miles de lecturas inválidas seguidas, sería la siguiente
    mejora. Requiere migración con aprobación del DBA.
- **Grants de `sgpmp_app` en la BD efímera:** se otorgaron a mano solo para la prueba. En DEV
  y TEST ya existen.
