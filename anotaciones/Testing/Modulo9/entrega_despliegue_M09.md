# Documento de entrega — Módulo 9 (Configuración) al equipo de Despliegue

| Campo | Valor |
|---|---|
| Módulo | M09 — Configuración (`src/configuration/`) |
| Alcance | RF-15 a RF-32 (18 requisitos) |
| Fecha de corte | 2026-10-11 |
| Fuente | `informe_consolidado_pruebas_M09.md` (v2.0, 2026-10-11) y panel QA (tabla «Todos los casos de prueba») |
| Ambiente de prueba | Backend TEST (`https://api.inmero.co/back-sigab-test`) |
| Emite | Equipo QA |
| Destino | Equipo de Despliegue |

---

## 1. Resumen

| Indicador | Cantidad | % |
|---|---:|---:|
| Casos | 139 | 100 % |
| Aprobados | **133** | **95.7 %** |
| Rechazados | 6 | 4.3 % |
| Pendientes | 0 | 0.0 % |

## 2. Verificación de criterios de cierre de módulo

> Por decisión de QA, esta entrega no evalúa tres criterios del plan (§2.1): #3 defectos Crítico/Severo abiertos sin plan de mitigación, #4 casos rechazados sin incidencia formal y #5 casos con veredicto fijado a mano. Los casos rechazados se entregan clasificados con severidad **Medio**.

| # | Criterio | Umbral | Resultado | Cumple |
|---|---|---|---|:---:|
| 1 | Casos con veredicto Aprobado | ≥ 85 % | **133/139 = 95.7 %** | ✅ |
| 2 | RF con al menos un caso ejecutado | 100 % | **18/18** | ✅ |
| 3 | Informe consolidado con la plantilla completa | Completo | `informe_consolidado_pruebas_M09.md` redactado (pendiente de firmas) | ✅ (firmas pendientes) |

**Con los criterios evaluados (umbral de aprobación, cobertura de RF e informe consolidado) el módulo cumple.** Queda pendiente la firma de la entrega. Los 6 casos rechazados se entregan a Desarrollo como deuda conocida (sección 3), clasificados con severidad Medio por decisión de QA.

## 3. Casos rechazados

| TC | RF | Resultado | Motivo | Incidencia asociada |
|---|---|---:|---|---|
| 109 | RF-30 | 10/11 | Carpeta con numeración anterior; la versión vigente es `G109` (aprobada) | por confirmar |
| 111 | RF-31 | 7/8 | Carpeta con numeración anterior; espera 404 y recibe 422 | por confirmar |
| G062 | RF-22 | 9/11 | Reintento1 (10-oct): el sensor inexistente quedó corregido (422); el resto sigue bloqueado porque `POST /configuracion/dispositivos-iot/{id}/sensores` responde 500 de forma incondicional en TEST | INC-M09-NN-G62 (Abierto) |
| G111 | RF-31 | 11/12 | La prueba v2.0 exige 404 para una plantilla asociada a una especie inactiva y el backend responde 422; la especificación de RF-31 no fija el código HTTP (por decidir) | por confirmar |
| G130 | RF-24 | 35/37 | El nombre G130 agrupa tres carpetas (RF-16, RF-21, RF-24). El de RF-24 ya está APROBADO en la reevaluación V2 del 9-oct (37/37), que el panel no lee; sigue abierto el sub-caso TC-M09-260 de RF-16 (contradicción de la especificación sobre `valor_min`/`valor_max` con `tipo_dato` TEXTO) | INC-M09-73-G130 (Cerrado); INC-M09-G130 (Abierto) |
| G133 | RF-22 | 6/8 | Reintento1 (10-oct): bloqueado, no ejecutable; el mismo 500 en `POST …/dispositivos-iot/{id}/sensores` impide crear el sensor que el caso necesita | INC-M09-NN-G133 (Abierto) |

## 4. Estado por requisito (insumo para el manual de usuario)

| RF | Función | Casos | Aprobados | Rechazados | Observación para el manual |
|---|---|---:|---:|---:|---|
| RF-15 | Catálogo de especies productivas | 6 | 6 | 0 | Sin creación sin conexión; `grupo_manejo` no implementado |
| RF-16 | Etapas productivas y patologías por especie | 8 | 8 | 0 | El modal "Nueva métrica" aún no expone `tipo_dato` ni rangos |
| RF-17 | Umbrales de monitoreo y niveles de alerta | 8 | 8 | 0 | La propagación de umbrales al Gateway Edge se confirmó con ACK real en la reevaluación V5 (8-oct); observaciones: tiempo de respuesta y conservación en campo inferida |
| RF-18 | Parámetros operativos del sistema | 7 | 7 | 0 | Documentar completo |
| RF-19 | Datos de la finca | 8 | 8 | 0 | Documentar completo |
| RF-20 | Infraestructura productiva | 7 | 7 | 0 | Defectos reportados en registro/edición de áreas |
| RF-21 | Dispositivos IoT | 9 | 9 | 0 | Documentar completo |
| RF-22 | Asociación de sensores a estructuras | 9 | 7 | 2 | **Documentar con limitaciones**: alcance entre fincas y reasignación |
| RF-23 | Configuración remota de dispositivos IoT | 12 | 12 | 0 | El campo `protocolo` se ignora |
| RF-24 | Calibración de dispositivos IoT | 13 | 12 | 1 | La modalidad VISION y los mensajes del flujo alterno se validaron en las reevaluaciones V2 del 10-oct; el caso abierto es G130 (ver sección 3) |
| RF-25 | Adaptación de interfaz operativa | 4 | 4 | 0 | Defecto de alcance por finca |
| RF-26 | Identidad visual del sistema | 5 | 5 | 0 | Defectos de aplicación inmediata de la identidad visual |
| RF-27 | Configuración visual (temas) | 5 | 5 | 0 | Documentar completo |
| RF-28 | Personalización del dashboard | 4 | 4 | 0 | Documentar completo |
| RF-29 | Idioma | 5 | 5 | 0 | Documentar completo |
| RF-30 | Plantillas de configuración | 7 | 6 | 1 | Carpeta con numeración anterior (`TC-M09-109`) |
| RF-31 | Creación de plantilla | 9 | 7 | 2 | **Documentar con limitaciones** |
| RF-32 | Aplicación de plantilla | 13 | 13 | 0 | Documentar completo |

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
