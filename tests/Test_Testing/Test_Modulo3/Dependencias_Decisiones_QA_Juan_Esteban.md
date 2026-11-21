# Dependencias y decisiones QA — Módulo 03 — Juan Esteban

**Fecha de corte:** 2026-10-17 · **Alcance:** 31 grupos y 65 casos (ver `Inventario_Construccion_Juan_Esteban.md`).

**Fuentes:**
- la matriz oficial;
- el documento `DEV-Reparto_Tareas_Integracion_AIoT.md`, que describe cambios planificados y no desplegados;
- los README y el código de los ejecutores;
- los informes de cierre de construcción.

Ninguna decisión se resuelve aquí y la matriz no se modifica.

En la columna **Alcance**:
- **Caso** significa que el impedimento bloquea el caso completo.
- **Variante** significa que bloquea solo una parte; el resto del caso se evalúa y puede rechazar, pero el caso no puede aprobarse mientras falte esa variante.

## 1. Dependencias de Desarrollo

| Dependencia | Qué falta o qué cambia | Grupos / casos afectados | Alcance | Responsable | Condición de desbloqueo |
| --- | --- | --- | --- | --- | --- |
| **RF-60: transición temporal de conectividad** | No hay un disparador aislado ni un reloj de pruebas. Los estados SIN_SEÑAL / OFFLINE / GRIS por ausencia de reportes los produce una tarea periódica global que no ve el sandbox. | G90 (175, 176); G93 (184, variante «todos SIN_SEÑAL»); G96 (187, variantes SIN_SEÑAL y OFFLINE); G104 (204, variante GRIS); G105 (205, panel con GRIS) | G90: caso. G93, G96, G104: variante (se descubre en solo lectura si existe). G105: preparación de la sesión. | Desarrollo backend | Disparador de evaluación RF-60 invocable dentro del RUN, o reloj de pruebas oficial |
| **DEV-06: token de servicio en `/iot/*`** | `access_key = serial` dejará de aceptarse y el contrato del token aún no está definido | Todos los grupos que preparan lecturas o alertas por API de dispositivo: G87–G92, G96, G97, G99, G100, G102–G104, G107, G110, G120 y G126–G129 | Caso (falla la preparación, resultado BLOQUEADO) | Desarrollo backend | Contrato publicado. Adaptar el punto único de credencial de cada grupo (`cuerpoLectura` / `cuerpoAlerta` / `cuerpoDispositivo` o equivalente). |
| **DEV-05: ingesta con post-commit** (RF-61, RF-62, semáforo RF-17, alertas de heartbeat) | Lo que se calcula tras el commit no es visible dentro de la transacción del sandbox | G88, G89, G92, G96, G97 (vinculación); G102–G104 (estado actual); G104 (semáforo AMARILLO/ROJO) | Caso o variante, según el grupo. Las precondiciones lo detectan y dan BLOQUEADO, no RECHAZADO. | Desarrollo backend + QA | Mecanismo observable en el sandbox o decisión sobre dónde evaluar estos efectos |
| **DB-02: corrección de `fn_ingesta_telemetria`** | FUERA_DE_RANGO contra el umbral de la especie, `valor_ajustado` NULL sin calibración, rango físico de M09 | G87 (derivación de valores fuera de rango); G102–G104, G107 y G126–G129 (lecturas de 25 °C que podrían clasificarse distinto) | Caso (la preparación se detiene con un mensaje explícito) | Desarrollo BD | Revisar los valores de preparación tras el despliegue |
| **DEV-02: calidad desde `telemetria_calidad`** | RF-62 deja de actualizar `telemetrias` | G126 (el snapshot incluye `telemetria_calidad`; absorbe el cambio) | Sin bloqueo previsto | Desarrollo backend | — |
| **DEV-11/12/13: alertas y heartbeat** | Cambios en alertas técnicas y su exposición | G89, G97, G98, G104, G107 y G129 (crean alertas por `POST /iot/alertas`) | Caso (preparación) | Desarrollo backend | Adaptar `cuerpoAlerta` si cambia el contrato |
| **M08: exportación** | `GET /historial/exportar` responde 503 `M08_NO_DISPONIBLE` | G124 (249, 250, 254); G125 (251, 265; 253 necesita además un hook de fallo); G127 (variante EXPORTACION) | G124 y G125: caso. G127: variante condicional («cuando aplique»), la consulta se evalúa igual. | Desarrollo M08 | Servicio desplegado en TEST; para el volumen, aceptación expresa del efecto `volumen-exportacion` |
| **M08: casos que no dependen de él** | — | G125 (252); G128 (401 en exportar); G129 (260: el permiso se valida antes del servicio) | Ninguno | — | — |
| **RF-54: sincronización del buffer local** | No hay contrato de sincronización BUFFER_LOCAL; el flujo C no expone el momento de sincronización | G120 (241–243; 243 explícitamente) | Caso / variante según el caso | Desarrollo backend | Contrato RF-54 y DEV-06 publicados |
| **Auditoría del historial (RF-59 CA-16)** | El caso de uso no registra las consultas | G127 (256) | Caso. Con el testigo positivo cumplido, la ausencia del registro es evidencia de incumplimiento. | Desarrollo backend | Implementación; si es post-commit, un mecanismo observable |
| **Auditoría de accesos denegados** | El control RBAC no registra los 403 | G107 (209); G129 (258 y 260, aserción de auditoría) | Aserción (variante propia de auditoría) | Desarrollo backend | Registro de denegaciones consultable en RF-10 / RF-63 |
| **Bitácoras específicas RF-58** | No se descubrió un contrato GET de bitácora de degradación ni de consistencia | G101 (196–200); G110 (263) | Caso / variante | Desarrollo backend | Contrato de consulta publicado |
| **Filtro `id_activo_biologico` del historial** | No existe en el contrato | G129 (259, variante ACTIVO) | Variante (precondición dinámica) | Desarrollo backend | El filtro aparece en `filtros_aplicados` |
| **Expiración de sesión observable** | JWT de 8 h; no hay reloj ni disparador de expiración | G95 (186) | Caso (ABORTADA_PREFLIGHT documentada) | Desarrollo backend / QA | Duración corta en TEST o disparador oficial |
| **Estímulos de carga y degradación** | Ráfaga observable por el backend; continuidad del sandbox durante esperas largas | G100 (195); G101 | Caso | Desarrollo backend / QA | Mecanismo de estímulo aislado |
| **TLS del canal** | La matriz lo marca «fuera de stack» (requiere sniffer o cliente TLS) | G109 (212) | Caso | Infraestructura / QA | Aceptar la sonda TLS de Node o una herramienta acordada |
| **Permiso SELECT sobre `auditoria.logs_dml`** | Testigo de aislamiento y rollback de los grupos con sandbox | Todos los grupos con escrituras preparatorias | Caso (sin el testigo, aislamiento «no verificable» y el RUN se detiene) | DBA | Confirmar el permiso para el rol de la aplicación en TEST |

