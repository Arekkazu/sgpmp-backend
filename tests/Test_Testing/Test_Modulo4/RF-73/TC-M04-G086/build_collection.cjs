/**
 * build_collection.cjs - TC-M04-G086: Negativa - Rechazo de Eventos Malformados (RF-73)
 * Módulo 4: Predicción e IA
 * 
 * Subcasos:
 * - TC-M04-264 (Payload sin campos obligatorios): [BLOQUEADO] - No existe endpoint REST para ingesta directa de eventos de auditoría.
 * - TC-M04-268 (Sin id_referencia): [BLOQUEADO] - Mismo motivo por inexistencia de endpoint de ingesta.
 * - TC-M04-269 (Payload_evento vacío): [BLOQUEADO] - Mismo motivo por inexistencia de endpoint de ingesta.
 * - Verificación de Inmutabilidad e Inexistencia de Inyección Manual: POST /prediccion/auditoria retorna 405/404.
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M04-G086: Negativa - Rechazo de eventos malformados (RF-73)",
    _postman_id: "a0486001-0000-4000-8000-000000000086",
    description: "Evaluación de robustez y rechazo ante intentos de inyección de auditoría malformada (RF-73 / RF-10) bajo Sandbox Transaccional SGPMP.",
    schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  event: [
    {
      listen: "prerequest",
      script: {
        type: "text/javascript",
        exec: [
          "if (!pm.collectionVariables.get(\"run_id\")) {",
          "    pm.collectionVariables.set(\"run_id\", \"test-\" + pm.variables.replaceIn('{{$guid}}'));",
          "}",
          "pm.request.headers.upsert({ key: 'X-Test-Run-Id',  value: pm.collectionVariables.get(\"run_id\") });",
          "pm.request.headers.upsert({ key: 'X-Sandbox-Secret', value: pm.collectionVariables.get(\"sandbox_secret\") });"
        ]
      }
    }
  ],
  variable: [
    { key: "baseUrl", value: "https://api.inmero.co/back-sigab-test", type: "string" },
    { key: "run_id", value: "", type: "string" },
    { key: "sandbox_secret", value: "377ab8a5ddc2e5b7f7fb5b58533329eb6ce7f22b99cbd6ad5ffecf3e05b7f8ff", type: "string" },
    { key: "admin_password", value: "", type: "string" },
    { key: "token", value: "", type: "string" },
    { key: "correlacion_id_g086", value: "e0486001-0000-4000-8000-000000000086", type: "string" }
  ],
  item: [
    {
      name: "01-Login-ADMIN",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"NW-01: Autenticación exitosa del Administrador (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('token');",
              "    pm.collectionVariables.set('token', data.token);",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "POST",
        header: [
          { key: "Content-Type", value: "application/json" }
        ],
        body: {
          mode: "raw",
          raw: JSON.stringify({
            correo_electronico: "administador.dev@gmail.com",
            contrasena: "{{admin_password}}"
          })
        },
        url: {
          raw: "{{baseUrl}}/sesiones/",
          host: ["{{baseUrl}}"],
          path: ["sesiones", ""]
        }
      }
    },
    {
      name: "02-Preflight-Auditoria-M04",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"NW-02: Preflight exitoso sobre GET /prediccion/auditoria (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('items');",
              "    pm.expect(Array.isArray(data.items)).to.be.true;",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria?pagina=1&por_pagina=10",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "pagina", value: "1" },
            { key: "por_pagina", value: "10" }
          ]
        }
      }
    },
    {
      name: "03-TC-M04-264-Payload-Incompleto-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-264 (Payload sin campos obligatorios): No existe endpoint de ingesta directa de eventos en /prediccion/auditoria. Los eventos se producen exclusivamente por eventos de dominio interno.');"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "04-TC-M04-268-Sin-Id-Referencia-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-268 (Sin id_referencia): Inexistencia de endpoint de ingesta directa de auditoría. Bloqueado conforme a advertencia de RF-10/schema audit.');"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "05-TC-M04-269-Payload-Vacio-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-269 (Payload_evento vacío): Inexistencia de endpoint de ingesta directa de auditoría. Bloqueado conforme a advertencia de RF-10/schema audit.');"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "06-Verificar-Rechazo-Inyeccion-Manual-POST",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"06.01: POST directo a /prediccion/auditoria es estrictamente rechazado (HTTP 404 o 405)\", function () {",
              "    pm.expect([404, 405]).to.include(pm.response.code);",
              "    if (pm.response.code === 201) {",
              "        pm.expect.fail('[DEFECTO CRITICO] POST /prediccion/auditoria permitió inyección manual ilegítima');",
              "    }",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "POST",
        header: [
          { key: "Authorization", value: "Bearer {{token}}" },
          { key: "Content-Type", value: "application/json" }
        ],
        body: {
          mode: "raw",
          raw: JSON.stringify({
            tipo_evento: "EVENTO_MALFORMADO_PRUEBA",
            payload_evento: {}
          })
        },
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "07-Teardown-Sandbox-Rollback",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"NW-Teardown: Rollback transaccional exitoso del sandbox (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    var statusMsg = data.status || data.mensaje || \"\";",
              "    pm.expect(statusMsg).to.include(\"Rollback exitoso\");",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "DELETE",
        header: [
          { key: "X-Sandbox-Secret", value: "{{sandbox_secret}}" }
        ],
        url: {
          raw: "{{baseUrl}}/test-control/runs/{{run_id}}",
          host: ["{{baseUrl}}"],
          path: ["test-control", "runs", "{{run_id}}"]
        }
      }
    }
  ]
};

const targetDir = path.resolve(__dirname);
const targetFile = path.join(targetDir, 'test_tc_m04_g086.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G086 generada exitosamente en ${targetFile}`);
