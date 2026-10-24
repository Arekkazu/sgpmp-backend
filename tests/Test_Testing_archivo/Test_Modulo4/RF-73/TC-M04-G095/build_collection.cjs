/**
 * build_collection.cjs - TC-M04-G095: OWASP API8/API10 — Headers, Errores y Fuzzing (RF-73)
 * Herramienta: Postman / Newman
 * Módulo 4: Predicción e IA (Fase de Diseño y Construcción)
 * 
 * Subcasos:
 * - TC-M04-295: Headers de seguridad (CSP, HSTS, X-Frame, X-Content-Type) y política CORS
 * - TC-M04-296: Errores sin detalles internos (ausencia de stack traces, DB tracebacks)
 * - TC-M04-299: Fuzzing controlado de tipos, límites y longitudes extremas (siempre 4XX, nunca 500)
 */

const fs = require('fs');
const path = require('path');

const collection = {
  info: {
    name: "TC-M04-G095: OWASP API8/API10 - Headers, errores y fuzzing (RF-73)",
    _postman_id: "a0495001-0000-4000-8000-000000000095",
    description: "Diseño de pruebas para validar cabeceras de seguridad HTTP, control de excepciones sin fugas internas y robustez ante fuzzing en auditoría M04 (RF-73).",
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
              "pm.test(\"NW-01: Autenticación inicial del Administrador (HTTP 200)\", function () {",
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
      name: "02-TC-M04-295-Headers-Seguridad-HTTP",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-295a: Presencia de cabeceras de seguridad OWASP\", function () {",
              "    pm.expect(pm.response.code).to.eql(200);",
              "    pm.expect(pm.response.headers.get('X-Content-Type-Options')).to.eql('nosniff');",
              "    pm.expect(pm.response.headers.get('X-Frame-Options')).to.eql('DENY');",
              "    pm.expect(pm.response.headers.get('Strict-Transport-Security')).to.include('max-age');",
              "    pm.expect(pm.response.headers.get('Content-Security-Policy')).to.include(\"default-src 'none'\");",
              "    if (!pm.response.headers.get('Referrer-Policy')) {",
              "        console.log('[DISCREPANCIA] Header Referrer-Policy ausente en respuesta de API.');",
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
      name: "03-TC-M04-295-CORS-Preflight-Malicioso",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-295b: Rechazo de origen no permitido en preflight CORS\", function () {",
              "    var allowOrigin = pm.response.headers.get('Access-Control-Allow-Origin');",
              "    if (allowOrigin === '*') {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] Access-Control-Allow-Origin respondió comodín '*' con credenciales activas.\");",
              "    }",
              "    pm.expect(allowOrigin).to.not.eql('https://attacker.example');",
              "});"
            ]
          }
        }
      ],
      request: {
        method: "OPTIONS",
        header: [
          { key: "Origin", value: "https://attacker.example" },
          { key: "Access-Control-Request-Method", value: "GET" }
        ],
        url: {
          raw: "{{baseUrl}}/prediccion/auditoria",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"]
        }
      }
    },
    {
      name: "04-TC-M04-296-Errores-Sin-Detalles-Internos",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-296: Errores no revelan trazas internas ni stack traces\", function () {",
              "    pm.expect([400, 422]).to.include(pm.response.code);",
              "    var bodyStr = pm.response.text();",
              "    pm.expect(bodyStr).to.not.include('Traceback');",
              "    pm.expect(bodyStr).to.not.include('psycopg2');",
              "    pm.expect(bodyStr).to.not.include('sqlalchemy');",
              "    pm.expect(bodyStr).to.not.include('/src/');",
              "    var data = pm.response.json();",
              "    pm.expect(data).to.satisfy(function(d) {",
              "        return d.detail !== undefined || (d.error_code !== undefined && d.message !== undefined);",
              "    });",
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
          raw: "{{baseUrl}}/prediccion/auditoria?pagina=invalido",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "pagina", value: "invalido" }
          ]
        }
      }
    },
    {
      name: "05-TC-M04-299-Fuzzing-Tipo-Incorrecto-PorPagina",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-299a: Fuzzing por_pagina string 'abc' retorna HTTP 422/400 (nunca 500)\", function () {",
              "    if (pm.response.code >= 500) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] El servidor respondió HTTP \" + pm.response.code + \" ante entrada no tipada.\");",
              "    }",
              "    pm.expect([400, 422]).to.include(pm.response.code);",
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
          raw: "{{baseUrl}}/prediccion/auditoria?por_pagina=abc",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "por_pagina", value: "abc" }
          ]
        }
      }
    },
    {
      name: "06-TC-M04-299-Fuzzing-Valor-Negativo",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-299b: Fuzzing por_pagina=-1 es rechazado con HTTP 422 (nunca 500)\", function () {",
              "    if (pm.response.code >= 500) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] Error interno HTTP \" + pm.response.code + \" ante por_pagina negativo.\");",
              "    }",
              "    pm.expect([400, 422]).to.include(pm.response.code);",
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
          raw: "{{baseUrl}}/prediccion/auditoria?por_pagina=-1",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "por_pagina", value: "-1" }
          ]
        }
      }
    },
    {
      name: "07-TC-M04-299-Fuzzing-Numero-Gigante",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-299c: Fuzzing por_pagina=999999999 es rechazado con HTTP 422 (nunca 500)\", function () {",
              "    if (pm.response.code >= 500) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] Error interno HTTP \" + pm.response.code + \" ante por_pagina desbordado.\");",
              "    }",
              "    pm.expect([400, 422]).to.include(pm.response.code);",
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
          raw: "{{baseUrl}}/prediccion/auditoria?por_pagina=999999999",
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "por_pagina", value: "999999999" }
          ]
        }
      }
    },
    {
      name: "08-TC-M04-299-Fuzzing-String-Extremo",
      event: [
        {
          listen: "test",
          script: {
            type: "text/javascript",
            exec: [
              "pm.test(\"TC-M04-299d: Fuzzing con string de 10,000 caracteres no produce HTTP 500\", function () {",
              "    if (pm.response.code >= 500) {",
              "        pm.expect.fail(\"[DEFECTO CONOCIDO] Servidor devolvió HTTP \" + pm.response.code + \" ante string de 10k caracteres.\");",
              "    }",
              "    pm.expect([400, 414, 422]).to.include(pm.response.code);",
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
          raw: "{{baseUrl}}/prediccion/auditoria?id_referencia=" + "A".repeat(10000),
          host: ["{{baseUrl}}"],
          path: ["prediccion", "auditoria"],
          query: [
            { key: "id_referencia", value: "A".repeat(10000) }
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
const targetFile = path.join(targetDir, 'test_tc_m04_g095.json');
fs.writeFileSync(targetFile, JSON.stringify(collection, null, 2), 'utf8');
console.log(`Colección TC-M04-G095 generada exitosamente en ${targetFile}`);
