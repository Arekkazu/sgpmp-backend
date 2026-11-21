# Informe consolidado de pruebas — Módulo 1 (Identidad y Acceso)
## Resumen de resultados y entrega formal a Desarrollo

| Campo | Valor |
|---|---|
| Módulo | M01 — Identidad y Acceso (`src/identity_access/`) |
| Alcance | RF-01 a RF-14 |
| Período de ejecución | 2026-08-28 a 2026-09-13 |
| Fecha de corte del informe | 2026-09-13 (v2.1 — actualiza el corte del 2026-09-08) |
| Ambientes | Backend TEST (`sigab-backendtest-…sslip.io/api-sgpmp-test`) · Frontend TEST (`sigab-frontendtest-…sslip.io`) |
| Herramientas | Newman/Postman (API), Pytest (backend), Cypress (frontend) |
| Casos ejecutados | 141 de 141 (100 %) |
| Equipo QA | Laura Lopez, Daniela Castillo, Juan Manuel, Sebastian, Juan Parra, Juan Hernando |
| Fuente de datos | Panel QA (`qa-dashboard/`), evidencias en `tests/Test_Testing/Test_Modulo1/` (backend) y `testing/test_testing/Modulo1/` (frontend) |

> Los conteos reflejan el estado del repositorio a la fecha de corte. Un caso
> reejecutado después del corte puede cambiar de veredicto. La clasificación de
> los hallazgos **sin incidencia formal** (sección 4.B) es una propuesta de QA y
> debe confirmarse con Desarrollo antes de asignarse.
>
> **Nota de la v2.0:** esta actualización corrige además un defecto del propio
> panel QA (`qa-dashboard/scanner.py`) que, para carpetas de TC con varios
> reportes de reintento (ej. `..._reintento.html` / `..._reintento2.html`),
> podía elegir el intento equivocado — los archivos quedan con mtimes casi
> idénticos tras un `git clone`/checkout en bloque, que no reflejan el orden
> real en que se ejecutaron los reintentos. El escáner ahora prioriza el
> archivo con el sufijo de versión más alto (`reintento2` > `reintento`,
> `v2.0` > sin sufijo, `DEFINITIVO` > `parteN`) antes de usar mtime como
> desempate. Esto movió varios casos de Rechazado a Aprobado (validado con
> evidencia de contenido, no solo con el cambio de veredicto) y subió el %
> de aprobación del módulo de 82.3 % (corte 08-09) a 90.8 % (corte 13-09).

---

## 1. Resumen ejecutivo

| Indicador | Cantidad | % |
|---|---:|---:|
| **Total de casos** | 141 | 100 % |
| Aprobados | 129 | 91.5 % |
| Rechazados | 12 | 8.5 % |
| Pendientes de ejecución | 0 | 0 % |

```
Aprobado    █████████████████████████████████████████████░░░  91.5%
Rechazado   █████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   8.5%
```

**Cumple el umbral de aceptación (≥ 85 % de casos Aprobados sobre el total
planeado). Veredicto del módulo: APROBADO CON RESERVAS** — el umbral global
se cumple y RF-08 ya pasó a conforme tras corrección y reejecución; la
reserva restante se concentra en un único requisito:

- **RF-13 (Visualización de perfil propio)** — 40 % de aprobación (2/5), sin
  cambios desde el corte anterior. El defecto de frontend que impide abrir el
  detalle de perfil (`/usuarios/undefined/detalle`, la tabla de usuarios no
  propaga `id_usuario`) sigue sin corregir — ver INC-M01-11-87/89.

Todos los demás requisitos que antes tenían reserva (RF-01, RF-02, RF-03,
RF-04, RF-07, RF-08, RF-09, RF-10, RF-14) ya están en ✅ Aprobado o ⚠️
Aprobado con observaciones acotadas — ver el detalle por RF en la sección 2.

**INC-M01-03-119 (Crítico) ya se reverificó con éxito** (retest v2.0,
2026-09-13): `DELETE /roles/{id}` responde 200 y elimina de verdad un rol sin
usuarios asociados — ver TC-M01-119 en la sección 4.E. Durante esa
reverificación se descubrió un **defecto nuevo y no relacionado**,
**INC-M01-24-500-nombre-rol**: crear un rol cuyo nombre empieza exactamente
con `"Auxiliar de Campo"` responde 500 en vez de 201/409, reproducido 10/10
veces. Se entrega a Desarrollo como incidencia nueva — ver sección 4.A.

