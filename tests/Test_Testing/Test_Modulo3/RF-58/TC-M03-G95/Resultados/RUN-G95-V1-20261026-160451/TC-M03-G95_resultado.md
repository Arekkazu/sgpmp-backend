# TC-M03-G95 — APROBADO

## Decisión del caso

Caso agrupado G95; original TC-M03-186. **Decisión:** **APROBADO**. Motivo: Oráculo completo y equivalencia aprobada. ¿RUN oficial? Sí. Falta: ninguna comprobación.

| ID | Fuente | Estado | Observado | Evidencia |
|---|---|---|---|---|
| UI-186-01 | UI | APROBADO | Sin GET 200 tras 401, Auto detenido, aviso de sesión terminada y login | cypress/UI-186-01.json |
| UI-186-02 | UI | APROBADO | Tras reingreso, monitoreo cargado con nuevo GET dashboard 200 | cypress/UI-186-01.json |
| API-186-01 | API | APROBADO | Token anterior rechazado: dashboard HTTP 401; refresh HTTP 401 | newman/newman-G95.json |

## Historial de intentos

- Intento 1, `RUN-G95-V1-20261026-154635` (`AUT-G95-V1-20261026`, 2026-10-26 ~15:46–15:47 UTC): **NO_CONCLUYENTE**, no oficial; el registro QA lo identificó como `TECNICO`. Login del Productor por UI HTTP 200; `/sesiones/refresh`, `/usuarios/me` y `/sesiones/me/permisos` HTTP 200 fuera del sandbox. Dashboard global HTTP 200 con 412 sensores. Cypress no encontró `input[type="number"]`: el frontend desplegado usaba el combobox «Área» (`origin/test` 81058af5) y el spec correspondía a d69b6e17. No hubo segundo login ni Newman. GET del Administrador dentro del RUN HTTP 200 con eco; DELETE HTTP 200; rollback CONFIRMADO. La discrepancia fue de automatización QA, corregida en ORD-G95-012. La evidencia nativa de este intento se eliminó por decisión del responsable QA el 2026-10-26, después de transcribir este resumen.
- Intento 2, `RUN-G95-V1-20261026-160451` (`AUT-G95-V1-R2-20261026`): **APROBADO**, RUN oficial. Sus evidencias se enumeran abajo y permanecen en esta carpeta.

## Decisiones metodológicas

Mecanismo, decisión del responsable QA (2026-10-26): «Acepto el segundo login real como mecanismo equivalente para G95. Corrige los detalles pendientes y deja listo el ensayo.» Segundo login real: el JWT anterior recibe 401 y el refresh previo 401/410; `src/shared/jwt.py:100-131` explica la respuesta al vencimiento. Frontend de referencia origin/test 81058af5: `src/shared/api/http.ts:203-243` intenta refresh y, ante rechazo 401/410, guarda motivo y ruta antes de redirigir; `src/shared/auth/AuthContext.tsx:162-189,224-234` gestiona la restauración; `src/auth/pages/LoginPage.tsx:29-45,74-80` y `src/shared/i18n/locales/es-CO/auth.json:52-63` muestran el aviso. No prueba el vencimiento temporal del JWT ni el temporizador de inactividad de 30 min.

Mensaje, decisión del responsable QA (2026-10-26): «No quiero que seas tan estricto con la evaluación, no rechaces la prueba simplemente porque no dice exactamente lo que se espera, Sesión cerrada o sesión expirada dan a entender lo mismo.» Sesión cerrada equivale a sesión expirada cuando el aviso visible comunica que la sesión terminó y hay que volver a ingresar. Aviso visible exacto observado en /login: "Sesión cerrada Cerramos tu sesión por seguridad: tu credencial de sesión se usó dos veces. Ingresa de nuevo y, si no fuiste tú, cambia tu contraseña.". Sin aviso visible, UI-186-01 no cumple.

