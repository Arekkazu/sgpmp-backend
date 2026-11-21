# Auditoría de criterio de aceptación — RF-55.1 / CU-02 / TC-M03-076

Fecha de esta revisión: 2026-10-30 (actualización con **RF-55 versión 2.0**).  
Alcance documental. **No** se modificó código, pruebas, evidencias, PASS offline ni informes del 25 de octubre.

Firmware de referencia: `qa/rf55-validation-e618a75`, commit `e618a75`.

Convención: el texto entre comillas es cita de un archivo local o, en §2.0, el **contenido de RF-55 v2.0 aportado para esta actualización**. No se inventan números de línea.

---

## 1. Documentos consultados

### 1.1 RF-55 versión 2.0 (esta actualización)

Se buscó de nuevo en el workspace (`integrador`, `anotaciones/Requerimientos`, worktrees, respaldos) un archivo titulado o equivalente a `Especificacion-Requerimientos-Modulo3` / ficha **RF-55 v2.0**. **El fichero no está versionado aquí**; no hay PDF/Markdown/xlsx con paginación o líneas citables.

El contenido de RF-55 v2.0 usado abajo es el **comunicado en la solicitud de actualización de auditoría** (2026-10-30). Hasta que ese documento se copie al repositorio, **no hay sección/página/línea exacta que citar**. No se fabrican referencias numéricas.

Cuando el archivo exista en disco, sustituir las etiquetas «RF-55 v2.0 — cláusula N» por la sección real.

### 1.2 Copias locales (sin cambio respecto a la auditoría previa)

Script e informe QA 076; `rf55_preparacion.py`; INC-M03-111, INC-M03-118, INC-M03-108; CURLs/gaps CU-02 (RF-56); API M03; CONTRATO Edge; DTO `RecibirEventoEdgeDTO`.

### 1.3 Siguen ausentes en disco

Matriz G37–G64; `PLAN_RF55_00_CONTEXTO_Y_CONTRATOS.md`; `M03-SPLIT.md`; xlsx Drive.

---

## 2. Evidencias textuales de RF-55 v2.0

Cláusulas incorporadas (paráfrasis autorizada de la actualización; **no** son líneas de un archivo local):

| Id | Contenido de RF-55 v2.0 |
|---|---|
| C1 | RF-55.1 es el procesamiento básico por umbrales y es **obligatorio**. |
| C2 | El procesamiento Edge genera **eventos estructurados**. |
| C3 | La **fase 5** contempla las categorías NORMAL, DESVIACIÓN_SIMPLE y DESVIACIÓN_COMPUESTA. |
| C4 | Estructura mínima del evento: `id_evento`, `sensor_id`, `tipo_evento`, `variables_involucradas`, `severidad`, timestamps, `origen`, `estado_conectividad`. |
| **CA-6** | Exige **generar un evento** cuando se detecte una condición **normal o anómala**. |
| **CA-8** | Exige **enviar automáticamente el evento al sistema central** cuando hay conectividad. |
| **CA-10** | Exige **persistencia local de eventos** para trazabilidad. |
| C8 | El flujo indica **RF-56/RF-57 con conectividad** y **RF-54 sin conectividad**. |

MQTT **no** aparece en estas cláusulas. El envío de CA-8 es al **sistema central** (en la arquitectura actual: broker → RF-56). Confundir CA-8 con “debe usarse MQTT” sería añadir un medio que el RF no nombra.

Cita previa INC-M03-111 (archivo local), no v2.0:

> "NORMAL: valor dentro de rango" y "DESVIACIÓN SIMPLE: una variable fuera de rango"

Esa cita **no** sustituye CA-6/CA-8.

---

## 3. CU-02 y 4. TC-M03-076 (sin cambio de hechos)

CU-02 en anotaciones M03 = **RF-56** (ingesta/paquete). G43 etiqueta RF-55.1 / CU-02.

QA 076: “evento NORMAL” en el **nodo**; no dice “POST”. Con RF-55 v2.0, “evento” se alinea con **evento estructurado** (C2, C4, CA-6), no con una fila de historial sin `id_evento` de evento publicado.

---

## 5. Comparación requisito v2.0 vs firmware `e618a75`

No se iguala `registrar_normal` a CA-6.