Un conjunto de hallazgos Medio/Bajo queda por formalizar/triar (sección
4.B). Tres casos siguen bloqueados por limitaciones del ambiente de pruebas
(no constituyen defecto de producto). El caso que estaba pendiente de
consolidar evidencia (TC-M01-109) ya se resolvió: la evidencia frontend fue
localizada y el caso pasó a Aprobado (7/7).

> **Nota sobre el escáner de reintentos:** el % de aprobación subió de 82.3 %
> (corte 08-09) a 90.8 % principalmente porque `qa-dashboard/scanner.py`
> elegía por error el reporte de un intento anterior en varios TC con
> reintentos (ver nota de la v2.0 arriba), no porque se hayan ejecutado
> pruebas nuevas entre el 08-09 y el 13-09. Los reintentos que cambiaron de
> veredicto ya estaban ejecutados y con evidencia guardada desde antes del
> corte anterior; el informe del 08-09 simplemente no los estaba leyendo bien.

---

## 2. Resultados por requisito

| RF | Título | Casos | Aprob. | Rech. | Pend. | % Aprob. | Veredicto |
|----|--------|------:|------:|-----:|-----:|--------:|-----------|
| RF-01 | Registro de usuarios | 20 | 19 | 1 | 0 | 95 % | ⚠️ Aprobado con observaciones |
| RF-02 | Autenticación de usuarios | 13 | 13 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-03 | Gestión de roles | 8 | 8 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-04 | Gestión de permisos | 7 | 6 | 1 | 0 | 86 % | ⚠️ Aprobado con observaciones |
| RF-05 | Edición de datos de usuario | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-06 | Gestión de cuentas de usuario | 9 | 9 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-07 | Cambio de contraseña | 12 | 12 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-08 | Recuperación de contraseña | 13 | 12 | 1 | 0 | 92 % | ⚠️ Aprobado con observaciones |
| RF-09 | Restablecimiento de contraseña | 12 | 10 | 2 | 0 | 83 % | ⚠️ Aprobado con observaciones |
| RF-10 | Historial de acceso y auditoría | 14 | 12 | 2 | 0 | 86 % | ⚠️ Aprobado con observaciones |
| RF-11 | Visualización de usuarios (listado) | 6 | 6 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-12 | Visualización de detalle de usuario | 4 | 4 | 0 | 0 | 100 % | ✅ Aprobado |
| RF-13 | Visualización de perfil propio | 5 | 2 | 3 | 0 | 40 % | ❌ No conforme |
| RF-14 | Notificar a los usuarios | 12 | 10 | 2 | 0 | 83 % | ⚠️ Aprobado con observaciones |

**RF-08 y RF-09** mejoraron sustancialmente respecto al corte del 08-09 (54 %
y 67 % → 92 % y 83 %): los defectos de canal lateral temporal (INC-M01-21-041),
rate-limit prematuro (INC-M01-12-107) y bloqueo por fuerza bruta en
restablecimiento (INC-M01-17-058) tienen evidencia de retest exitoso.
**RF-03** pasa a ✅ Aprobado: INC-M01-03-119 (Crítico) se reverificó con éxito
el 2026-09-13 (ver 4.E). El defecto nuevo descubierto durante esa
reverificación (INC-M01-24-500-nombre-rol) no afecta el veredicto de RF-03
porque no corresponde a ningún caso planeado del módulo — se entrega a
Desarrollo como hallazgo aparte (sección 4.A).

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

> Esta sección se reconcilió con el registro completo de `qa-dashboard/incidencias.csv`
> (22 incidencias de M01). El corte del 08-09 solo listaba 9; varias Severo no
> estaban aquí todavía. `incidencias.csv` en sí quedó desactualizado en varios
> campos "Estado" (sigue en "Abierto" pese a existir retest exitoso con evidencia
> — ver columna Retest); **queda como acción de QA actualizarlo** (ver sección 5).

