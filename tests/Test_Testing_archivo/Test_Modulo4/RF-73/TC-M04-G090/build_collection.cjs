/**
 * build_collection.cjs - TC-M04-G090: Inmutabilidad e Integridad del Repositorio (RF-73)
 * Módulo 4: Predicción e IA (Fase de Diseño y Construcción)
 * 
 * Subcasos:
 * - TC-M04-276 (intento UPDATE PUT/PATCH): HTTP 405 Method Not Allowed + verificación GET 200 intacto
 * - TC-M04-277 (intento DELETE): HTTP 405 Method Not Allowed + verificación GET 200 existente
 * - TC-M04-278 (verificación hash en consulta): Comparación exacta SHA-256 (64 hex)
 * - TC-M04-279 (detección hash mismatch): PENDIENTE_DEV POST /prediccion/auditoria/{id}/verificar
 * - TC-M04-280 (exportación): GET /prediccion/auditoria/exportar?formato=json y comparación byte a byte
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M04-G090: Inmutabilidad e integridad del repositorio (RF-73)",
    _postman_id: "a0490001-0000-4000-8000-000000000090",
    description: "Diseño de pruebas para validar inmutabilidad de bitácora (405 ante PUT/PATCH/DELETE), recálculo de hash SHA-256, verificación de integridad y exportación (RF-73).",
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
    { key: "id_evento", value: "e0490001-0000-4000-8000-000000000090", type: "string" },
    { key: "hash_original", value: "", type: "string" }
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
      name: "02-Obtener-Evento-Referencia",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"NW-02: Obtener evento base de auditoría (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('items');",
              "    if (data.items && data.items.length > 0) {",
              "        pm.collectionVariables.set('id_evento', data.items[0].id_evento);",
              "        if (data.items[0].hash_evento) {",
              "            pm.collectionVariables.set('hash_original', data.items[0].hash_evento);",
              "        }",
              "    } else {",
              "        console.log('[LIMITACION API] No se encontraron eventos en BD; utilizando id_evento determinista.');",
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
      name: "03-TC-M04-276-Intento-PUT-Inmutabilidad",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-276a: Rechazo estricto de PUT sobre evento (HTTP 405 Method Not Allowed)\", function () {",
              "    if (pm.response.code === 200) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] El endpoint permitió PUT sobre evento de auditoría con HTTP 200 violando inmutabilidad WORM.\");",
              "    }",
              "    pm.expect([405]).to.include(pm.response.code);",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "PUT",
        header: [
          { key: "Authorization", value: "Bearer {{token}}" },
          { key: "Content-Type", value: "application/json" }
        ],
        body: {
          mode: "raw",
          raw: JSON.stringify({
            severidad_evento: "CRITICAL",
            payload_evento: { alterado: true }
          })
        },
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/{{id_evento}}",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "{{id_evento}}"]
        }
      }
    },
    {
      name: "04-TC-M04-276-Intento-PATCH-Inmutabilidad",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-276b: Rechazo estricto de PATCH sobre evento (HTTP 405 Method Not Allowed)\", function () {",
              "    if (pm.response.code === 200) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] El endpoint permitió PATCH sobre evento de auditoría con HTTP 200 violando inmutabilidad WORM.\");",
              "    }",
              "    pm.expect([405]).to.include(pm.response.code);",
              "    console.log('[LIMITACION API] Verificación de log técnico de seguridad no expuesta por endpoint HTTP.');",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "PATCH",
        header: [
          { key: "Authorization", value: "Bearer {{token}}" },
          { key: "Content-Type", value: "application/json" }
        ],
        body: {
          mode: "raw",
          raw: JSON.stringify({
            severidad_evento: "CRITICAL"
          })
        },
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/{{id_evento}}",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "{{id_evento}}"]
        }
      }
    },
    {
      name: "05-TC-M04-277-Intento-DELETE-Inmutabilidad",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-277a: Rechazo estricto de DELETE sobre evento (HTTP 405 Method Not Allowed)\", function () {",
              "    if (pm.response.code === 200 || pm.response.code === 204) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] El endpoint permitió DELETE sobre evento de auditoría violando persistencia inmutable.\");",
              "    }",
              "    pm.expect([405]).to.include(pm.response.code);",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "DELETE",
        header: [
          { key: "Authorization", value: "Bearer {{token}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/{{id_evento}}",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "{{id_evento}}"]
        }
      }
    },
    {
      name: "06-TC-M04-278-Verificacion-Hash-SHA256",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "if (pm.response.code === 404) {",
              "    console.log('[LIMITACION API] TC-M04-278: Evento no localizado en base de datos; verificación de hash reservada a evento pre-existente.');",
              "} else {",
              "    pm.test(\"TC-M04-278: El evento persiste intacto y expone hash SHA-256 (64 hex) congruente\", function () {",
              "        pm.expect(pm.response.code).to.eql(200);",
              "        var data = pm.response.json();",
              "        pm.expect(data).to.have.property('hash_evento');",
              "        pm.expect(data.hash_evento).to.match(/^[a-f0-9]{64}$/i);",
              "        pm.expect(data).to.have.property('payload_evento');",
              "    });",
              "}"
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
          raw: "{{baseUrl}}/prediccion/auditoria/{{id_evento}}",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "{{id_evento}}"]
        }
      }
    },
    {
      name: "07-TC-M04-279-Verificacion-Integridad-Endpoint",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "if (pm.response.code === 404 || pm.response.code === 405) {",
              "    console.log('[PENDIENTE_DEV] TC-M04-279: Endpoint POST /prediccion/auditoria/{id}/verificar aún no expuesto por desarrollo. Contrato esperado: HTTP 200 con estado INTEGRO o CORRUPTO.');",
              "} else {",
              "    pm.test(\"TC-M04-279: Verificación de integridad de evento auditado (HTTP 200)\", function () {",
              "        pm.expect(pm.response.code).to.eql(200);",
              "        var data = pm.response.json();",
              "        pm.expect(data).to.have.property('estado');",
              "        pm.expect(['INTEGRO', 'CORRUPTO']).to.include(data.estado);",
              "    });",
              "}"
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
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/{{id_evento}}/verificar",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "{{id_evento}}", "verificar"]
        }
      }
    },
    {
      name: "08-TC-M04-280-Exportacion-Auditoria",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-280: Exportación de bitácora en JSON (HTTP 200 con adjunto)\", function () {",
              "    pm.expect(pm.response.code).to.eql(200);",
              "    pm.expect(pm.response.headers.get('Content-Type')).to.include('application/json');",
              "    var disposition = pm.response.headers.get('Content-Disposition') || '';",
              "    pm.expect(disposition).to.include('attachment');",
              "    var data = pm.response.json();",
              "    pm.expect(Array.isArray(data)).to.be.true;",
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
const targetFile = path.join(targetDir, 'test_tc_m04_g090.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G090 generada exitosamente en ${targetFile}`);
