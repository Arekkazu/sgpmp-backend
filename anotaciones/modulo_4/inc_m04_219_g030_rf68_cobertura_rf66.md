# INC-M04-219-G030 · RF-68 — Cobertura mínima de inferencias

Fecha: 2026-10-30. Responsable Git verificado: Leandro. Issue: [#854](https://github.com/Arekkazu/sgpmp-backend/issues/854).

## Definición funcional confirmada

La ficha RF-68 contiene una contradicción: E1 y CA-5 admiten ejecutar sin RF-66 con confianza reducida, mientras que la restricción de validación, E8 y CA-10 exigen detenerse por debajo del 60 % de activos con inferencias recientes (≤30 minutos).

El usuario confirmó aplicar el mínimo obligatorio del 60 % a la inferencia individual, rechazando también 45 % y 55 % con HTTP 422 y auditoría. Se conserva el camino poblacional por score_anomalia de RFC-009. Esa decisión sustituye E1/CA-5 únicamente para la insuficiencia de inferencias individuales; no elimina los otros motivos de ejecución degradada.

Fuentes revisadas: Especificacion-Requerimientos-Modulo4.md, Requerimientos_M04_RF64-RF73.md y acuerdo AIOT-DEV-03. Ambas copias de RF-68 contienen la contradicción; la issue no tenía comentarios adicionales al consultar GitHub. No se agregan tareas o criterios no suministrados.

## Reproducción y causa raíz

El dominio usaba COBERTURA_MINIMA_FS=0.50. Con 11/20 salidas recientes aceptaba Fs=0.20 y modo NORMAL. Con 9/20 omitía Fs y continuaba DEGRADADO con COBERTURA_RF66_MENOR_AL_50. La caché se consultaba antes de verificar la cobertura y podía reutilizar un resultado calculado con la regla anterior.

La reproducción previa quedó en .pytest_cache/g43_antes.xml y g43_antes.log: cinco pruebas esperaban rechazo para 0, 1, 9, 10 y 11 salidas de 20, pero el modelo continuaba. Esa ejecución fallida de diagnóstico no se cuenta como validación final.

## Flujo resultante

1. JWT/RBAC y acceso al lote permanecen antes de exponer datos o registrar el intento del lote.
2. Se obtiene la configuración RF-65 vigente.
3. El dominio selecciona las inferencias con edad entre cero y 30 minutos, ambos límites incluidos. Para un ID de activo repetido toma la última salida reciente y cuenta ese individuo una vez.
4. Sin score_anomalia, la cobertura individual debe ser al menos 0.60. El cálculo no redondea el porcentaje antes de compararlo.
5. Si no cumple, lanza DatosContagioError con ERROR_DATOS_INSUFICIENTES y el contexto de cobertura. El caso de uso registra el evento RF-73, confirma esa auditoría y responde HTTP 422 mediante BusinessRuleError. No calcula P, no guarda un resultado nuevo ni solicita una alerta RF-57.
6. Si cumple, continúa el flujo existente de caché/frecuencia, sincronización, fórmula, persistencia, auditoría y alertas. La comprobación previa impide que una caché antigua eluda el mínimo o utilice inferencias que acaban de vencer.
7. Si existe score_anomalia, se conserva el Fs poblacional de RFC-009, incluido el valor cero.

El dominio vuelve a aplicar la misma función de validación al calcular directamente. Los errores reales del registro de auditoría conservan rollback y propagación; no se convierten en un cálculo aprobado.

## Contrato y ejemplos

| Entradas individuales recientes | Total declarado | Cobertura | Resultado |
|---:|---:|---:|---|
| 0 | 20 | 0 % | 422 ERROR_DATOS_INSUFICIENTES |
| 9 | 20 | 45 % | 422 ERROR_DATOS_INSUFICIENTES |
| 10 | 20 | 50 % | 422 ERROR_DATOS_INSUFICIENTES |
| 11 | 20 | 55 % | 422 ERROR_DATOS_INSUFICIENTES |
| 12 | 20 | 60 % | 201; Fs se calcula |
| 20 | 20 | 100 % | 201; Fs se calcula |

Con 4 enfermos de 20, Fa=0.5, Fd=0.5 y pesos 0.5/0.3/0.2, Fs=0.2 y P=0.3500. La respuesta normal de éxito y la reutilización HTTP 200 de una caché válida mantienen su esquema.

El rechazo registra inferencias_recientes, total_activos_lote, cobertura_rf66 y cobertura_minima_rf66 en payload_evento, junto con el lote, configuración y motivo. Se utiliza el tipo de evento existente ERROR_DATOS_INSUFICIENTES, resultado_operacion=FALLIDO y la referencia de entidad lote.

## Archivos

| Archivo | Cambio |
|---|---|
| src/prediction/domain/entities/riesgo_contagio.py | Mínimo 0.60, selección reciente por individuo y contexto del rechazo |
| src/prediction/application/use_cases/riesgo_contagio/estimar_riesgo_contagio_use_case.py | Validación antes de caché y contexto en RF-73 |
| src/prediction/infrastructure/routers/riesgo_contagio_router.py | Documentación OpenAPI del rechazo E8/CA-10 |
| tests/prediction/test_rf68_riesgo_contagio.py | Sustituir la expectativa antigua de E1 por el rechazo confirmado |
| tests/prediction/test_inc_m04_219_cobertura_rf66.py | Regresiones de dominio, orquestación y caché |
| tests/integration/test_inc_m04_219_cobertura_rf66_integration.py | HTTP/PostgreSQL, auditoría, RLS, caché y rollback |

Todos los archivos de código tienen la cabecera de seguimiento correspondiente sin borrar filas anteriores. Hay dos informes Markdown adicionales: este diagnóstico y la descripción preparada del PR.

## BD, RBAC y migraciones

La inspección oficial fue exclusivamente de lectura y verificó current_database=sgpmp_dev, current_user=member_dev y transaction_read_only=on. Existen el evento ERROR_DATOS_INSUFICIENTES, sus columnas y las tablas configuraciones_motor_ia/resultados_riesgo_contagio. Auditoría y resultados tienen RLS y FORCE RLS. Los roles de API consultados no son superusuarios ni BYPASSRLS y tienen permisos SQL sobre las tablas revisadas.

member_dev no pudo consultar modulo1.permisos ni public.alembic_version (SQLSTATE 42501); no se infiere su contenido ni una revisión desplegada. El RBAC se comprobó en PostgreSQL local y por HTTP: Administrador/Veterinario conservan ejecución sobre recurso 41; Productor responde 403; otro Veterinario sin la finca responde 404; sin JWT responde 401.

No se agrega migración, enum, columna, permiso de negocio ni política. La base local sgpmp_g43_test se migró desde cero a la única head 67e33de11180. Los privilegios de preparación se limitaron a esa base local. No se ejecutó DDL/DML en la base oficial.

## Pruebas finales

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato RF-68/RFC-009, tres archivos | 71 | 0 | 0 |
| Integración HTTP/PostgreSQL 18, G030 | 17 | 0 | 0 |
| Total distinto | 88 | 0 | 0 |

Evidencias: .pytest_cache/g43_unit.xml/log y .pytest_cache/g43_pg.xml/log. No se suman corridas repetidas. La integración conserva una advertencia preexistente de TestClient/httpx.

Cobertura: 45/50/55 %, 60 % exacto y superior; vigencia de 30 minutos; exclusión de futuro/obsoletos; individuos repetidos y su última salida; score poblacional cero/no cero; contrato opcional; caché válida, caché legacy y vencimiento; auditoría de rechazo y ausencia de resultado/alerta; JWT/RBAC/finca; rollback tras flush de auditoría.

Las solicitudes de integración corren como sgpmp_app y una prueba observa current_user=sgpmp_app, rolsuper=false y rolbypassrls=false durante el rechazo. La siembra y las aserciones usan el usuario de preparación local; no representan el rol normal de la API. No se desactivaron triggers, RLS ni restricciones. Las salidas RF-66 son entradas sintéticas controladas del contrato HTTP; no se acredita la ejecución de un motor RF-66 real.

Los lanzadores ignorados mantienen el shim fcntl exclusivamente en pruebas Windows. Las pruebas unitarias usan fakes; la auditoría persistida, RLS y rollback se verifican por separado con PostgreSQL real.

## Límites y dependencias

- Se conserva el contrato existente: si se omite total_activos_lote, se deriva del número de salidas recientes; sin IDs, cada entrada representa un individuo según ese contrato. Para acreditar cobertura del lote real, el emisor debe informar el total completo y salidas por individuo. Esta corrección no contrasta ese inventario contra M02 ni consulta automáticamente todas las inferencias RF-66.
- No se modifican resultados históricos previos. Una solicitud insuficiente no reutiliza esos resultados por caché.
- La rama parte de dev actualizado e94232b5086bc1232a77a9f1a625225165eb9a49. No incorpora los cambios independientes de #852 (umbrales/alertas) ni #853 (densidad histórica). Al integrarlos deben conservarse los tres cambios y sus cabeceras; verificar su estado en GitHub antes de integrarlos.
- Pendiente actualizar la definición funcional y la matriz QA para reflejar la prioridad del mínimo del 60 % confirmada, desplegar y reejecutar TC-M04-G030 en TEST autorizado.
- No hay validación sobre un despliegue compartido ni publicación de PR. Commit y push autorizados por el usuario para esta entrega; no se solicitó publicar un PR.

## Cierre del entorno

Se retiró exclusivamente sgpmp_g43_test, verificando que las demás bases locales permanecieran intactas, y se detuvo el clúster iniciado para la tarea. Evidencia en .pytest_cache/g43_cierre_bd.log. Los scripts y logs temporales se conservan fuera del commit.