| Incidencia | RF | Caso(s) | Severidad | Estado formal (`incidencias.csv`) | Retest (corte 13-09) | Descripción | Documento de análisis |
|---|---|---|---|---|---|---|---|
| **INC-M01-03-119** | RF-03 | TC-M01-119 | Crítico | **Corregido — retest exitoso 2026-09-13** | ✅ Aprobado — TC-M01-119 v2.0 crea su propio rol único (patrón TC-114/122/123/124, ya no depende del fixture fijo "Auxiliar de Campo"), lo elimina con `DELETE /roles/{id}` → **200**, y confirma que desaparece del listado | `DELETE /roles/{id}` devolvía 500 para cualquier rol no protegido; el rol y sus permisos permanecían en BD | `inc_m01_03_119_eliminar_rol.md`, `inc_m01_03_119_ci_alembic_test_db.md`, `TC-M01-119/test_tc_m01_119_v2.py` |
| **INC-M01-24-500-nombre-rol** *(nueva, descubierta el 13-09)* | RF-03 | — (fuera del árbol de TC planeados) | Crítico | **Abierto — reportada a Desarrollo** | ❌ Reproducido 10/10 (curl + Python `requests`, 3 logins distintos, control intercalado) | `POST /roles/` responde 500 `ERROR_INTERNO` cuando `nombre_rol` empieza exactamente con `"Auxiliar de Campo"` (el nombre del rol semilla original de INC-M01-03-119, ya eliminado). Variantes de mayúsculas/espaciado no lo reproducen — apunta a una comparación de string exacta mal manejada, posible residuo de la eliminación del rol id_rol=10. **Nota abierta:** la reproducción vía el script de pytest de esta misma carpeta no dispara el 500 (sí lo dispara el mismo código fuera de pytest); la causa de esa discrepancia no se identificó y se deja para que Desarrollo la investigue con acceso a logs/DB | `INC-M01-24-500-nombre-rol/Resultados/INC-M01-24_evidencia-v2.0.md` |
| **INC-M01-06-024** | RF-02 | TC-M01-024 | Severo | Abierto *(desactualizado)* | ✅ Aprobado — retest exitoso 2026-09-11 | `get_db()` no reintentaba la conexión a PostgreSQL 3× ni traducía el fallo; ante caída de BD respondía 500 en vez de 503. Ahora reintenta 3 veces y traduce a 503 `BD_NO_DISPONIBLE` | `inc_m01_06_024_errores_bd.md` |
| **INC-M01-10-11** | RF-01 | TC-M01-011 | Severo | Abierto *(desactualizado)* | ✅ Aprobado — reevaluación técnica 2026-09-10, HTTP 400 confirmado en ambos escenarios (token vacío / inválido) | El backend no validaba `captcha_token` en el servidor (aceptaba registro con token vacío/inválido, HTTP 201) | `TC-M01-011_REEVALUACION_20260910.md` (frontend) |
| **INC-M01-12-107** | RF-08 | TC-M01-107 | Severo | Abierto *(desactualizado)* | ✅ Aprobado — retest con evidencia posterior al corte 08-09 | El rate-limit de recuperación de contraseña bloqueaba prematuramente (en la 2ª solicitud, cupo 2/3) en vez de solo al exceder 3/hora | `qa-dashboard/incidencias.csv` |
| **INC-M01-17-058** | RF-09 | TC-M01-058 | Severo | Abierto *(desactualizado)* | ✅ Aprobado — retest con evidencia posterior al corte 08-09 | `POST /contrasena/restablecer` no bloqueaba tras 5 intentos consecutivos con token inválido (sin fuerza bruta) | `qa-dashboard/incidencias.csv` |
| **INC-M01-21-041** | RF-08 | TC-M01-041 | Severo | Abierto *(desactualizado)* | ✅ Aprobado — retest con evidencia posterior al corte 08-09 | Canal lateral temporal: el envío SMTP síncrono para correos existentes añadía ~3.8 s, permitiendo inferir si un correo está registrado | `inc_m01_21_041_rf08_tiempo_recuperacion.md` |
| **INC-M01-23-045** | RF-02 (rel. RF-06) | — | Severo | Abierto | Sin caso TC dedicado en el árbol de pruebas — **pendiente de verificación explícita** | Bloqueo de fuerza bruta (5 intentos) sobre una cuenta Administrador respondía 500 en vez de 423 (trigger de protección de rol no distingue el propio mecanismo de bloqueo automático) | `qa-dashboard/incidencias.csv` |
| **INC-M01-05-035** | RF-07 | TC-M01-035 | Medio | Abierto *(desactualizado)* | ✅ Aprobado — retest V2.0 verificado (0 fallidas) | `PUT /contrasena/usuarios/{id}` aceptaba como nueva contraseña la actual (200) en vez de rechazarla (409); faltaba la migración del trigger de no-reutilización | `inc_m01_05_035_rf07_reutilizacion_contrasena.md` |
| **INC-M01-08-38** | RF-07 | TC-M01-038 | Medio | Abierto *(desactualizado)* | ✅ Aprobado — retest 2026-09-12 contra `origin/test` (SAVEPOINT), 2/2 pasaron | El `rollback` ante fallo de invalidación de sesiones deshacía también el cambio de contraseña ya aplicado; la excepción se propagaba sin 500 controlado | `inc_m01_08_38_rf07_fallo_invalidacion.md`, `tc_m01_038_retest.py` |
| **INC-M01-16-057** | RF-09 | TC-M01-057 | Medio | Abierto *(desactualizado)* | ✅ Aprobado — retest V2.0 verificado | El restablecimiento aceptaba la contraseña actual (200) en vez de rechazarla (409) — mismo gap que INC-M01-05-035, en el flujo de RF-09 | `inc_m01_16_057_rf09_reutilizacion_contrasena.md` |
| **INC-M01-07-43** | RF-08 | TC-M01-043, TC-M01-112 | Medio | Abierto *(desactualizado)* | ✅ Aprobado — retest verificado | El límite de recuperación de contraseña respondía 422 en vez de 429 al excederse (la regla de negocio sí bloqueaba; solo el código HTTP era incorrecto) | `qa-dashboard/incidencias.csv` |
| **INC-M01-09-043** | RF-08 | TC-M01-043 | Medio | Abierto *(desactualizado)* | ✅ Aprobado — retest verificado | El límite de 3 solicitudes/hora por IP solo se aplicaba cuando el correo existía; con correos inexistentes nunca bloqueaba | `qa-dashboard/incidencias.csv` |
| **INC-M01-02-71** | RF-10 | TC-M01-071 | Medio | Abierto | ❌ Sigue Rechazado | La paginación por offset del historial de auditoría devuelve un registro duplicado en el borde entre páginas cuando se insertan eventos durante la navegación | `qa-dashboard/incidencias.csv` |
| **INC-M01-22-074** | RF-10 | TC-M01-074 | Medio | Abierto | ❌ Sigue Rechazado | El botón "Exportar CSV" queda fuera del viewport a 1280px de ancho; no alcanzable con un clic real | `qa-dashboard/incidencias.csv` |
| **INC-M01-11-87/89** | RF-13 | TC-M01-087, TC-M01-089 | Media | Abierto | ❌ Sigue Rechazado — **sin cambios desde el 08-09** | El listado de usuarios no propaga `id_usuario` a la fila de la tabla; el frontend llama `/usuarios/undefined/detalle` → HTTP 400. Bloquea completamente RF-13 | `qa-dashboard/incidencias.csv` |

