# Solicitud de Permisos de Base de Datos para QA (DBA)

## Resumen Ejecutivo
Para permitir la ejecución de las suites de prueba de integración y pruebas unitarias de persistencia directa del módulo 3 (específicamente **RF-63: Auditoría y Trazabilidad de Telemetría IoT**, caso de prueba **TC-M03-G191**), se requiere que el usuario de pruebas `member_qa` tenga permisos de ejecución sobre la función `modulo1.fn_es_usuario_servicio()`.

Actualmente, las políticas RLS (Row Level Security) activadas en `modulo3.bitacora_auditoria_iot` invocan dicha función durante las consultas `SELECT` e inserciones `INSERT`, provocando una falla de privilegios insuficientes (`SQLSTATE 42501`).

---

## 1. Base de Datos
- **Instancia / Host:** `158.69.200.27`
- **Puerto:** `5448`
- **Nombre de Base de Datos:** `sgpmp_test`
- **Ambiente:** TEST (Pre-producción / Pruebas Automatizadas)

---

## 2. Usuario / Rol Beneficiario
- **Rol / Usuario:** `member_qa`

---

## 3. Objeto Afectado
- **Esquema:** `modulo1`
- **Objeto:** `FUNCTION modulo1.fn_es_usuario_servicio()`

---

## 4. Privilegio Solicitado
- **Privilegio:** `EXECUTE`

---

## 5. Comando SQL Sugerido
```sql
GRANT EXECUTE ON FUNCTION modulo1.fn_es_usuario_servicio() TO member_qa;
```

*(En caso de que existan sobrecargas o esquemas de búsqueda específicos, asegurar el grant sobre todas las firmas de la función en `modulo1`)*:
```sql
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA modulo1 TO member_qa; -- Opcional / Alternativa para esquema completo de utilidades en TEST
```

---

## 6. Justificación Técnica
- **Contexto Operativo:**
  La Restricción 4.4 del RF-63 estipula que los eventos de telemetría IoT provienen de un bus de mensajería interno y no de endpoints HTTP públicos expuestos al usuario. Por ello, la suite de pruebas `TC-M03-G191` (Pytest) valida la persistencia y completitud de eventos mediante interacción directa con `RegistrarEventoAuditoriaIotUseCase` y `SqlAlchemyBitacoraAuditoriaIotRepository`.
- **Comportamiento en Runtime:**
  Al ejecutar transacciones sobre `modulo3.bitacora_auditoria_iot`, las políticas RLS de PostgreSQL evalúan la regla de servicio invocando `modulo1.fn_es_usuario_servicio()`.
- **Error Capturado en Diagnóstico:**
  ```text
  sqlalchemy.exc.ProgrammingError: (psycopg2.errors.InsufficientPrivilege) permission denied for function fn_es_usuario_servicio
  [SQL: SELECT modulo3.bitacora_auditoria_iot.id_evento AS ... FROM modulo3.bitacora_auditoria_iot WHERE ...]
  [SQLSTATE: 42501]
  ```
- **Conclusión:** Sin este permiso, PostgreSQL bloquea tanto la consulta de verificación como la inserción bajo el rol `member_qa`, impidiendo la validación automatizada de CA-13.

---

## 7. Impacto y Análisis de Riesgo de Seguridad
- **Tipo de Función:** `fn_es_usuario_servicio()` es una función de evaluación lógica / consulta de contexto de sesión y roles.
- **Mutabilidad:** NO realiza mutación de datos (`INSERT`, `UPDATE`, `DELETE`) ni operaciones DDL sobre ningún esquema.
- **Alcance:** El cambio se solicita exclusivamente para la base de datos de pruebas `sgpmp_test` en el puerto `5448`. No compromete ambientes de producción ni modifica datos productivos.
- **Nivel de Riesgo:** **MÍNIMO / INEXISTENTE**. Permite que el usuario técnico de QA opere en coherencia con las políticas RLS definidas por el equipo de seguridad.

---

## 8. Casos de Prueba Afectados
1. **TC-M03-G191:** Tolerancia a eventos incompletos de telemetría IoT (RF-63, CA-13).
2. **TC-M03-367:** Subcaso nominal agrupado en G191 para eventos sin `tipo_evento` o sin `componente_origen`.
3. **Validaciones Directas DB:** Todas las suites y scripts de diagnóstico directo que consulten o auditen `modulo3.bitacora_auditoria_iot` utilizando las credenciales asignadas a QA en `.env.test`.

