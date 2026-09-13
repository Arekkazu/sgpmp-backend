# TC-M09-G23 — RF17, valores límite

Responsable Juan Esteban. Solo TEST real. No ejecutar G22 ni G24.

Ejecución del 2026-09-05 concluida: Newman y Cypress PASS para ambos originales.
Consultar RESULTADOS/TC-M09-G23_resultado.md. No ejecutar G22, G24 ni otros
casos desde este directorio.

| Caso | GIVEN | WHEN | THEN |
|---|---|---|---|
| TC-M09-50 | Admin autorizado, especie/variable activas, combinación libre y x físicamente válido | POST con min=x, max=x | 400 VAL_ENTRADA, fields.valor_max con rechazo min/max, sin ID/estado de éxito y GET sin registro |
| TC-M09-51 | Mismas precondiciones, x>y dentro del catálogo | POST con min=x, max=y | Mismo rechazo y ausencia de persistencia |

DTO registrar_umbral_dto.py valida valor_max antes de construir el agregado.
error_handlers.py convierte RequestValidationError en HTTP 400 VAL_ENTRADA.
No hay un error_code exclusivo para rango: se valida también fields y su mensaje.
Tres niveles sintácticamente válidos y contiguos se toman de un intervalo físico
positivo. Es matemáticamente imposible cubrir un padre vacío/invertido con tres
subrangos de longitud positiva. No se prueban esas consecuencias: la respuesta
debe señalar exclusivamente valor_max y la relación min/max antes del caso de uso.

Requisitos ya instalados: Newman 6.2.2, htmlextra 1.23.1, Cypress 13.17.0.
Variables de proceso: TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, G23_CASE (TC-M09-50
o TC-M09-51), G23_RUN_ID único (tc50-intento1, etc.). NODE_PATH resuelve Newman
global. No colocar credenciales en archivos. No cambiar package.json.

Desde G23: node run-newman.cjs
Desde raíz frontend: node_modules/.bin/cypress.cmd run --project
testing/test_testing/Modulo9/RF-17/TC-M09-G23 --config-file cypress.config.cjs
--browser electron

Una invocación ejecuta un caso. No reintentos automáticos. Máximo dos POST por
caso; si 400 con validación y ausencia confirmada, no repetir Newman. Si aparece
201 o persistencia inválida, detener todo G23 sin limpiar datos. Antes de cualquier
reintento consultar GET. La UI puede bloquear localmente; no reemplaza Newman.

HTML generado por htmlextra real, headers y environment omitidos, requests
autenticados sanitizados después del envío. JSON propio incluye solo negocio.
Cypress: video false, screenshotOnRunFailure true, blackout de campos de login,
capturas explícitas del formulario, sin mocks ni esperas fijas. G22 se preserva.

Estado inicial: ambas ramas qa/juan-esteban-m09. Backend limpio; frontend con
archivos untracked preexistentes únicamente de G22. SHAs locales:
frontend 966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56;
backend b6131f190e01768599f3ef5e4f9c13487cd78f68. SHA desplegado no confirmado.