**Único punto abierto de criterio de Crítico/Severo:** INC-M01-24-500-nombre-rol
(Crítico, nueva, sin plan de mitigación de Desarrollo todavía — reportada el
13-09). No bloquea ningún caso planeado del módulo (no hay TC que dependa de
crear un rol con ese nombre exacto), pero sí es un defecto de producto
Crítico real y reproducido, así que debe tratarse con la misma prioridad que
cualquier otro hallazgo Crítico entregado a Desarrollo. INC-M01-03-119 ya
está cerrado con retest exitoso. INC-M01-23-045 (Severo) sigue sin caso de
prueba propio en el árbol — se recomienda crear uno antes de la
certificación final.

### 4.B — Hallazgos sin incidencia formal (pendientes de triar con Desarrollo)

> TC-M01-044, TC-M01-049, TC-M01-058 y TC-M01-092 salieron de esta tabla: pasaron
> a Aprobado con evidencia de retest (092 se referencia además en la fila
> INC-M01-23-045 de 4.A, pendiente de un caso de prueba dedicado). TC-M01-074 y
> TC-M01-087/089 se formalizaron como incidencias — ver 4.A.

| Caso | RF | Capa | Observado | Clasificación propuesta (QA) |
|---|---|---|---|---|
| TC-M01-050 | RF-09 | backend | Restablecimiento responde **422** donde se esperaba **202** | Triage — posible defecto o ajuste de contrato de prueba |
| TC-M01-054 | RF-09 | backend | Varias aserciones: 422/401 donde se esperaban 202/409 (incluye reutilización de token) | Triage |
| TC-M01-127 | RF-04 | backend | Tiempo de respuesta 427 ms / 226 ms por encima del umbral de 200 ms | Rendimiento (RNF) |
| TC-M01-091 | RF-14 | frontend | La bandeja muestra "No tienes notificaciones" aunque la API sí devuelve el evento | Defecto de producto (frontend) |

