# TC-M09-G39 (agrupa TC-M09-81) — Actualización concurrente de la configuración operativa

**RF-18 / CU-04 — Gestionar Infraestructura Productiva**
**Tipo de prueba:** Concurrencia / Integración (Pytest) — requiere controlar el orden exacto
de dos escrituras entrelazadas sobre la misma fila; un cliente HTTP (Newman) no puede
orquestar eso de forma determinista.

## Ubicación del script

```
tests/Test_Testing/Test_Modulo9/RF-18/TC-M09-G39/test_rf18_concurrencia_actualizar_parametros.py
```

Usa los mismos fixtures reales de `tests/integration/conftest.py` (`db_session`,
`crear_usuario_db`) vía el `conftest.py` local de esta carpeta (igual patrón que
TC-M09-G38).

## Qué prueba

`ActualizarConfiguracionUseCase` aplica concurrencia optimista comparando el
`fecha_actualizacion` que trae el DTO del cliente contra el valor real en BD; si no
coinciden, lanza `PreconditionFailedError` (412) en vez de aplicar el cambio.

La prueba simula dos administradores que abrieron la pantalla de parámetros al mismo
tiempo (ambos parten del mismo `fecha_actualizacion`) usando **dos `Session` de SQLAlchemy
independientes**, cada una con su propio mapa de identidad, bindeadas a la misma conexión
de la prueba (mismo patrón que `crear_sesion_background` en `tests/integration/conftest.py`
para simular la sesión de otro request). Esto evita que la segunda sesión reuse en caché
el valor que la primera ya modificó: su lectura de concurrencia golpea la BD real, igual
que le pasaría a un request HTTP nuevo.

1. Admin 1 ejecuta el `PATCH` con el `fecha_actualizacion` leído → se acepta, la config
   queda en `frecuencia_muestreo=45, heartbeat=100`.
2. Admin 2 ejecuta su propio `PATCH` (valores distintos) con el **mismo**
   `fecha_actualizacion` original, ahora ya desactualizado → se rechaza con
   `PreconditionFailedError` / `CONFLICTO_CONCURRENCIA` (412).
3. Se confirma con un `SELECT` fresco que el estado final es el que dejó Admin 1, no el de
   Admin 2 (la operación de Admin 2 no tocó nada).

## Cómo correrlo

```powershell
$env:DATABASE_URL = "postgresql://usuario:clave@host:puerto/basedatos_test"
$env:TEST_DATABASE_URL = "postgresql://usuario:clave@host:puerto/basedatos_test"
python -m pytest "tests/Test_Testing/Test_Modulo9/RF-18/TC-M09-G39/test_rf18_concurrencia_actualizar_parametros.py" -m integration -v
```

Corre dentro de una transacción exterior que se revierte al finalizar (ver
`tests/integration/README.md`): no deja usuarios, configuraciones ni filas de auditoría
residuales en la base, sin importar contra qué entorno se ejecute.

## Resultado de la ejecución (2026-09-06)

Ejecutado contra la base de test compartida del proyecto (`docker-compose.test.yml`,
`sgpmp_test`):

```
tests/Test_Testing/Test_Modulo9/RF-18/TC-M09-G39/test_rf18_concurrencia_actualizar_parametros.py::test_TC_M09_81_segunda_actualizacion_concurrente_es_rechazada_con_412 PASSED

1 passed, 1 warning in 4.95s
```

Se confirmó, con una consulta aparte tras la corrida, que no quedó ningún efecto residual
en la base compartida (config activa, total de filas de auditoría y usuarios de prueba
idénticos a antes de correr la suite).

**Estado: PASA.** Ante dos actualizaciones concurrentes sobre la misma configuración, la
primera se acepta y la segunda se rechaza con 412 sin alterar el estado que dejó la
primera — el control de concurrencia optimista se comporta como exige el RF.
