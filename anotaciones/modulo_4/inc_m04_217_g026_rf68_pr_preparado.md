# RF-68 — Aplicar los umbrales activos de contagio y alerta · INC-M04-217-G026

## Desvío identificado

| RF exige | Antes | Ahora |
|---|---|---|
| RF-65 configura el umbral de riesgo alto para META; RF-68 usa su configuración activa | Se leía config_version, pero se clasificaba ALTO desde 0.70 fijo | ALTO desde umbral_riesgo_alto de esa configuración |
| Umbral crítico independiente de RF-65, según decisión funcional confirmada para #852 | Todo ALTO con confianza normal intentaba generar alerta | Requiere ALTO, confianza normal y P >= umbral_alerta_critica |
| Trazabilidad del ciclo y conservación del histórico | El snapshot conservaba versión y pesos, pero no los umbrales aplicados | Snapshot y auditoría conservan ambos umbrales; se admiten históricos sin esa clave |

Referencias: [#852](https://github.com/Arekkazu/sgpmp-backend/issues/852), INC-M04-217-G026, evidencia QA TC-M04-G026 v2.0 (caso complementario 4.2), RF-65/RFC-009 y RF-68 CA-2/3/6/7/9, RNF-03. No se recibieron IDs de historia, tareas o épica adicionales.

## Causa raíz

EstimarRiesgoContagioUseCase obtenía ambos umbrales de RF-65, pero ParametrosContagio no recibía el de clasificación. discretizar aplicaba 0.50/0.70 fijos y la emisión hacia RF-57 dependía únicamente de ALTO y confianza normal. La integración PostgreSQL reveló además que el adaptador de contagio emitía RF-57 como el solicitante, aunque su evidencia RF-63 exige la identidad de servicio.

## Cambios implementados

- Pasar umbral_riesgo_alto al dominio y aplicarlo de forma inclusiva.
- Consultar umbral_alerta_critica antes de emitir/asociar la alerta RF-57.
- Conservar fórmula, pesos, corte existente de MEDIO, mínimos sanitarios, degradación y exclusión de alertas con confianza baja.
- Guardar umbrales_aplicados en el JSONB existente y en RF-73, asociado a config_version.
- Emitir RF-57 con el contexto de servicio existente y restaurar la identidad original; el acceso al lote se comprueba antes como el solicitante y la persistencia RF-68 conserva su contexto.
- Actualizar la documentación del endpoint y agregar regresiones unitarias y PostgreSQL/HTTP.

El usuario confirmó usar ambos umbrales por separado, resolviendo la diferencia entre RF-65 y RF-68 paso 8/CA-3. Los mínimos sanitarios siguen imponiendo al menos MEDIO con más del 50 % de individuos enfermos y ALTO con más del 70 %. Un ALTO sanitario no omite el umbral crítico para generar alerta.

## Migración

No requiere migración. Reutiliza las columnas RF-65 y variables_ambientales_snap JSONB. No modifica políticas RLS, permisos RBAC, catálogos ni triggers de producción.

## Contrato resultante

POST /prediccion/riesgo-contagio conserva sus DTO, campos públicos y códigos HTTP. Con Fs=0.60, Fa=1, Fd=1, pesos 0.5/0.3/0.2 y umbrales 0.90/0.95, responde HTTP 201 con P=0.8000, nivel MEDIO (1), config_version correspondiente y alerta_id=null.

ALTO desde P >= umbral_riesgo_alto; alerta desde P >= umbral_alerta_critica si el resultado es ALTO y tiene confianza normal. Se conservan el intervalo mínimo por lote y la caché por huella/config_version. Cambiar configuración afecta los siguientes ciclos y no reclasifica resultados anteriores.

## Pruebas realizadas

| Grupo | Aprobadas | Fallidas | Omitidas |
|---|---:|---:|---:|
| Unitarias y contrato RF-65/RF-68 (5 archivos seleccionados) | 98 | 0 | 0 |
| HTTP con PostgreSQL 18 real, JWT/RBAC/RLS | 11 | 0 | 0 |
| **Total distinto** | **109** | **0** | **0** |

Los 38 casos focalizados iniciales están incluidos en los 98; no se suman otra vez. Los intentos fallidos y las corridas interrumpidas no se cuentan como aprobados. Advertencia preexistente de TestClient/httpx; no hay fallos de las corridas finales.

Cobertura: caso QA reproducido; fronteras inclusivas de ambos umbrales; configuración creada/actualizada; siguiente ciclo e histórico; caché; confianza y prevalencia sanitaria; snapshot y RF-73; alerta RF-57 real; rollback completo; JWT, RBAC e inaccesibilidad de finca ajena.

Las pruebas PostgreSQL usan base local exclusiva, migrada desde cero y rol sgpmp_app sin superusuario ni BYPASSRLS. No equivalen a una ejecución sobre TEST desplegado.

## Integración con sgpmp_dev

Inspección oficial exclusivamente de lectura. Se verificaron columnas, CHECK/FK, índices, triggers y RLS/FORCE RLS. Las consultas de permisos y alembic_version fueron denegadas; no se afirma una revisión desplegada a partir de Git. Se verificó RBAC en la base aislada migrada. Sin DDL/DML oficial ni despliegue.

## Dependencias y pendientes

Requiere el esquema existente de RF-65/RF-68 y RF-57/RF-73. La base local se migró hasta 67e33de11180 y se aprovisionaron privilegios SQL para la API y el propietario del trigger de historial RF-65; no se relajaron políticas ni restricciones. Queda desplegar la rama y reejecutar TC-M04-G026 en un sandbox autorizado de TEST.

## Alcance del commit

Alcance de la entrega: 5 archivos de producción, 3 archivos de pruebas y 2 informes. Evidencias/lanzadores en .pytest_cache excluidos. No se incluyen los archivos ajenos previamente sin seguimiento. Commit y push autorizados por el usuario para esta corrección. El PR se entrega como texto para revisión.

## Revisión contra dev

Rama fix/inc-m04-217-g026-umbrales-contagio-rf68 creada desde dev actualizado a e94232b5086bc1232a77a9f1a625225165eb9a49. La comparación contiene únicamente esta corrección y sus evidencias permanentes.