## 2. Decisiones QA pendientes

| Grupo | Decisión | Opciones registradas | Mientras no se decida |
| --- | --- | --- | --- |
| **G98** (191) | Severidades del panel | La matriz usa ALTA/MEDIA; RF-57 y el enum de BD usan LEVE/MODERADO/CRITICO | Grupo **congelado**; sin ejecución |
| **G103** (203) | Alcance de la medición de rendimiento | a) Tiempo HTTP (implementado, Newman como equivalente de k6) · b) Renderizado en navegador (Cypress con Performance API) · c) Instalar k6. Decisorio: primera carga (implementado) o percentil. Petición con o sin filtro por unidad. Validez de medir dentro del sandbox. | Se ejecuta según lo implementado. La matriz no fija estadístico ni capa. |
| **G105** (205) | Protocolo con usuarios | Número mínimo de participantes y ensayos; criterio en todos los ensayos (implementado) o en un porcentaje; conjunto de datos QA persistente para la sesión | Sin panel preparado no hay sesión: BLOQUEADO |
| **G106** (206) | Periodo y frecuencia de disponibilidad | Duración (obligatoria con `--duracion`), intervalo (60 s por defecto), tiempo límite (10 s), sonda desde el equipo QA o desde la infraestructura | No se ejecuta sin `--duracion` |
| **G107** (207, 209) | Unidad no asignada y forma de la denegación | a) Definir «unidad no asignada» (no existe asignación por unidad; el alcance es por granja) · b) Si un 200 sin datos equivale a «denegado» (hoy API-207-02 exige 4xx) | 209 no aprobable (API-209-03 bloqueado); 207 evalúa con 4xx |
| **G125** (265) | Política oficial de frecuencia y límite de latencia | Política acotable y límite de degradación para otros usuarios | 265 BLOQUEADO |
| **G128** (257) | Procedencia y expiración del JWT | Implementado: login oficial dentro de un RUN, token guardado fuera del repositorio (`~/.sigab-qa/TC-M03-G128/`) y usado después de `exp` + 150 s. G108 usa en cambio una variable de entorno (`QA_G108_EXPIRED_TOKEN`) sin trazar su procedencia. | Aprobar el mecanismo y la ubicación del almacén; decidir si G108 debe alinearse |
| **G129** (258–261) | Equivalencias y comparación | a) `id_unidad_productiva` = `id_infraestructura` · b) Indistinguibilidad entre ajeno e inexistente incluyendo mensaje y estado (implementado) · c) «Acceso exclusivo a A» verificado como «sin acceso a B» · d) 258 se evalúa por contenido (sin código HTTP) y 261 exige que no haya respuesta de historial | Se ejecuta según lo implementado |
| G102 (201, 202, 213) | Prueba de carga k6 | Sin criterio de carga en los resultados esperados; el sandbox serializa | Solo criterios funcionales |
| G102–G104, G129 | Actor del dashboard | Ingeniero de Campo, porque el Productor no lee `modulo9.sensores` por RLS | Se usa el Ingeniero |
| G94 (185) | Retirada temporal de granjas del Productor | El ejecutor quita sus asignaciones con `PUT /usuarios/{id}/fincas` dentro del sandbox (con rollback) | Confirmar que es aceptable según la regla de no alterar asociaciones reales, o usar una cuenta QA sin granjas |
| G96, G104 | Uso de estados descubiertos (no construidos) | SIN_SEÑAL, OFFLINE y GRIS se buscan en solo lectura entre datos reales | Válido solo si existen; si no, BLOQUEADO |