### 4.C — Casos bloqueados / limitaciones del ambiente de pruebas

*No constituyen defecto de producto; requieren acción de QA o de Implementación.*

| Caso | RF | Causa | Acción |
|---|---|---|---|
| TC-M01-102 | RF-01 | **INC-M01-13** — el backend TEST exige la firma real de reCAPTCHA v2 y rechaza tokens simulados (comportamiento correcto del producto). QA no puede completar el reintento de registro tras reconexión | Coordinar con Implementación un bypass de CAPTCHA para TEST o un token de prueba válido |
| TC-M01-040 | RF-08 | El script conserva el placeholder `PEGAR_AQUI_EL_TOKEN_DEL_CORREO` sin reemplazar → 401 por token inválido | Corregir la automatización (QA) y reejecutar |
| TC-M01-088 | RF-13 | El login de la cuenta de prueba responde **403** (cuenta desactivada o sin permiso) | Aprovisionar/revisar la cuenta de prueba (QA) y reejecutar |
| TC-M01-094 | RF-14 | 401 de autenticación + error de JavaScript en el propio script (`Cannot read properties of undefined`) | Revisar setup y script (QA); reejecutar |

### 4.D — Pendiente de ejecución

Ninguno. TC-M01-109 (la única pendiente al corte del 08-09) ya tiene veredicto
— ver 4.E.

### 4.E — Corregido y reverificado durante la campaña (histórico)

