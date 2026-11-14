# INC-M03-129-G27 · #684 — Alerta de capacidad del buffer RF-54 / RF-60 / RF-63

Fecha: 2026-10-27. Cabeceras: Leandro, verificado mediante git config user.name.

## Alcance confirmado y referencias

Issue #684, TC-M03-045/G27; RF-54 Fase 4, E1 y Salidas §2; AIOT-DEV-03 P2/P5/D10; DEV-11/AIOT-08.

RF-54 exige BUFFER_CAPACITY_WARNING y expone WARNING desde 80 % y CRITICO desde 95 %. El umbral que dispara el aviso es configurable en Edge (80 % es el ejemplo de la Fase 4). D10 solo contemplaba BUFFER_OVERFLOW y BUFFER_DATA_CORRUPTION. Se explicó la diferencia y el usuario confirmó ampliar POST /iot/eventos-buffer: aviso LEVE, escalamiento de la misma alerta a CRITICO desde 95 %, integración IoT pendiente documentada. No se vuelve a crear el buffer en backend.

Rama fix/inc-m03-129-g27-alerta-capacidad-buffer-rf54, creada desde dev actualizado: 5691096b8497b9fc445abf0a7579409c8de6550f.

[PR #806 / #681](https://github.com/Arekkazu/sgpmp-backend/pull/806) seguía abierto y sin fusionar al consultar. Su snapshot y GET /buffer clasifican ocupación; no generan estas alertas. Esta corrección funciona con el evento D10 ampliado y no depende de esa rama. Tampoco incorpora #682 / PR #807: BUFFER_ACTIVO describe el estado operativo del dispositivo y no es la severidad de esta alerta.

## Causa raíz y reproducción

EventoBuffer admitía únicamente OVERFLOW y DATA_CORRUPTION. El caso de uso tampoco tenía una regla para avisos de capacidad ni su escalamiento. La prueba de entrada con evento BUFFER_CAPACITY_WARNING y ocupación 80 falló antes de modificar producción por el enum; evidencia .pytest_cache/g30_antes.log/xml.

El backend no podía recibir el aviso de RF-54 por el contrato D10 vigente. Esto confirma una brecha del backend en el contrato ampliado; la generación y el transporte del evento requieren también el componente IoT.

## Recorrido y decisiones de implementación

Edge mide ocupación y emite EVENTO_BUFFER → broker extrae serial del tópico status y reenvía POST con token de servicio → DTO valida el sobre → adaptador M09 resuelve dispositivo/infraestructura → caso de uso obtiene el advisory lock existente (3505, dispositivo) → busca alerta técnica abierta → crea o consolida → repositorio hace flush y auditoría RF-57 obligatoria → caso de uso confirma o revierte → auditoría RF-54/RF-63 best-effort posterior → GET /iot/alertas-tecnicas aplica JWT, RBAC 36/Leer y alcance por finca.

- Se amplía el enum público del DTO; el schema de recibo conserva sus campos.
- Un aviso de capacidad recibido genera LEVE si es menor a 95 % y CRITICO desde 95 %. No se impone un mínimo adicional de 80 al evento emitido por Edge: el umbral de aviso allí puede configurarse.
- Una alerta ACTIVA/EN_ATENCION del mismo tipo y dispositivo recibe la ocurrencia y solo incrementa su severidad usando SeveridadAlerta existente. No se rebaja una crítica abierta por un reporte menor o atrasado.
- ultima_ocurrencia conserva el máximo timestamp reportado. Los campos iniciales, incluido metadato_evento, siguen describiendo la primera ocurrencia; cada nuevo aviso conserva su porcentaje y severidad efectiva en RF-63.
- No se crean transiciones de estado de alerta al escalar severidad. El trigger mantiene el historial único de estados. Tras cerrar el incidente por el flujo existente puede abrirse otro.
- Los avisos repetidos se consolidan y cuentan como ocurrencias. D10 no aporta ID de evento para prometer exactamente una ocurrencia por reintento.
- OVERFLOW sigue siendo MODERADO y DATA_CORRUPTION, CRITICO; sus contratos se conservan.
- No se agrega recuperación automática, notificación push ni una interpretación del porcentaje como estado de atención. CRITICO es severidad; ACTIVA/EN_ATENCION sigue siendo el ciclo de vida.

## BD y RBAC: verificación previa

La inspección oficial utilizó member_dev sobre sgpmp_dev con SET TRANSACTION READ ONLY (on). Se revisaron columnas/tipos/FK/restricciones/índices, políticas y definiciones de triggers.

alertas.tipo_variable es VARCHAR(50); acepta el nuevo código sin cambiar columnas. Severidad utiliza los valores existentes. enum_tipo_alerta_tecnica no tiene columnas dependientes en el catálogo consultado; es un catálogo SQL actualmente sin uso por este flujo y no se modifica ni se inventa otro. No se necesita migración.

Se preservan los triggers de inmutabilidad, historial inicial, transiciones y no borrado. alertas/historial/auditoría no tienen RLS; la lectura usa el alcance de aplicación y las entidades M09 conservan RLS/FORCE. El nuevo endpoint no agrega rutas; conserva la autenticación del broker y la lectura dinámica por permisos.

member_dev no pudo consultar permisos ni public.alembic_version (42501). No se eludió esa restricción ni se aplicaron DDL/DML oficiales. Los permisos efectivos se verifican en PostgreSQL local bajo sgpmp_app sin superusuario ni BYPASSRLS. El aprovisionamiento SQL de fixtures se realiza exclusivamente allí.

## Auditoría y garantías

Crear/consolidar incluye la evidencia RF-57 del repositorio en la misma transacción. Su fallo revierte alerta, frecuencia, severidad e historial relacionado. La evidencia específica RF-54 conserva el comportamiento best-effort después del primer commit: si falla, no revierte la alerta ya confirmada. Esta limitación preexistente se prueba y se informa; no se transforma en un bloqueo funcional adicional.

Se agrega severidad_alerta a la evidencia del nuevo evento, junto a porcentaje y timestamp recibidos. La auditoría del aviso crítico utiliza ERROR, siguiendo el patrón de incidentes de buffer existente.

## Pruebas y evidencias

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| tests/telemetry: fakes y contratos HTTP | 744 | 0 | 0 |
| PostgreSQL real: específicas #684 | 19 | 0 | 0 |
| PostgreSQL real: regresión DEV-49 | 11 | 0 | 0 |
| **Total distinto final** | **774** | **0** | **0** |

La suite de telemetría incluye 29 casos nuevos de #684. La integración comprueba límites 80/95, consolidación 80→95→80, estados ACTIVA/EN_ATENCION/terminales, metadatos originales y reportes atrasados, token de broker, JWT, RBAC, alcance por finca, separación técnica/operativa, auditoría real y fallos inyectados de evidencia con rollback real. Dos pruebas coordinan conexiones concurrentes bajo el lock del dispositivo y verifican una alerta con severidad máxima.

Corridas exploratorias: una falló antes del cambio por el enum (reproducción esperada); la primera focalizada tuvo una aserción nueva que exigía rechazar un datetime sin zona, corregida al contrato UTC compartido; la primera integración obtuvo 18/19 por ordenar auditoría con timestamp_registro transaccional y UUID, corregido en la prueba para ordenar por fecha_hora. Las corridas finales completas aprobaron 744/744 y 30/30. No se suman las repeticiones.

Evidencias: .pytest_cache/g30_antes.xml, g30_foco.xml, g30_pg_foco.xml, g30_unit_final.xml, g30_pg_final.xml, g30_resumen_final.json y sus logs. Se mantienen las advertencias preexistentes de Starlette/httpx y Operation ID duplicado de auditoría.

Las pruebas con fakes/contrato HTTP se distinguen de las que ejecutan PostgreSQL, triggers y locks reales. SQL directo y HTTP local no acreditan publicación MQTT, medición física, firmware ni un entorno desplegado.

El shim fcntl se limita a los lanzadores de pruebas Windows. Scripts, logs y XML ignorados en .pytest_cache/g30_*. No se incluyen credenciales ni evidencias temporales en el commit.

La base local sgpmp_g30_test se eliminó al terminar y el clúster quedó detenido. Se comprobó que las otras bases se conservaron. Logs y scripts permanecen ignorados en .pytest_cache/g30_cierre_bd.log, g30_cierre_cluster.log y g30_estado_cluster_final.log.

## Integración y pendientes

Ver [contrato para IoT](inc_m03_129_g27_rf54_integracion_iot.md). Firmware/AIOT-08 debe emitir el nuevo aviso al alcanzar advertencia y reportar también el nivel crítico; broker debe admitir el código y reenviar el sobre con serial/token. Reportar solo ocupación en un heartbeat no ejecuta este endpoint ni crea una alerta por sí mismo.

Después del despliegue coordinado se debe repetir TC-M03-045 con Edge real. El backend queda validado localmente; la integración IoT y QA desplegado permanecen pendientes.

## Entrega

Dos archivos de producción, tres de pruebas y cuatro documentos (incluida la referencia API). Cabeceras de seguimiento actualizadas, frontend y archivos ajenos preservados. El usuario autorizó commit y push de esta corrección. La publicación del PR queda pendiente.
