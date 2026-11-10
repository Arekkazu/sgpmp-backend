# TC-M06-G43 — RUN-G43-V1-20261110-041146

G43 | RF-87 | TC-M06-024, TC-M06-025, TC-M06-026, TC-M06-027 | V1 | TEST | autorización AUT-G43-V1-R4-20261110 | commit no consultado (Git prohibido).

## Resumen

| Caso | Estado | Motivo |
|---|---|---|
| TC-M06-024 | RECHAZADO | pausa_EN_CIERRE,cierre_autorizado |
| TC-M06-025 | APROBADO | Criterios conformes |
| TC-M06-026 | RECHAZADO | confirmacion_individual,costo_revelacion,sin_estimacion_indebida,ui_confirmacion |
| TC-M06-027 | RECHAZADO | pausa_EN_CIERRE,si_exclusion,ui_lista |

## Criterios API y UI

| Caso | Criterio | Esperado | Observado | Cumple |
|---|---|---|---|---|
| TC-M06-024 | pausa_EN_CIERRE | EN_CIERRE durante la solicitud de autorización | HTTP 409; estado ABIERTO | RECHAZADO |
| TC-M06-024 | cierre_autorizado | HTTP 200 | HTTP 500; error ERROR_INTERNO | RECHAZADO |
| TC-M06-025 | aviso_api | N y lista completa de activos y especies | N=1; activos 1568:QA-M06C-VR-01:Caprino Qa Aislado | APROBADO |
| TC-M06-025 | no_rollback | ABIERTO y línea base intacta | HTTP 409; mensaje 1 activos no tienen precio de mercado vigente. Autorice su exclusión o inclúyalos con el último precio conocido como estimación.; sin cambios true | APROBADO |
| TC-M06-025 | si_exclusion | CERRADO y exclusión PENDIENTE_PRECIO | HTTP 200; estado CERRADO; excluidos 1568:PENDIENTE_PRECIO | APROBADO |
| TC-M06-025 | ui_lista | lista completa visible | panel 025 RECHAZADO; lista true; controles radio:sin-precio,radio:sin-precio | APROBADO |
| TC-M06-026 | confirmacion_individual | confirmación del párrafo 30 por activo | prevalidacion 220 1569,1570,1571; UI false; POST HTTP 200 | RECHAZADO |
| TC-M06-026 | costo_revelacion | método COSTO y revelación RF-92 | POST 220 HTTP 200; costo/revelacion false | RECHAZADO |
| TC-M06-026 | sin_estimacion_indebida | activos sin condiciones PENDIENTE_PRECIO | excluidos ; estimados  | RECHAZADO |
| TC-M06-026 | ui_confirmacion | controles por activo | panel 026 RECHAZADO; confirmacion false | RECHAZADO |
| TC-M06-027 | lista_api | id de asiento, activo y eslabón incompleto | prevalidacion 8 17:944:lecturas_nic41 | APROBADO |
| TC-M06-027 | pausa_EN_CIERRE | EN_CIERRE durante la solicitud de autorización | HTTP 409; estado ABIERTO | RECHAZADO |
| TC-M06-027 | no_rollback | ABIERTO y línea base intacta | POST 8 HTTP 409; sin cambios true; periodo ABIERTO | APROBADO |
| TC-M06-027 | si_exclusion | CERRADO y exclusión PENDIENTE_PRECIO | HTTP 200; estado CERRADO; excluidos 1568:PENDIENTE_PRECIO | RECHAZADO |
| TC-M06-027 | ui_lista | lista completa visible | panel 027 estado RECHAZADO; lista false; controles checkbox: | RECHAZADO |

## Precios

| Especie | P_ini id/fecha | P_nuevo id/fecha | Congelado id/fecha |
|---|---|---|---|
| 39 | 18 / 2026-11-07 | 486 / 2026-11-09 |  /  |

## Activos sin precio

| Periodo | Prevalidacion | Excluidos | Procesados |
|---|---|---|---|
| 219 | 1568 | 1568 | 1 |
| 220 | 1569,1570,1571 |  | 5 |

## Lineas

| Linea | Activo | Eslabon faltante | Excluida | Destino |
|---|---|---|---|---|
| 17 | 944 | lecturas_nic41 | no observable | no observable |

