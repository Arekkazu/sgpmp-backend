# TC-M09-G77 — RESULTADO

## DECISIÓN GENERAL

### BLOCKED

TC-M09-148 no puede ejecutar el único POST negativo porque TEST no dispone de
un actor no autorizado con sesión autenticada. Productor, el actor preferido,
y Contador, la única alternativa permitida, respondieron 403 en el login con el
mensaje de cuenta desactivada. El código revisado demuestra que ese estado se
valida antes de verificar la credencial, por lo que no se hicieron intentos con
datos supuestos.

| Caso | Resultado | Motivo | Categoría de error | Equipo responsable | Acción |
| --- | --- | --- | --- | --- | --- |
| TC-M09-148 | BLOCKED | Productor y Contador están desactivados en TEST y no se puede demostrar “usuario autenticado + rol no autorizado”. | INFRAESTRUC — Infraestructura / Sistema Externo TEST | DBA | **REPORTAR AL DBA** para habilitar una cuenta TEST activa con rol Productor o Contador, conservando su rol no autorizado. |

No se demostró un defecto de RBAC ni corresponde reportar a Desarrollo: el
endpoint de calibración no recibió una solicitud de un actor negativo
autenticado.

## CONTRATO RBAC REVISADO

El contrato local y OpenAPI de TEST identifican:

- Endpoint: POST /configuracion/sensores/{id_sensor}/calibrar.
- Protección: require_permission(12, 1) para crear en el recurso sensores.
- Respuesta de autorización prevista por el endpoint: 403.
- El router documenta Productor con lectura del recurso sensores y sin creación;
  la creación está disponible para Administrador e Ingeniero de Campo.

El login valida el estado de la cuenta antes de la verificación de credencial.
Por ello los 403 recibidos para Productor y Contador corresponden a cuentas
desactivadas y no constituyen el 403 RBAC que TC-M09-148 requiere validar.

## DATOS UTILIZADOS

| Dato | Valor |
| --- | --- |
| Actor preferido | Productor |
| Resultado del login Productor | 403 — cuenta desactivada |
| Alternativa justificada | Contador; se usó porque Productor no puede iniciar sesión |
| Resultado del login Contador | 403 — cuenta desactivada |
| Autenticación de actor negativo | No disponible |
| Dispositivo | ID 1, IOT-EST01-HLA-001, activo |
| Sensor | ID 3, Sensor oxígeno disuelto estanque-01, activo y asociado al dispositivo |
| Área | ID 1, asociación activa y coherente |
| Rango técnico | OXIGENO: 0.0000 a 20.0000 |
| Valor de referencia preparado | 10.0000, interior al rango |
| Payload funcionalmente válido | Preparado por contrato y discovery; no enviado |

## VALIDACIÓN RBAC

| Validación | Resultado |
| --- | --- |
| Usuario autenticado como Productor/Contador | No; ambas cuentas están desactivadas |
| Rol no autorizado confirmado por sesión | No verificable sin sesión |
| Roles autorizados de RF-24 | Ingeniero de Campo / Administrador |
| Única invalidez del POST | No aplicable; el POST no se ejecutó |
| HTTP esperado en el POST | 403 Forbidden |
| HTTP obtenido en el POST | No aplicable; se preservó el límite de intentos |
| Respuesta funcional RBAC | No verificable |
| POST de calibración ejecutado | No; 0 de 2 permitidos |

## PERSISTENCIA

| Evidencia | BEFORE | AFTER | Cambió |
| --- | --- | --- | --- |
| Cantidad del historial del sensor 3 | 2 | 2 | No |
| IDs existentes | [9, 3] | [9, 3] | No |
| Nueva calibración TC148 | No aplica | No | No |

El historial AFTER fue consultado mediante GET con un actor autorizado
exclusivamente para lectura. Se mantuvo intacto. No hubo POST de calibración,
SQL de escritura ni modificación de dispositivo, sensor, área, rango, rol o
usuario.

## EVIDENCIA Y EJECUCIÓN

- Precheck sanitizado: precheck-rbac.json.
- Newman 6.2.2 y htmlextra 1.23.1 estaban disponibles.
- No se generó HTML Newman ni JSON de ejecución: producirlos sin una sesión
  negativa válida o sin POST real sería evidencia fabricada.
- Se realizaron únicamente logins necesarios y GET de discovery/historial.
- No se usaron credenciales persistidas, tokens, cabeceras de autenticación ni
  datos de sesión en los artefactos.

## ORIGEN DEL BLOQUEO

| Origen | Resultado |
| --- | --- |
| Producto | No demostrado |
| Automatización/prueba | No |
| Entorno TEST | Sí |
| Bloqueo | Sí |
| Categoría | INFRAESTRUC — Infraestructura / Sistema Externo TEST |
| Equipo responsable | DBA |
| Acción | **REPORTAR AL DBA** |

Solicitud de desbloqueo: habilitar en TEST una única cuenta existente de
Productor o Contador, manteniendo el rol actual y sin otorgarle el permiso
sensores:crear. QA reanudará G77 con un único POST RBAC funcionalmente válido.

## ENTORNO Y GIT

| Elemento | Valor |
| --- | --- |
| Fecha local de ejecución | 2026-09-06 |
| Backend TEST | https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test |
| Frontend TEST | https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io |
| Backend branch / SHA | qa/juan-esteban-m09 / adc3932b9f0293a76ebec7e89ed877274791b6a1 |
| Frontend branch / SHA | qa/juan-esteban-m09 / 966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56 |
| SHA desplegado en TEST | No confirmado |

Los dos repositorios estaban en la rama requerida. Se preservaron cambios
externos sin seguimiento; en frontend también existía previamente la eliminación
de .gitkeep de G22. No se revisó ni modificó G22, G74, G75 ni G76.

En el cierre read-only, backend registró 48 entradas de estado y 159 archivos
sin seguimiento; tres pertenecen a G77. No hubo diferencias de archivos
rastreados en backend. Frontend registró 11 entradas de estado y 31 archivos
sin seguimiento; git diff --stat muestra exclusivamente el cambio externo
preexistente de G22. Ningún archivo de G77 existe en frontend.

## CONTROLES CUMPLIDOS

- No se modificó código funcional, permisos, roles, usuarios, dispositivos,
  sensores, áreas, rangos, infraestructura ni dependencias.
- No se ejecutó Cypress, PostgreSQL ni operaciones mutantes de base de datos.
- No hubo limpieza, commit, push, pull, merge ni cambio de rama.

La ejecución queda detenida para revisión humana.

## ACTUALIZACIÓN POSTERIOR

El 2026-09-06 se reintentó la precondición con la credencial TEST suministrada.
Productor y Contador mantuvieron el mismo 403 por cuenta desactivada. El
resultado vigente continúa BLOCKED y su evidencia está en
RESULTADOS/run-20260906-003326/TC-M09-G77_resultado.md.