Recarga, decisión del responsable QA (2026-10-26): «Sí, ajusta UI-186-02: aprueba si tras reingresar el dashboard de monitoreo se recarga con datos nuevos (navegando a él si hace falta); la página de aterrizaje y la pérdida de filtro/Auto ON van como observación.» Fuente: `tests/Test_Testing/Requerimientos/Especificacion-Requerimientos-Modulo3.md:5338-5350,5442-5446`. RF-58 E5: «Al reingresar, el dashboard se recarga con el estado más reciente»; postcondición 1: «El dashboard refleja el estado más reciente de todas las variables activas del usuario».

## Identificación

G95; TC-M03-186; RF-58/CU04 E5; V1; RUN RUN-G95-V1-20261026-160451; TEST; autorización AUT-G95-V1-R2-20261026; frontend de referencia SGPMP-FRONT-END-PWA origin/test 81058af57d5d80d523fb5225f8eab48e0307ba85; commit backend NO VERIFICADO; Node v22.15.1; herramientas {"newman":{"status":0,"error":null,"version":"6.2.2"},"cypress":{"status":0,"error":null,"version":"14.5.4"}}.

## Resumen de veredictos

TC-M03-186: APROBADO. Estado técnico OK; consume versión true.

## Esperado y observado

Esperado literal de la matriz: La actualización automática se detiene, se muestra el aviso de sesión expirada y se redirige al login sin pérdida del estado visual; al reingresar, el dashboard se recarga con el estado más reciente.

Observado: {
  "ui": {
    "caso": "TC-M03-186",
    "id": "UI-186-01/UI-186-02",
    "mecanismo": "segundo_login_real",
    "captura": true,
    "dashboard_inicial_200": true,
    "auto_on": true,
    "periodica_200": true,
    "auto_motivo": null,
    "filtro_fijado": true,
    "filtro_id": 3,
    "segundo_login_200": true,
    "dashboard_rechazado_401": true,
    "redirigido_login": true,
    "aviso_sesion_terminada": true,
    "sin_200_vencida": true,
    "auto_detenido": true,
    "estado_visual_conservado": false,
    "aviso_texto": "Sesión cerrada Cerramos tu sesión por seguridad: tu credencial de sesión se usó dos veces. Ingresa de nuevo y, si no fuiste tú, cambia tu contraseña.",
    "filtro_conservado": false,
    "auto_conservado": true,
    "retorno_automatico": true,
    "ruta_aterrizaje": "/telemetria/monitoreo",
    "navegacion_manual": false,
    "reingreso_200": true,
    "monitoreo_cargado": true,
    "error_interno_visible": false,
    "recarga_200_posterior": true,
    "infra_5xx": false,
    "error_qa": null,
    "error_selector": null,
    "bloqueo_datos": null,
    "e7_riesgo": false,
    "e7_motivo": "UNIDAD_COMPLETA_SIN_GRIS_VIGENTE_EN_PRIMERA_PAGINA",
    "lecturas_dashboard": 7,
    "peticiones": [
      {
        "metodo": "POST",
        "ruta": "/api-sgpmp-test/sesiones/",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "POST",
        "ruta": "/api-sgpmp-test/sesiones/refresh",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/configuracion/interfaz/contexto",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/usuarios/me",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/sesiones/me/permisos",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/configuracion/personalizacion/idioma",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/configuracion/personalizacion/tema",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/notificaciones",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/iot/monitoreo/dashboard",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/iot/monitoreo/dashboard",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/iot/monitoreo/dashboard",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/iot/monitoreo/dashboard",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/iot/monitoreo/dashboard",
        "http": 401,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "POST",
        "ruta": "/api-sgpmp-test/sesiones/refresh",
        "http": 401,
        "fuera_sandbox": true,
        "posterior_reingreso": false
      },
      {
        "metodo": "POST",
        "ruta": "/api-sgpmp-test/sesiones/",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": true
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/sesiones/me/permisos",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": true
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/usuarios/me",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": true
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/configuracion/interfaz/contexto",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": true
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/configuracion/personalizacion/tema",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": true
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/configuracion/personalizacion/idioma",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": true
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/notificaciones",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": true
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/iot/monitoreo/dashboard",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": true
      },
      {
        "metodo": "GET",
        "ruta": "/api-sgpmp-test/iot/monitoreo/dashboard",
        "http": 200,
        "fuera_sandbox": true,
        "posterior_reingreso": true
      }
    ]
  },
  "admin": {
    "http": 200,
    "eco": true
  }
}. Aviso visible exacto en /login: "Sesión cerrada Cerramos tu sesión por seguridad: tu credencial de sesión se usó dos veces. Ingresa de nuevo y, si no fuiste tú, cambia tu contraseña.".

