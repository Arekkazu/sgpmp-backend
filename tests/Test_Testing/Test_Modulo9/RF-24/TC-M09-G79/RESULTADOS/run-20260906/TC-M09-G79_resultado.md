# TC-M09-G79 — RESULTADO

## DECISIÓN GENERAL

**APROBADO**

Ante un fallo controlado en la persistencia de auditoría, el registro de calibración
no deja ningún dato parcial: el producto no confirma la transacción, ejecuta rollback
y convierte el fallo en el error de trazabilidad que RF-24 define, con HTTP 500. Los
históricos previos permanecen intactos. No hay defectos que reportar.

| Caso | Resultado | Motivo | Categoría de error | Equipo responsable | Acción |
| ---------- | -------------------------------- | ------ | ------------------ | ------------------ | ------ |
| TC-M09-150 | **APROBADO** | Calibración válida + fallo inyectado en la persistencia de auditoría: 0 commits, 1 rollback, `InfrastructureError AUDITORIA_CALIBRACION_FALLIDA` → HTTP 500, ninguna calibración ni auditoría persistida, escritura provisional descartada y las dos calibraciones históricas conservadas | No aplica | No aplica | Ninguna |

Responsable QA: Juan Esteban. M09 / RF-24 / CU-05. Prioridad alta. Tipo: integridad.
Técnica: pruebas de integración. Herramienta: **Pytest**. Actor: Ingeniero de campo.
Sin Cypress, sin Newman, **sin PostgreSQL directo**. G74, G75, G76, G77 y G78 no se
ejecutaron. No se avanzó a ningún otro grupo.

---

## ALCANCE Y TIPO DE EVIDENCIA

`Tipo de evidencia: integración transaccional controlada (harness Pytest en proceso).`

**No fue una prueba E2E contra el backend desplegado.** El entorno TEST se consultó
únicamente por **GET**, para dos cosas: tomar datos reales con los que parametrizar
el escenario y demostrar al cierre que G79 no escribió nada allí.

Qué demuestra esta evidencia, ejecutando el **código real** de
`RegistrarCalibracionUseCase`:

- que el caso de uso **no llama a `commit()`** cuando la auditoría falla;
- que **llama a `rollback()`** exactamente una vez;
- que convierte la excepción de persistencia en `InfrastructureError` con el código y
  el mensaje que RF-24 exige, mapeado a **HTTP 500** por la jerarquía de errores real;
- que, sobre una sesión que emula flush/commit/rollback, no queda calibración, ni
  auditoría huérfana, ni resto provisional, ni alteración de los históricos.

Qué **no** demuestra, y se declara sin rodeos: que el motor PostgreSQL descarte
físicamente la fila ya insertada por el `flush()`. Eso exigiría el harness de
integración con una base migrada, que no estaba disponible (ver más abajo). La
garantía verificada aquí es la del control transaccional del producto, que es donde
vive el defecto que TC-M09-150 busca.

### Por qué no se usó el harness con PostgreSQL real

`tests/integration/conftest.py` existe y sería la evidencia más fuerte, pero exige
`TEST_DATABASE_URL` apuntando a una base de pruebas dedicada y ya migrada:

- no hay ninguna `TEST_DATABASE_URL` ni `DATABASE_URL` definida en el entorno;
- `.env.dev` apunta al puerto **5447**, donde no responde ningún servicio;
- crearla implicaría `createdb` + `alembic upgrade head`, es decir **crear una base y
  ejecutar migraciones**, que este caso prohíbe expresamente;
- la base TEST desplegada no sirve: el usuario QA es de solo lectura y calibrar
  requiere escribir, lo que además probaría «conectividad/permisos», no atomicidad.

Se optó por el **harness ya establecido en el proyecto** para esta misma propiedad:
`tests/configuration/test_rf32_snapshot_rollback_atomicidad.py`, que ejecuta el use
case real con dobles de repositorio que comparten una única `TransactionalStore` con
áreas *staged* y *committed*, precisamente para verificar atomicidad entre
repositorios sin PostgreSQL. G79 replica ese patrón. **No se inventó un mecanismo
nuevo ni se modificó nada del producto.**

---

## TRANSACCIÓN IDENTIFICADA

Revisión de solo lectura de `registrar_calibracion_use_case.py` y
`calibracion_repository.py`:

`Inicio transacción:` la sesión inyectada en el caso de uso; el bloque transaccional
efectivo empieza en `try:` justo antes de `calibracion_repo.guardar(...)`.

