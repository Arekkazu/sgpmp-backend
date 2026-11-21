# TC-M09-G77 — RESULTADO

## DECISIÓN GENERAL

### BLOCKED

Este reintento se realizó con la credencial TEST proporcionada para usuarios,
sin almacenarla en archivos. Productor, el actor preferido de TC-M09-148,
respondió 403 en el login indicando que su cuenta está desactivada. Se aplicó
la única alternativa autorizada, Contador, que respondió el mismo 403 por cuenta
desactivada.

El código de login revisado valida el estado de la cuenta antes de comparar la
credencial. Por tanto, estas respuestas prueban que no existe una sesión activa
de Productor ni Contador disponible en TEST; no representan el 403 RBAC del
POST de calibración que el caso requiere.

| Caso | Resultado | Motivo | Categoría de error | Equipo responsable | Acción |
| --- | --- | --- | --- | --- | --- |
| TC-M09-148 | BLOCKED | Los dos actores negativos permitidos están desactivados en TEST. No se puede demostrar usuario autenticado con rol no autorizado. | INFRAESTRUC — Infraestructura / Sistema Externo TEST | DBA | **REPORTAR AL DBA** para habilitar una cuenta TEST Productor o Contador, sin cambiar su rol ni conceder permiso sensores:crear. |

No corresponde reportar a Desarrollo porque no se alcanzó a evaluar el control
RBAC del endpoint.

## EVIDENCIA DEL REINTENTO

| Validación | Resultado |
| --- | --- |
| Login Productor con credencial TEST suministrada | 403 — cuenta desactivada |
| Login Contador como alternativa permitida | 403 — cuenta desactivada |
| Actor negativo con sesión autenticada | No disponible |
| POST de calibración | No ejecutado; 0 de 2 permitidos |
| Historial sensor 3 después del reintento | 200; total 2; IDs [9, 3] |
| Historial alterado | No |

La consulta de historial fue un GET realizado con Ingeniero de Campo
exclusivamente para lectura. Los datos previamente descubiertos continúan
siendo funcionalmente válidos para el futuro POST: dispositivo 1 activo, sensor
3 activo y asociado al área 1, categoría OXIGENO y valor de referencia 10.0000
dentro de su rango 0.0000 a 20.0000.

## ORIGEN DEL BLOQUEO Y ESCALAMIENTO

| Origen | Resultado |
| --- | --- |
| Producto | No demostrado |
| Automatización/prueba | No |
| Entorno TEST | Sí |
| Bloqueo | Sí |
| Categoría | INFRAESTRUC — Infraestructura / Sistema Externo TEST |
| Equipo responsable | DBA |
| Acción | **REPORTAR AL DBA** |

El DBA debe habilitar una única cuenta TEST ya existente de Productor o
Contador y conservar su rol no autorizado. Cuando esté disponible, G77 debe
reanudar con un único POST válido y esperar 403 sin persistencia.

## EVIDENCIA Y CONTROLES

- Evidencia sanitizada: precheck-rbac-reintento.json.
- No se generó HTML Newman ni reporte JSON de ejecución porque no hubo sesión
  negativa autenticada ni POST RBAC; generar esas evidencias sería simular la
  prueba.
- No se persistieron credenciales, tokens, cabeceras de autenticación ni datos
  de sesión.
- No se modificaron código, datos, permisos, roles, usuarios, dispositivos,
  sensores, áreas, rangos, infraestructura ni dependencias.
- No se ejecutó Cypress, SQL de escritura, limpieza, commit, push, pull, merge
  ni cambio de rama.

## ENTORNO

| Elemento | Valor |
| --- | --- |
| Fecha local | 2026-09-06 |
| Backend TEST | https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test |
| Frontend TEST | https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io |
| Backend branch / SHA | qa/juan-esteban-m09 / adc3932b9f0293a76ebec7e89ed877274791b6a1 |
| Frontend branch / SHA | qa/juan-esteban-m09 / 966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56 |
| SHA desplegado en TEST | No confirmado |

## GIT FINAL

El cierre read-only registró 48 entradas en el estado del backend y 161
archivos sin seguimiento; cinco pertenecen a G77. No hubo diferencias en
archivos rastreados del backend. Frontend registró 11 entradas de estado y 31
archivos sin seguimiento; git diff --stat contiene únicamente el cambio externo
preexistente de G22. No existe ningún archivo G77 en frontend. Todos esos
cambios ajenos se preservaron.

La ejecución se detiene para revisión humana.