| Incidencia / Caso | RF | Caso | Severidad | Resultado |
|---|---|---|---|---|
| INC-M01-01-01 | RF-01 | TC-M01-002 | Crítico | `GET /usuarios/activar/{token}` → 500 `AUDITORIA_OBLIGATORIA_FALLIDA`. **Corregido el 2026-08-29**; retest exitoso (HTTP 200, `resultado_TC-M01-02_reintento2_20260829.html`) |
| TC-M01-109 | RF-01 | TC-M01-109 | — | Prueba extrema de pérdida de conexión intermitente. La evidencia frontend (Fase B, 2026-09-06, Sebastián) ya se consolidó en `Modulo1/RF-01/TC-M01-109/`; el escáner la lee correctamente ahora — **7/7 checkpoints Aprobado** |
| INC-M01-03-119 | RF-03 | TC-M01-119 | Crítico | `DELETE /roles/{id}` devolvía 500 para cualquier rol no protegido. **Corregido** (PR #62, migración `c4a19e7d2b63`); **retest v2.0 exitoso el 2026-09-13** — 200, el rol eliminado ya no aparece en el listado (`test_tc_m01_119_v2.py`) |

---

## 5. Condiciones de la entrega

1. **Se entrega a Desarrollo** el conjunto de defectos abiertos de las secciones
   4.A y 4.B con su evidencia asociada. Cada incidencia formal tiene su
   documento de análisis con causa raíz; los hallazgos de 4.B requieren una
   reunión de triage para confirmar clasificación, severidad y responsable.
2. **Prioridad sugerida de corrección (actualizada al 13-09, v2.1):**
   - **Alta:** INC-M01-24-500-nombre-rol (Crítico, nueva — ver 4.A),
     INC-M01-11-87/89 (RF-13 frontend, sigue bloqueando el requisito
     completo), INC-M01-23-045 (crear caso de prueba dedicado y verificar).
   - **Media:** INC-M01-02-71, INC-M01-22-074, hallazgos RF-09 (TC-050/054),
     TC-M01-091 (RF-14).
   - **Baja:** hallazgo de rendimiento TC-M01-127 (RNF).
   - **Cerrado:** INC-M01-03-119 (retest exitoso 2026-09-13).
3. **Criterio de aceptación del módulo:** el umbral global (≥ 85 % Aprobado) ya
   se cumple (91.5 %) y RF-08 y RF-03 ya pasaron a conforme. **Reserva
   restante: RF-13** pasa a ✅ Aprobado tras corregir y reejecutar
   TC-M01-087/089; el resto de RF con ⚠️ se acepta con los hallazgos abiertos
   registrados como deuda conocida. INC-M01-24-500-nombre-rol (Crítico, nueva)
   todavía no tiene plan de mitigación de Desarrollo — es el único punto
   abierto del criterio de Crítico/Severo al 13-09.
4. **Retorno esperado de Desarrollo:** por cada incidencia, rama/PR de
   corrección y confirmación de despliegue en TEST para que QA ejecute la
   retroprueba; para RF-13, confirmación explícita de que el endpoint de
   listado ya expone `id_usuario`.
5. **Acciones internas de QA antes de la certificación final:**
   - Resolver los 3 casos restantes de la sección 4.C (TC-M01-040, TC-M01-088,
     TC-M01-094; TC-M01-102 depende de que Implementación provea un token de
     reCAPTCHA de prueba válido).
   - Actualizar `qa-dashboard/incidencias.csv`: agregar INC-M01-24-500-nombre-rol
     y marcar INC-M01-03-119 como Corregido; 10 filas más siguen en "Abierto"
     pese a tener retest exitoso con evidencia (ver columna "Retest" de 4.A).
   - Crear el caso de prueba dedicado para INC-M01-23-045.
   - Investigar con Desarrollo por qué la reproducción de
     INC-M01-24-500-nombre-rol vía pytest no dispara el 500 que sí se observa
     fuera de pytest (ver nota en `INC-M01-24-500-nombre-rol/Resultados/`).
   - Formalizar como incidencias los hallazgos de 4.B que Desarrollo confirme.

---

## 6. Control del documento

| Versión | Fecha | Autor | Cambios |
|---|---|---|---|
| 1.0 | 2026-09-08 | Equipo QA | Versión inicial — corte al 2026-09-08 |
| 2.0 | 2026-09-13 | Equipo QA | Corte actualizado al 2026-09-13. Corrige un defecto de `qa-dashboard/scanner.py` (selección del reporte equivocado entre reintentos con mtime casi idéntico) que subestimaba el % de aprobación (82.3 % → 90.8 % real). Reconcilia 4.A con `incidencias.csv` completo (9 → 14 incidencias referenciadas, incluye las Severo que faltaban). Cierra TC-M01-109 (ya no pendiente). RF-08 pasa de No conforme a Aprobado con observaciones; reserva del módulo se reduce a RF-13 e INC-M01-03-119 (verificación bloqueada por ambiente, no por defecto sin plan). |
| 2.1 | 2026-09-13 | Equipo QA | Reverificación en vivo de INC-M01-03-119 contra el backend TEST real (`admin.dev@gmail.com`): `DELETE /roles/{id}` confirmado en 200, retest v2.0 de TC-M01-119 pasa (ya no depende del fixture fijo). RF-03 pasa a ✅ Aprobado (100 %); % del módulo sube a 91.5 % (129/141). Durante la reverificación se descubrió y documentó **INC-M01-24-500-nombre-rol** (Crítico, nuevo): `POST /roles/` con `nombre_rol` que empieza con "Auxiliar de Campo" responde 500, reproducido 10/10 fuera de pytest — único punto abierto del criterio de Crítico/Severo al cierre de esta versión. |

**Firmas de entrega**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM | | | |
