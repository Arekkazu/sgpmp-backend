# TC-M03-G103 — RF-58 / CU04 (RNF-04)

Caso original: **TC-M03-203**. La carga inicial de la vista de monitoreo con 50 sensores activos debe ser inferior a 1 segundo, bajo condiciones documentadas.

## Escenario construido en el sandbox (APIs oficiales)

- **Unidad:** una unidad QA con **exactamente 50 sensores activos**. Cada sensor se registra, se asocia, se calibra y recibe una lectura válida (RF-53). Hay un dispositivo sin gateway, sin MQTT.
- **Actor:** Ingeniero de Campo, actor de CU04. La matriz no fija actor, y el Productor no tiene lectura sobre `modulo9.sensores` por RLS.
- **Precondiciones `[PRE]`:**
  - alcance del Ingeniero sobre la unidad;
  - los 50 sensores tienen estado actual en el sandbox (`modulo3.estados_actuales_sensores`, sin RLS);
  - en la carga inicial, la respuesta contiene exactamente esos 50 sensores con lectura.

  Si alguna falla, el caso queda BLOQUEADO, nunca RECHAZADO.

## Medición

- **Petición medida:** `GET /iot/monitoreo/dashboard?id_infraestructura=<unidad>&pagina=1&por_pagina=50`, la misma que hace la vista al filtrar por la unidad. La ejecuta Newman, de forma secuencial, 10 veces.
- **Decisoria (PERF-203-01):** la **primera** petición, que es la carga inicial. Debe cumplir < 1000 ms, estrictamente.
- **INFO:** las 9 repeticiones y sus estadísticos (mínimo, mediana, p95 y máximo), para documentar la reproducibilidad.
- **Condiciones registradas en la evidencia:**
  - fecha, destino, cliente y versión de Node;
  - volumen (50 sensores, 1 lectura por sensor), actor y parámetros;
  - tamaño de la respuesta;
  - latencia de referencia de la red;
  - sandbox activo: el RUN se atiende en una sola sesión transaccional sin confirmar;
  - la primera muestra incluye el establecimiento de la conexión del cliente.

No se usa Cypress: la matriz solo pide k6. Tampoco hay relojes falsos ni respuestas simuladas.

## REQUIERE DECISIÓN QA

1. **k6 frente a Newman.** La matriz propone k6, que no está instalado ni forma parte de las herramientas del paquete. Newman mide el mismo tiempo de respuesta HTTP con un único cliente secuencial.
2. **Estadístico decisorio.** Se tomó la primera carga, por ser la lectura literal de «carga inicial». Si QA prefiere un percentil (por ejemplo, p95 de las 10 muestras), basta cambiar qué aserción es `ASSERT` en la colección.
3. **Tiempo de API o de renderizado.** La matriz habla de «respuesta/renderizado inicial» y propone k6, que mide HTTP. El tiempo de renderizado en el navegador no se mide.
4. **Medición dentro del sandbox.** Los datos solo existen dentro del RUN, de modo que la medición incluye la sobrecarga del sandbox. Medir fuera exigiría datos persistentes, que no están autorizados.

## Aislamiento, rollback y veredicto

- **Aislamiento:** el testigo es el INSERT del dispositivo en `auditoria.logs_dml`. Se exige 1 dentro del RUN, 0 fuera y 0 tras el rollback. Una consulta fallida es «no verificable» y detiene el RUN.
- **Veredicto:**
  - RECHAZADO: la carga inicial ≥ 1000 ms con la vista correctamente preparada.
  - BLOQUEADO: fallos de precondición, entorno, rollback o automatización.
  - APROBADO: solo con PERF-203-01 verificada.

## Dependencias de Desarrollo

- **DEV-06:** la credencial del dispositivo está concentrada en `cuerpoLectura` (`monitoreo_lib.mjs`).
- **DEV-05:** si el estado actual pasa a post-commit, el `[PRE]` lo detecta y bloquea.

## Uso

```
node ejecutar_tc_m03_g103.mjs --validar-local
node --test validar_local_g103.mjs
node ejecutar_tc_m03_g103.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login
```

La ejecución solo procede con autorización de Desarrollo y `QA_AUTORIZADO=SI`. V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`. Cada RUN produce un informe Markdown y `evidencia.json`.