## 3. Dependencias de preparación

| Elemento | Requisito | Grupos | Alcance |
| --- | --- | --- | --- |
| **Cuenta de preparación (Administrador)** | `QA_SETUP_EMAIL`. Crea granjas, áreas, dispositivos y activos, y consulta bitácoras y permisos. | Todos los grupos con escenario construido | Caso |
| **Productor** | Cuenta activa; G94 necesita poder quedar sin granjas | G87–G89, G93, G94, G97, G105 y otros | Caso |
| **Ingeniero de Campo** | Lectura de monitoreo e historial (recursos 33 y 34) | G96, G97, G102–G104, G106, G107 y G126–G129 | Caso |
| **Veterinario** | Lectura de monitoreo | G97 (190) | Caso 190 |
| **Rol sin lectura del monitoreo (33)** | Cuenta QA entre las candidatas | G107 (208) | Caso |
| **Rol con lectura y sin exportación (34: 2 sí, 5 no)** | Cuenta QA entre las candidatas | G129 (260) | Caso |
| **Rol sin lectura del historial (34)** | Cuenta QA entre las candidatas | G129 (261) | Caso |
| **Sesión única por usuario** | Un login invalida el token anterior | Todos | No ejecutar en paralelo grupos que compartan cuenta |
| **Sandbox** | `/test-control/runs` y `/test-control/query` activos; secreto configurado; máximo 5 RUN; 180 s de inactividad | Todos los grupos con escrituras o consultas de testigo | Caso |
| **Testigos de aislamiento** | `auditoria.logs_dml` consultable (1 dentro, 0 fuera, 0 tras el rollback) | Grupos con escrituras | Caso |
| **Efectos autorizados** | `notificacion-login` (todos); `sesion-persistente` (G106); `volumen-exportacion` y `fallo-exportador` (G124, G125); efectos persistentes declarados en los planes de G87–G92 | Según el grupo | Caso |
| **Destinos** | `SIGAB_API_TEST_BASE` y `SIGAB_FRONT_TEST_URL` HTTPS de TEST y distintos entre sí (G87, G88, G102, G104 lo exigen) | Grupos con Cypress | Caso |
| **Token expirado oficial** | Ejecutar `--preparar-token-expirable` al menos 8 h antes | G128 (2 de las 6 variantes) | Variante |
| **Datos persistentes para la sesión manual** | Panel con 4 estados y una alerta durante la sesión | G105 | Caso |
| **Duración de la observación** | Valor explícito | G106 | Caso |
| **Cuenta QA del frontend** | Login de interfaz en TEST | Grupos con Cypress | Variantes de interfaz |
