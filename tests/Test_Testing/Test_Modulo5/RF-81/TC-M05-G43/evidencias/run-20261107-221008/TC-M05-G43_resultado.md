# Reporte de Prueba: TC-M05-G43 (RF-81)
## Control de Acceso por Rol y Unidad, y Auditoría de Consultas, Exportaciones y Rechazos
### Casos TC-M05-102 y TC-M05-105 (Agrupados 037 y 040)

> **Tipo de corrida:** evaluacion oficial; corrida realizada tras corregir el test; la corrida anterior queda archivada en evidencias/.

- **ID Caso:** TC-M05-G43 (Plano: 102, 105 | Agrupado: 037, 040)
- **Ambiente:** `https://www.api.inmero.co/api-sgpmp-test`
- **Veredicto Global:** **RECHAZADO** (9/11 OK, 2 Fallas)
- **Fecha:** 2026-11-07 22:10:24 (America/Bogota)
- **Run IDs Sandbox:** `tc-m05-g43-admin-227a63ee, tc-m05-g43-gestor-eadc760b, tc-m05-g43-productor-2c95c6d9`

## Resumen de Checkpoints
| # | Paso | Esperado | Obtenido | Estado |
|---|------|----------|----------|--------|
| 1 | T00 Setup de activo C y línea base (Admin) | Activo C creado con fase y 3 registros de suministros (HTTP 201) | Activo C creado (HTTP 201), fase abierta, 3 registros de suministros cargados. Estado: OK. | **OK** |
| 2 | B01 Auditoría de consulta con resultados (105 / 040) | CONSULTA_HISTORIAL_EJECUTADA registrado con id_usuario, id_activo y EXITOSO en <= 2 s (CA-8 / RNF-05) | CONSULTA_HISTORIAL_EJECUTADA registrado con id_usuario, id_activo y EXITOSO en <= 2 s. Estado: OK. | **OK** |
| 3 | B02 Auditoría de consulta sin resultados (105 / 040, CU04 FA-01) | CONSULTA_HISTORIAL_EJECUTADA registrado en la bitácora ante consulta vacía | Consulta sin resultados auditada en la bitacora de M05. Estado: OK. | **OK** |
| 4 | B03 Auditoría de exportación síncrona PDF y Excel (105 / 040) | EXPORTACION_HISTORIAL_GENERADA registrado en <= 2 s para PDF y Excel | EXPORTACION_HISTORIAL_GENERADA auditado para PDF y Excel en <= 2 s. Estado: OK. | **OK** |
| 5 | B04 Naturaleza de solo lectura e inmutabilidad (102 / 037) | POST, PUT, PATCH, DELETE sobre /suministros/historial rechazados con 405 Method Not Allowed; historial inalterado | POST/PUT/PATCH/DELETE rechazados con 405 Method Not Allowed; datos inalterados. Estado: OK. | **OK** |
| 6 | A01 Gestor de Granja consulta activo de su unidad (102 / 037) | HTTP 200 con items y resumen para activo 1042 en finca 464 asignada; PUT/DELETE rechazados (405) | Gestor de Granja consulta activo 1042 en su finca 464 con HTTP 200; solo lectura verificada. Estado: OK. | **OK** |
| 7 | A02 Rechazo a usuario sin la unidad del activo (102 / 037) | HTTP 403 con mensaje de E2 ('No tiene permisos para consultar el historial del activo [id]. Verifique su rol y unidades productivas asignadas.') y sin fuga de datos | AssertionError: Defecto de producto: el backend respondio HTTP 404 (ACTIVO_NO_ENCONTRADO) en lugar de HTTP 403 (E2/CA-3) al consultar activo 957 fuera de su unidad asignada, debido a que RLS en modulo2.activos_biologicos oculta el registro antes de AlcanceActivoPort. | **FALLA** |
| 8 | A03 Auditoría de consulta rechazada (102 / 037, CU04 FA-04) | Registro de 1 evento de auditoría en la bitácora con resultado RECHAZADO tras el intento denegado | AssertionError: Defecto de producto: No se registro evento de auditoria en modulo5.auditorias_suministros para la consulta rechazada. El componente RBAC (src/shared/rbac.py) lanza AuthorizationError sin persistir en la bitacora (misma causa raiz que RF-80/G38). | **FALLA** |
| 9 | A04 Productor consulta activo de su unidad (102 / 037) | HTTP 200 con items y resumen para activo 957 en finca 1 asignada | Productor consulta activo 957 en su finca 1 con HTTP 200. Estado: OK. | **OK** |
| 10 | T98 Cierre estricto de todas las corridas sandbox | Todas las corridas (Admin, Gestor, Productor) cerradas con HTTP 200 ('Rollback exitoso') | Todas las corridas cerraron exitosamente con HTTP 200 ('Rollback exitoso'). Estado: OK. | **OK** |
| 11 | T99 Inocuidad final fuera de sandbox | Verificación fuera de sandbox: activo C responde HTTP 404 (0 efectos persistidos) | Verificación sin sandbox completada; activo C responde HTTP 404 (0 efectos persistidos). Estado: OK. | **OK** |