`Escritura calibración:` `SqlAlchemyCalibracionRepository.guardar()` hace
`db.add(orm)` + **`db.flush()`** + `db.refresh(orm)`. **Escribe, pero no confirma.**

`Escritura auditoría:` `auditoria_repo.registrar(...)`, dentro del mismo `try`,
**después** del flush de la calibración.

`Commit esperado:` `self.db.commit()`, una sola vez, **después** de la auditoría.

`Rollback handler:` `except Exception: self.db.rollback(); raise` que envuelve ambas
escrituras. Además, el fallo de auditoría se envuelve antes en
`InfrastructureError(AUDITORIA_CALIBRACION_FALLIDA)`.

`Misma transacción calibración/auditoría:` **Sí.** Ambas escrituras ocurren sobre la
misma sesión y entre el mismo `try` y el único `commit()`. La arquitectura permite la
garantía que RF-24 exige, así que no procede la salvedad prevista para el caso
contrario.

## FAULT INJECTION

`Mecanismo:` doble de `AuditoriaCalibracionRepository` —la interfaz real del puerto de
dominio— que lanza la excepción en lugar de escribir. Es fault injection, no un mock
de éxito: el commit, el rollback, el manejo de la excepción y el error resultante los
produce el producto.

`Punto exacto:` `auditoria_repo.registrar()`, **después** del flush de la calibración
y **antes** del commit. Es el flujo alterno «Fallo en el registro de auditoría» que
RF-24 describe; no se inventó un fallo distinto.

`Excepción:` `sqlalchemy.exc.OperationalError`, del tipo que el código real afronta
ante un fallo de persistencia. No se forzó un constraint distinto ni un dato inválido,
porque eso probaría validación de entrada y no atomicidad.

`Modificó infraestructura:` **No.**

`Modificó producto:` **No.**

`Fault point alcanzado:` **Sí** — la auditoría se intentó exactamente una vez y la
prueba capturó el estado provisional en ese instante.

`Determinismo:` total. No depende de carreras, timeouts ni saturación: se sabe
exactamente qué operación falló.

`Prueba de que el fallo ocurrió con escritura previa ya realizada:` en el momento de
llamar a la auditoría, el área provisional contenía **una** calibración nueva con el
valor enviado, además de los históricos. Es la evidencia de «flush sí, commit no».

Configuración de arranque del harness: el archivo QA fija `DATABASE_URL` a una URL
que no apunta a ninguna base real, porque `src/shared/database.py` la exige al
importarse. El engine de SQLAlchemy es perezoso y el harness nunca usa `engine` ni
`SessionLocal` —la sesión la sustituye el doble—, de modo que no se abre ninguna
conexión. No se modificó `src/` ni ninguna configuración desplegada.

---

## DATOS UTILIZADOS

Descubiertos por GET contra TEST real, sin IDs supuestos y sin POST exploratorios.

| Dato | Valor |
|---|---|
| Actor | Ingeniero de campo, `id_usuario` 4, permisos recurso 12: **C=1, R=2, U=3** |
| Dispositivo | **3** — `IOT-ALE01-HLA-003`, activo |
| Sensor | **6** — «Sensor temperatura alevinera-01», `TEMPERATURA`, activo, del dispositivo 3 |
| Área | **3** — «Zona de incubación, profundidad 15 cm», asociación vigente |
| Rango técnico | `TEMPERATURA 0.0000 – 45.0000`, de `GET /configuracion/sensores/rangos-calibracion` |
| Valor | **22.5000** — interior del rango, con aritmética decimal exacta |
| Historial previo del sensor | **2** calibraciones: **#10** (`0.0000`) y **#11** (`45.0000`) |

La calibración es completamente válida: dispositivo activo, sensor perteneciente a
él, área correcta, valor dentro del rango y actor autorizado. **Una ejecución de
control sin fault injection registra esa misma calibración con éxito** (1 commit, 0
rollbacks, auditoría escrita), lo que demuestra que la única variable que cambia el
resultado es el fallo inyectado, no el dato.

---

## TABLA BEFORE / AFTER

