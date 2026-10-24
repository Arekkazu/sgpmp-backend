/**
 * build_collection.cjs - TC-M04-G097: Resiliencia — Reintentos Automáticos (RF-73)
 * Herramienta: Postman / Newman
 * Módulo 4: Predicción e IA (Fase de Diseño y Construcción)
 * 
 * Subcasos:
 * - TC-M04-053: Reintento transitorio automático antes de activación de contingencia
 * 
 * NOTA DE ARQUITECTURA: La inyección de fallos transitorios en el pool de PostgreSQL
 * requiere manipulación de infraestructura (viola Regla #2 en sandbox) y se cataloga
 * formalmente como FASE SEPARADA — RESILIENCIA.
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M04-G097: Resiliencia - Reintentos automaticos (RF-73)",
    _postman_id: "a0497001-0000-4000-8000-000000000097",
    description: "Diseño de pruebas para validar la política de reintentos automáticos ante fallos transitorios de persistencia en auditoría M04 (RF-73).",
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
    { key: "token", value: "", type: "string" }
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
              "pm.test(\"NW-01: Autenticación exitosa Admin (HTTP 200)\", function () {",
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
      name: "02-Health-Disponibilidad-Servicio",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-053a: Estado del servicio de backend y persistencia (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [],
        url: {
          raw: "{{baseUrl}}/health",
          host: ["{{baseUrl}}"],
          path: ["health"]
        }
      }
    },
    {
      name: "03-TC-M04-053-Verificar-Inexistencia-Falla-Persistencia",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-053b: Verificación de ausencia de eventos de falla de persistencia (HTTP 200)\", function () {",
              "    pm.response.to.have.status(200);",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.have.property('items');",
              "    var fallas = (data.items || []).filter(function (it) {",
              "        return it.tipo_evento === 'AUDITORIA_FALLA_PERSISTENCIA' || it.tipo_evento === 'AUDITORIA_FALLBACK_ACTIVADO';",
              "    });",
              "    pm.expect(fallas.length).to.eql(0);",
              "    console.log('[FASE SEPARADA] TC-M04-053: Inyección de fallo puntual en conexión transitoria requiere entorno aislado fuera de sandbox.');",
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
          raw: "{{baseUrl}}/prediccion/auditoria?pagina=1&por_pagina=20",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "pagina", value: "1" },
            { key: "por_pagina", value: "20" }
          ]
        }
      }
    },
    {
      name: "04-Teardown-Sandbox-Rollback",
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
const targetFile = path.join(targetDir, 'test_tc_m04_g097.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G097 generada exitosamente en ${targetFile}`);
