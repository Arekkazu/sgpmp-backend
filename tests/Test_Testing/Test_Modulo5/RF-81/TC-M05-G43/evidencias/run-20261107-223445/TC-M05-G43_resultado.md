# Reporte de Prueba: TC-M05-G43 (RF-81)
## Control de Acceso por Rol y Unidad, y Auditoría de Consultas, Exportaciones y Rechazos
### Casos TC-M05-102 y TC-M05-105 (Agrupados 037 y 040)

> **Tipo de corrida:** Evaluación Oficial (primera evaluación oficial de RF-81).

- **ID Caso:** TC-M05-G43 (Plano: 102, 105 | Agrupado: 037, 040)
- **Ambiente:** `https://www.api.inmero.co/api-sgpmp-test`
- **Veredicto Global:** **RECHAZADO** (6/11 OK, 5 Fallas)
- **Fecha:** 2026-11-07 22:35:01 (America/Bogota)
- **Run IDs Sandbox:** `tc-m05-g43-admin-d64e2de4, tc-m05-g43-gestor-04df5f89, tc-m05-g43-productor-4be7df0e`

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Setup de activo C y línea base (Admin) | Activo C creado con fase y 3 registros de suministros (HTTP 201) | Activo C creado (HTTP 201), fase abierta, 3 registros de suministros cargados. Estado: OK. | **OK** |
| 2 | B01 Auditoría de consulta con resultados (105 / 040) | CONSULTA_HISTORIAL_EJECUTADA registrado con id_usuario, id_activo, resultado EXITOSO, filtros aplicados y total registros retornados en <= 2 s (CA-8 / RNF-05) | CONSULTA_HISTORIAL_EJECUTADA registrado con id_usuario, id_activo y EXITOSO en <= 2 s. Estado: FALLA. | **FALLA** |
| 3 | B02 Auditoría de consulta sin resultados (105 / 040, CU04 FA-01) | CONSULTA_HISTORIAL_EJECUTADA registrado con filtros aplicados y total registros retornados (0) en la bitácora | Consulta sin resultados auditada en la bitacora de M05. Estado: FALLA. | **FALLA** |
| 4 | B03 Auditoría de exportación síncrona PDF y Excel (105 / 040) | EXPORTACION_HISTORIAL_GENERADA registrado con filtros aplicados y total registros exportados en <= 2 s | EXPORTACION_HISTORIAL_GENERADA auditado para PDF y Excel en <= 2 s. Estado: FALLA. | **FALLA** |
| 5 | B04 Naturaleza de solo lectura e inmutabilidad (102 / 037) | POST, PUT, PATCH, DELETE sobre /suministros/historial rechazados con 405 Method Not Allowed; historial inalterado | POST/PUT/PATCH/DELETE rechazados con 405 Method Not Allowed; datos inalterados. Estado: OK. | **OK** |
| 6 | A01 Gestor de Granja consulta activo de su unidad (102 / 037) | HTTP 200 con items y resumen para activo 1042 en finca 464 asignada; PUT/DELETE rechazados (405) | Gestor de Granja consulta activo 1042 en su finca 464 con HTTP 200; solo lectura verificada. Estado: OK. | **OK** |
| 7 | A02 Rechazo a usuario sin la unidad del activo (102 / 037) | HTTP 403 con mensaje de E2 ('No tiene permisos para consultar el historial del activo [id]. Verifique su rol y unidades productivas asignadas.') y sin fuga de datos | AssertionError: Defecto de producto: el backend respondio HTTP 404 (ACTIVO_NO_ENCONTRADO) en lugar de HTTP 403 (E2/CA-3) al consultar activo 957 fuera de su unidad asignada, debido a que RLS en modulo2.activos_biologicos oculta el registro antes de AlcanceActivoPort. | **FALLA** |
| 8 | A03 Auditoría de consulta rechazada (102 / 037, CU04 FA-04) | Registro de al menos 1 evento de auditoría en la bitácora con resultado RECHAZADO tras el intento denegado | AssertionError: Defecto de producto: No se registro evento de auditoria en modulo5.auditorias_suministros para la consulta rechazada. El componente RBAC (src/shared/rbac.py) lanza AuthorizationError sin persistir en la bitacora (misma causa raiz que RF-80/G38). | **FALLA** |
| 9 | A04 [OBSERVACION] Productor consulta activo de su unidad (102 / 037) | HTTP 200 con items y resumen para activo 957 en finca 1 asignada (observación informativa) | Resultado: Completado exitosamente sin excepciones. | **OK** |
| 10 | T98 Cierre estricto de todas las corridas sandbox | Todas las corridas (Admin, Gestor, Productor) cerradas con HTTP 200 ('Rollback exitoso') | Todas las corridas cerraron exitosamente con HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| 11 | T99 Inocuidad final fuera de sandbox | Verificación fuera de sandbox: activo C responde HTTP 404 (0 efectos persistidos) | Verificación sin sandbox completada; activo C responde HTTP 404 (0 efectos persistidos). Estado: OK. | **OK** |

