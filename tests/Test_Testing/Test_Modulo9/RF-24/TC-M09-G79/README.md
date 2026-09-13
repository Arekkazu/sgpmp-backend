# TC-M09-G79 — RF-24, atomicidad de la calibración ante fallo de persistencia

Responsable QA Juan Esteban. No ejecutar G74–G78 desde aquí. No avanzar a otro grupo.
Herramienta: **Pytest**. Sin Cypress, sin Newman, **sin PostgreSQL directo**.

Ejecución `run-20260906` concluida. Decisión general: **APROBADO**.
TC-M09-150 APROBADO. Sin defectos que reportar.
Consultar `RESULTADOS/run-20260906/TC-M09-G79_resultado.md`.

| Caso | GIVEN | WHEN | THEN |
|---|---|---|---|
| TC-M09-150 | Calibración completamente válida sobre datos reales de TEST | Falla la persistencia de la auditoría, tras el flush de la calibración y antes del commit | Sin commit, con rollback, `AUDITORIA_CALIBRACION_FALLIDA` → HTTP 500, ningún dato parcial y históricos intactos |

## Tipo de evidencia — se declara sin rodeos

`integración transaccional controlada (harness Pytest en proceso)`

**No es E2E contra el backend desplegado.** TEST se consulta solo por **GET**: para
tomar datos reales y para demostrar al cierre que G79 no escribió nada allí.

Se ejecuta el **código real** de `RegistrarCalibracionUseCase`. Lo único inyectado es
el fallo; el commit, el rollback, el manejo de la excepción y el error resultante los
produce el producto.

- **Demuestra**: que el caso de uso no confirma, ejecuta rollback, envuelve el fallo
  en `InfrastructureError` con el mensaje de RF-24 (HTTP 500) y no deja calibración,
  auditoría huérfana, resto provisional ni histórico alterado.
- **No demuestra**: que el motor PostgreSQL descarte físicamente la fila del `flush`.
  Eso exige el harness `tests/integration` con `TEST_DATABASE_URL`, no disponible.

### Por qué no se usó PostgreSQL real

No hay `TEST_DATABASE_URL` ni `DATABASE_URL` en el entorno; `.env.dev` apunta al
puerto 5447, caído; crear la base exigiría `createdb` + `alembic upgrade head`, es
decir crear esquema y migrar, prohibido por el caso; y la base TEST desplegada tiene
usuario de solo lectura, con lo que probaría permisos, no atomicidad.

Se replica en su lugar el patrón ya establecido por
`tests/configuration/test_rf32_snapshot_rollback_atomicidad.py`: dobles de repositorio
que comparten una única `TransactionalStore` con áreas *staged* y *committed*, que es
como este proyecto verifica atomicidad entre repositorios sin PostgreSQL.

## Mapa transaccional verificado

```
try:
    calibracion_repo.guardar()   -> add + FLUSH  (escribe, no confirma)
    auditoria_repo.registrar()   -> punto de fault injection
    db.commit()
except Exception:
    db.rollback(); raise
```

Calibración y auditoría comparten transacción: **sí**. El fallo de auditoría se
envuelve en `InfrastructureError(AUDITORIA_CALIBRACION_FALLIDA)` → HTTP 500.

## Lo que NO se hizo para provocar el fallo

No se apagó ni reinició PostgreSQL, no se revocaron permisos, no se bloquearon
conexiones, no se eliminaron tablas, no se usaron credenciales incorrectas, no se
ejecutó SQL de ningún tipo y no se tocó infraestructura. El fallo se induce
exclusivamente dentro del proceso de prueba, sobre un doble del puerto de auditoría, y
esa excepción es la **precondición** del caso, no una incidencia de infraestructura.

Tampoco se fuerza un constraint distinto ni un dato inválido: eso probaría validación
de entrada, no atomicidad.

## Requisitos y ejecución

Ya instalados, no se instala nada: Python 3.13.13, pytest 9.0.3, SQLAlchemy 2.0.50.

Variables de proceso: `QA_EMAIL` y `QA_PASSWORD` (Ingeniero de campo), `G79_RUN_ID` y
`G79_INTENTO`. Las credenciales nunca se escriben en archivos; el tipo del token
redacta su `repr` para que pytest no lo vuelque en un traceback.

`src/shared/database.py` exige `DATABASE_URL` al importarse: el propio archivo QA fija
una URL que no apunta a ninguna base real. El engine de SQLAlchemy es perezoso y el
harness nunca lo usa, así que no se abre ninguna conexión. **No se modifica `src/`.**

```
# desde la raíz del backend
python -m pytest tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G79/test_tc_m09_150.py -v \
  --junitxml=tests/Test_Testing/Test_Modulo9/RF-24/TC-M09-G79/RESULTADOS/<run>/pytest-TC-M09-150-intentoN.xml

# cierre: verificación read-only en TEST, auditoría de secretos y Git
python verificar_cierre.py
```

Máximo **2 ejecuciones funcionales**, nunca una tercera. No se repite un PASS salvo
causa concreta; si una ejecución dejara datos parciales: detener, no limpiar, no
reparar y conservar los IDs.

## Evidencia

`RESULTADOS/<G79_RUN_ID>/` con el log y el JUnit XML por intento, el descubrimiento,
el JSON sanitizado por intento, la verificación final de solo lectura, el escaneo de
secretos, el estado de Git y el informe.

Estado inicial: ambas ramas en `qa/juan-esteban-m09`. SHAs locales: backend
`adc3932b9f0293a76ebec7e89ed877274791b6a1`, frontend
`966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`. SHA desplegado no confirmado.
