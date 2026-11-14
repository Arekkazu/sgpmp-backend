# TC-M03-G94 — RECHAZADO

## 1. Identificación

Grupo G94; caso TC-M03-185; RF-58/CU04 E4; versión V1; RUN RUN-G94-V1-20261031-090629; ambiente TEST según el RUN; autorización AUT-G94-V1-R3-20261031; rama NO_VERIFICADA; commit NO_VERIFICADO. Node de regeneración v22.15.1; herramientas registradas en [preflight.json](preflight.json): Newman 6.2.2, Cypress 14.5.4, Chrome disponible.

## 2. Resumen ejecutivo y decisión del grupo

**Decisión del caso del grupo:** RECHAZADO. RUN oficial: sí; estado técnico OK. Total 1 caso: aprobados 0, rechazados 1, bloqueados 0 y no concluyentes 0. API-185-01/02 cumplieron; UI-185-01 incumplió el aviso visual exigido.

| Caso | Funcional | Técnico |
|---|---|---|
| TC-M03-185 | RECHAZADO | OK |

## 3. Detalle por caso y comprobaciones API/UI

### TC-M03-185

**Objetivo:** Informar al usuario sin unidades productivas asignadas.

**Precondiciones:** Usuario con sesión válida y sin ninguna granja ni unidad productiva vinculada. Se verificó el detalle del Productor y /usuarios/me tras el PUT dentro del RUN: HTTP 200, cero fincas.

**Pasos:** Preflight, logins, RUN, PUT de fincas vacías, verificación, Newman, perfil posterior, Cypress, DELETE y restitución.

**Entradas:** Productor de QA; IDs originales de fincas 1, 57, 80, 184; área previa 3.

**Esperado literal:** HTTP 200 con arreglos vacíos. La interfaz muestra "No tiene unidades productivas asignadas" y sugiere contactar al administrador; no se devuelve ningún dato de otras granjas ni error interno.

**Observado por API pública:** API-185-01: APROBADO, HTTP 200, total 0 y arreglos vacíos (HTTP 200); API-185-02: APROBADO, HTTP 200, total 0 y arreglos vacíos (HTTP 200).

**Observado por UI:** 1 prueba(s); dashboard HTTP 200; perfil 0 fincas; texto «0 sensores · actualizado 04:06:56 a. m. | Tus fincas aún no tienen sensores. Se registran en Configuración › IoT.»; canario E7 SIN_SENSORES_OBSERVADOS. La captura muestra «Monitoreo en Tiempo Real», «0 sensores · actualizado 04:06:56 a. m.», cinco KPI en 0 (Sensores, Fuera de rango, Cerca del límite, Sin datos y Normales), un bloque de marcador difuminado sin datos y el mensaje sobre registrar sensores en Configuración › IoT.

- **Mensaje requerido:** No aparece «No tiene unidades productivas asignadas».
- **Contacto con el administrador:** No se sugiere; el texto remite a Configuración › IoT.
- **Datos de otras granjas:** Ninguno observado; el canario no registró sensores ajenos.
- **Tarjetas:** El detector marcó false por un bloque de marcador difuminado; la captura no muestra datos de otra granja.
- **Error interno:** No se observó.

**Decisión del caso:** **RECHAZADO.** La API cumplió; la UI no mostró el aviso exigido ni sugirió contactar al administrador; por eso se rechaza el caso.

**Qué falta:** Corregir el estado vacío de usuario sin unidades y acreditarlo en una reevaluación API/UI autorizada; la causa raíz sigue sin confirmar.

| Comprobación | Tipo | Esperado | Observado | HTTP | Estado | Evidencia |
|---|---|---|---|---|---|---|
| API-185-01 | API | HTTP 200; total 0 y arreglos vacíos; sin datos de otras granjas | HTTP 200, total 0 y arreglos vacíos | 200 | APROBADO | [newman/newman-G94.json](newman/newman-G94.json) |
| API-185-02 | API | HTTP 200; total 0 y arreglos vacíos para el área antes asignada; sin datos ajenos | HTTP 200, total 0 y arreglos vacíos | 200 | APROBADO | [newman/newman-G94.json](newman/newman-G94.json) |
| UI-185-01 | UI | «No tiene unidades productivas asignadas»; sugerir contactar al administrador; sin datos ajenos ni error interno | La pantalla cargó y difiere del oráculo visual; 0 sensores · actualizado 04:06:56 a. m. \| Tus fincas aún no tienen sensores. Se registran en Configuración › IoT. | 200 | RECHAZADO | [cypress/UI-185-01.json](cypress/UI-185-01.json), [cypress/g94.cy.js/UI-185-01.png](cypress/g94.cy.js/UI-185-01.png) |

## 4. Incidencias y antecedentes

### INC-M03-185-G94-01 — El usuario sin unidades asignadas ve «Tus fincas aún no tienen sensores…» en lugar del aviso de falta de unidades

