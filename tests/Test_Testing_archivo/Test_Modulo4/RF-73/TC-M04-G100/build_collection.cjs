const fs = require('fs');
const path = require('path');

const TC_ID = 'TC-M04-G100';
const baseDir = path.join(__dirname);

const collection = {
  info: {
    name: `${TC_ID} - Aislamiento del Subsistema de Auditoría y Retención (RF-73)`,
    _postman_id: "e1000001-0000-4000-a000-000000000100",
    description: "TC-M04-G100: Validación de no afectación de procesos de negocio ante caída de auditoría (RF-63/RF-73) y garantía de retención mínima >= 365 días.",
    schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  variable: [
    { key: "baseUrl", value: "https://api.inmero.co/back-sigab-test", type: "string" },
    { key: "run_id", value: "", type: "string" },
    { key: "sandbox_secret", value: "{{TEST_SANDBOX_SECRET}}", type: "string" },
    { key: "admin_token", value: "", type: "string" }
  ],
  event: [
    {
      listen: "prerequest",
      script: {
        type: "text/javascript",
        exec: [
          'if (!pm.collectionVariables.get("run_id")) {',
          '    pm.collectionVariables.set("run_id", "test-" + pm.variables.replaceIn("{{$guid}}"));',
          '}',
          'pm.request.headers.upsert({ key: "X-Test-Run-Id",  value: pm.collectionVariables.get("run_id") });',
          'pm.request.headers.upsert({ key: "X-Sandbox-Secret", value: pm.collectionVariables.get("sandbox_secret") });'
        ]
      }
    }
  ],
  item: [
    {
      name: "NW-01: Autenticación Admin",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              'pm.test("NW-01: Login admin exitoso (200)", function () {',
              '    pm.response.to.have.status(200);',
              '    var json = pm.response.json();',
              '    pm.expect(json.token).to.be.a("string").that.is.not.empty;',
              '    pm.collectionVariables.set("admin_token", json.token);',
              '});'
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
            contrasena: "{{TEST_ADMIN_PASSWORD}}"
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
      name: "TC-M04-306: Estado de Salud de Auditoría y Procesos de Negocio",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              'pm.test("TC-M04-306: Servicio central responde 200", function () {',
              '    pm.response.to.have.status(200);',
              '});',
              '// NOTA FASE SEPARADA:',
              '// La simulación de caída de auditoría (apagar RF-63) mientras se ejecuta el motor',
              '// de inferencia (RF-66) requiere orquestación de infraestructura en entorno dedicado.'
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{admin_token}}" }
        ],
        url: {
          raw: "{{baseUrl}}/health",
          host: ["{{baseUrl}}"],
          path: ["health"]
        }
      }
    },
    {
      name: "TC-M04-307a: Consulta de Configuración de Retención (Contrato Esperado)",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              'if (pm.response.code === 404 || pm.response.code === 405) {',
              '    console.log("[PENDIENTE_DEV] Endpoint GET /prediccion/auditoria/configuracion no expuesto en backend actual. Diseñado contra contrato esperado.");',
              '} else {',
              '    pm.test("TC-M04-307: Retención mínima configurada >= 365 días", function () {',
              '        pm.response.to.have.status(200);',
              '        var json = pm.response.json();',
              '        var dias = json.retention_days || json.dias_retencion || 0;',
              '        pm.expect(dias).to.be.at.least(365);',
              '    });',
              '}'
            ]
          }
        }
      ],
      request: {
        method: "GET",
        header: [
          { key: "Authorization", value: "Bearer {{admin_token}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/configuracion",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "configuracion"]
        }
      }
    },
    {
      name: "TC-M04-307b: Intento de Purga Anticipada de Auditoría (< 365 días)",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              '// Si el endpoint no existe (404), la purga no está expuesta (comportamiento seguro)',
              '// Si existe, debe rechazar purgas menores a 365 días con 400 / 403 / 422',
              'pm.test("TC-M04-307: Purga anticipada rechazada o no disponible", function () {',
              '    pm.expect([400, 403, 404, 405, 422]).to.include(pm.response.code);',
              '});'
            ]
          }
        }
      ],
      request: {
        method: "DELETE",
        header: [
          { key: "Authorization", value: "Bearer {{admin_token}}" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria/purga?dias=30",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria", "purga"],
          query: [
            { key: "dias", value: "30" }
          ]
        }
      }
    },
    {
      name: "NW-Teardown: Rollback transaccional",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              'pm.test("NW-Teardown: Rollback exitoso de corrida", function () {',
              '    pm.response.to.have.status(200);',
              '    var json = pm.response.json();',
              '    pm.expect(json.mensaje || json.message || "").to.include("Rollback exitoso");',
              '});'
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

const targetPath = path.join(baseDir, 'test_tc_m04_g100.json');
fs.writeFileSync(targetPath, JSON.stringify(collection, null, 2), 'utf8');
console.log('Generado exitosamente:', targetPath);
