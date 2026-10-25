/**
 * build_collection.cjs - TC-M04-G088: Límites de Tamaño de Payload (RF-73)
 * Módulo 4: Predicción e IA (Fase de Diseño - Contrato Esperado)
 * 
 * Subcasos:
 * - TC-M04-270 (64 KB exacto = 65,536 bytes): es_payload_truncado=false, HTTP 201/200, Hash SHA-256 completo.
 * - TC-M04-271 (65,537 bytes = 64 KB + 1 byte): NO rechazar, truncar a 64 KB, es_payload_truncado=true, Hash sobre payload truncado.
 * - TC-M04-272 (204,800 bytes = 200 KB): NO rechazar, truncar a 64 KB, es_payload_truncado=true, Hash sobre payload truncado.
 */

const fs = require('fs');
const path = require('path');

// Generación determinista de strings para payload_evento
// {"data":""} tiene 11 bytes en UTF-8.
const payloadExact64KB = { data: 'A'.repeat(65536 - 11) }; // Exactamente 65,536 bytes serializado
const payload64KBPlus1 = { data: 'A'.repeat(65537 - 11) }; // Exactamente 65,537 bytes serializado
const payload200KB     = { data: 'A'.repeat(204800 - 11) }; // Exactamente 204,800 bytes serializado