| Recurso | BEFORE | AFTER | Diferencia esperada | Observado |
| ------------------------------ | ------ | ----- | ------------------- | --------- |
| Calibraciones del sensor (harness) | 2 (#10, #11) | 2 (#10, #11) | Ninguna | **Ninguna** |
| Auditoría relacionada (harness) | 0 | 0 | Ninguna | **Ninguna** |
| Área provisional de la sesión | = confirmado | = confirmado | Ninguna | **Ninguna** |
| Historial real del sensor en TEST | 2 (`[11, 10]`) | 2 (`[11, 10]`) | Ninguna | **Ninguna** |

## CONSISTENCIA

`Calibración parcial encontrada:` **No**

`Auditoría parcial encontrada:` **No**

`Registro huérfano encontrado:` **No**

`Histórico previo alterado:` **No** — #10 y #11 conservan valor y fecha exactos

`Rollback completo:` **Sí** — 0 commits, 1 rollback, y el área provisional quedó
idéntica al estado confirmado

## RESPUESTA

`Status esperado:` HTTP 500 (RF-24, flujo alterno de fallo de auditoría)

`Status obtenido:` **HTTP 500** — `InfrastructureError.status_code`

`Mensaje/código esperado:` error de trazabilidad; el ajuste no ha sido aplicado

`Mensaje/código obtenido:` `AUDITORIA_CALIBRACION_FALLIDA` — «Error de integridad: No
se pudo garantizar la trazabilidad de la calibración. El ajuste no ha sido aplicado;
por favor, intente de nuevo.»

El 500 no se aceptó por sí solo: se comprobó además la ausencia total de persistencia
parcial, que es lo que da valor al caso.

---

## Pytest

| Python | pytest | Intento | Tests | Fallidos | Log | XML | JSON |
|---|---|---|---:|---:|---|---|---|
| 3.13.13 | 9.0.3 | 1 | 13 | 0 | `pytest-TC-M09-150-intento1.log` | `pytest-TC-M09-150-intento1.xml` | `TC-M09-150-evidencia-intento1.json` |
| 3.13.13 | 9.0.3 | 2 | 13 | 0 | `pytest-TC-M09-150-intento2.log` | `pytest-TC-M09-150-intento2.xml` | `TC-M09-150-evidencia-intento2.json` |

**2 ejecuciones, el máximo permitido. No hubo una tercera.**

Por qué se usó el segundo intento, estando el primero en verde: el descubrimiento del
intento 1 seleccionó un sensor **sin calibraciones previas** (sensor 7), de modo que
la comprobación «históricos previos intactos» quedaba **vacía** — no había nada que
conservar. Era una carencia de la prueba, no del producto: no hubo persistencia en
ningún sitio y repetir era seguro, así que se corrigió únicamente el archivo QA para
que el descubrimiento prefiera un sensor **con** historial, y el intento 2 se ejecutó
sobre el sensor 6, con dos calibraciones reales que sí pueden verificarse. Ambos
intentos coinciden en todo lo demás. La evidencia del intento 1 se conserva íntegra.

Las 13 comprobaciones cubren precondiciones (actor, dispositivo, sensor, área, valor y
control sin fallo), fault injection (punto alcanzado, escritura previa al fallo, error
y status) y atomicidad (sin commit, con rollback, sin calibración, sin auditoría, área
provisional descartada, históricos intactos y TEST sin escrituras).

## ORIGEN DEL FALLO

No hubo fallos: el original quedó APROBADO. La única incidencia de ejecución fue la
carencia del descubrimiento del intento 1 —origen: automatización, ya corregida— sin
efecto sobre el producto ni sobre la clasificación.

## DEFECTO DETECTADO

**Ninguno.** No se encontró persistencia parcial, ni auditoría huérfana, ni alteración
de históricos, ni respuesta contraria al contrato. No se propone ID de incidencia, no
se asigna severidad y no se creó ningún ticket en Taiga ni GitHub.

## Comprobaciones exigidas antes de aprobar

1. ¿Calibración completamente válida? **Sí** — y la ejecución de control lo confirma.
2. ¿Fault point alcanzado? **Sí** — auditoría intentada una vez.
3. ¿El fallo ocurrió dentro del proceso transaccional? **Sí** — tras el flush de la
   calibración y antes del commit.
4. ¿El producto manejó la excepción? **Sí** — `InfrastructureError` con código propio.
5. ¿No se creó calibración? **Sí.**
6. ¿No se creó auditoría parcial? **Sí.**
7. ¿No quedaron filas auxiliares parciales? **Sí** — área provisional descartada.
8. ¿Históricos previos intactos? **Sí** — #10 y #11 sin cambios.
9. ¿Respuesta acorde al contrato? **Sí** — HTTP 500 y mensaje de RF-24.
10. ¿Rollback completo demostrado? **Sí**, en el alcance declarado más arriba.

## Seguridad

- No se modificó código funcional: ni `src/`, ni servicios, repositorios, gestor de
  transacciones, auditoría, modelos, excepciones ni conexión de BD. Solo se leyeron.
- **No se alteró PostgreSQL de ninguna forma**: no se ejecutó SQL, ni de lectura ni de
  escritura. No se revocaron permisos, no se bloquearon conexiones, no se detuvo ni
  reinició ningún servicio y no se usaron credenciales incorrectas para simular fallos.
- El fallo se indujo **exclusivamente dentro del proceso de prueba**, sobre un doble
  del puerto de auditoría. Esa excepción es la **precondición** del caso, no una
  incidencia de infraestructura.
- No se instalaron ni actualizaron dependencias. No se tocó Docker, Dokploy, Nginx,
  CI/CD ni variables desplegadas.
- **TEST no recibió ninguna escritura**: el historial del sensor 6 tenía 2
  calibraciones al inicio y las mismas 2 al cierre, con idénticos IDs.
- **Sin cleanup**: no hubo nada que limpiar, porque nada persistió.
- Contraseña y token solo en memoria del proceso; el tipo del token redacta su `repr`
  para que pytest no lo vuelque en un traceback.
- Escaneo final de secretos sobre los artefactos del run buscando **valores**: JWT,
  cabecera de autorización con token, cabecera de cookie, tokens en pares clave-valor
  y cadenas de conexión. **Sin hallazgos.** La URL del harness no contiene credenciales
  reales ni apunta a ninguna base existente. Registrado en
  [seguridad-evidencias.json](seguridad-evidencias.json).
- No hubo `git commit`, `push`, `pull`, `merge`, `rebase`, `reset`, `clean`, `stash`,
  `checkout`, `switch`, creación o borrado de rama, tags ni PR.

## Entorno

- Fecha: 2026-09-06 UTC.
- Modalidad de ejecución: **harness Pytest en proceso** para el escenario
  transaccional; TEST remoto solo para descubrimiento y verificación por GET.
- PostgreSQL directo: **no utilizado**.
- Backend TEST: `https://sigab-backendtest-389pcb-a48238-158-69-200-27.sslip.io/api-sgpmp-test`
- Frontend TEST: `https://sigab-frontendtest-6aqrny-d2b730-158-69-200-27.sslip.io`
- Rama backend: `qa/juan-esteban-m09` · SHA local `adc3932b9f0293a76ebec7e89ed877274791b6a1`
- Rama frontend: `qa/juan-esteban-m09` · SHA local `966621df4e2c6a1f2c9233ea5ebefbb9e3bc2f56`
- **SHA desplegado en TEST no confirmado.** Los SHA anteriores son locales.
- Dependencias verificadas, ninguna instalada: Python 3.13.13, pytest 9.0.3,
  SQLAlchemy 2.0.50, psycopg2 2.9.12.

## Git final

Backend (`qa/juan-esteban-m09`, `adc3932b9f0293a76ebec7e89ed877274791b6a1`):
`git diff --stat` vacío — ningún archivo versionado modificado. Lo nuevo son los
archivos QA de este grupo bajo `RF-24/TC-M09-G79/`, más los untracked previos de
otros grupos que ya existían al comenzar.

Frontend: **G79 no ejecutó ninguna operación sobre el repositorio de frontend.**
Sigue presente, fuera del alcance de este grupo, la eliminación ya observada desde
G75 de `testing/test_testing/Modulo9/RF-17/TC-M09-G22/.gitkeep`; conforme a las
reglas no se revirtió ni se restauró, y se vuelve a documentar para revisión humana.

Detalle en [git-final.json](git-final.json).

---

## Estado de cierre

G79 queda ejecutado y detenido para revisión humana. TC-M09-150 **APROBADO** en el
alcance declarado: atomicidad del registro de calibración ante fallo de persistencia
de auditoría, verificada sobre el código real del caso de uso. Decisión general
**APROBADO**. Sin defectos que reportar a ningún equipo.

Recomendación para revisión humana, no bloqueante: si se quiere elevar esta evidencia
a nivel de motor —comprobar que PostgreSQL descarta físicamente la fila del `flush`—
basta con habilitar el harness `tests/integration` con una `TEST_DATABASE_URL`
dedicada; la prueba de G79 es reutilizable tal cual sobre esa sesión real. No se
avanza a otro grupo.
