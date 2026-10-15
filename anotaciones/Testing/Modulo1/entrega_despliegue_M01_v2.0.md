# Documento de entrega — Módulo 1 (Identidad y Acceso) al equipo de Despliegue — v2.0

| Campo | Valor |
|---|---|
| Módulo | M01 — Identidad y Acceso (`src/identity_access/`) |
| Alcance | RF-01 a RF-14 (14 requisitos) |
| Fecha de corte | 2026-10-12 |
| Fuente | `informe_consolidado_pruebas_M01_v2.0.md` (v2.0, 2026-10-12) y panel QA (tabla «Todos los casos de prueba») |
| Ambiente de prueba | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Emite | Equipo QA |
| Destino | Equipo de Despliegue |

---

## 1. Resumen

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 141 | 100 % |
| Aprobados | **140** | **99.3 %** |
| Rechazados | 1 | 0.7 % |
| Pendientes | 0 | 0.0 % |

## 2. Verificación de criterios de cierre de módulo

> Por decisión de QA, esta entrega no evalúa tres criterios del plan (§2.1): #3 defectos Crítico/Severo abiertos sin plan de mitigación, #4 casos rechazados sin incidencia formal y #5 casos con veredicto fijado a mano. Los casos rechazados se entregan clasificados con severidad **Medio**.

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **140/141 = 99.3 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **14/14** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | `informe_consolidado_pruebas_M01_v2.0.md` redactado (pendiente de firmas) | ✅ (firmas pendientes) |

**Con los criterios evaluados (umbral de aprobación, cobertura de RF e informe consolidado) el módulo cumple.** Queda pendiente la firma de la entrega. Los 1 casos rechazados se entregan a Desarrollo como deuda conocida (sección 3), clasificados con severidad Medio por decisión de QA.

## 3. Casos rechazados

| TC | RF | Resultado | Motivo | Incidencia asociada |
|---|---|---:|---|---|
| 102 | RF-01 | 5/6 | Prueba extrema de pérdida de conexión: el reintento de registro tras reconectar (CP-05) recibe 400 `CAPTCHA_INVALIDO`. El backend TEST valida el reCAPTCHA con Google (comportamiento correcto del producto) y QA no dispone de un token de prueba aceptado en TEST; 5 de 6 comprobaciones pasan | INC-M01-10-11 (Abierto) |

### Casos bloqueados y dependencias

Un caso del módulo no se pudo completar:

| TC | RF | Causa del bloqueo | Qué hace falta |
|---|---|---|---|
| M01-102 | RF-01 | El paso final (reintento de registro tras reconectar) requiere que el backend TEST acepte un token de reCAPTCHA. TEST valida el token con el servicio de Google, y QA no dispone de un token aceptado. No depende de otro módulo: es una configuración de TEST | Que Despliegue configure las claves de prueba de reCAPTCHA en TEST; con eso QA reejecuta el caso |

## 4. Estado por requisito (insumo para el manual de usuario)

| RF | Función | Casos | Aprobados | Rechazados | Observación para el manual |
|---|---|---:|---:|---:|---|
| RF-01 | Registro de usuarios | 20 | 19 | 1 | El registro exige reCAPTCHA; en TEST faltan las claves de prueba (caso M01-102 pendiente de reejecución) |
| RF-02 | Autenticación de usuarios | 13 | 13 | 0 | Documentar completo |
| RF-03 | Gestión de roles | 8 | 8 | 0 | Documentar completo |
| RF-04 | Gestión de permisos | 7 | 7 | 0 | Documentar completo |
| RF-05 | Edición de datos de usuario | 6 | 6 | 0 | Documentar completo |
| RF-06 | Gestión de cuentas de usuario | 9 | 9 | 0 | Documentar completo |
| RF-07 | Cambio de contraseña | 12 | 12 | 0 | Documentar completo |
| RF-08 | Recuperación de contraseña | 13 | 13 | 0 | Documentar completo |
| RF-09 | Restablecimiento de contraseña | 12 | 12 | 0 | Documentar completo |
| RF-10 | Historial de acceso y auditoría | 14 | 14 | 0 | Documentar completo |
| RF-11 | Visualización de usuarios (listado) | 6 | 6 | 0 | Documentar completo |
| RF-12 | Visualización de detalle de usuario | 4 | 4 | 0 | Documentar completo |
| RF-13 | Visualización de perfil propio | 5 | 5 | 0 | Documentar completo |
| RF-14 | Notificar a los usuarios | 12 | 12 | 0 | Documentar completo |

## 5. Decisión de liberación a `main`

Marque la opción que aplique y firme:

- [ ] **Liberación certificada por QA** — con los criterios evaluados cumplidos; requiere las firmas de esta entrega.
- [ ] **Liberación con condiciones definidas por Coordinación**: ________________________________________________

Si se autoriza, Despliegue puede programar el despliegue a `main` y el equipo de documentación puede iniciar el manual de usuario con las observaciones de la sección 4. Los RF marcados «con limitaciones» deben documentarse indicando la limitación conocida.

## 6. Firmas de entrega

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Coordinación / PM (excepción) | | | |
| Equipo de Despliegue (recibido) | | | |
