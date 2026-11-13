# TC-M06-G36 - APROBADO

## Identificacion

Grupo G36; TC-M06-009 y TC-M06-010; RF-86 restriccion 5, CA-12 y CA-13; version 2; RUN RUN-G36-V2-20261112-062154; ambiente TEST; autorizacion AUT-G36-V2-20261112; commit TEST informado 453277e4, no comprobado en vivo; Node v22.15.1; Newman 6.2.2; Cypress 0 (solo API).

## Veredictos

- TC-M06-009: APROBADO
- TC-M06-010: APROBADO

Oficial: true. Condiciones: {"rollback":true,"casos_decididos":true,"newman":true,"presupuesto":true}. Solicitudes API del ejecutor y Newman: 119/150. Tres logins se ejecutan antes del RUN.

## Preflight vivo

- periodo_hoy_abierto: esperado "Periodo actual ABIERTO", observado ["CERRADO","CERRADO","ABIERTO","ABIERTO","ABIERTO","ABIERTO","ABIERTO","ABIERTO","ABIERTO","ABIERTO"], cumple true, bloqueante true
- dos_bovinos_elegibles: esperado "Al menos dos bovinos", observado [1627,1831], cumple true, bloqueante true
- precio_vigente: esperado "PESO_KG vigente", observado [18,18], cumple true, bloqueante true
- matriz_tb_pm: esperado "TB y PM presentes", observado ["AJUSTE_PERIODO_ANTERIOR","AJUSTE_PERIODO_ANTERIOR","AJUSTE_PERIODO_ANTERIOR","AJUSTE_PERIODO_ANTERIOR","AJUSTE_PERIODO_ANTERIOR","BAJA_ACTIVO","BAJA_ACTIVO","BAJA_ACTIVO","BAJA_ACTIVO","BAJA_ACTIVO","CONSUMO_INSUMO","CONSUMO_INSUMO","CONSUMO_INSUMO","CONSUMO_INSUMO","CONSUMO_INSUMO","CONSUMO_INSUMO","DEPRECIACION_ACTIVO_COSTO","DEPRECIACION_ACTIVO_COSTO","DEPRECIACION_ACTIVO_COSTO","DEPRECIACION_ACTIVO_COSTO","DEPRECIACION_ACTIVO_COSTO","DEPRECIACION_ACTIVO_COSTO","DETERIORO_ACTIVO_COSTO","DETERIORO_ACTIVO_COSTO","DETERIORO_ACTIVO_COSTO","DETERIORO_ACTIVO_COSTO","DETERIORO_ACTIVO_COSTO","DETERIORO_ACTIVO_COSTO","MANO_OBRA_PROPIA","MANO_OBRA_PROPIA","MANO_OBRA_PROPIA","MANO_OBRA_PROPIA","MANO_OBRA_PROPIA","MANO_OBRA_PROPIA","MANO_OBRA_PROPIA","PRODUCTO_AGRICOLA","PRODUCTO_AGRICOLA","PRODUCTO_AGRICOLA","PRODUCTO_AGRICOLA","PRODUCTO_AGRICOLA","RECONOCIMIENTO_DIFERENCIA","RECONOCIMIENTO_DIFERENCIA","RECONOCIMIENTO_DIFERENCIA","RECONOCIMIENTO_DIFERENCIA","RECONOCIMIENTO_DIFERENCIA","RECONOCIMIENTO_DIFERENCIA","RECONOCIMIENTO_DIFERENCIA","RECONOCIMIENTO_NACIMIENTO","RECONOCIMIENTO_NACIMIENTO","RECONOCIMIENTO_NACIMIENTO","RECONOCIMIENTO_NACIMIENTO","RECONOCIMIENTO_NACIMIENTO","RECONOCIMIENTO_NACIMIENTO","VARIACION_VR_PM","VARIACION_VR_PM","VARIACION_VR_PM","VARIACION_VR_PM","VARIACION_VR_PM","VARIACION_VR_TB","VARIACION_VR_TB","VARIACION_VR_TB","VARIACION_VR_TB","VARIACION_VR_TB"], cumple true, bloqueante true
- contador2_acceso: esperado "GET activo 200", observado [1627,1831], cumple true, bloqueante true

## Detalle por caso

### TC-M06-009

**Esperado:** Nueve PUT/PATCH/DELETE bloqueados con 409 y orientacion al correctivo; variacion y linea identicas campo a campo.

**Preparacion:** {"activo_id":1627,"periodo_id":241,"precio_id":18,"evento_id":1644,"variacion_id":411,"linea_id":5646}

