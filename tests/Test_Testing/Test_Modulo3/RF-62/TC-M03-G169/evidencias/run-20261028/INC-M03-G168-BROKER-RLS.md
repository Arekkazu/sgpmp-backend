# INCIDENCIA: INC-M03-G168-BROKER-RLS

**Identificador:** `INC-M03-G168-BROKER-RLS`  
**Requerimientos:** RF-62 / RF-53  
**Módulo:** Módulo 3 (Telemetría e Ingesta IoT)  
**Severidad:** Severo (Bloqueante para suites de prueba con autosiembra en Sandbox)  
**Equipo Responsable:** Desarrollo Backend / DBA  
**Fecha de Detección:** 2026-10-28  
**Casos Afectados:** `TC-M03-G168`, `TC-M03-G169`  

---

## 1. Síntoma Observado

En peticiones dirigidas a `POST /iot/telemetria` (y `POST /iot/telemetria/batch`) autenticadas mediante `Authorization: Bearer <BROKER_SERVICE_TOKEN>`, el backend rechaza la ingesta con:

- Código HTTP: `HTTP 401 Unauthorized`
- Body:
  ```json
  {
    "error_code": "ERROR_AUTENTICACION",
    "message": "Dispositivo o sensor no encontrado o inactivo.",
    "fields": [],
    "timestamp": "2026-10-28T23:31:16.890123+00:00"
  }
  ```
- En llamadas batch, responde `HTTP 200 OK` silencioso con `aceptados = 0` y `rechazados = N`, indicando la misma causa interna.

El fallo ocurre a pesar de que:
1. El sensor y dispositivo fueron creados exitosamente (`HTTP 201 Created`) segundos antes dentro de la misma corrida transaccional (`X-Test-Run-Id`).
2. El sensor está debidamente asociado al área de la finca (`tiene_estado = true`).
3. La variable (`TEMPERATURA_AMBIENTAL`), categoría y rangos son válidos.

---

## 2. Causa Raíz (Técnica)

La tabla `modulo9.sensores` tiene configurada la política de seguridad a nivel de filas:
```sql
ALTER TABLE modulo9.sensores ENABLE ROW LEVEL SECURITY;
ALTER TABLE modulo9.sensores FORCE ROW LEVEL SECURITY;
```
La política `pol_sensores_select` filtra las filas accesibles asegurando que el usuario pertenezca a la finca mediante la tabla relacional `modulo1.usuarios_fincas`.

Cuando el token de broker se utiliza en `POST /iot/telemetria`, el middleware y contexto resuelven la identidad del usuario de servicio (`servicio.sistema@sgpmp.local`). 

Al crearse dinámicamente una finca en el sandbox durante la prueba (ej. `Finca <nombre>`), dicha finca se vincula únicamente al administrador que la crea (`id_usuario = 104`), pero **NO** se vincula a `servicio.sistema@sgpmp.local` en `modulo1.usuarios_fincas`.

Por consiguiente:
1. Al invocar `fn_validar_dispositivo` o consultar `modulo9.sensores`, la política RLS evalúa la pertenencia de `servicio.sistema@sgpmp.local`.
2. Como el usuario de servicio no está asociado a la finca recién creada, PostgreSQL retorna **cero filas** de forma transparente.
3. La lógica de negocio asume que el sensor no existe o está inactivo y emite `HTTP 401 ERROR_AUTENTICACION`.

---

## 3. Impacto en Cascada

Al fallar la ingesta en el subcaso:
1. La variable `tel_id` queda sin valor (vacía).
2. El siguiente paso (`POST /iot/calidad/{tel_id}/evaluar`) se ejecuta como `POST /iot/calidad//evaluar` o `POST /iot/calidad/evaluar`.
3. Al no existir un método POST sobre la raíz de `/iot/calidad` (solo existe `GET /iot/calidad`), FastAPI devuelve `HTTP 405 Method Not Allowed`.
4. Todas las aserciones de calidad y verificación de inmutabilidad de telemetría fallan en cascada.

---

## 4. Fixes Propuestos (Opciones de Solución)

1. **Opción A (Recomendada en BD):** Definir la función de validación de sensores como `SECURITY DEFINER` para que se ejecute con privilegios del schema owner y omita el bloqueo de RLS en la verificación técnica de hardware:
   ```sql
   ALTER FUNCTION modulo3.fn_validar_dispositivo(...) SECURITY DEFINER;
   ```
2. **Opción B (Excepción RLS):** Modificar la política RLS en `modulo9.sensores` (`pol_sensores_servicio` o similar) para que el rol de servicio (`servicio.sistema@sgpmp.local`) o superusuario tenga bypass explícito de pertenencia a fincas:
   ```sql
   CREATE POLICY pol_sensores_servicio ON modulo9.sensores
   FOR SELECT TO app_user
   USING (current_setting('app.current_user_email', true) = 'servicio.sistema@sgpmp.local');
   ```
3. **Opción C (Use Case Backend):** En `finca_repository.py` / `CrearFincaUseCase`, auto-asignar siempre el usuario de servicio (`servicio.sistema@sgpmp.local`) en `modulo1.usuarios_fincas` cada vez que se cree una nueva finca.

---

## Casos afectados (actualizado 2026-10-28)

- TC-M03-G168 — bloqueado en ejecución (documentado en §19.1 de la guía)
- TC-M03-G169 — corrida V1 ejecutada, resultado: RECHAZADO (9/27 asserts fail)
  por cascada del 401 en ingesta. No se reintenta hasta que este INC se resuelva.

## Estado del caso G169

- **Primera corrida (V1)**: 2026-10-28 — RECHAZADO
- **Reintento 1**: pendiente (bloqueado por este INC)
