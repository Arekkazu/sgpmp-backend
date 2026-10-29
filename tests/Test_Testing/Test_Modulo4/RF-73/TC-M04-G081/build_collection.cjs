/**
 * build_collection.cjs - TC-M04-G081: Registro de Eventos de Inferencia (RF-73)
 * Módulo 4: Predicción e IA
 * 
 * Subcasos:
 * - TC-M04-250 (INFERENCIA_EJECUTADA): [BLOQUEADO] - Endpoint productor RF-66 no expuesto en backend REST.
 * - TC-M04-251 (INFERENCIA_RECHAZADA): [BLOQUEADO] - RF-66 no expone API REST para payload corrupto.
 * - TC-M04-252 (ALERTA_PREDICCION_GENERADA): [BLOQUEADO] - POST /iot/alertas M03 no emite a M04.
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M04-G081: Registro de eventos de inferencia (RF-73)",
    _postman_id: "a0481001-0000-4000-8000-000000000081",
    description: "Suite de verificación de auditoría de inferencia y alertas (RF-73) bajo Sandbox Transaccional SGPMP.",
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
    { key: "correlacion_id_g081", value: "e0481001-0000-4000-8000-000000000081", type: "string" }
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
              "    pm.expect(data).to.have.property('total');",
              "    pm.expect(data).to.have.property('pagina');",
              "    pm.expect(data).to.have.property('por_pagina');",
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
      name: "03-TC-M04-250-Inferencia-Ejecutada-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-250 (INFERENCIA_EJECUTADA): El endpoint productor RF-66 no está expuesto en la API REST de FastAPI (vive en subsistema AIoT/externo). Sin pm.test para evitar falsos aprobados.');"
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
          raw: "{{baseUrl}}/prediccion/auditoria?tipo_evento=INFERENCIA_EJECUTADA",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "tipo_evento", value: "INFERENCIA_EJECUTADA" }
          ]
        }
      }
    },
    {
      name: "04-TC-M04-251-Inferencia-Rechazada-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-251 (INFERENCIA_RECHAZADA): RF-66 no expone API REST para enviar payload corrupto y forzar evento de rechazo en auditoría.');"
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
          raw: "{{baseUrl}}/prediccion/auditoria?tipo_evento=INFERENCIA_RECHAZADA",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "tipo_evento", value: "INFERENCIA_RECHAZADA" }
          ]
        }
      }
    },
    {
      name: "05-TC-M04-252-Alerta-Prediccion-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-252 (ALERTA_PREDICCION_GENERADA): El endpoint POST /iot/alertas de RF-57 no emite eventos hacia la bitácora M04 (solo gestiona alertas ambientales M03).');"
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
          raw: "{{baseUrl}}/prediccion/auditoria?tipo_evento=ALERTA_PREDICCION_GENERADA",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "tipo_evento", value: "ALERTA_PREDICCION_GENERADA" }
          ]
        }
      }
    },
    {
      name: "06-Teardown-Sandbox-Rollback",
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

const targetFile = path.join(__dirname, 'test_tc_m04_g081.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G081 generada exitosamente en ${targetFile}`);