## UI

| Panel | Pruebas ejecutadas | Estado | Acta |
|---|---|---|---|
| 027 | 1 | RECHAZADO | cypress/027/G43-UI-027.json |
| 025 | 1 | RECHAZADO | cypress/025/G43-UI-025.json |
| 026 | 1 | RECHAZADO | cypress/026/G43-UI-026.json |

## Incidencias

- INC-M06-G32-01 (casos TC-M06-024,TC-M06-027): esperado Cierre 8 completado; obtenido HTTP 500; auditoría del RUN registra CIERRE_PERIODO_FALLIDO en paso 3; hora UTC del POST 2026-11-10T04:12:12.838Z. Evidencia: resultado.json. Impacto: Ramas autorizadas de 024 y 027 sin resultado. Severidad ALTA: El cierre autorizado queda bloqueado sin alternativa observada.; certeza PROBABLE: coincide con el patrón de G42; confirmar con el log del backend de la hora del POST. Equipo inicial Desarrollo: Primera discrepancia en la API pública de cierre. Hipótesis, sin atribuir causa raíz: La causa de este RUN requiere corroboración con el log del backend.. Acción: Responsable QA solicita el log del backend de la hora UTC del POST..
- INC-M06-G43-01 (casos 024,027): esperado EN_CIERRE durante autorización; obtenido ABIERTO. Evidencia: resultado.json. Impacto: La pausa no expone EN_CIERRE.. Severidad MEDIA: La secuencia de autorización incumple un estado requerido; la decisión sigue disponible.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia en API o UI pública de cierre observada en TEST. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar. Acción: Corregir y repetir en RUN autorizado.
- INC-M06-G43-02 (casos 027): esperado UI con asiento, activo y eslabón faltante; obtenido Lista incompleta. Evidencia: cypress/027/G43-UI-027.json. Impacto: No se identifica qué excluir.. Severidad MEDIA: La lista incompleta limita la decisión; la API puede mostrar los datos.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia en API o UI pública de cierre observada en TEST. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar. Acción: Corregir y repetir en RUN autorizado.
- INC-M06-G43-03 (casos 026): esperado Confirmación por activo del párrafo 30, COSTO y revelación; sin precio vencido ni estimado; obtenido Criterios no satisfechos. Evidencia: resultado.json; cypress/026/G43-UI-026.json. Impacto: Valoración NIC 41 incorrecta.. Severidad ALTA: La falta de confirmación o el uso de precio vencido o estimado contradice RF-89 CA-8 y puede alterar la valoración NIC 41.; certeza CONFIRMADA. Equipo inicial Desarrollo: Primera discrepancia en API o UI pública de cierre observada en TEST. Hipótesis, sin atribuir causa raíz: Causa raíz por determinar. Acción: Corregir y repetir en RUN autorizado.

## Herramientas y evidencias

Node v22.15.1; Newman codigo 0; Cypress codigo 0, pruebas 3.
- cypress/025/G43-cypress-salida.log
- cypress/025/G43-cypress.json
- cypress/025/G43-UI-025.json
- cypress/025/screenshots/g43.cy.js/G43-UI-025.png
- cypress/026/G43-cypress-salida.log
- cypress/026/G43-cypress.json
- cypress/026/G43-UI-026.json
- cypress/026/screenshots/g43.cy.js/G43-UI-026.png
- cypress/027/G43-cypress-salida.log
- cypress/027/G43-cypress.json
- cypress/027/G43-UI-027.json
- cypress/027/screenshots/g43.cy.js/G43-UI-027.png
- newman/newman-G43.html
- newman/newman-G43.json

## Problemas tecnicos


## Observaciones

- Momento de la decisión de 025: observado en la prevalidación; se registra separado del veredicto.
- Vida útil: el código local consultado la configura en M06; RF-88 la ubica en M09.
- Equinos valorados por costo con precio vigente inicial: fuera del alcance de G43.

## Cierre, rollback y accion

Registro OFICIAL. Rollback verificado: si. Lecturas poscierre sin cabeceras RUN
Las incidencias requieren correccion y reevaluacion expresamente autorizada.