## Cobertura No Ejecutada
1. **Roles Contador y Revisor Fiscal (Restr. 2 / TC-M05-102 / 037):**
   - **Razón:** El archivo `.env.test` solo provee credenciales para Administrador, Gestor de Granja (`gestor.granja.test@pecuaria.co`), Productor y Veterinario. No existen credenciales configuradas para Contador ni Revisor Fiscal en el ambiente de pruebas.
2. **Eliminación y purga de archivos asíncronos a las 72 h (RNF-06):**
   - **Razón:** Requiere esperar 72 horas reales o manipular el reloj de base de datos/sistema operativo, lo cual está prohibido por las reglas de pruebas de QA.

## Diagnóstico de Defectos de Producto
### 1. Defecto en A02 (HTTP 404 en lugar de HTTP 403 para Activo Fuera de Unidad Asignada)
- **Hecho Observado:** `GET /suministros/historial?id_activo_biologico=957` ejecutado por Gestor de Granja (`id_usuario=30`, asignado a fincas 81 y 464) respondió HTTP 404 (`error_code: ACTIVO_NO_ENCONTRADO`, mensaje: `"El activo biológico 957 no existe."`).
- **Ruta de Código (Inferencia):**
  1. `src/supplies/infrastructure/routers/historial_suministros_router.py:73`
  2. `src/supplies/application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py:144` (`_validar()`):
     Invoca `activo = self.activo_port.obtener(filtros.id_activo_biologico)`.
  3. `src/supplies/infrastructure/adapters/activo_m02_adapter.py:34`:
     Invoca `self._repo.obtener_por_id(id_activo)` (`SqlAlchemyActivoBiologicoRepository`).
  4. En PostgreSQL, la tabla `modulo2.activos_biologicos` tiene RLS activo (`fn_fincas_del_usuario`), por lo que la consulta retorna `None` antes de que el use case llegue a evaluar `AlcanceActivoPort` (línea 152), levantando `NotFoundError` (404) en vez de `AuthorizationError` (403 con mensaje de E2).
- **Clasificación:** Defecto de diseño / arquitectura (orden de validaciones y encapsulamiento de RLS entre módulos).
- **Posible Solución:** Evaluar el alcance del usuario a través de un puerto de infraestructura con credencial de servicio desacoplada de la sesión de usuario, o estructurar la verificación de pertenencia a nivel de finca antes del filtro de activos biológicos.

### 2. Defecto en A03 (Auditoría de Consultas Rechazadas no Persistida)
- **Hecho Observado:** Tras el rechazo de la consulta, la consulta SQL a `modulo5.auditorias_suministros` arrojó 0 registros de tipo rechazo/denegado para el usuario y activo.
- **Ruta de Código (Inferencia):** `src/shared/rbac.py` y `src/supplies/application/use_cases/historial_suministros/consultar_historial_suministros_use_case.py`. Al lanzar `AuthorizationError` o `NotFoundError`, la ejecución no llega al bloque `_auditar_consulta()` ni el middleware de RBAC cuenta con llamada a `AuditoriaSuministroPort`.
- **Causa Raíz Compartida:** Es la misma causa raíz documentada en RF-80 (TC-M05-G38): el componente transversal de RBAC y las excepciones previas al use case no emiten eventos a la bitácora de auditoría de M05.
- **Clasificación:** Defecto de producto.
