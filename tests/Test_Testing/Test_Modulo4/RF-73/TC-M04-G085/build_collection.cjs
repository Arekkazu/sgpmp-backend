/**
 * build_collection.cjs - TC-M04-G085: Retroalimentación Clínica y Conflictos (RF-73)
 * Módulo 4: Predicción e IA
 * 
 * Subcasos:
 * - TC-M04-262 (RETROALIMENTACION_REGISTRADA): [BLOQUEADO] - Precondición de inferencia no generable por API REST (RF-66 no operativo).
 * - TC-M04-263 (CONFLICTO_RETROALIMENTACION): [BLOQUEADO] - Mismo motivo por dependencia estricta de inferencia previa existente.
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M04-G085: Retroalimentacion clinica y conflictos (RF-73)",
    _postman_id: "a0485001-0000-4000-8000-000000000085",
    description: "Suite de auditoría para retroalimentación clínica veterinaria y detección de conflictos (RF-73 / RF-72) bajo Sandbox Transaccional SGPMP.",
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
    { key: "id_inferencia_valida", value: "", type: "string" },
    { key: "correlacion_id_g085", value: "e0485001-0000-4000-8000-000000000085", type: "string" }
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
      name: "02-Explorar-Historial-Inferencias",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"02.01: Consulta de historial diagnóstico M04 (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('items');",
              "    if (data.items && data.items.length > 0) {",
              "        pm.collectionVariables.set('id_inferencia_valida', data.items[0].id_resultado_inferencia);",
              "        console.log('[INFO] Inferencia existente descubierta:', data.items[0].id_resultado_inferencia);",
              "    } else {",
              "        console.log('[INFO] No hay inferencias preexistentes en la base de datos de TEST.');",
              "    }",
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
          raw: "{{baseUrl}}/prediccion/historial-diagnostico?pagina=1&por_pagina=10",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "historial-diagnostico"],
          query: [
            { key: "pagina", value: "1" },
            { key: "por_pagina", value: "10" }
          ]
        }
      }
    },
    {
      name: "03-TC-M04-262-Retroalimentacion-Registrada-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-262 (RETROALIMENTACION_REGISTRADA): La precondición requiere un id_resultado_inferencia válido generado por API. Al no estar expuesto el motor RF-66, el caso queda BLOQUEADO conforme a las instrucciones de QA.');"
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
          raw: "{{baseUrl}}/prediccion/auditoria?tipo_evento=RETROALIMENTACION_REGISTRADA",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "tipo_evento", value: "RETROALIMENTACION_REGISTRADA" }
          ]
        }
      }
    },
    {
      name: "04-TC-M04-263-Conflicto-Retroalimentacion-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-263 (CONFLICTO_RETROALIMENTACION): Requiere emitir dos feedbacks contradictorios sobre la misma inferencia. Bloqueado por ausencia de inferencias generables vía API.');"
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
          raw: "{{baseUrl}}/prediccion/auditoria?tipo_evento=CONFLICTO_RETROALIMENTACION",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "tipo_evento", value: "CONFLICTO_RETROALIMENTACION" }
          ]
        }
      }
    },
    {
      name: "05-Teardown-Sandbox-Rollback",
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
const targetFile = path.join(targetDir, 'test_tc_m04_g085.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G085 generada exitosamente en ${targetFile}`);
