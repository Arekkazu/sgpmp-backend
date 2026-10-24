/**
 * build_collection.cjs - TC-M04-G094: OWASP API2 — Autenticación y Gestión de Sesión (RF-73)
 * Herramienta: Postman / Newman
 * Módulo 4: Predicción e IA (Fase de Diseño y Construcción)
 * 
 * Subcasos:
 * - TC-M04-293: Token obligatorio en endpoints de auditoría (sin auth, header vacío, token alterado) -> 401
 * - TC-M04-294: Invalidación estricta de sesión tras logout (DELETE /sesiones/) y rechazo de reuso -> 401
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M04-G094: OWASP API2 - Autenticacion y sesion (RF-73)",
    _postman_id: "a0494001-0000-4000-8000-000000000094",
    description: "Diseño de pruebas para validar control de acceso y autenticación OWASP API2 en endpoints de auditoría M04 e invalidación tras logout (RF-73).",
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
    { key: "token_valido", value: "", type: "string" },
    { key: "token_manipulado", value: "", type: "string" },
    { key: "id_evento_ficticio", value: "e0494001-0000-4000-8000-000000000094", type: "string" }
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
              "pm.test(\"NW-01: Autenticación inicial del Administrador (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('token');",
              "    pm.collectionVariables.set('token_valido', data.token);",
              "    var t = data.token;",
              "    var manipulated = t.substring(0, t.length - 8) + 'ABCDEFGH';",
              "    pm.collectionVariables.set('token_manipulado', manipulated);",
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
      name: "02-TC-M04-293a-Sin-Auth-Listado",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-293a1: Rechazo HTTP 401 sin header Authorization en GET /prediccion/auditoria\", function () {",
              "    if (pm.response.code !== 401) {",
              "        console.log('[DISCREPANCIA] Se esperaba 401 y respondió: ' + pm.response.code);",
              "    }",
              "    pm.expect(pm.response.code).to.eql(401);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('error_code');",
              "    pm.expect(data).to.have.property('message');",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "03-TC-M04-293a-Sin-Auth-Exportar",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-293a2: Rechazo HTTP 401 sin header Authorization en GET /prediccion/auditoria/exportar\", function () {",
              "    pm.expect(pm.response.code).to.eql(401);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('error_code');",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/exportar?formato=json",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "exportar"],
          query: [
            { key: "formato", value: "json" }
          ]
        }
      }
    },
    {
      name: "04-TC-M04-293a-Sin-Auth-Detalle",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-293a3: Rechazo HTTP 401 sin header Authorization en GET /prediccion/auditoria/{id}\", function () {",
              "    pm.expect(pm.response.code).to.eql(401);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('error_code');",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/{{id_evento_ficticio}}",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "{{id_evento_ficticio}}"]
        }
      }
    },
    {
      name: "05-TC-M04-293b-Header-Vacio-Listado",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-293b: Rechazo HTTP 401 ante Authorization Bearer vacío\", function () {",
              "    pm.expect(pm.response.code).to.eql(401);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('error_code');",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer " }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "06-TC-M04-293c-Token-Manipulado-Listado",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-293c: Rechazo HTTP 401 ante token con firma alterada\", function () {",
              "    pm.expect(pm.response.code).to.eql(401);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('error_code');",
              "    pm.expect(data.message).to.be.a('string');",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token_manipulado}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "07-TC-M04-294-Verificar-Token-Valido",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-294a: Token válido permite acceso antes de logout (HTTP 200)\", function () {",
              "    pm.expect(pm.response.code).to.eql(200);",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token_valido}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria?pagina=1&por_pagina=5",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "pagina", value: "1" },
            { key: "por_pagina", value: "5" }
          ]
        }
      }
    },
    {
      name: "08-TC-M04-294-Ejecutar-Logout",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-294b: Logout exitoso invalidando sesión (HTTP 200)\", function () {",
              "    pm.expect(pm.response.code).to.eql(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data.message || '').to.include('cerrada');",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "DELETE",
        header: [
          { key: "Authorization", value: "Bearer {{token_valido}}" }
        ],
        url: {
          raw: "{{baseUrl}}/sesiones/",
          host: ["{{baseUrl}}"],
          path: ["sesiones", ""]
        }
      }
    },
    {
      name: "09-TC-M04-294-Reuso-Token-Revocado",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-294c: Rechazo estricto HTTP 401 al reutilizar token tras logout\", function () {",
              "    if (pm.response.code === 200) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] El token fue reutilizado con éxito tras logout violando RF-02 y OWASP API2.\");",
              "    }",
              "    pm.expect(pm.response.code).to.eql(401);",
              "    var data = pm.response.json();",
              "    pm.expect(data.error_code).to.eql('TOKEN_REVOCADO');",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token_valido}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "10-Teardown-Sandbox-Rollback",
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
const targetFile = path.join(targetDir, 'test_tc_m04_g094.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G094 generada exitosamente en ${targetFile}`);