- **Esperado:** HTTP 200 con arreglos vacíos. La interfaz muestra "No tiene unidades productivas asignadas" y sugiere contactar al administrador; no se devuelve ningún dato de otras granjas ni error interno.
- **Obtenido:** El perfil del Productor tenía 0 fincas. La UI mostró «0 sensores · actualizado 04:06:56 a. m. | Tus fincas aún no tienen sensores. Se registran en Configuración › IoT.», sin el aviso de falta de unidades ni la sugerencia de contactar al administrador.
- **Evidencia:** [acta Cypress](cypress/UI-185-01.json), [captura real](cypress/g94.cy.js/UI-185-01.png), [Newman](newman/newman-G94.json).
- **Impacto y severidad:** MEDIA: el mensaje engañoso envía al Productor a registrar sensores cuando necesita asignación de unidades; no se observaron datos ajenos ni error interno. El impacto acreditado es esta variante de estado vacío.
- **Equipo inicial:** Desarrollo. La primera discrepancia acreditada está en la presentación UI mientras API-185-01/02 devolvieron HTTP 200 y arreglos vacíos. Esta derivación no atribuye causa raíz.
- **Certeza:** CONFIRMADA para la discrepancia visual en TEST; causa técnica NO CONFIRMADA.
- **Hipótesis por lectura local previa:** `SGPMP-FRONT-END-PWA/src/telemetry/pages/MonitoreoView.tsx:211` usa `t('monitoreoview.sin_sensores_en_tus_fincas')` sin estado específico de usuario sin unidades; `src/shared/i18n/locales/es-CO/telemetry.json:342` define el texto observado. No se verificó qué versión del frontend estaba desplegada en TEST.
- **Ruta de investigación:** Comparar perfil sin fincas, respuesta del dashboard y rama de render del estado vacío; confirmar la versión desplegada y verificar la distinción entre «sin unidades asignadas» y «unidades sin sensores».
- **Acción correctiva:** Mostrar un estado vacío específico cuando el perfil no tiene fincas ni unidades, con «No tiene unidades productivas asignadas» y sugerencia de contactar al administrador; repetir API y UI en una reevaluación autorizada.

**Reproducción:**

1. Iniciar sesión como Productor con cero fincas y unidades asignadas en el RUN autorizado.
2. Confirmar por API pública el perfil sin fincas y el dashboard con HTTP 200, total 0 y arreglos vacíos.
3. Abrir «Monitoreo en Tiempo Real» y observar el texto, las tarjetas y posibles datos ajenos.
4. Comparar la captura y el acta con el aviso y la sugerencia exigidos por TC-M03-185.


INC-M03-184-G93-02: sesión 5xx en antecedentes del [RUN oficial G93](../../../TC-M03-G93/Resultados/RUN-G93-V1-20261031-080847/TC-M03-G93_resultado.md); en G93 no se reprodujo con peticiones serializadas. En este RUN G94, las peticiones de sesión fueron HTTP 200 con eco; no se reproduce aquí. Causa raíz NO DETERMINADA. Antecedentes históricos saneados: [?ndice y SHA-256](api/antecedentes/indice.json), [acta UI saneada del intento 2](api/antecedentes/intento-2-ui.json), [API Newman saneada del intento 2](api/antecedentes/intento-2-api.json), [transcripci?n del intento 1](api/antecedentes/intento-1-transcripcion.txt), [captura real del intento 2](api/antecedentes/intento-2-ui.png). El RUN de origen del intento 2 fue eliminado por decisión del responsable QA; estos extractos no modifican el resultado de este RUN.

**Problemas técnicos QA:** ninguno registrado.

## 5. Análisis de causas

La primera discrepancia pública aparece en la UI: el perfil tiene cero fincas y las dos consultas Newman devuelven arreglos vacíos, pero el aviso visual no corresponde al requerido. Por ello la atención inicial corresponde a Desarrollo. La lectura local previa de `SGPMP-FRONT-END-PWA/src/telemetry/pages/MonitoreoView.tsx:211` y `src/shared/i18n/locales/es-CO/telemetry.json:342` orienta la hipótesis de una rama de render sin estado específico; no confirma el código desplegado ni la causa raíz. Rutas de producto consultadas en esta orden: ninguna; se revisaron la matriz, la automatización de G94, el informe G93 y las evidencias saneadas del RUN.

## 6. Conclusiones y acciones

RECHAZADO: la API cumplió y la UI mostró un mensaje distinto del requerido, sin sugerencia de contactar al administrador. Desarrollo debe atender INC-M03-185-G94-01; el responsable QA decide el seguimiento y una reevaluación autorizada tras la corrección. Esta regeneración documental no repitió pruebas ni cambió veredictos.

## 7. Herramientas, evidencias, bitácora y rollback

Newman: 1 ejecución(es); Cypress: 1 prueba(s). Evidencias reales:

- [preflight.json](preflight.json)
- [resultado.json](resultado.json)
- [newman/newman-G94.json](newman/newman-G94.json)
- [newman/newman-G94.html](newman/newman-G94.html)
- [cypress/UI-185-01.log](cypress/UI-185-01.log)
- [cypress/UI-185-01.json](cypress/UI-185-01.json)
- [cypress/UI-185-01-cypress.json](cypress/UI-185-01-cypress.json)
- [cypress/g94.cy.js/UI-185-01.png](cypress/g94.cy.js/UI-185-01.png)

Bitácora saneada: 12 solicitudes directas. Efectos previstos: dos logins previos, lecturas públicas, un PUT de fincas vacías dentro del RUN y DELETE; la UI no pulsa controles de sensores. No se acredita ausencia de efectos externos por este informe. DELETE HTTP 200; fincas originales 1, 57, 80, 184; posteriores 1, 57, 80, 184; rollback CONFIRMADO por lectura pública. Conjunto exacto de fincas restituido por DELETE. Logins y auditoría no se declaran revertidos.