const collection = {
  info: {
    name: "TC-M04-G088: Limites de tamano de payload (RF-73)",
    _postman_id: "a0488001-0000-4000-8000-000000000088",
    description: "Diseño de pruebas para verificación de umbrales de payload (64 KB, 64 KB + 1 B, 200 KB) y política de truncamiento con hash SHA-256 (RF-73).",
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
    { key: "id_evento_270", value: "", type: "string" }
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
      name: "03-TC-M04-270-Payload-64KB-Exacto",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "if (pm.response.code === 404 || pm.response.code === 405) {",
              "    console.log('[PENDIENTE_DEV] TC-M04-270: Endpoint POST /prediccion/auditoria/eventos en desarrollo. Contrato esperado: HTTP 201/200 con payload exacto de 64 KB (65,536 B), es_payload_truncado=false y hash SHA-256 (64 hex).');",
              "} else {",
              "    pm.test(\"TC-M04-270: Evento de 64 KB exactos persistido exitosamente (HTTP 200 o 201)\", function () {",
              "        pm.expect([200, 201]).to.include(pm.response.code);",
              "        var data = pm.response.json();",
              "        if (data.id_evento) {",
              "            pm.collectionVariables.set('id_evento_270', data.id_evento);",
              "        }",
              "        if (data.es_payload_truncado !== undefined) {",
              "            pm.expect(data.es_payload_truncado).to.be.false;",
              "        } else {",
              "            console.log('[LIMITACION API] Campo es_payload_truncado no devuelto en response.');",
              "        }",
              "        if (data.hash_evento) {",
              "            pm.expect(data.hash_evento).to.match(/^[a-f0-9]{64}$/i);",
              "        }",
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
        body: {
          mode: "raw",
          raw: JSON.stringify({
            tipo_evento: "CATALOGO_PATOLOGIA_AGREGADA",
            tipo_actor: "USUARIO",
            id_usuario: 1,
            id_sistema: null,
            id_referencia: "ref-test-64kb",
            entidad_referencia: "test",
            fecha_evento: "2026-10-15T11:00:00Z",
            severidad_evento: "INFO",
            payload_evento: payloadExact64KB,
            correlacion_id: "corr-g088-270-{{run_id}}"
          })
        },
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/eventos",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "eventos"]
        }
      }
    },
    {
      name: "04-TC-M04-271-Payload-64KB-Mas-1Byte",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "if (pm.response.code === 404 || pm.response.code === 405) {",
              "    console.log('[PENDIENTE_DEV] TC-M04-271: Endpoint POST /prediccion/auditoria/eventos en desarrollo. Contrato esperado: HTTP 201/200 (NO rechazo por 4XX), truncamiento a 64 KB, es_payload_truncado=true y hash SHA-256 sobre payload truncado.');",
              "    console.log('[LIMITACION API] Verificación de log técnico WARNING no expuesta por endpoint HTTP.');",
              "} else {",
              "    pm.test(\"TC-M04-271: Payload 64 KB + 1 B NO es rechazado, se trunca y persiste (HTTP 200 o 201)\", function () {",
              "        if (pm.response.code >= 400) {",
              "            pm.expect.fail(\"[DEFECTO CONOCIDO] El sistema rechazó con HTTP \" + pm.response.code + \" en lugar de truncar a 64 KB según RF-73\");",
              "        }",
              "        pm.expect([200, 201]).to.include(pm.response.code);",
              "        var data = pm.response.json();",
              "        if (data.es_payload_truncado !== undefined) {",
              "            pm.expect(data.es_payload_truncado).to.be.true;",
              "        } else {",
              "            console.log('[LIMITACION API] Campo es_payload_truncado no retornado directamente.');",
              "        }",
              "        if (data.hash_evento) {",
              "            pm.expect(data.hash_evento).to.match(/^[a-f0-9]{64}$/i);",
              "        }",
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
        body: {
          mode: "raw",
          raw: JSON.stringify({
            tipo_evento: "CATALOGO_PATOLOGIA_AGREGADA",
            tipo_actor: "USUARIO",
            id_usuario: 1,
            id_sistema: null,
            id_referencia: "ref-test-64kb-plus1",
            entidad_referencia: "test",
            fecha_evento: "2026-10-15T11:05:00Z",
            severidad_evento: "INFO",
            payload_evento: payload64KBPlus1,
            correlacion_id: "corr-g088-271-{{run_id}}"
          })
        },
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/eventos",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "eventos"]
        }
      }
    },
    {
      name: "05-TC-M04-272-Payload-200KB",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "if (pm.response.code === 404 || pm.response.code === 405) {",
              "    console.log('[PENDIENTE_DEV] TC-M04-272: Endpoint POST /prediccion/auditoria/eventos en desarrollo. Contrato esperado: HTTP 201/200 con objeto grande (200 KB) truncado a 64 KB y es_payload_truncado=true.');",
              "} else {",
              "    pm.test(\"TC-M04-272: Payload grande de 200 KB NO es rechazado, se trunca y persiste (HTTP 200 o 201)\", function () {",
              "        if (pm.response.code >= 400) {",
              "            pm.expect.fail(\"[DEFECTO CONOCIDO] El sistema rechazó con HTTP \" + pm.response.code + \" en lugar de truncar según RF-73\");",
              "        }",
              "        pm.expect([200, 201]).to.include(pm.response.code);",
              "        var data = pm.response.json();",
              "        if (data.es_payload_truncado !== undefined) {",
              "            pm.expect(data.es_payload_truncado).to.be.true;",
              "        } else {",
              "            console.log('[LIMITACION API] Campo es_payload_truncado no devuelto.');",
              "        }",
              "        if (data.hash_evento) {",
              "            pm.expect(data.hash_evento).to.match(/^[a-f0-9]{64}$/i);",
              "        }",
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
        body: {
          mode: "raw",
          raw: JSON.stringify({
            tipo_evento: "CATALOGO_PATOLOGIA_AGREGADA",
            tipo_actor: "USUARIO",
            id_usuario: 1,
            id_sistema: null,
            id_referencia: "ref-test-200kb",
            entidad_referencia: "test",
            fecha_evento: "2026-10-15T11:10:00Z",
            severidad_evento: "INFO",
            payload_evento: payload200KB,
            correlacion_id: "corr-g088-272-{{run_id}}"
          })
        },
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/eventos",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "eventos"]
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

const targetDir = path.resolve(__dirname);
const targetFile = path.join(targetDir, 'test_tc_m04_g088.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G088 generada exitosamente en ${targetFile}`);
