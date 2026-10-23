/**
 * build_collection.cjs - TC-M04-G096: Control de Acceso, IDOR y RBAC (RF-73)
 * Herramienta: Postman / Newman
 * Módulo 4: Predicción e IA (Fase de Diseño y Construcción)
 * 
 * Subcasos:
 * - TC-M04-048: Prevención de IDOR sobre /prediccion/auditoria/{id} con rol PRODUCTOR (403/404, nunca 200)
 * - TC-M04-049: Enmascaramiento y ausencia de datos sensibles en logs técnicos (LIMITACION API / PENDIENTE_DEV)
 * - TC-M04-051: Rechazo estricto RBAC HTTP 403 a rol PRODUCTOR en /prediccion/auditoria
 * - TC-M04-052: Restricción de acceso a rol AUDITOR_EXTERNO solo a períodos cerrados (PENDIENTE_DEV)
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M04-G096: Control de acceso, IDOR y RBAC (RF-73)",
    _postman_id: "a0496001-0000-4000-8000-000000000096",
    description: "Diseño de pruebas para validar controles de autorización OWASP API1 (BOLA/IDOR), API5 (BFLA/RBAC) y ASVS V7 en auditoría M04 (RF-73).",
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
    { key: "producer_password", value: "", type: "string" },
    { key: "token_admin", value: "", type: "string" },
    { key: "token_productor", value: "", type: "string" },
    { key: "id_evento_real", value: "e0496001-0000-4000-8000-000000000096", type: "string" }
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
              "pm.test(\"NW-01: Autenticación inicial Admin (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('token');",
              "    pm.collectionVariables.set('token_admin', data.token);",
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
      name: "02-Admin-Obtener-IdEvento-Real",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"NW-02: Admin obtiene evento real de auditoría (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    if (data.items && data.items.length > 0) {",
              "        pm.collectionVariables.set('id_evento_real', data.items[0].id_evento);",
              "    }",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token_admin}}" }
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
      name: "03-Login-PRODUCTOR",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"NW-03: Autenticación de PRODUCTOR (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('token');",
              "    pm.collectionVariables.set('token_productor', data.token);",
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
            correo_electronico: "productor@pecuaria.co",
            contrasena: "{{producer_password}}"
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
      name: "04-TC-M04-051-RBAC-Productor-Bloqueado",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-051: Rechazo HTTP 403 a rol PRODUCTOR en GET /prediccion/auditoria\", function () {",
              "    if (pm.response.code === 200) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] El rol PRODUCTOR pudo consultar la bitácora M04 con HTTP 200 violando matriz RBAC.\");",
              "    }",
              "    pm.expect([403]).to.include(pm.response.code);",
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
          { key: "Authorization", value: "Bearer {{token_productor}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "05-TC-M04-048-IDOR-Productor-Detalle-Evento",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-048a: Prevención IDOR - PRODUCTOR recibe HTTP 403/404 al consultar evento existente (nunca 200)\", function () {",
              "    if (pm.response.code === 200) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] Vulnerabilidad OWASP API1 (IDOR): PRODUCTOR accedió al detalle de evento ajeno con HTTP 200.\");",
              "    }",
              "    pm.expect([403, 404]).to.include(pm.response.code);",
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
          { key: "Authorization", value: "Bearer {{token_productor}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/{{id_evento_real}}",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "{{id_evento_real}}"]
        }
      }
    },
    {
      name: "06-TC-M04-048-IDOR-Fuerza-Bruta-Secuencial",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-048b: Fuerza bruta secuencial no expone eventos a PRODUCTOR (nunca 200)\", function () {",
              "    pm.expect(pm.response.code).to.not.eql(200);",
              "    pm.expect([403, 404, 422]).to.include(pm.response.code);",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token_productor}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/00000000-0000-0000-0000-000000000001",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "00000000-0000-0000-0000-000000000001"]
        }
      }
    },
    {
      name: "07-TC-M04-049-Logs-Tecnicos-Sin-PII",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "if (pm.response.code === 404 || pm.response.code === 405) {",
              "    console.log('[LIMITACION API] TC-M04-049: Endpoint GET /logs/tecnicos no expuesto por la API REST.');",
              "} else {",
              "    pm.test(\"TC-M04-049: Logs técnicos enmascaran tokens y credenciales\", function () {",
              "        pm.expect(pm.response.code).to.eql(200);",
              "        var text = pm.response.text();",
              "        pm.expect(text).to.not.include('Bearer eyJ');",
              "    });",
              "}"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token_admin}}" }
        ],
        url: {
          raw: "{{baseUrl}}/logs/tecnicos?run_id={{run_id}}",
          host: ["{{baseUrl}}"],
          path: ["logs", "tecnicos"],
          query: [
            { key: "run_id", value: "{{run_id}}" }
          ]
        }
      }
    },
    {
      name: "08-TC-M04-052-Auditor-Externo-Periodos-Cerrados",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[PENDIENTE_DEV] TC-M04-052: Rol AUDITOR_EXTERNO no provisionado en backend. Contrato esperado: HTTP 403 ante período abierto y HTTP 200 ante período histórico cerrado.');"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{token_admin}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria?fecha_hasta=2026-09-01T00:00:00Z",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "fecha_hasta", value: "2026-09-01T00:00:00Z" }
          ]
        }
      }
    },
    {
      name: "09-Teardown-Sandbox-Rollback",
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
const targetFile = path.join(targetDir, 'test_tc_m04_g096.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G096 generada exitosamente en ${targetFile}`);