| Función | RF-55 v2.0 | Firmware (NORMAL / 076) |
|---|---|---|
| Detección de condición NORMAL | Fase 5 incluye NORMAL (C3); CA-6 parte de “cuando se detecte” | Sí: banda `normal` identificada (`evaluar_simple` retorna `None` **porque** es normal, no por error) |
| Clasificación NORMAL | Categoría NORMAL (C3) | Sí, en historial: `clasificacion=NORMAL` |
| Generación de **evento estructurado** NORMAL | C2, C4, **CA-6** (normal **o** anómala) | **No.** No hay `EventoEdge` / `a_payload` / `id_evento` de evento. `evaluar_simple` → `None` |
| Persistencia local | **CA-10** (eventos) | Hay fila historial `LOCAL` **sin** evento estructurado. Telemetría sí se encola. **No** es persistencia de un evento CA-4/C4 |
| Enrutamiento **con** conectividad | **CA-8** + flujo RF-56/RF-57 (C8) | **No aplica:** no existe evento que enviar. FakeLink: cero mensajes `…/evento` |
| Enrutamiento **sin** conectividad | Flujo RF-54 (C8) | **No aplica** para NORMAL: no entra `KIND_EVENTO` al buffer |

Valores fuera de `[valor_min, valor_max]` (077/078): sí hay evento estructurado `DESVIACION_SIMPLE` y encolado. Eso **no** cubre CA-6 para la condición **normal** (076).

Contrato firmware (`CONTRATO_EVENTO_EDGE.md` §1 / §3): “`NORMAL` nunca se emite”. Eso **choca** con CA-6 v2.0; es decisión de implementación, no el RF v2.0.

---

## 6. CA-6 y CA-8 contra el firmware (TC-M03-076)

| Criterio | Exigencia (v2.0) | Firmware | Veredicto 076 |
|---|---|---|---|
| CA-6 | Generar evento ante condición **normal o** anómala | Condición normal **sin** evento estructurado | **Incumplimiento** (076) |
| CA-8 | Enviar el evento al sistema central si hay conectividad | No hay evento NORMAL que enviar | **Incumplimiento** (076), consecuencia de CA-6 |
| CA-10 | Persistencia local de **eventos** | Historial de clasificación, no evento C4 | **No equivalente** a CA-10 para NORMAL |

RF-55.1 obligatorio (C1): el motor de umbrales **existe** para clasificar; el hueco auditado es el **flujo de evento NORMAL**, no la ausencia total de RF-55.1.

---

## 7. Contradicciones

1. **RF-55 v2.0 CA-6** (evento también si NORMAL) vs **CONTRATO / INC-M03-108** (NORMAL no se publica).
2. Historial `LOCAL` vs evento mínimo C4 (`id_evento`, `tipo_evento`, …).
3. Etiqueta G43 CU-02 vs CU-02 = RF-56 en anotaciones.
4. PASS offline 076 vs CA-6/CA-8 (no son el mismo objeto de prueba).

---

## 8. Qué falta

- Copiar al repo el PDF/Markdown **RF-55 v2.0** para citar sección/página/línea.
- Decisión de producto si el CONTRATO (no emitir NORMAL) queda derogando CA-6: **no está en esta auditoría**; el RF v2.0, tal como se incorporó, no exceptúa NORMAL.
- Integración real (Raspberry / sistema central): **no ejecutada**; el incumplimiento CA-6 se observa ya en el clasificador (`None` + sin `EventoEdge`).

---

## 9. Conclusión (TC-M03-076)

**El firmware no cumple completamente RF-55 v2.0 en lo evaluado para TC-M03-076.**

- **Cumple (alcance limitado):** detección y clasificación de la banda `normal`; registro en historial local.
- **Incumple CA-6:** no genera el **evento estructurado** NORMAL (C2, C4). El historial `registrar_normal` **no** es ese evento.
- **Incumple CA-8** para 076: sin evento, no hay envío automático al sistema central con conectividad (el medio MQTT es implementación; el fallo es la ausencia de evento, no la ausencia de un broker en la prueba offline).
- **No se declara** incumplimiento de todo RF-55 (p. ej. 077/078, RF-55.2, SLA). Solo 076 / flujo NORMAL.

### PASS offline vs flujo de eventos

Los **PASS offline** demuestran: `evaluar_simple is None`, historial `NORMAL`/`LOCAL`, cero publicación en mock. Eso es **clasificación + política actual de no emitir**.  
**No** demuestran CA-6 ni CA-8. El PASS **no se altera** en esta revisión; **no** equivale a APROBADO del flujo de eventos de RF-55 v2.0.

Recomendación (sin código): el dueño de RF-55 debe o bien (a) implementar evento estructurado NORMAL y su envío (CA-6/CA-8), o (b) emitir un cambio formal al RF/CONTRATO que exceptúe NORMAL de CA-6. Hasta entonces, 076 queda **clasificación offline OK** e **incumplimiento del flujo de eventos** según v2.0.

---

## 10. Cambios de esta revisión documental

- Actualizado únicamente este archivo.
- Informes 25-oct, evidencias, PASS offline, código: **intactos**.
- Pytest / Raspberry / Mosquitto / commit: **no**.
