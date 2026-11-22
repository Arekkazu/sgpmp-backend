# INC-M04-217-G026 · RF-68 — Umbrales activos de contagio

Fecha: 2026-10-30. Responsable Git verificado: Leandro.
Issue: [#852](https://github.com/Arekkazu/sgpmp-backend/issues/852).
Rama: `fix/inc-m04-217-g026-umbrales-contagio-rf68`.
Base: `dev` actualizado por fast-forward a `e94232b5086bc1232a77a9f1a625225165eb9a49`.

## Diagnóstico confirmado

El reporte `resultado_tc-m04-g026_v20.html` registra 118 aserciones, una fallida y ninguna omitida. El caso complementario 4.2 obtiene P=0.8000, ALTO y alerta con config_version=2 aunque RF-65 ya tiene umbrales 0.90/0.95. Esta es evidencia de QA en TEST, distinta de las pruebas locales de esta corrección.

El router carga el caso de uso, que obtiene correctamente la configuración RF-65. El repositorio y la entidad de configuración ya transportan ambos umbrales. La pérdida ocurre al construir ParametrosContagio: se pasaban pesos y rangos, pero no el umbral de clasificación. La función discretizar usaba 0.70 fijo y el caso de uso generaba la alerta únicamente por nivel ALTO y confianza normal.

La integración real encontró además que la emisión RF-57 desde el usuario Veterinario no podía registrar la evidencia RF-63: RLS solo permite esa escritura como servicio. AlertaContagioRf57Adapter ahora utiliza el contexto existente como_sistema para emitir/consolidar esa alerta automática y restaura la identidad del solicitante al salir. El acceso al lote se verifica antes con la identidad original; los resultados RF-68 se escriben como el usuario. No se cambia la política ni se inventa una identidad.

La reproducción automatizada contra el código original de origin/dev produjo 3 fallidas y 4 aprobadas: caso QA, probabilidad 0.8999 con umbral 0.90 y siguiente ciclo con nueva configuración. La primera ejecución de esa reproducción no alcanzó las aserciones por permisos del directorio temporal de Windows; se corrigió exclusivamente el lanzador con --basetemp.

## Definición funcional aplicada

Referencias: RF-65 descripción de parámetros, restricción 6, RFC-009 (META) y CA-5; RF-68 precondición 4, paso 5, paso 7, paso 8, CA-2/3/6/7/9 y RNF-03.

El usuario confirmó expresamente: usar por separado los dos umbrales de RF-65, conservar la prohibición de alertar con confianza baja y los mínimos sanitarios obligatorios de RF-68. Esta decisión resuelve la diferencia entre RF-65 (umbral independiente para alerta) y RF-68 paso 8/CA-3 (alerta por clase ALTO).

- ALTO cuando P >= umbral_riesgo_alto.
- Se conserva el corte existente de MEDIO en P >= 0.50 cuando no aplica ALTO; no se inventa un umbral configurable de MEDIO.
- La alerta RIESGO_CONTAGIO requiere ALTO, confianza normal y P >= umbral_alerta_critica. La igualdad pertenece al intervalo superior.
- Más del 50 % de individuos enfermos impone al menos MEDIO; más del 70 % impone ALTO. Esos porcentajes describen prevalencia sanitaria, no sustituyen el umbral configurable de probabilidad. El conteo de enfermos conserva su definición individual P(riesgo alto)>0.70.
- Por ello un ALTO impuesto por prevalencia puede quedar sin alerta crítica si P no alcanza el umbral crítico confirmado. El score poblacional no se interpreta como porcentaje de individuos enfermos.

## Cambios y contrato resultante

1. Dominio: ParametrosContagio recibe el umbral de riesgo alto y discretizar lo aplica, conservando fórmula, pesos, reglas sanitarias y validaciones de calidad.
2. Aplicación: toma ambos umbrales de la misma configuración/version usada en el cálculo y aplica el umbral crítico antes de invocar RF-57.
3. Persistencia: el JSON existente variables_ambientales_snap conserva umbrales_aplicados. Su lectura reconstruye los Decimal y admite registros históricos sin esa clave, sin reconstruirles valores supuestos.
4. Auditoría RF-73: el evento de cálculo y el de alerta incluyen los umbrales y la versión aplicada.
5. Integración RF-57/RF-63: emisión automática con identidad de servicio existente, después de validar el acceso al lote, y restauración del contexto del solicitante.
6. Router: documentación del comportamiento dinámico. Se conservan DTO, campos de respuesta, HTTP 201 de cálculo, HTTP 200 de caché y HTTP 429 dentro del intervalo mínimo con entradas/configuración distintas.

Caso QA: Fs=0.60, Fa=1 y Fd=1 con pesos 0.5/0.3/0.2 → P=0.80, MEDIO y alerta_id=null para umbrales 0.90/0.95.

La huella ya incluye config_version. Un cambio de versión no reutiliza el resultado del ciclo anterior; sigue vigente el intervalo mínimo de cinco segundos. Los resultados históricos mantienen su clasificación, versión y snapshot originales. Las alertas históricas siguen su ciclo RF-57 y no se eliminan por cambiar los umbrales.

## BD, migraciones y seguridad

Inspección oficial: conexión member_dev a sgpmp_dev con SET TRANSACTION READ ONLY y rollback. Se comprobaron columnas, FK, CHECK, índices, RLS, FORCE RLS, políticas y triggers de configuraciones_motor_ia y resultados_riesgo_contagio, además de la auditoría. Ambos umbrales ya existen; el CHECK por paradigma los exige para META y los restringe a 0.50–0.95 con orden crítico >= alto. El resultado ya admite clases 0–2 y snapshot JSONB.

No se ejecutó DDL/DML en la base oficial. La consulta de modulo1.permisos y de public.alembic_version fue denegada (42501); no se infiere de ello una falta de permisos RBAC ni una revisión desplegada. La revisión de permisos se completó en la base local migrada: recurso 41, acciones C/R/E para Administrador y Veterinario; Ingeniero solo R.

No hay migración nueva. PostgreSQL 18 local: base exclusiva sgpmp_g41_test, migrada desde cero hasta head 67e33de11180. Se aprovisionaron allí privilegios SQL de las tablas/secuencias utilizadas para sgpmp_app; no se cambiaron las políticas, los roles de negocio ni los triggers. La preparación se realiza como propietario; las solicitudes HTTP corren como sgpmp_app, sin superusuario/BYPASSRLS. Los catálogos y activos de las fixtures son datos sintéticos de pruebas y se revierten con la transacción exterior.

## Validación

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato RF-65/RF-68 (5 archivos seleccionados) | 98 | 0 | 0 |
| HTTP con PostgreSQL 18 real, JWT/RBAC/RLS | 11 | 0 | 0 |
| **Total distinto** | **109** | **0** | **0** |

Los 38 casos focalizados iniciales están incluidos en los 98; no se suman otra vez. Los intentos fallidos y las corridas interrumpidas no se cuentan como aprobados. Advertencia preexistente de TestClient/httpx; no hay fallos de las corridas finales.

Cobertura: caso QA con creación y actualización RF-65; fronteras de riesgo y alerta; mínimos sanitarios; confianza baja; snapshot/auditoría; caché; siguiente ciclo por versión; persistencia real de alerta; rollback de resultado, alerta y auditoría; restauración de identidad después de emitir la alerta; JWT/RBAC y finca ajena.

Las comprobaciones unitarias usan fakes. Las pruebas de integración utilizan HTTP TestClient, JWT real y PostgreSQL real con TEST_ROL_APP=sgpmp_app. El shim fcntl permanece solo en los lanzadores locales de pruebas. No se ha desplegado esta rama ni reejecutado Newman sobre TEST/DEV compartido.

Durante la preparación se corrigieron fixtures sin catálogo ACTIVO, fechas obligatorias y coherencia del lote poblacional, se completaron privilegios SQL locales para los adaptadores, la bitácora RF-63 y sgpmp_owner (trigger RF-65), y se registraron los modelos ORM relacionados como en el arranque completo. Esos errores de preparación no se contabilizan como pruebas aprobadas. Las primeras corridas HTTP dentro del sandbox no completaron su ejecución; las corridas finales se realizaron fuera del sandbox para permitir el bucle de eventos local de TestClient.

### Evidencias reproducibles

- .pytest_cache/g41_antes.xml y g41_antes.log: reproducción contra origin/dev (3 fallidas, 4 aprobadas).
- .pytest_cache/g41_unit.xml y g41_unit.log: 98 aprobadas en test_rf68_riesgo_contagio.py, test_inc_m04_217_umbrales_contagio.py, test_rfc009_taxonomia_paradigma.py, test_dev36_concurrencia_historial_motor.py y test_dev09_sincronizar_config_motor_nodos.py.
- .pytest_cache/g41_pg.xml y g41_pg.log: 11 aprobadas en test_inc_m04_217_umbrales_contagio_integration.py.
- .pytest_cache/g41_preflight.json: metadatos oficiales leídos; g41_migraciones.log: migración local desde cero; g41_grants.py: perfil de privilegios SQL local.
- .pytest_cache/g41_verificacion.json: conteo sin duplicar casos, AST de los 8 archivos de código y cabeceras verificadas con fecha/identidad reales. git diff --check sin errores.

## Archivos y entrega

Producción: riesgo_contagio.py, estimar_riesgo_contagio_use_case.py, resultado_riesgo_contagio_repository.py, riesgo_contagio_router.py y alerta_contagio_rf57_adapter.py bajo src/prediction.
Pruebas: tests/prediction/test_rf68_riesgo_contagio.py, tests/prediction/test_inc_m04_217_umbrales_contagio.py y tests/integration/test_inc_m04_217_umbrales_contagio_integration.py.
Informes: este diagnóstico y inc_m04_217_g026_rf68_pr_preparado.md.

Se eliminó exclusivamente sgpmp_g41_test y se detuvo el clúster iniciado para esta tarea. Se verificó que las demás bases locales se conservaron; evidencia en .pytest_cache/g41_cierre_bd.log.

Evidencias locales y lanzadores: .pytest_cache/g41_*; no forman parte de la entrega. Se preservaron AGENTS.md y los documentos ajenos previamente sin seguimiento. Commit y push autorizados por el usuario para esta tarea; no se solicitó publicar un PR.
