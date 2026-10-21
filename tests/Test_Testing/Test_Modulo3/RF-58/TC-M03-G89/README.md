# TC-M03-G89 — Automatización QA reutilizable

RF-58 Monitoreo Ambiental en Tiempo Real · CU04 · Responsable QA: Juan Esteban · Prioridad Alta.
Fuente: `Casos_Prueba(Modulo3 Agrupado).csv`, fila TC-M03-G89. Endpoint: `GET /iot/monitoreo/dashboard`.
Herramienta de la matriz: Postman/Newman (sin escenarios UI).

Sin ejecuciones oficiales todavía: Desarrollo no ha autorizado la evaluación del Módulo 03.

## Casos

| Caso | Qué se comprueba |
| --- | --- |
| TC-M03-173 | Lectura 25 en el rango óptimo (VERDE) + alerta CRITICO activa → ROJO y se devuelve el `id_alerta` |
| TC-M03-174 | Base VERDE + alerta activa LEVE o MODERADO → AMARILLO; con la alerta RESUELTA o DESCARTADA → VERDE |

Las aserciones (PRE/ASSERT) están en `g89_casos.mjs`. El estado base VERDE se comprueba
**antes** de crear las alertas (PRE-173-04, PRE-174-04).

## Archivos

| Archivo | Función |
| --- | --- |
| `ejecutar_tc_m03_g89.mjs` | Único ejecutor: validación local y ejecución oficial. |
| `g89_casos.mjs` | Catálogo de casos y aserciones, plan de datos y efectos persistentes conocidos. |
| `g89_lib.mjs` | Funciones comunes del ejecutor (copia idéntica a la de G87 y G88). |
| `TC-M03-G89.postman_collection.json` | Escenarios API (20 peticiones). Sin autorización omite todas las peticiones. |
| `validar_local_g89.mjs` | Pruebas unitarias locales (`node --test`). |

## Uso

```powershell
node ejecutar_tc_m03_g89.mjs --validar-local
# Solo con autorización expresa de Desarrollo y QA_AUTORIZADO=SI:
node ejecutar_tc_m03_g89.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

Resultados:

- V1: `RESULTADOS/<RUN_ID>/TC-M03-G89_resultado.md`
- V2 y siguientes: `EvaluacionVN/RESULTADOS/<RUN_ID>/TC-M03-G89_reevaluacion_VN.md`

Cada RUN contiene el informe y `evidencia.json`; si aplica, también `newman/` con el HTML.

## Datos que prepara el ejecutor y la colección (sandbox, API oficial)

- **Especie:** sin Gateway Edge (comprobado por SQL), sin umbral para TEMPERATURA_AMBIENTAL y sin métricas obligatorias.
- **Área y activo:** área nueva de esa especie con un único activo INDIVIDUAL. RF-61 lo exige para VINCULAR la lectura y clasificarla con el umbral.
- **Sensores:** dispositivo sin gateway con 5 sensores calibrados, uno por situación de alerta (RF-57 deduplica por sensor y variable).
- **Umbral:** 20–30 °C (`precaucion [19,20] · normal [20,30] · critico [30,31]`), registrado por la colección.
- **Alertas:** creadas por `POST /iot/alertas` con la credencial del dispositivo, en dos variantes:
  - una resuelta por el ciclo oficial ACTIVA → EN_ATENCION → RESUELTA;
  - una DESCARTADA.

## Riesgos y efectos conocidos

- **Notificación de login:** cada login genera una notificación persistente fuera del sandbox. Exige `--aceptar-efectos notificacion-login` (2 logins por RUN).
- **Cuentas QA bloqueadas:** quedan bloqueadas para uso externo mientras el RUN está abierto.
- **Timeout del sandbox:** 180 s de inactividad.
- **Aislamiento:** se verifica con testigos sin RLS.
- **Alertas sin efectos externos:** solo escriben en `modulo3`, mediante triggers internos.
- **Hipótesis estática** (no confirmada): al resolver o descartar una alerta se limpia `id_alerta`, pero no se restaura `estado_semaforo`. API-174-04 y API-174-05 lo contrastan.
