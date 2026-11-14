# RF-73 — Validar eventos de auditoría M04 antes de persistir · INC-M04-158-G086

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| Tipo dentro del catálogo cerrado | Un tipo desconocido podía llegar al INSERT y al respaldo de contingencia | TipoEventoM04 valida las 41 etiquetas antes de persistir |
| Referencia obligatoria | Permitía id_referencia nulo | Rechazo E1 sin insertar el original |
| Identidad exclusiva del actor | Se delegaba al CHECK; se trataba como fallo de infraestructura | Validación de USUARIO/SISTEMA/DISPOSITIVO_EDGE en dominio |
| Payload no vacío y campos mínimos aplicables | INFERENCIA_EJECUTADA no tenía mínimos y aceptaba payload vacío/incompleto | Validación previa y mínimos de inferencia; un tipo desconocido nunca equivale a esquema libre |
| Rechazo trazable | No generaba E1 en todos esos canales | Resultado tipado AUDITORIA_EVENTO_INVALIDO, incidente correlacionado y log técnico |

Referencias: #726, INC-M04-158-G086, G086/G087, RF-73 E1/CA-13/CA-15/RNF-07, RFC-009 y AIOT-DEV-03 DEV-03/DEV-37.

## Causa raíz

La validación vivía parcialmente en el adaptador SQLAlchemy y solo comprobaba las claves de algunos tipos. El catálogo de PostgreSQL y el constraint de actor no se reflejaban en el contrato de dominio. Los errores semánticos de la entrada podían confundirse con fallos reintentables de infraestructura y terminar como originales inválidos en contingencia.

La reproducción de origin/dev en PostgreSQL local confirmó inserciones de inferencias vacías/incompletas y referencias nulas. G087 contiene además un defecto en su conteo previo: una etiqueta inexistente se compara directamente contra una columna enum antes de invocar registrar(). Las pruebas de esta corrección sí alcanzan el repositorio.

## Cambios implementados

- Servicio de dominio para catálogo, actor, referencia y payload, con ResultadoRegistroAuditoriaM04.
- Rechazo previo al INSERT; registro de AUDITORIA_EVENTO_INVALIDO con identidad de sistema, correlación, referencia al intento, ERROR/FALLIDO y hash.
- Defensa ante DataError de enums y chk_eam_actor_exclusivo dentro de savepoints, sin reintentar ni respaldar el original inválido.
- Se conservan reintentos y respaldo para fallos reales; el commit sigue perteneciendo al caso de uso.
- Se ajustan referencias de consultas globales, incidentes previos al registro y sincronización; identidad del conflicto clínico; mínimos auditables del reporte de integridad OTA.
- Cabeceras de seguimiento y regresiones previas conservadas.

## Migración

No requiere migración ni modificación de históricos. La BD oficial solo se inspeccionó en READ ONLY. Se preservan enums, constraints, trigger append-only y permisos existentes.

## Contrato resultante

Por decisión confirmada del usuario y RF-73 RNF-07, el rechazo devuelve un resultado tipado con aceptado=false, codigo=AUDITORIA_EVENTO_INVALIDO y los campos inválidos, sin interrumpir una operación principal válida. No se añadió un POST público de auditoría ni un nuevo HTTP 400.

Un evento aceptado queda admitido para BD o contingencia según DEV-37; el resultado no afirma un commit todavía no ejecutado. Si el emisor revierte, se revierte también la fila E1, mientras el log técnico conserva la evidencia del rechazo. No hay commit autónomo oculto.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias/regresiones tests/prediction | 226 | 0 | 0 |
| PostgreSQL 18 real, contrato HTTP y regresiones DEV-03/RF-69 | 40 | 0 | 0 |
| Total distinto | 266 | 0 | 0 |

Incluye 67 pruebas nuevas: 34 unitarias y 33 de integración. Las corridas repetidas no se suman.

Se verifican los casos equivalentes de G086/G087, coincidencia del enum, actores válidos/ inválidos, enums y CHECK reales, sesión utilizable tras rechazo, commit/rollback y continuidad. La API corre bajo sgpmp_app con JWT real y RBAC: Administrador/Veterinario permitidos, Productor/Ingeniero/Contador rechazados. Regresiones de consultas/exportación, versiones, conflicto clínico y reporte OTA. En las dos últimas, los puertos ajenos a la auditoría son fakes explícitos; no se afirma una prueba end-to-end de firmware/persistencia clínica.

Pruebas locales sobre una base exclusiva migrada desde cero; BD temporal eliminada y clúster de pruebas detenido tras validar. Evidencias y lanzadores en .pytest_cache, fuera del cambio.

## Integración con sgpmp_dev

Se verificaron en lectura el catálogo de 41 tipos, columnas, índices, CHECK de actor, FK y trigger append-only. La tabla de auditoría M04 no tiene RLS en el esquema inspeccionado; se conserva la protección de su API por RBAC. Los roles normales inspeccionados no tienen superusuario ni BYPASSRLS.

No se modificó sgpmp_dev ni se validó un despliegue. El usuario disponible no puede consultar permisos ni alembic_version (42501); no se afirma la revisión desplegada.

## Dependencias y pendientes

QA debe repetir G086/G087 en el entorno actualizado, corregir el conteo previo del tipo desconocido usando una comparación textual y aplicar el contrato interno acordado de rechazo tipado. Los scripts QA originales no se modificaron ni se presentaron como reejecutados.

Se preservan los mínimos preexistentes de los emisores de versiones y retroalimentación; esta corrección no inventa metadatos que sus contratos actuales no proporcionan. No certifica los requisitos de carga de RF-73 ni reconstruye referencias de eventos históricos.

## Alcance del commit

Cambio preparado para commit y push autorizados por el usuario: 11 archivos de producción, 6 de pruebas y 2 informes Markdown. Sin migraciones, frontend ni evidencias temporales. Este documento no implica la publicación de un PR.

Informe: [Diagnóstico y evidencias](inc_m04_158_g086_rf73_validacion_auditoria.md).

## Revisión contra dev

Rama `fix/inc-m04-158-g086-validacion-auditoria-rf73`, creada desde dev actualizado en `5691096b8497b9fc445abf0a7579409c8de6550f`. No arrastra commits de las ramas anteriores M03. Se preservaron los archivos locales ajenos.
