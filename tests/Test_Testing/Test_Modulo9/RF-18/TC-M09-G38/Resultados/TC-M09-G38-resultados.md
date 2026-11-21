# TC-M09-G38 (agrupa TC-M09-80) — Rollback de parámetros operativos ante fallo de auditoría

**RF-18 / CU-04 — Gestionar Infraestructura Productiva**
**Tipo de prueba:** Integración (Pytest) — no es un caso Newman/HTTP: requiere forzar un
fallo real en el subsistema de auditoría y verificar el rollback directamente en BD, no
solo el código de respuesta de un endpoint.

## Ubicación del script

```
tests/Test_Testing/Test_Modulo9/RF-18/TC-M09-G38/test_rf18_rollback_auditoria_parametros.py
```

Vive junto a la evidencia del caso (esta carpeta) en vez de en `tests/integration/`, pero
necesita los mismos fixtures reales de esa suite (`db_session`, `crear_usuario_db` — sesión
con savepoints sobre PostgreSQL real). `conftest.py`, en esta misma carpeta, carga por ruta
el `conftest.py` de `tests/integration/` y reexporta esos fixtures en vez de duplicar su
lógica, para no desincronizarse si ese archivo cambia.

## Qué prueba

`ActualizarConfiguracionUseCase.execute()` escribe la config y el registro de auditoría en
la misma transacción y hace `rollback()` ante cualquier excepción:

```python
try:
    config_actualizada = self.config_repo.actualizar(config)
    self.auditoria_repo.registrar(...)
    self.db.commit()
except Exception:
    self.db.rollback()
    raise
```

El script ejercita el repositorio SQLAlchemy **real** de `configuraciones_globales` contra
PostgreSQL (no un fake en memoria) y fuerza el fallo únicamente en el subsistema de
auditoría con un adaptador roto (`_AuditoriaRotaFake.registrar()` lanza `RuntimeError`),
simulando el fallo real que pide el caso (ej.: constraint violado, tabla bloqueada, error
de serialización JSONB en `AuditoriaConfigModel`). Verifica el estado con un `SELECT`
fresco después del fallo -no el objeto de dominio en memoria, que el use case ya había
mutado antes de intentar persistir- exactamente lo que pide la nota de clasificación del
caso ("verificar el rollback en BD").

Dos pruebas:

1. **`test_TC_M09_80_fallo_de_auditoria_revierte_la_modificacion_de_parametros`** — con el
   adaptador de auditoría roto: confirma que `frecuencia_muestreo`/`heartbeat`/
   `fecha_actualizacion` quedan exactamente como estaban antes del intento, y que no queda
   ninguna fila nueva en `auditorias_configuraciones_globales`.
2. **`test_control_modificacion_exitosa_persiste_y_deja_registro_de_auditoria`** — control
   positivo con el `SqlAlchemyAuditoriaConfigRepository` real (sin forzar el fallo):
   confirma que el arnés sí distingue éxito de fallo (no está sesgado a que el rollback
   ocurra siempre por otra razón) y que en el camino feliz sí persisten los nuevos valores
   y sí se crea la fila de auditoría.

## Cómo correrlo

Requiere una base de datos de test con el esquema `modulo9` aplicado (ver
`tests/integration/README.md`). La variable se define solo en la terminal, nunca en un
archivo versionado:

```powershell
$env:DATABASE_URL = "postgresql://usuario:clave@host:puerto/basedatos_test"      # requerido por src/shared/database.py al importar el paquete
$env:TEST_DATABASE_URL = "postgresql://usuario:clave@host:puerto/basedatos_test" # BD real usada por la prueba
python -m pytest "tests/Test_Testing/Test_Modulo9/RF-18/TC-M09-G38/test_rf18_rollback_auditoria_parametros.py" -m integration -v
```

Cada prueba corre dentro de una transacción exterior que se revierte al finalizar (ver
`tests/integration/conftest.py`): no deja usuarios, configuraciones ni filas de auditoría
residuales en la base, sin importar contra qué entorno se ejecute.

## Resultado de la ejecución (2026-09-06)

Ejecutado contra la base de test compartida del proyecto (`docker-compose.test.yml`,
`sgpmp_test`):

```
tests/Test_Testing/Test_Modulo9/RF-18/TC-M09-G38/test_rf18_rollback_auditoria_parametros.py::test_TC_M09_80_fallo_de_auditoria_revierte_la_modificacion_de_parametros PASSED
tests/Test_Testing/Test_Modulo9/RF-18/TC-M09-G38/test_rf18_rollback_auditoria_parametros.py::test_control_modificacion_exitosa_persiste_y_deja_registro_de_auditoria PASSED

2 passed, 1 warning in 7.42s
```

Se confirmó además, con una consulta aparte tras la corrida, que no quedó ningún efecto
residual en la base compartida (config activa, total de filas de auditoría y usuarios de
prueba idénticos a antes de correr la suite).

**Estado: PASA.** El rollback ante fallo de auditoría se comporta como exige el RF: ni la
configuración ni un registro parcial de auditoría sobreviven a un fallo del subsistema de
auditoría.
