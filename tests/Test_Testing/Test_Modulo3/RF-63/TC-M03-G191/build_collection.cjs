/**
 * build_collection.cjs - TC-M03-G191: Robustez ante Eventos Incompletos y Rechazo de Inyección
 * RF-63 (Bitácora de Auditoría IoT)
 * 
 * Subcasos:
 * 1. Subcasos (a), (b), (c): Inyección con campos faltantes por bus/cola interna -> [BLOQUEADO]
 *    (No existe endpoint público para inyectar directo al emisor/cola interna).
 * 2. Subcaso (d): Rechazo de Inyección Manual Directa por API (POST manual por usuario/admin)
 *    - POST /iot/auditoria con payload de evento -> Esperado 404 / 405 (o 403)
 *    - POST /iot/auditoria/eventos con payload de evento -> Esperado 404 / 405 (o 403)
 *    - Si responde 201 -> [DEFECTO CRITICO] Vulnerabilidad de inyección directa de auditoría.
 * 3. Subcaso (e): Evento de control completo -> [BLOQUEADO] por mismo motivo que a/b/c.
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M03-G191: Robustez ante Eventos Incompletos y Rechazo de Inyeccion (RF-63)",
    _postman_id: "77777777-1111-4444-8888-000000000191",
    description: "Evaluación de rechazo de inyección manual de eventos en bitácora y reporte de bloqueo para inyecciones internas de bus.",
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
    { key: "run_id", value: "", type: "string" }
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
      name: "02_TC_367_Inyeccion_Interna_Bus_Bloqueada",
      item: [
        {
          name: "Subcasos a, b, c, e: Inyeccion por Bus Interno [BLOQUEADO]",
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
                  "// Subcasos a, b, c, e: Inyección de eventos con campos faltantes directamente al emisor/cola",
                  "console.log('[BLOQUEADO] Subcasos a, b, c, e requieren inyectar eventos truncados en el bus/cola interna.');",
                  "console.log('[MOTIVO] El backend no expone API pública de ingestión directa a la cola interna de auditoría.');",
                  "console.log('[EVALUACION] Se ejecuta únicamente el subcaso (d): Verificación de rechazo de inyección manual por API.');"
                ]
              }
            }
          ]
        }
      ]
    },
    {
      name: "03_Subcaso_d_Rechazo_Inyeccion_Manual_API",
      item: [
        {
          name: "Intento 01: POST /iot/auditoria (Inyeccion Manual)",
          request: {
            method: "POST",
            header: [
              { key: "Authorization", value: "Bearer {{adminToken}}" },
              { key: "Content-Type", value: "application/json" }
            ],
            body: {
              mode: "raw",
              raw: JSON.stringify({
                tipo_evento: "INYECCION_MANUAL_ILEGITIMA",
                severidad_log: "CRITICAL",
                clasificacion_registro: "TECNICO",
                datos_antes: {},
                datos_despues: { intento: "forzado" }
              })
            },
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
                  "pm.test('03.01 Inyección manual vía POST /iot/auditoria debe ser rechazada (404/405)', function() {",
                  "    if (pm.response.code === 201) {",
                  "        pm.expect.fail('[DEFECTO CRITICO] POST /iot/auditoria permitió inyección manual de eventos');",
                  "    }",
                  "    pm.expect([404, 405]).to.include(pm.response.code);",
                  "});"
                ]
              }
            }
          ]
        },
        {
          name: "Intento 02: POST /iot/auditoria/eventos (Ruta Alternativa)",
          request: {
            method: "POST",
            header: [
              { key: "Authorization", value: "Bearer {{adminToken}}" },
              { key: "Content-Type", value: "application/json" }
            ],
            body: {
              mode: "raw",
              raw: JSON.stringify({
                tipo_evento: "EVENTO_FALSO",
                severidad_log: "ERROR"
              })
            },
            url: {
              raw: "{{baseUrl}}/iot/auditoria/eventos",
              host: ["{{baseUrl}}"],
              path: ["iot", "auditoria", "eventos"]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('03.02 Inyección manual vía POST /iot/auditoria/eventos debe ser rechazada (404/405)', function() {",
                  "    if (pm.response.code === 201) {",
                  "        pm.expect.fail('[DEFECTO CRITICO] POST /iot/auditoria/eventos permitió inyección manual de eventos');",
                  "    }",
                  "    pm.expect([404, 405]).to.include(pm.response.code);",
                  "});"
                ]
              }
            }
          ]
        },
        {
          name: "Verificar Integridad de la Bitacora tras Intentos de Inyeccion",
          request: {
            method: "GET",
            header: [{ key: "Authorization", value: "Bearer {{adminToken}}" }],
            url: {
              raw: "{{baseUrl}}/iot/auditoria?tipo_evento=INYECCION_MANUAL_ILEGITIMA",
              host: ["{{baseUrl}}"],
              path: ["iot", "auditoria"],
              query: [{ key: "tipo_evento", value: "INYECCION_MANUAL_ILEGITIMA" }]
            }
          },
          event: [
            {
              listen: "test",
              script: {
                type: "text/javascript",
                exec: [
                  "pm.test('03.03 Confirmar que ningún evento ilegítimo fue insertado en bitácora', function() {",
                  "    pm.expect(pm.response.code).to.equal(200);",
                  "    const res = pm.response.json();",
                  "    const items = res.items || res;",
                  "    pm.expect(items.length).to.equal(0);",
                  "});"
                ]
              }
            }
          ]
        }
      ]
    },
    {
      name: "04_Teardown",
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
                  "pm.test('04.01 Teardown exitoso del sandbox (200)', function() {",
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
const targetFile = path.join(targetDir, 'test_tc_m03_g191.json');

fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección G191 generada exitosamente en ${targetFile}`);
console.log(`Carpetas: ${collection.item.length}, Requests totales: ${collection.item.reduce((acc, f) => acc + f.item.length, 0)}`);
