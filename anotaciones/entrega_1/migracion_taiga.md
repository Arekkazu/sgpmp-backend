# Migración de tareas a Taiga — Entrega 1 (Módulos 1, 9 y 2)

- **Origen:** SGPMP DESARROLLO (id `1802172`)
- **Destino:** Proyecto Integrador III 2026-1 (id `1771570`)
- **Milestone destino:** `Entrega 1 (Módulos 1, 9 y 2)` (id `528658`)
- **Swimlane:** `Desarrollo` (id `39132`)
- **Épicas destino:** M01 `347307` · M09 `347663` · M02 `349097`
- **Total:** 80 US migradas (Backend #6–#52 + Frontend #53–#85)

| # Origen | # Destino | Mód | Estado destino | Prioridad | Asignado | Título |
|---|---|---|---|---|---|---|
| 6 | 1594 | M01 | Aprobado/Completado | p0-critico | leandroEstiven | [Back-end] RF-11: Bloquear/eliminar endpoint legacy GET /usuarios/ sin auth |
| 7 | 1595 | M01 | Aprobado/Completado | p0-critico | leandroEstiven | [Back-end] RF-01/08/09: Hashear tokens de un solo uso |
| 8 | 1596 | M01 | Aprobado/Completado | p1-alto | leandroEstiven | [Back-end] RF-05/06: Unificar RBAC en router y quitar id_rol hardcodeado en gestión de cuenta/perfil |
| 9 | 1597 | M01 | Aprobado/Completado | p1-alto | leandroEstiven | [Back-end] RF-02: JWT a 8h y declarar JWT_EXPIRE_HOURS en .env.example |
| 10 | 1598 | M01 | En Revisión Interna | p1-alto | leandroEstiven | [Back-end] RF-01/10: Auditoría de registro y activación de cuenta |
| 11 | 1599 | M01 | Por Hacer | p1-alto | leandroEstiven | [Back-end] RF-04/06: Cambio de rol de usuario debe aplicarse sin esperar relogin |
| 12 | 1600 | M01 | Por Hacer | p1-alto | leandroEstiven | [Back-end] RF-01: Agregar CAPTCHA en registro |
| 13 | 1601 | M01 | Por Hacer | p2-medio | leandroEstiven | [Back-end] RF-01: confirmar_contraseña, numero_identificacion numérico, envío asíncrono |
| 14 | 1602 | M01 | Por Hacer | p2-medio | leandroEstiven | [Back-end] RF-02: Estado SUSPENDIDO o documentar uso de Eliminado |
| 15 | 1603 | M01 | Por Hacer | p2-medio | leandroEstiven | [Back-end] RF-10: Corregir categoría de eventos de auditoría |
| 16 | 1604 | M01 | Por Hacer | p2-medio | leandroEstiven | [Back-end] RF-11: Ordenar listado de usuarios por fecha de registro descendente |
| 17 | 1605 | M01 | Por Hacer | p2-medio | leandroEstiven | [Back-end] RF-12: Sembrar permiso para ver identificación completa |
| 18 | 1606 | M01 | Por Hacer | p2-medio | leandroEstiven | [Back-end] RF-14: Notificaciones de registro/activación + bandeja de notificaciones internas |
| 19 | 1607 | M01 | Por Hacer | p2-medio | SamuelPR21 | [Back-end] [DBA] RF-06: Traducir errores de trigger de gestión de cuenta a error de dominio |
| 20 | 1608 | M01 | Por Hacer | p3-bajo | leandroEstiven | [Back-end] RF-10: Política de retención de auditoría (12 meses) |
| 21 | 1609 | M01 | Por Hacer | p3-bajo | arekkazu | [Back-end] Doc: Actualizar CLAUDE.md con hallazgos confirmados de Módulo 1 |
| 22 | 1610 | M02 | Por Hacer | p0-critico | SamuelPR21 | [Back-end] [DBA] RF-52: Bitácora de auditoría append-only a nivel de DB |
| 23 | 1611 | M02 | En Revisión Interna | p0-critico | Danielsxanti | [Back-end] RF-38/44/45: Cerrar segundo camino de cambio de estado (PATCH /{id}/estado) |
| 24 | 1612 | M02 | Por Hacer | p1-alto | SamuelPR21 | [Back-end] [DBA] RF-39/40/41/42: Traducir errores de trigger PL/pgSQL a error de dominio |
| 25 | 1613 | M02 | Por Hacer | p1-alto | Danielsxanti | [Back-end] RF-40: Corregir bug de unidad 'gr' vs 'g' en evento de crecimiento |
| 26 | 1614 | M02 | Por Hacer | p1-alto | Danielsxanti | [Back-end] RF-42: Corregir bug de restricción LOTE en evento reproductivo |
| 27 | 1615 | M02 | Por Hacer | p1-alto | SamuelPR21 | [Back-end] [DBA] RF-38/44/45: Unificar valores de modulo_origen en historicos_estados_activos |
| 28 | 1616 | M02 | Por Hacer | p1-alto | Danielsxanti | [Back-end] RF-33: Snapshot inicial (Evento 0), CHECK soporte_documental, código HTTP |
| 29 | 1617 | M02 | Por Hacer | p2-medio | Danielsxanti | [Back-end] RF-34: fecha_referencia, 404 sin asociación activa, sensores_en_infraestructura |
| 30 | 1618 | M02 | Por Hacer | p1-alto | Danielsxanti | [Back-end] RF-35: RBAC Veterinario, validar eventos pendientes, concurrencia optimista |
| 31 | 1619 | M02 | Por Hacer | p1-alto | Danielsxanti | [Back-end] RF-36: Ficha de gestión de lote, densidad máxima, ingreso de individuos |
| 32 | 1620 | M02 | Por Hacer | p2-medio | Danielsxanti | [Back-end] RF-37: fase_destino/confirmacion_no_estandar, fecha no futura, RBAC |
| 33 | 1621 | M02 | Por Hacer | p2-medio | Danielsxanti | [Back-end] RF-48: Regla C2 (compatibilidad tipo infraestructura), formato de error |
| 34 | 1622 | M02 | Por Hacer | p1-alto | Danielsxanti | [Back-end] RF-49: Compatibilidad de especie sensor-activo y ciclo de vida completo |
| 35 | 1623 | M02 | Por Hacer | p2-medio | Danielsxanti | [Back-end] RF-50: modulo_consumidor real y rate limiting (429) |
| 36 | 1624 | M02 | Por Hacer | p2-medio | Danielsxanti | [Back-end] RF-51: conversion_alimenticia y flujos alternos de indicadores |
| 37 | 1625 | M02 | Por Hacer | p2-medio | Danielsxanti | [Back-end] RF-47: Sección 8 (accesos directos), densidad real, fallo parcial por sección |
| 38 | 1626 | M02 | Por Hacer | p3-bajo | Danielsxanti | [Back-end] RBAC sistemático más amplio/estrecho de lo autorizado (Módulo 2) |
| 39 | 1627 | M02 | Por Hacer | p2-medio | SamuelPR21 | [Back-end] [DBA] RF-49/52: id_evento_correlacionado y vistas vw_rf52_* para M08 |
| 40 | 1628 | M02 | Por Hacer | p3-bajo | Danielsxanti | [Back-end] Doc: Actualizar notas desactualizadas en anotaciones/modulo_2/ |
| 41 | 1629 | M09 | En Revisión Interna | p1-alto | arekkazu | [Back-end] RF-19/20: Reemplazar stubs de finca e infraestructura por consultas reales |
| 42 | 1630 | M09 | Por Hacer | p1-alto | arekkazu | [Back-end] RF-32: Corregir bug de concurrencia optimista en aplicar plantilla |
| 43 | 1631 | M09 | Por Hacer | p0-critico | arekkazu | [Back-end] RF-23: Definir alcance de integración MQTT real para esta entrega |
| 44 | 1632 | M09 | Por Hacer | p2-medio | arekkazu | [Back-end] RF-23: Timeout de confirmación (30s), estado No Confirmado, rangos por tipo de dispositivo |
| 45 | 1633 | M09 | Por Hacer | p1-alto | arekkazu | [Back-end] RF-16: Decidir si patologías es catálogo global o por especie |
| 46 | 1634 | M09 | Por Hacer | p2-medio | arekkazu | [Back-end] RF-15/19/20: Ajustar RBAC más amplio de lo autorizado |
| 47 | 1635 | M09 | Por Hacer | p2-medio | arekkazu | [Back-end] RF-24: Validación de rango de calibración por tipo de sensor |
| 48 | 1636 | M09 | Por Hacer | p2-medio | arekkazu | [Back-end] RF-28: Validar límite de 12 widgets, solapamiento y span en dashboard |
| 49 | 1637 | M09 | Por Hacer | p1-alto | arekkazu | [Back-end] RF-29: Alcance del motor de i18n y validación de locale_code |
| 50 | 1638 | M09 | Por Hacer | p2-medio | SamuelPR21 | [Back-end] [DBA] Agregar UNIQUE(id_usuario)/UNIQUE(id_finca) faltantes |
| 51 | 1639 | M09 | Por Hacer | p3-bajo | arekkazu | [Back-end] RF-30/31: Changelog de versiones de esquema y validación de plantilla vacía |
| 52 | 1640 | M09 | Por Hacer | p3-bajo | arekkazu | [Back-end] RF-25/26/27: Revisiones menores opcionales (WCAG, vista previa) |
| 53 | 1641 | M01 | En Revisión Interna | p0-critico | leandroEstiven | [Frontend] JWT de localStorage a variable en memoria (RF-02) |
| 54 | 1642 | M01 | En Revisión Interna | p0-critico | leandroEstiven | [Frontend] Logout llama DELETE /sesiones/ (RF-02) |
| 55 | 1643 | M01 | Por Hacer | p1-alto | leandroEstiven | [Frontend] Timeout de inactividad 30 min (RF-02) |
| 56 | 1644 | M01 | Por Hacer | p1-alto | leandroEstiven | [Frontend] Mapeo errores 410/429 en errors.ts (RF-08/09) |
| 57 | 1645 | M02 | Por Hacer | p0-critico | Danielsxanti | [Frontend] Pasar tipo_activo a EventoReproductivoForm, restringir LOTE a nacimiento (RF-42) |
| 58 | 1646 | M02 | Por Hacer | p1-alto | Danielsxanti | [Frontend] Propagación de error en useFichaIntegral → FichaIntegralView (RF-47) |
| 59 | 1647 | M02 | Por Hacer | p1-alto | Danielsxanti | [Frontend] Pasar estadoActual a FasesSection, ocultar "Cambiar fase" en CERRADO/BAJA (RF-37) |
| 60 | 1648 | M09 | Por Hacer | p0-critico | arekkazu | [Frontend] Fix usePermission(12,5)→(12,1) en CalibracionSection (RF-24) |
| 61 | 1649 | M09 | Por Hacer | p0-critico | arekkazu | [Frontend] Corregir mapeo theme_mode 0/1/2→1/2/3 + conectar AppBar (RF-27) |
| 62 | 1650 | M01 | Por Hacer | p1-alto | leandroEstiven | [Frontend] CAPTCHA real reemplaza checkbox simulado (RF-01) |
| 63 | 1651 | M01 | Por Hacer | p2-medio | SamuelPR21 | [Frontend] Corrección verificación integridad + archivado en auditoría (RF-10) |
| 64 | 1652 | M01 | Por Hacer | p2-medio | leandroEstiven | [Frontend] CSV exporta resultado completo, no solo página actual (RF-10) |
| 65 | 1653 | M01 | Por Hacer | p2-medio | leandroEstiven | [Frontend] Bandeja de notificaciones interna (RF-14) |
| 66 | 1654 | M02 | Por Hacer | p1-alto | Danielsxanti | [Frontend] Captura de atributos_dinamicos en Registro de Activo (RF-33) |
| 67 | 1655 | M02 | Por Hacer | p1-alto | SamuelPR21 | [Frontend] Validación uniforme de fecha max={HOY} en forms de eventos (RF-39/40/41/42) |
| 68 | 1656 | M02 | Por Hacer | p1-alto | SamuelPR21 | [Frontend] Mapeo ApiError.field → setError en todos los forms de escritura (transversal M2) |
| 69 | 1657 | M02 | Por Hacer | p2-medio | Danielsxanti | [Frontend] id_especie/id_infraestructura como selects de catálogo (RF-33) |
| 70 | 1658 | M02 | En Redacción | p2-medio | SamuelPR21 | [Frontend] Validación cantidad_afectada ≤ cantidad_actual en baja parcial (RF-36/45) |
| 71 | 1659 | M02 | Por Hacer | p2-medio | Danielsxanti | [Frontend] Bloqueo de TRATAMIENTO/VACUNACION sin DIAGNÓSTICO previo (RF-41) |
| 72 | 1660 | M02 | Por Hacer | p3-bajo | Danielsxanti | [Frontend] Ocultar campos irrelevantes por categoría reproductiva (RF-42) |
| 73 | 1661 | M02 | Por Hacer | p2-medio | Danielsxanti | [Frontend] Selector/catálogo de fases por especie en CambiarFase (RF-37) |
| 74 | 1662 | M09 | Por Hacer | p0-critico | arekkazu | [Frontend] Conectar DashboardPage a useDashboardLayout (RF-28) |
| 75 | 1663 | M09 | Por Hacer | p1-alto | arekkazu | [Frontend] Reemplazar buildSnapshot() con captura real de configuración (RF-31) |
| 76 | 1664 | M09 | Por Hacer | p1-alto | arekkazu | [Frontend] Conectar ContextoInterfaz API al layout/sidebar (RF-25) |
| 77 | 1665 | M09 | Por Hacer | p2-medio | arekkazu | [Frontend] Implementar i18n con i18next es/en (RF-29) |
| 78 | 1666 | M09 | Por Hacer | p2-medio | arekkazu | [Frontend] Validar coherencia unidad↔tipo_medición en métricas (RF-16) |
| 79 | 1667 | M09 | Por Hacer | p2-medio | arekkazu | [Frontend] Validar no-solapamiento de niveles de alerta (RF-17) |
| 80 | 1668 | M09 | Por Hacer | p2-medio | arekkazu | [Frontend] Catálogo tipo_area extensible, no hardcodeado (RF-20) |
| 81 | 1669 | M09 | Por Hacer | p2-medio | arekkazu | [Frontend] UI para registrar sensores bajo dispositivo (RF-21) |
| 82 | 1670 | M02 | Por Hacer | p2-medio | SamuelPR21 | [Frontend] CSV export en AuditoriaM02View (RF-52) |
| 83 | 1671 | M09 | Por Hacer | p3-bajo | arekkazu | [Frontend] Aviso de reasignación en wizard de sensores (RF-22) |
| 84 | 1672 | M09 | Por Hacer | p3-bajo | arekkazu | [Frontend] Validar tamaño/formatos de logo + botón descartar (RF-26) |
| 85 | 1673 | M01 | Aprobado/Completado | — | arekkazu | [FRONT-END][BACKEND ]IMPLEMENTACION DE SSO |

> Generado automáticamente. El proyecto origen no fue modificado; solo se leyeron sus user stories.