**Observado:** Nueve bloqueos 409 orientados al correctivo; huellas identicas.; {"intentos":[{"ruta":"/finanzas/variaciones/411","metodo":"PUT","http":409,"codigo":"VARIACION_INMUTABLE","mensaje":"Las variaciones de valor razonable no se modifican ni se eliminan: quedan como registro permanente. Para corregir una, solicite un correctivo; se registrará uno nuevo con el monto opuesto que referencia el original, y se aplicará cuando otro Contador lo apruebe."},{"ruta":"/finanzas/variaciones/411","metodo":"PATCH","http":409,"codigo":"VARIACION_INMUTABLE","mensaje":"Las variaciones de valor razonable no se modifican ni se eliminan: quedan como registro permanente. Para corregir una, solicite un correctivo; se registrará uno nuevo con el monto opuesto que referencia el original, y se aplicará cuando otro Contador lo apruebe."},{"ruta":"/finanzas/variaciones/411","metodo":"DELETE","http":409,"codigo":"VARIACION_INMUTABLE","mensaje":"Las variaciones de valor razonable no se modifican ni se eliminan: quedan como registro permanente. Para corregir una, solicite un correctivo; se registrará uno nuevo con el monto opuesto que referencia el original, y se aplicará cuando otro Contador lo apruebe."},{"ruta":"/finanzas/periodos/241/variaciones/411","metodo":"PUT","http":409,"codigo":"VARIACION_INMUTABLE","mensaje":"Las variaciones de valor razonable no se modifican ni se eliminan: quedan como registro permanente. Para corregir una, solicite un correctivo; se registrará uno nuevo con el monto opuesto que referencia el original, y se aplicará cuando otro Contador lo apruebe."},{"ruta":"/finanzas/periodos/241/variaciones/411","metodo":"PATCH","http":409,"codigo":"VARIACION_INMUTABLE","mensaje":"Las variaciones de valor razonable no se modifican ni se eliminan: quedan como registro permanente. Para corregir una, solicite un correctivo; se registrará uno nuevo con el monto opuesto que referencia el original, y se aplicará cuando otro Contador lo apruebe."},{"ruta":"/finanzas/periodos/241/variaciones/411","metodo":"DELETE","http":409,"codigo":"VARIACION_INMUTABLE","mensaje":"Las variaciones de valor razonable no se modifican ni se eliminan: quedan como registro permanente. Para corregir una, solicite un correctivo; se registrará uno nuevo con el monto opuesto que referencia el original, y se aplicará cuando otro Contador lo apruebe."},{"ruta":"/finanzas/lineas/5646","metodo":"PUT","http":409,"codigo":"LINEA_ASIENTO_INMUTABLE","mensaje":"Las líneas de asiento no se modifican ni se eliminan. Si la línea viene de una variación errónea, solicite el correctivo de esa variación: al aprobarse se registra la línea inversa. Un reconocimiento inicial se corrige con su reversión."},{"ruta":"/finanzas/lineas/5646","metodo":"PATCH","http":409,"codigo":"LINEA_ASIENTO_INMUTABLE","mensaje":"Las líneas de asiento no se modifican ni se eliminan. Si la línea viene de una variación errónea, solicite el correctivo de esa variación: al aprobarse se registra la línea inversa. Un reconocimiento inicial se corrige con su reversión."},{"ruta":"/finanzas/lineas/5646","metodo":"DELETE","http":409,"codigo":"LINEA_ASIENTO_INMUTABLE","mensaje":"Las líneas de asiento no se modifican ni se eliminan. Si la línea viene de una variación errónea, solicite el correctivo de esa variación: al aprobarse se registra la línea inversa. Un reconocimiento inicial se corrige con su reversión."}],"orientados":9,"bloqueados":9,"campos_alterados":[]}

**Decision:** APROBADO.

### TC-M06-010

**Esperado:** Solicitud pendiente con monto opuesto; sin efecto previo; aprobacion del Contador; original y correctivo visibles, linea inversa positiva.

**Preparacion:** {"activo_id":1831,"periodo_id":241,"precio_id":18,"evento_id":1645,"variacion_id":412,"linea_id":5647}

**Observado:** Solicitud pendiente, aprobacion, historial y linea inversa acreditados.; {"creacion_http":201,"doble_control":"Doble control activo: el solicitante no pudo aprobar.","doble_control_http":403,"doble_control_codigo":"APROBADOR_DEBE_SER_OTRO","aprobacion_http":200,"solicitud_id":1,"original_id":412,"correctivo_id":413,"efectivo_antes":false,"original_visible":true,"correctivo_visible":true,"linea_inversa":true}

**Decision:** APROBADO.

## Comprobaciones API

- G36-API-009-01 (TC-M06-009): APROBADO; Nueve bloqueos 409 orientados al correctivo; huellas identicas.; evidencia resultado.json
- G36-API-009-02 (TC-M06-009): APROBADO; Nueve bloqueos 409 orientados al correctivo; huellas identicas.; evidencia resultado.json
- G36-API-010-01 (TC-M06-010): APROBADO; Solicitud pendiente, aprobacion, historial y linea inversa acreditados.; evidencia resultado.json
- G36-API-010-02 (TC-M06-010): APROBADO; Solicitud pendiente, aprobacion, historial y linea inversa acreditados.; evidencia resultado.json

## Evidencias reales

- preflight.json
- resultado.json
- TC-M06-G36_reevaluacion_V2.md
- newman/newman-G36.json
- newman/newman-G36.html

## Observaciones: seguimiento de incidencias V1

- INC-M06-G36-01: CORREGIDA. TC-M06-009: APROBADO; TC-M06-010: APROBADO

La cuenta aprobadora 169 fue preparada por SQL con autorizacion del responsable QA; el Contador 2 se usa cuando el producto impide la autoaprobacion. Las incidencias distintas se registran como nuevas en V2.

## Incidencias de producto

Ninguna comprobada.

## Problemas tecnicos

Ninguno observado.

## Cierre y rollback

DELETE HTTP 200; rollback verificado por lecturas publicas poscierre. Ambos activos restaurados tras DELETE.

## Conclusion y acciones

Conservar evidencias y derivar incidencias comprobadas a Desarrollo.
