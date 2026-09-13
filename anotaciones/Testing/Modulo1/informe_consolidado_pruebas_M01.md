# Informe consolidado de pruebas — Módulo 1 (Identidad y Acceso)
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M01 — Identidad y Acceso (`src/identity_access/`) |
| Alcance | RF-01 a RF-14 |
| Período de ejecución | 2026-08-28 a 2026-09-06 |
| Fecha de corte del informe | 2026-09-08 |
| Ambientes | Backend TEST (`sigab-backendtest-…sslip.io/api-sgpmp-test`) · Frontend TEST (`sigab-frontendtest-…sslip.io`) |
| Herramientas | Newman/Postman (API), Pytest (backend), Cypress (frontend) |
| Casos ejecutados | 140 de 141 (99.3 %) |
| Equipo QA | Laura Lopez, Daniela Castillo, Juan Manuel, Sebastian, Juan Parra, Juan Hernando |
| Fuente de datos | Panel QA (`qa-dashboard/`), evidencias en `tests/Test_Testing/Test_Modulo1/` (backend) y `testing/test_testing/Modulo1/` (frontend) |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso
> reejecutado después del corte puede cambiar de veredicto. La clasificación de
> los hallazgos **sin incidencia formal** (sección 4.B) es una propuesta de QA y
> debe confirmarse con Desarrollo antes de asignarse.

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| **Total de casos** | 141 | 100 % |
| Aprobados | 116 | 82.3 % |
| Rechazados | 24 | 17.0 % |
| Pendientes de ejecución | 1 | 0.7 % |

```
Aprobado    ████████████████████████████████████████░░░░░░░░  82.3%
Rechazado   ████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  17.0%
```

**Veredicto del módulo: APROBADO CON RESERVAS.**

Los flujos centrales de identidad y acceso —registro, autenticación, gestión de
roles y permisos, edición de usuario, cuentas, historial y auditoría, listado y
detalle de usuarios, notificaciones— están **conformes** o conformes con
observaciones acotadas. Las reservas se concentran en dos requisitos:

- **RF-08 (Recuperación de contraseña)** — 54 % de aprobación, 6 rechazos con
  varios defectos independientes (código HTTP del rate-limit, canal lateral
  temporal, resiliencia ante caída de SMTP, cobertura del límite por IP).
- **RF-13 (Visualización de perfil propio)** — 40 % de aprobación, defecto de
  frontend que impide abrir el detalle de perfil (`/usuarios/undefined/detalle`).

Se entregan a Desarrollo **9 incidencias formales** y **10 hallazgos por
formalizar/triar**. Cuatro casos están bloqueados por limitaciones del ambiente
de pruebas (no constituyen defecto de producto) y uno queda pendiente de
consolidar evidencia.

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-01 | Registro de usuarios | 20 | 18 | 1 | 1 | 90 % | ⚠️ Aprobado con observaciones |
| RF-02 | Autenticación de usuarios | 13 | 12 | 1 | 0 | 92 % | ⚠️ Aprobado con observaciones |
| RF-03 | Gestión de roles | 8 | 7 | 1 | 0 | 88 % | ⚠️ Aprobado con observaciones |
| RF-04 | Gestión de permisos | 7 | 6 | 1 | 0 | 86 % | ⚠️ Aprobado con observaciones |
| RF-05 | Edición de datos de usuario | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-06 | Gestión de cuentas de usuario | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-07 | Cambio de contraseña | 12 | 10 | 2 | 0 | 83 % | ⚠️ Aprobado con observaciones |
| RF-08 | Recuperación de contraseña | 13 | 7 | 6 | 0 | 54 % | ❌ No conforme |
| RF-09 | Restablecimiento de contraseña | 12 | 8 | 4 | 0 | 67 % | ⚠️ Condicionado |
| RF-10 | Historial de acceso y auditoría | 14 | 12 | 2 | 0 | 86 % | ⚠️ Aprobado con observaciones |
| RF-11 | Visualización de usuarios (listado) | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-12 | Visualización de detalle de usuario | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-13 | Visualización de perfil propio | 5 | 2 | 3 | 0 | 40 % | ❌ No conforme |
| RF-14 | Notificar a los usuarios | 12 | 9 | 3 | 0 | 75 % | ⚠️ Aprobado con observaciones |

**Leyenda:** ✅ Aprobado — sin hallazgos · ⚠️ Aprobado con observaciones — hallazgos
acotados, no bloquean el flujo principal · ⚠️ Condicionado — patrón de fallos a
resolver antes de aceptar · ❌ No conforme — requiere corrección y reejecución.

---

## 3. Cobertura y método

- **API backend:** colecciones Postman ejecutadas con Newman (reporter `htmlextra`);
  100 casos. Pruebas de lógica interna, reintentos y fallos simulados con Pytest
  (15 casos, reporte `pytest-html`).
- **Frontend:** recorridos Cypress con veredicto en JSON propio y reporte
  `mochawesome`; 23 casos.
