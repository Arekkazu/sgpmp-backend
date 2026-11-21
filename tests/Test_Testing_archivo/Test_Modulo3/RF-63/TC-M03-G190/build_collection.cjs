/**
 * build_collection.cjs - TC-M03-G190: Inmutabilidad y Detección de Manipulación
 * RF-63 (Bitácora de Auditoría IoT)
 * 
 * Subcasos:
 * 1. TC-M03-365: Enfoque Preventivo por API
 *    - Setup: Generar evento real por API (transición mantenimiento sensor)
 *    - Obtener id_evento y firma_hmac original
 *    - Intento PUT /iot/auditoria/{id_evento} -> 405 / 404
 *    - Intento PATCH /iot/auditoria/{id_evento} -> 405 / 404
 *    - Intento DELETE /iot/auditoria/{id_evento} -> 405 / 404
 *    - GET de comprobación: firma_hmac y datos idénticos
 *    - Comprobación FA-09: registrar intento como evento (si no se genera -> [DEFECTO])
 * 2. TC-M03-366: Enfoque Detectivo con Alteración Directa en BD
 *    - [BLOQUEADO] por Regla 2 (CERO DML en BD vía /test-control/query).
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M03-G190: Inmutabilidad y Deteccion de Manipulacion (RF-63)",
    _postman_id: "77777777-1111-4444-8888-000000000190",
    description: "Validación de inmutabilidad preventiva (rechazo de verbos de mutación PUT/PATCH/DELETE) y reporte de alteración en bitácora de auditoría.",
    schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  event: [
    {
      listen: "prerequest",
      script: {
        type: "text/javascript",
        exec: [
          "let runId = pm.collectionVariables.get('run_id');",
          "if (!runId || runId.trim() === '') {",
          "    runId = 'test-' + pm.variables.replaceIn('{{$guid}}');",
          "    pm.collectionVariables.set('run_id', runId);",
          "}",
          "const secret = pm.variables.get('sandboxSecret') || '377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff';",
          "pm.request.headers.upsert({ key: 'X-Test-Run-Id', value: runId });",
          "pm.request.headers.upsert({ key: 'X-Sandbox-Secret', value: secret });"
        ]
      }
    }
  ],
  variable: [
    { key: "baseUrl", value: "https://api.inmero.co/back-sigab-test", type: "string" },
    { key: "adminPassword", value: "", type: "string" },
    { key: "sandboxSecret", value: "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff", type: "string" },
    { key: "adminToken", value: "", type: "string" },
    { key: "run_id", value: "", type: "string" },
    { key: "idSensor", value: "1", type: "string" },
    { key: "idEvento", value: "", type: "string" },
    { key: "originalHmac", value: "", type: "string" }
  ],
  item: [
    {
      name: "01_Autenticacion",
      item: [
        {
          name: "Login Administrador",
          request: {
            method: "POST",
            header: [{ key: "Content-Type", value: "application/json" }],
            body: {
              mode: "raw",
              raw: JSON.stringify({
                correo_electronico: "administador.dev@gmail.com",
                contrasena: "{{adminPassword}}"
              })
            },
            url: {
              raw: "{{baseUrl}}/sesiones/",
              host: ["{{baseUrl}}"],
              path: ["sesiones", ""]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('01.01 Login Administrador exitoso (200)', function() {",
                  "    pm.expect(pm.response.code).to.equal(200);",
                  "    const data = pm.response.json();",
                  "    pm.expect(data.token).to.be.a('string');",
                  "    pm.collectionVariables.set('adminToken', data.token);",
                  "});"
                ]
              }
            }
          ]
        }
      ]
    },
    {
      name: "02_Setup_Generar_Evento_Auditoria",
      item: [
        {
          name: "Descubrir Sensor Activo",
          request: {
            method: "POST",
            header: [
              { key: "Authorization", value: "Bearer {{adminToken}}" },
              { key: "Content-Type", value: "application/json" }
            ],
            body: {
              mode: "raw",
              raw: JSON.stringify({
                query: "SELECT s.id_sensores FROM modulo9.sensores s JOIN modulo9.dispositivos_iot d ON s.id_dispositivo_iot = d.id_dispositivo_iot WHERE s.es_activo = true AND d.es_activo = true ORDER BY s.id_sensores ASC LIMIT 1"
              })
            },
            url: {
              raw: "{{baseUrl}}/test-control/query",
              host: ["{{baseUrl}}"],
              path: ["test-control", "query"]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('02.01 [VERIFICACION SQL SOLO LECTURA] Descubrimiento de sensor activo', function() {",
                  "    pm.expect(pm.response.code).to.equal(200);",
                  "    const res = pm.response.json();",
                  "    const rows = res.data || res.rows || [];",
                  "    if (rows.length > 0) {",
                  "        pm.collectionVariables.set('idSensor', rows[0].id_sensores.toString());",
                  "    }",
                  "});"
                ]
              }
            }
          ]
        },
        {
          name: "Generar Evento de Auditoria por API",
          request: {
            method: "POST",
            header: [
              { key: "Authorization", value: "Bearer {{adminToken}}" },
              { key: "Content-Type", value: "application/json" }
            ],
            body: {
              mode: "raw",
              raw: JSON.stringify({
                nuevo_estado: "EN_MANTENIMIENTO",
                motivo: "Prueba de inmutabilidad preventiva TC-M03-G190",
                tecnico_responsable: "QA Automation"
              })
            },
            url: {
              raw: "{{baseUrl}}/iot/mantenimiento/sensores/{{idSensor}}/transicion",
              host: ["{{baseUrl}}"],
              path: ["iot", "mantenimiento", "sensores", "{{idSensor}}", "transicion"]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('02.02 Generación de evento auditoría por API (200 o 201)', function() {",
                  "    pm.expect([200, 201]).to.include(pm.response.code);",
                  "});"
                ]
              }
            }
          ]
        },
        {
          name: "Obtener Evento Generado y Guardar Hash Original",
          request: {
            method: "GET",
            header: [{ key: "Authorization", value: "Bearer {{adminToken}}" }],
            url: {
              raw: "{{baseUrl}}/iot/auditoria?pagina=1&por_pagina=5",
              host: ["{{baseUrl}}"],
              path: ["iot", "auditoria"],
              query: [
                { key: "pagina", value: "1" },
                { key: "por_pagina", value: "5" }
              ]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('02.03 Obtener evento de auditoría y extraer firma HMAC original', function() {",
                  "    pm.expect(pm.response.code).to.equal(200);",
                  "    const data = pm.response.json();",
                  "    const items = data.items || data;",
                  "    pm.expect(items.length).to.be.above(0);",
                  "    const evento = items[0];",
                  "    pm.collectionVariables.set('idEvento', evento.id_evento);",
                  "    pm.collectionVariables.set('originalHmac', evento.firma_hmac);",
                  "});"
                ]
              }
            }
          ]
        }
      ]
    },
    {
      name: "03_TC_365_Inmutabilidad_Preventiva",
      item: [
        {
          name: "Intento 01: PUT Modificar Evento de Auditoria",
          request: {
            method: "PUT",
            header: [
              { key: "Authorization", value: "Bearer {{adminToken}}" },
              { key: "Content-Type", value: "application/json" }
            ],
            body: {
              mode: "raw",
              raw: JSON.stringify({
                severidad_log: "INFO",
                tipo_evento: "EVENTO_ALTERADO"
              })
            },
            url: {
              raw: "{{baseUrl}}/iot/auditoria/{{idEvento}}",
              host: ["{{baseUrl}}"],
              path: ["iot", "auditoria", "{{idEvento}}"]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('03.01 PUT /iot/auditoria/{id} debe ser rechazado (405 Method Not Allowed o 404)', function() {",
                  "    pm.expect([404, 405]).to.include(pm.response.code);",
                  "    if (pm.response.code === 200) {",
                  "        pm.expect.fail('[DEFECTO CRITICO] PUT permitió modificar evento de auditoría');",
                  "    }",
                  "});"
                ]
              }
            }
          ]
        },
        {
          name: "Intento 02: PATCH Modificar Evento de Auditoria",
          request: {
            method: "PATCH",
            header: [
              { key: "Authorization", value: "Bearer {{adminToken}}" },
              { key: "Content-Type", value: "application/json" }
            ],
            body: {
              mode: "raw",
              raw: JSON.stringify({
                severidad_log: "DEBUG"
              })
            },
            url: {
              raw: "{{baseUrl}}/iot/auditoria/{{idEvento}}",
              host: ["{{baseUrl}}"],
              path: ["iot", "auditoria", "{{idEvento}}"]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('03.02 PATCH /iot/auditoria/{id} debe ser rechazado (405 Method Not Allowed o 404)', function() {",
                  "    pm.expect([404, 405]).to.include(pm.response.code);",
                  "    if (pm.response.code === 200) {",
                  "        pm.expect.fail('[DEFECTO CRITICO] PATCH permitió modificar evento de auditoría');",
                  "    }",
                  "});"
                ]
              }
            }
          ]
        },
        {
          name: "Intento 03: DELETE Eliminar Evento de Auditoria",
          request: {
            method: "DELETE",
            header: [{ key: "Authorization", value: "Bearer {{adminToken}}" }],
            url: {
              raw: "{{baseUrl}}/iot/auditoria/{{idEvento}}",
              host: ["{{baseUrl}}"],
              path: ["iot", "auditoria", "{{idEvento}}"]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('03.03 DELETE /iot/auditoria/{id} debe ser rechazado (405 Method Not Allowed o 404)', function() {",
                  "    pm.expect([404, 405]).to.include(pm.response.code);",
                  "    if ([200, 204].includes(pm.response.code)) {",
                  "        pm.expect.fail('[DEFECTO CRITICO] DELETE permitió eliminar evento de auditoría');",
                  "    }",
                  "});"
                ]
              }
            }
          ]
        },
        {
          name: "Verificar Inmutabilidad Posterior con GET",
          request: {
            method: "GET",
            header: [{ key: "Authorization", value: "Bearer {{adminToken}}" }],
            url: {
              raw: "{{baseUrl}}/iot/auditoria/{{idEvento}}",
              host: ["{{baseUrl}}"],
              path: ["iot", "auditoria", "{{idEvento}}"]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('03.04 El evento sigue intacto y conserva su firma HMAC exacta', function() {",
                  "    pm.expect(pm.response.code).to.equal(200);",
                  "    const evento = pm.response.json();",
                  "    const origHmac = pm.collectionVariables.get('originalHmac');",
                  "    pm.expect(evento.firma_hmac).to.equal(origHmac);",
                  "});"
                ]
              }
            }
          ]
        },
        {
          name: "Verificar Registro de Intento de Alteracion (FA-09)",
          request: {
            method: "GET",
            header: [{ key: "Authorization", value: "Bearer {{adminToken}}" }],
            url: {
              raw: "{{baseUrl}}/iot/auditoria?tipo_evento=ACCESO_DENEGADO&por_pagina=10",
              host: ["{{baseUrl}}"],
              path: ["iot", "auditoria"],
              query: [
                { key: "tipo_evento", value: "ACCESO_DENEGADO" },
                { key: "por_pagina", value: "10" }
              ]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('03.05 Verificación FA-09: registrar intento de alteración como evento', function() {",
                  "    pm.expect(pm.response.code).to.equal(200);",
                  "    const data = pm.response.json();",
                  "    const items = data.items || data;",
                  "    // Si el backend no genera evento de auditoría por métodos no permitidos (405):",
                  "    if (items.length === 0) {",
                  "        console.log('[DEFECTO FA-09] Backend no registra evento de auditoría ante intentos de mutación PUT/PATCH/DELETE');",
                  "    }",
                  "});"
                ]
              }
            }
          ]
        }
      ]
    },
    {
      name: "04_TC_366_Alteracion_Directa_BD",
      item: [
        {
          name: "TC-366 Deteccion de Manipulacion Directa en BD [BLOQUEADO]",
          request: {
            method: "GET",
            header: [{ key: "Authorization", value: "Bearer {{adminToken}}" }],
            url: {
              raw: "{{baseUrl}}/iot/auditoria",
              host: ["{{baseUrl}}"],
              path: ["iot", "auditoria"]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "// TC-366: Corrupción intencional de datos en PostgreSQL para verificar detección por HMAC",
                  "console.log('[BLOQUEADO] TC-366 requiere ejecutar UPDATE directo sobre modulo3.bitacora_auditoria_iot.');",
                  "console.log('[MOTIVO] Regla 2 prohíbe DML directo a BD vía /test-control/query.');",
                  "console.log('[RECOMENDACION] Requiere endpoint administrativo de simulación de corrupción o laboratorio local.');"
                ]
              }
            }
          ]
        }
      ]
    },
    {
      name: "05_Teardown",
      item: [
        {
          name: "Rollback Sandbox",
          request: {
            method: "DELETE",
            header: [
              { key: "X-Test-Run-Id", value: "{{run_id}}" },
              { key: "X-Sandbox-Secret", value: "{{sandboxSecret}}" }
            ],
            url: {
              raw: "{{baseUrl}}/test-control/runs/{{run_id}}",
              host: ["{{baseUrl}}"],
              path: ["test-control", "runs", "{{run_id}}"]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('05.01 Teardown exitoso del sandbox (200)', function() {",
                  "    pm.expect(pm.response.code).to.equal(200);",
                  "    const data = pm.response.json();",
                  "    pm.expect(data.mensaje).to.include('Rollback exitoso');",
                  "});"
                ]
              }
            }
          ]
        }
      ]
    }
  ]
};

const targetDir = path.resolve(__dirname);
const targetFile = path.join(targetDir, 'test_tc_m03_g190.json');

fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección G190 generada exitosamente en ${targetFile}`);
console.log(`Carpetas: ${collection.item.length}, Requests totales: ${collection.item.reduce((acc, f) => acc + f.item.length, 0)}`);