## Cobertura No Ejecutada y Observaciones
1. **Roles Contador y Revisor Fiscal (Restr. 2 / TC-M05-102 / 037):**
   - **Hecho Observado:** El archivo `.env.test` solo provee variables para `TEST_ADMIN_*`, `TEST_FIELD_ENGINEER_*`, `TEST_PRODUCER_*` y `TEST_VET_*`. No existen variables `TEST_ACCOUNTANT_*` ni `TEST_FISCAL_REVIEWER_*` en `.env.test`.
   - **Mapeo de Roles en BD:** `SELECT id_rol, nombre_rol FROM modulo1.roles` confirma: Rol 1: Administrador, Rol 2: Productor, Rol 3: Veterinario, Rol 4: Ingeniero de Campo, Rol 5: Contador, Rol 7: Gestor de Granja, Rol 8: Revisor Fiscal.
2. **Checkpoint A04 (Productor consulta activo 957):**
   - **Observación:** El rol Productor está fuera del alcance de la especificación funcional de RF-81 (reservado a Administrador, Gestor de Granja, Ingeniero de Campo, Contador y Revisor Fiscal). Se verificó con éxito como observación de interoperabilidad sin computar como checkpoint normativo restrictivo.
3. **Eliminación y purga de archivos asíncronos a las 72 h (RNF-06):**
   - **Razón:** Requiere esperar 72 horas reales o manipular el reloj del sistema, lo cual está prohibido por las reglas de QA.

## Diagnóstico de Defectos de Producto
### 1. Defecto en B01, B02 y B03 (Contenido Incompleto en Bitácora de Auditoría — CA-8 / Fase 7)
- **Hecho Observado:** Las filas generadas en `modulo5.auditorias_suministros` para `CONSULTA_HISTORIAL_EJECUTADA` y `EXPORTACION_HISTORIAL_GENERADA` tienen `datos_nuevos = null` y carecen de columnas para `filtros` y `total_registros_retornados` (o exportados).
- **Ruta de Código (Inferida y Verificada):**
  - `src/supplies/application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py:191`:
    `_auditar_consulta()` instancia `EventoAuditoriaSuministro` pasando únicamente `entidad_afectada`, `tipo_operacion`, `id_usuario`, `resultado`, `id_activo_biologico`, `id_ciclo_productivo`, omitiendo `datos_nuevos` y `total_registros_retornados`.
  - `src/supplies/application/use_cases/historial_suministros/exportar_historial_sincrono_use_case.py:194`:
    `_auditar_exportacion()` repite la misma omisión.
- **Clasificación:** Defecto de producto (omisión de campos requeridos por CA-8).
- **Posible Solución:** Enriquecer `EventoAuditoriaSuministro` con `datos_nuevos={"filtros": filtros.to_dict(), "total_registros_retornados": resultado.total_registros_filtrados}`.

### 2. Defecto en A02 (HTTP 404 en lugar de HTTP 403 para Activo Fuera de Unidad Asignada)
- **Hecho Observado:** `GET /suministros/historial?id_activo_biologico=957` ejecutado por Gestor de Granja (`id_usuario=30`, fincas 81 y 464) respondió HTTP 404 (`error_code: ACTIVO_NO_ENCONTRADO`, mensaje: `"El activo biológico 957 no existe."`). En contraste, el Productor consulta el activo 957 con HTTP 200, demostrando que el activo 957 sí existe en la base de datos.
- **Ruta de Código:**
  1. `src/supplies/infrastructure/routers/historial_suministros_router.py:123`
  2. `src/supplies/application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py:144` (`_validar()`):
     Invoca `activo = self.activo_port.obtener(filtros.id_activo_biologico)`.
  3. `src/supplies/infrastructure/adapters/activo_m02_adapter.py:37`:
     Invoca `self._repo.obtener_por_id(id_activo)`.
  4. **[INFERENCIA]:** En PostgreSQL, `modulo2.activos_biologicos` tiene RLS activo (`pol_activos_biologicos_select`). La sesión del Gestor no tiene visibilidad sobre fincas ajenas, por lo que la consulta retorna `None` antes de que el use case llegue a evaluar `AlcanceActivoPort` (línea 152), levantando `NotFoundError` (404) en vez de `AuthorizationError` (403 con mensaje de E2).
- **Clasificación:** Defecto de arquitectura / diseño (fuga de RLS intermódulo sobre el control de acceso de la API).

### 3. Defecto en A03 (Auditoría de Consultas Denegadas/Rechazadas no Persistida)
- **Hecho Observado:** Tras el rechazo de la consulta no autorizada en A02, la consulta SQL `SELECT count(*) FROM modulo5.auditorias_suministros WHERE entidad_afectada = 'historial_suministros' AND resultado IN ('RECHAZADO', 'FALLIDO')` arrojó 0 registros en la sandbox del Gestor.
- **Ruta de Código (Inferencia):** Al levantarse `NotFoundError` (o `AuthorizationError`), el flujo sale por excepción en FastAPI sin invocar `_auditar_consulta()` ni registrar en `modulo5.auditorias_suministros`.
- **Causa Raíz Compartida:** Es la misma causa raíz identificada en RF-80 (G38): las excepciones y denegaciones de acceso no son interceptadas para emitir eventos a la bitácora de auditoría de M05.
- **Clasificación:** Defecto de producto (omisión según CU04 FA-04).