- **Evidencia:** cada caso conserva su reporte de ejecución (HTML/JSON) y, en los
  casos extremos, un `TC-M01-XXX_resultado.md` con la narrativa del recorrido.
- **Tipos de prueba cubiertos:** funcional, validación, seguridad (OWASP API,
  ASVS), integridad, valores límite, resiliencia/pruebas extremas (pérdida de
  conexión, caída de BD, caída de SMTP).

---

## 4. Entrega a Desarrollo — registro de defectos

### 4.A — Incidencias formales

| Incidencia | RF | Caso(s) | Severidad | Estado | Descripción | Documento de análisis |
|---|---|---|---|---|---|---|
| **INC-M01-03-119** | RF-03 | TC-M01-119 | Crítico | Corregido en `dev` (PR #62, migración `c4a19e7d2b63`) — **retest pendiente** | `DELETE /roles/{id}` devuelve 500 para cualquier rol no protegido; el rol y sus permisos permanecen en BD | `inc_m01_03_119_eliminar_rol.md`, `inc_m01_03_119_ci_alembic_test_db.md` |
| **INC-M01-06-024** | RF-02 | TC-M01-024 | Severo | Abierto (rama `fix/inc-m01-06-024-reintentos-bd`) | `get_db()` no reintenta la conexión a PostgreSQL 3× ni traduce el fallo; ante caída de BD responde **500** en vez de **503** | `inc_m01_06_024_errores_bd.md` |
| **INC-M01-21-041** | RF-08 | TC-M01-041 | Medio | Abierto | Canal lateral temporal: el envío SMTP síncrono para correos **existentes** añade ~3.8 s, permitiendo inferir si un correo está registrado | `inc_m01_21_041_rf08_tiempo_recuperacion.md` |
| **INC-M01-05-035** | RF-07 | TC-M01-035 | Medio | Abierto | `PUT /contrasena/usuarios/{id}` acepta como nueva contraseña la **actual** (200) en vez de rechazarla (409); falta la migración del trigger de no-reutilización | `inc_m01_05_035_rf07_reutilizacion_contrasena.md` |
| **INC-M01-08-38** | RF-07 | TC-M01-038 | Medio | Abierto | El `rollback` ante fallo de invalidación de sesiones deshace también el cambio de contraseña ya aplicado (RF-07 exige conservarlo); la excepción se propaga sin 500 controlado | `inc_m01_08_38_rf07_fallo_invalidacion.md` |
| **INC-M01-16-057** | RF-09 | TC-M01-057 | Medio | Abierto | El restablecimiento acepta la contraseña **actual** (200) en vez de rechazarla (409) — mismo gap que INC-M01-05-035, en el flujo de RF-09 | `inc_m01_16_057_rf09_reutilizacion_contrasena.md` |
| **INC-M01-07-43** | RF-08 | TC-M01-043, TC-M01-112 | Medio | Abierto | El límite de recuperación de contraseña responde **422** en vez de **429** al excederse (la regla de negocio sí bloquea; solo el código HTTP es incorrecto) | `qa-dashboard/incidencias.csv` |
| **INC-M01-09-043** | RF-08 | TC-M01-043 | Medio | Abierto | El límite de 3 solicitudes/hora por IP solo se aplica cuando el correo existe; con correos inexistentes nunca bloquea (evento de contador no se registra en esa rama) | `qa-dashboard/incidencias.csv` |
| **INC-M01-02-71** | RF-10 | TC-M01-071 | Medio | Abierto | La paginación por offset del historial de auditoría devuelve un registro **duplicado** en el borde entre páginas cuando se insertan eventos durante la navegación | `qa-dashboard/incidencias.csv` |

### 4.B — Hallazgos sin incidencia formal (pendientes de triar con Desarrollo)

| Caso | RF | Capa | Observado | Clasificación propuesta (QA) |
|---|---|---|---|---|
| TC-M01-044 | RF-08 | backend | Con SMTP caído tras agotar reintentos, el endpoint responde **503** en vez de **202** con mensaje genérico (flujo alterno de RF-08) | Defecto de producto |
| TC-M01-049 | RF-08 | backend | Latencia de respuesta ~3.5 s por envío síncrono del correo dentro del request | Rendimiento — relacionado con INC-M01-21-041 |
| TC-M01-050 | RF-09 | backend | Restablecimiento responde **422** donde se esperaba **202** | Triage — posible defecto o ajuste de contrato de prueba |
| TC-M01-054 | RF-09 | backend | Varias aserciones: 422/401 donde se esperaban 202/409 (incluye reutilización de token) | Triage |
| TC-M01-058 | RF-09 | backend | Cuenta bloqueada devuelve **401** en vez de **423** | Triage — posible defecto |
| TC-M01-127 | RF-04 | backend | Tiempo de respuesta 427 ms / 226 ms por encima del umbral de 200 ms | Rendimiento (RNF) |
| TC-M01-074 | RF-10 | frontend | El botón "Exportar CSV" queda fuera del viewport y la descarga **offline** no se genera | Defecto de producto (frontend) |
| TC-M01-087 / TC-M01-089 | RF-13 | frontend | La tabla de usuarios no expone `id_usuario`; el frontend invoca `/usuarios/undefined/detalle` → **HTTP 400** ("Input should be a valid integer"). Impide abrir el detalle de perfil | Defecto de producto (frontend) — **prioridad alta** (bloquea RF-13) |
| TC-M01-091 | RF-14 | frontend | La bandeja muestra "No tienes notificaciones" aunque la API sí devuelve el evento | Defecto de producto (frontend) |
| TC-M01-092 | RF-14 | backend | Cuenta bloqueada devuelve **500** en vez de **423** | Triage — posible defecto |

### 4.C — Casos bloqueados / limitaciones del ambiente de pruebas

*No constituyen defecto de producto; requieren acción de QA o de Implementación.*

| Caso | RF | Causa | Acción |
|---|---|---|---|
| TC-M01-102 | RF-01 | **INC-M01-13** — el backend TEST exige la firma real de reCAPTCHA v2 y rechaza tokens simulados (comportamiento correcto del producto). QA no puede completar el reintento de registro tras reconexión | Coordinar con Implementación un bypass de CAPTCHA para TEST o un token de prueba válido |
| TC-M01-040 | RF-08 | El script conserva el placeholder `PEGAR_AQUI_EL_TOKEN_DEL_CORREO` sin reemplazar → 401 por token inválido | Corregir la automatización (QA) y reejecutar |
| TC-M01-088 | RF-13 | El login de la cuenta de prueba responde **403** (cuenta desactivada o sin permiso) | Aprovisionar/revisar la cuenta de prueba (QA) y reejecutar |
| TC-M01-094 | RF-14 | 401 de autenticación + error de JavaScript en el propio script (`Cannot read properties of undefined`) | Revisar setup y script (QA); reejecutar |

### 4.D — Pendiente de ejecución

| Caso | RF | Situación |
|---|---|---|
| TC-M01-109 | RF-01 (transversal RF-01/02/07/08/09) | Prueba extrema de pérdida de conexión intermitente. El panel lo marca "Pendiente" porque la carpeta backend está vacía; **existe evidencia frontend** (Fase B, 2026-09-06, Sebastián) en `Modulo1/RF-02-RF-07/TC-M01-109/`, que el escáner no lee por el nombre de carpeta combinado. Requiere consolidar la evidencia en una sola ubicación y confirmar veredicto |

### 4.E — Corregido y reverificado durante la campaña (histórico)

| Incidencia | RF | Caso | Severidad | Resultado |
|---|---|---|---|---|
| INC-M01-01-01 | RF-01 | TC-M01-002 | Crítico | `GET /usuarios/activar/{token}` → 500 `AUDITORIA_OBLIGATORIA_FALLIDA`. **Corregido el 2026-08-29**; retest exitoso (HTTP 200, `resultado_TC-M01-02_reintento2_20260829.html`) |

---

## 5. Condiciones de la entrega

1. **Se entrega a Desarrollo** el conjunto de defectos de las secciones 4.A y 4.B
   con su evidencia asociada. Cada incidencia formal tiene su documento de
   análisis con causa raíz; los hallazgos de 4.B requieren una reunión de triage
   para confirmar clasificación, severidad y responsable.
2. **Prioridad sugerida de corrección:**
   - **Alta:** INC-M01-03-119 (retest), INC-M01-06-024, TC-M01-087/089 (RF-13
     frontend), conjunto RF-08 (INC-M01-07-43, INC-M01-09-043, INC-M01-21-041,
     TC-M01-044).
   - **Media:** INC-M01-05-035, INC-M01-08-38, INC-M01-16-057, INC-M01-02-71,
     hallazgos RF-09 (TC-050/054/058), RF-14 (TC-091/092).
   - **Baja:** hallazgos de rendimiento (TC-M01-127, TC-M01-049).
3. **Criterio de aceptación del módulo:** RF-08 y RF-13 pasan a ✅ Aprobado tras
   corregir y reejecutar sus casos rechazados; el resto de RF con ⚠️ se aceptan
   con los hallazgos abiertos registrados como deuda conocida.
4. **Retorno esperado de Desarrollo:** por cada incidencia, rama/PR de corrección
   y confirmación de despliegue en TEST para que QA ejecute la retroprueba.
5. **Acciones internas de QA antes/durante el ciclo de corrección:** resolver los
   4 casos de la sección 4.C, consolidar la evidencia de TC-M01-109 y formalizar
   como incidencias los hallazgos de 4.B que Desarrollo confirme.

---

## 6. Control del documento

| Versión | Fecha | Autor | Cambios |
|---|---|---|---|
| 1.0 | 2026-09-08 | Equipo QA | Versión inicial — corte al 2026-09-08 |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