## Observaciones

- Filtro por unidad no conservado
- El aviso observado corresponde a una credencial reutilizada («tu credencial de sesión se usó dos veces») por el mecanismo de segundo login. El texto ante un vencimiento por tiempo no se observó.

## Comprobaciones API/UI

| UI-186-01 | UI | APROBADO | Sin GET 200 tras 401, Auto detenido, aviso de sesión terminada y login | cypress/UI-186-01.json |
| UI-186-02 | UI | APROBADO | Tras reingreso, monitoreo cargado con nuevo GET dashboard 200 | cypress/UI-186-01.json |
| API-186-01 | API | APROBADO | Token anterior rechazado: dashboard HTTP 401; refresh HTTP 401 | newman/newman-G95.json |

## Evidencias reales

- preflight.json
- cypress/UI-186-01.log
- cypress/g95.cy.js/UI-186-01-pagina-completa.png
- cypress/UI-186-01.json
- cypress/UI-186-01-cypress.json
- newman/newman-G95.json
- newman/newman-G95.html
- resultado.json
- TC-M03-G95_resultado.md

## Incidencias de producto

Sin discrepancias funcionales acreditadas en TEST.

## Incidencias técnicas QA

- Intento 1: selector obsoleto `input[type="number"]` frente al combobox «Área» del frontend desplegado; incidencia de automatización QA resuelta en ORD-G95-012. No acreditó un defecto de producto.
- Intento 2: desviación del presupuesto de SOL-G95-013: 7 lecturas del dashboard frente a «hasta 6» autorizadas. El spec ejecutado permitía 8; el límite futuro se corrigió a 6 en ORD-G95-014. No hubo escrituras de escenario; la unidad filtrada registró `e7_riesgo: false`. El alcance de posibles efectos de la carga global se describe abajo.

## Análisis de causas

La primera discrepancia pública orienta la atención inicial; la causa raíz no se atribuye por inferencia del código local.

## Efectos fuera del RUN

Logins del Productor y Administrador, reemplazo y rotación de sesión, último acceso, auditoría, notificaciones y lecturas del dashboard pueden persistir. La primera carga global puede activar correo E7; DELETE no revierte estos efectos. Riesgo E7 de la unidad filtrada: false; motivo: UNIDAD_COMPLETA_SIN_GRIS_VIGENTE_EN_PRIMERA_PAGINA. Lecturas del dashboard: 7 (límite autorizado: 6, SOL-G95-013; límite del spec ejecutado: 8). Productor: cero peticiones dentro del sandbox.

## Cierre y rollback

DELETE HTTP 200. Rollback CONFIRMADO: Sin escrituras de escenario dentro del RUN; DELETE 200. Sin escrituras de escenario dentro del RUN; DELETE 200. No se declaran revertidos los efectos externos.

Peticiones directas (sin credenciales): [{"metodo":"POST","ruta":"/sesiones/","http":200,"en_run":false,"eco":null},{"metodo":"GET","ruta":"/usuarios/me","http":200,"en_run":true,"eco":true},{"metodo":"DELETE","ruta":"/test-control/runs/RUN-G95-V1-20261026-160451","http":200,"en_run":false,"eco":null}].

## Conclusión y acción concreta

APROBADO. Responsable QA: revisar la evidencia pública y derivar las discrepancias confirmadas.
