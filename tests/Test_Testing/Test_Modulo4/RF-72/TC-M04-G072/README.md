# TC-M04-G072 — preparación de reevaluación V2

Orden ORD-G072-007. Grupo G072, casos TC-M04-226, 227 y 230, RF-72; control complementario RF-67. Esta carpeta contiene un ejecutor canónico `g072.mjs`, una colección `G072.postman_collection.json`, `lib/g072_core.mjs` y pruebas locales en `pruebas/`. No hay UI obligatoria ni spec Cypress. Los dos RUN V1 en `Resultados/` son evidencia histórica y no se modifican.

## Fuente y oráculos

Fuente primaria: `tests/Test_Testing/Test_Modulo4/Actualizacion_Matriz_RF69_RF72/Casos_Prueba(Mod4Agrupfinal)_actualizada.csv`, fila G072. RF: `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo4 (1).md`, líneas 4024, 4043–4061, 4065 y 4393–4394 (CA-14). RF-67 exige segregación de datos por finca.

- 226: A CORRECTO y B INCORRECTO sobre un resultado, ambos HTTP 201; B con conflicto, evento de auditoría `CONFLICTO_RETROALIMENTACION` que referencia el resultado, ambos íntegros en historial HTTP 200.
- 227: A CORRECTO, B PARCIAL y C INCORRECTO sobre otro resultado, tres registros íntegros e independientes en historial HTTP 200, sin consolidado ni ganador.
- 230: dos pares sobre resultados distintos, A y B CORRECTO y A y B INCORRECTO con igual patología; cuatro HTTP 201, sin flag ni evento de conflicto, ambos pares visibles en historial HTTP 200. La lectura inicial también debe responder 200.

Un historial 5xx tras registrar rechaza el caso cuya coexistencia no puede verificarse. Los casos independientes continúan. Un POST sin respuesta no se reintenta: el ejecutor busca coincidencias en el historial y registra la conciliación sin atribuir HTTP 201.

## Control RF-67

Antes del RUN se inician las sesiones de Veterinarios A, B, C y Administrador QA. Con este último se listan fincas, infraestructuras y activos por API pública, hasta encontrar un activo de una finca diferente de 84 y 184. Veterinario A consulta su historial: 403/404 aprueba el control; 200 con eventos abre incidencia nueva de seguridad para Desarrollo; sin activo ajeno verificable queda `NO_CONCLUYENTE`. El control no cambia los oráculos de 226, 227 y 230.

## V2 y presupuesto

El lanzador externo suministra `REEVALUAR` V2 o `REINTENTAR` V2 con `version_anterior: 1` y `alcance_reevaluacion`; `g072.mjs --capacidades` publica el contrato y `--comprobar` valida archivos locales. Un lanzamiento real exige autorización humana particular y contexto canónico. El informe se generará solo dentro de `EvaluacionV2/Resultados/RUN-G072-V2-<timestamp>/TC-M04-G072_reevaluacion_V2.md`, junto con `resultado.json` y reportes Newman reales.

Presupuesto máximo: 414 solicitudes, incluidas cuatro autenticaciones, hasta 100 lecturas de descubrimiento y control, nueve POST de retroalimentación, cinco consultas paginadas de historial, auditoría, DELETE y lectura poscierre. Timeout de 120 s para POST de escritura y Newman; 30 s para lecturas `fetch`; duración máxima de 14 400 s. Las lecturas de historial pueden materializar eventos y las de poscierre pueden generar `HISTORIAL_CONSULTADO` fuera del sandbox. El cierre y rollback solo se declaran verificados con DELETE 200 y comparación pública del historial.

V1 oficial: `RUN-G072-V1-20261029-165112`: 226 y 227 APROBADO con limitación de historial; 230 RECHAZADO por GET 500 `ERROR_INTERNO` tras 230a-B (`INC-M04-G072-230-01`). El intento técnico `RUN-G072-V1-20261029-161515` también se conserva. Issue #869 / PR #871 informan la corrección RLS; solo un RUN V2 autorizado puede confirmar el resultado.

Validación local sin TEST: `node --check g072.mjs`, `node --check lib/g072_core.mjs`, `node pruebas/g072_env.test.mjs`, `node pruebas/g072_ensayo.mjs`, `node g072.mjs --capacidades` y `node g072.mjs --comprobar`.
