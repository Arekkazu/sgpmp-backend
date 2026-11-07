/**
 * build_collection.cjs - TC-M04-G082: Ciclo de Vida del Modelo (RF-73)
 * Módulo 4: Predicción e IA
 * 
 * Subcasos:
 * - TC-M04-253 (VERSION_REGISTRADA): [BLOQUEADO] - Requiere X-RF71-Internal-Key y artefacto binario ONNX de pipeline interno RF-71.
 * - TC-M04-254 (VERSION_APROBADA): [BLOQUEADO] - Evaluación de métricas ejecutada internamente durante el registro de RF-71.
 * - TC-M04-255 (VERSION_RECHAZADA): [BLOQUEADO] - Mismo motivo por acoplamiento a pipeline interno RF-71.
 * - TC-M04-256 (VERSION_ACTIVADA): POST /prediccion/modelos/{id_version}/activar y verificación en GET /prediccion/auditoria.
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M04-G082: Ciclo de vida del modelo (RF-73)",
    _postman_id: "a0482001-0000-4000-8000-000000000082",
    description: "Suite de auditoría para el ciclo de vida de versiones de modelos de IA (RF-73 / RF-69) bajo Sandbox Transaccional SGPMP.",
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
    { key: "id_version_aprobada", value: "", type: "string" },
    { key: "correlacion_id_g082", value: "e0482001-0000-4000-8000-000000000082", type: "string" }
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
      name: "02-TC-M04-253-Version-Registrada-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-253 (VERSION_REGISTRADA): POST /prediccion/modelos requiere autenticación de infraestructura X-RF71-Internal-Key y artefacto binario ONNX propio de pipeline CI/CD interno. Sin pm.test para evitar falsos positivos.');"
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
          raw: "{{baseUrl}}/prediccion/auditoria?tipo_evento=VERSION_REGISTRADA",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "tipo_evento", value: "VERSION_REGISTRADA" }
          ]
        }
      }
    },
    {
      name: "03-TC-M04-254-Version-Aprobada-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-254 (VERSION_APROBADA): La validación automática de métricas (f1>=0.80, recall>=0.85) es disparada internamente durante el registro de RF-71. Bloqueado por misma causa de clave interna.');"
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
          raw: "{{baseUrl}}/prediccion/auditoria?tipo_evento=VERSION_APROBADA",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "tipo_evento", value: "VERSION_APROBADA" }
          ]
        }
      }
    },
    {
      name: "04-TC-M04-255-Version-Rechazada-Diagnostico",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "console.log('[BLOQUEADO] TC-M04-255 (VERSION_RECHAZADA): El rechazo por f1=0.70 requiere emitir payload de registro con métricas deficientes vía endpoint interno de RF-71. Bloqueado por misma causa.');"
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
          raw: "{{baseUrl}}/prediccion/auditoria?tipo_evento=VERSION_RECHAZADA",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "tipo_evento", value: "VERSION_RECHAZADA" }
          ]
        }
      }
    },
    {
      name: "05-Descubrir-Version-Aprobada",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"05.01: Consulta de versiones de modelos en catálogo (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('items');",
              "    var aprobadas = (data.items || []).filter(function(v) { return v.estado_version === 'APROBADO'; });",
              "    if (aprobadas.length > 0) {",
              "        pm.collectionVariables.set('id_version_aprobada', String(aprobadas[0].id_version_modelo));",
              "        console.log('[INFO] Versión aprobada descubierta:', aprobadas[0].id_version_modelo);",
              "    } else {",
              "        console.log('[INFO] No se encontró ninguna versión con estado APROBADO en el catálogo actual.');",
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
          raw: "{{baseUrl}}/prediccion/modelos?estado=APROBADO&limit=10&offset=0",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "modelos"],
          query: [
            { key: "estado", value: "APROBADO" },
            { key: "limit", value: "10" },
            { key: "offset", value: "0" }
          ]
        }
      }
    },
    {
      name: "06-TC-M04-256-Activar-Version-Modelo",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "var idVersion = pm.collectionVariables.get('id_version_aprobada');",
              "if (!idVersion) {",
              "    console.log('[BLOQUEADO] TC-M04-256 (VERSION_ACTIVADA): No existe versión previa en estado APROBADO en la base de datos de TEST para ejecutar la activación.');",
              "} else {",
              "    pm.test(\"TC-M04-256: Activación de versión aprobada exitosa (HTTP 200)\", function () {",
              "        pm.response.to.have.status(200);",
              "        var data = pm.response.json();",
              "        pm.expect(data.estado_version).to.equal('ACTIVO');",
              "        pm.expect(data.esta_produccion).to.be.true;",
              "    });",
              "}"
            ]
          }
        }
      ],
      request: {
        method: "POST",
        header: [
          { key: "Authorization", value: "Bearer {{token}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/modelos/{{id_version_aprobada}}/activar",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "modelos", "{{id_version_aprobada}}", "activar"]
        }
      }
    },
    {
      name: "07-TC-M04-256-Verificar-Auditoria-Activada",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "var idVersion = pm.collectionVariables.get('id_version_aprobada');",
              "if (!idVersion) {",
              "    console.log('[BLOQUEADO] TC-M04-256: Omitida verificación de auditoría por falta de versión aprobada previa.');",
              "} else {",
              "    pm.test(\"TC-M04-256: Evento VERSION_ACTIVADA persistido en bitácora M04 (HTTP 200)\", function () {",
              "        pm.response.to.have.status(200);",
              "        var data = pm.response.json();",
              "        pm.expect(data).to.have.property('items');",
              "        var items = data.items || [];",
              "        pm.expect(items.length).to.be.above(0);",
              "        var evento = items[0];",
              "        pm.expect(evento.tipo_evento).to.equal('VERSION_ACTIVADA');",
              "        pm.expect(evento.tipo_actor).to.equal('USUARIO');",
              "        pm.expect(evento.severidad_evento).to.equal('INFO');",
              "        pm.expect(evento.resultado_operacion).to.equal('EXITOSO');",
              "        pm.expect(evento.hash_evento).to.be.a('string');",
              "        pm.expect(evento.hash_evento.length).to.equal(64);",
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
          raw: "{{baseUrl}}/prediccion/auditoria?tipo_evento=VERSION_ACTIVADA&id_referencia={{id_version_aprobada}}&pagina=1&por_pagina=10",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "tipo_evento", value: "VERSION_ACTIVADA" },
            { key: "id_referencia", value: "{{id_version_aprobada}}" },
            { key: "pagina", value: "1" },
            { key: "por_pagina", value: "10" }
          ]
        }
      }
    },
    {
      name: "08-Teardown-Sandbox-Rollback",
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
const targetFile = path.join(targetDir, 'test_tc_m04_g082.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G082 generada exitosamente en ${targetFile}`);
