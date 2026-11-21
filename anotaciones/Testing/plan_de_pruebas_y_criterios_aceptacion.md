# Plan de Pruebas y Criterios de Aceptación — Equipo QA SGPMP

| Campo | Valor |
|---|---|
| Alcance | Todos los módulos de `sgpmp-backend` y `SGPMP-FRONT-END-PWA` |
| Audiencia | Equipo QA, Desarrollo, Implementación/DevOps, Coordinación |
| Basado en | Práctica ya en uso en M01 y M09 (`informe_consolidado_pruebas_M0X.md`), `qa-dashboard/`, `CONTRIBUTING.md`, `tests/integration/README.md` |
| Versión | 1.0 — 2026-09-11 |

Este documento fija **una sola vez** las reglas que hasta ahora se venían
aplicando de manera ad-hoc módulo a módulo, para que cualquier persona del
equipo — o el siguiente módulo que se aborde — las use sin tener que
reconstruirlas.

---

## 1. Objetivo y alcance

Estandarizar cómo un caso de prueba se mueve desde que se planea hasta que se
entrega formalmente, y con qué criterios se certifica que un módulo:

1. **puede pasar al siguiente eslabón del flujo** (otro módulo de QA, un cierre
   de sprint, o el visto bueno de Coordinación), y
2. **queda formalmente entregado a Desarrollo** con sus defectos documentados.

No reemplaza los informes de cierre por módulo (`informe_consolidado_pruebas_M0X.md`);
este documento es el **método**, esos informes son el **resultado** de aplicarlo.

---

## 2. Criterios de aceptación

### 2.1 Criterios de salida — QA certifica que el módulo puede avanzar

Un módulo se considera **listo para pasar al siguiente equipo del flujo**
cuando se cumplen **todas** las siguientes condiciones:

| # | Criterio | Umbral |
|---|---|---|
| 1 | Porcentaje de casos con veredicto **Aprobado** sobre el total planeado | **≥ 85 %** |
| 2 | Requisitos (RF) del módulo con al menos un caso ejecutado | **100 %** (ningún RF en 0 % ejecutado) |
| 3 | Defectos de severidad **Crítico** o **Severo** abiertos sin plan de mitigación aceptado por Desarrollo | **0** |
| 4 | Casos en estado Rechazado o Bloqueado sin incidencia formal o justificación documentada | **0** |
| 5 | Casos con veredicto fijado a mano en `declarados_sin_evidencia.csv` (sin reporte de herramienta) | **≤ 5 %** del módulo |
| 6 | Informe consolidado del módulo redactado y con las secciones de la plantilla (ver §6) | Completo |

Si el 85 % no se alcanza (caso de M09, 54.3 % al corte del 2026-09-08), el
informe **no certifica el módulo como listo** — documenta la brecha exacta,
la causa (ambiente desactualizado, ejecución incompleta, defectos reales) y un
plan de cierre, como se hizo en `informe_consolidado_pruebas_M09.md` §6-7.
Una excepción al umbral solo la autoriza **Coordinación**, nunca QA por su
cuenta, y debe quedar registrada en el control de versiones del informe.

### 2.2 Criterios de entrada — lo que Desarrollo/Implementación garantizan antes de que QA ejecute

QA no debe empezar a ejecutar un RF/módulo si falta alguno de estos puntos —
si se ejecuta de todas formas (por presión de cronograma), el hallazgo debe
marcarse "pendiente de confirmar contra build actualizado", como se hizo con
el cluster de HTTP 500 de M09 (ambiente corriendo una rama desactualizada).

- Build desplegado en el ambiente TEST correspondiente (backend y/o frontend),
  con la **versión identificada** (`vX.Y.Z-rc.N` o commit/rama exactos).
- `dev` mergeado a `test` sin conflictos pendientes de resolver.
- Migraciones de base de datos aplicadas y verificadas contra el esquema real
  (no contra lo que documenta el análisis).
- Documentación Swagger/OpenAPI actualizada para los endpoints del RF a probar.
- Commits de Desarrollo siguiendo `CONTRIBUTING.md` (tipo + scope), para que el
  RF quede trazable commit ↔ `CHANGELOG.md` ↔ incidencia.
- Cuentas y datos de prueba disponibles, con los roles/permisos sembrados en
  `modulo1.permisos` para el RF a probar.
- Ningún defecto Crítico conocido bloqueando el flujo principal sin aviso
  previo a QA.

### 2.3 Criterios de retorno — Desarrollo entrega una corrección a QA

Por cada incidencia que Desarrollo marca como corregida:

- Rama o PR de la corrección, referenciado en la incidencia.
- Confirmación explícita de que la corrección **ya está desplegada en TEST**
  (no solo mergeada a `dev`) antes de pedirle el retest a QA.
- Si aplica, prueba de regresión agregada al repo (patrón usado en
  `test_rf17_umbral_enum_insertmanyvalues.py`, `test_rf04_listar_roles_sin_n1.py`).

---

## 3. Flujo de trabajo de pruebas (nivel módulo)

```
1. Planeación         → consolidar el plan agrupado (TC-M0N-G01 … G-NN) con
                         RF, capa/herramienta, prioridad, responsable sugerido.
2. Asignación          → volcar el responsable real en asignaciones.csv
                         (qa-dashboard/); 0 casos "Sin asignar".
3. Verificación de     → confirmar §2.2 antes de arrancar. Si falta algo,
   entrada                se documenta como riesgo, no se bloquea sin avisar.
4. Ejecución            → un caso a la vez, ver §5 (flujo por caso).
5. Seguimiento          → panel QA (qa-dashboard/, refresco automático) como
                         fuente única de verdad de estado/porcentajes.
6. Cierre del RF        → cuando todos sus casos quedan en estado terminal
                         (Aprobado / Rechazado con incidencia / Bloqueado
                         justificado).
7. Informe consolidado  → aplicar §2.1; redactar informe_consolidado_pruebas_M0N.md.
8. Entrega formal       → firmas de QA / Desarrollo / Coordinación; el informe
                         es el artefacto de entrega, no un correo o un chat.
```

---

## 4. Herramientas de prueba

| Tipo de prueba | Herramienta | Cuándo se usa | Evidencia esperada |
|---|---|---|---|
| Funcional / validación de contrato API | **Postman + Newman** (reporter `htmlextra`) | Cualquier caso con contrato HTTP verificable (código, cuerpo, cabeceras) | `.html` en `Resultados/` |
| Lógica interna, reintentos, fallos simulados | **Pytest** (+ `pytest-html`) | Reglas de negocio internas, mocks de dependencias caídas (BD, SMTP, sesiones) — **nunca** caídas reales sobre el ambiente TEST compartido | `.html` (`pytest-html`) |
| Recorridos de interfaz (frontend) | **Cypress** | Flujos de UI, accesibilidad (`cypress-axe`), formularios | JSON propio con `checkpoints`, o `mochawesome` (HTML o log de consola) |
| Seguridad — OWASP API Top 10 / ASVS | **Pytest** + **OWASP ZAP** | BOLA, mass assignment, rate limiting, fuzzing, cabeceras, inventario de endpoints | `pytest-html` + hallazgos de ZAP referenciados en la ficha |
| Rendimiento / carga | **k6** | Rate limiting bajo ráfaga, payloads grandes, umbrales de tiempo de respuesta | Resumen JSON propio (`--summary-export` o script `handleSummary`) |
| Fuera del stack actual | Sniffer de red / cliente TLS-MQTT | Verificación de cifrado de canal (MQTT/LoRaWAN), TLS a bajo nivel | Se declara explícitamente "FUERA DE STACK"; no se improvisa una prueba parcial que dé falsa confianza |
| Seguimiento y consolidación | **Panel QA** (`qa-dashboard/`) | Agregación automática de resultados, asignaciones, incidencias, errores frecuentes | — (herramienta de gestión, no genera evidencia) |

**Convención de carpetas** (no negociable — es lo que `qa-dashboard/scanner.py`
sabe leer):

```
sgpmp-backend/tests/Test_Testing/Test_Modulo<N>/RF-XX/TC-M0<N>-G<n>/Resultados|RESULTADOS/
SGPMP-FRONT-END-PWA/testing/test_testing/Modulo<N>/RF-XX/TC-M0<N>-G<n>/RESULTADOS/
```

Un reporte guardado con un formato que el escáner no reconoce (o fuera de esta
estructura) **no cuenta como ejecutado** en el panel aunque exista en disco —
ver §5, paso 5.

---

## 5. Prerrequisitos para trabajar con pruebas

- **Accesos:** cuentas de prueba con los roles/permisos ya sembrados para el
  RF a probar; URLs y credenciales de los ambientes TEST (backend y frontend);
  acceso de lectura a `sgpmp-backend` y `SGPMP-FRONT-END-PWA` en rama `test`.
- **Entorno local:** Python 3 + Pytest; Node + Newman/Cypress; binario de k6.
  Para pruebas de integración contra PostgreSQL real: una base **exclusiva de
  pruebas** (`createdb pruebas` + `alembic upgrade head`, ver
  `tests/integration/README.md`) — nunca contra la base de desarrollo, y la
  cadena de conexión (`TEST_DATABASE_URL`) solo se define en la terminal,
  jamás en un archivo versionado.
- **Panel QA:** `qa-dashboard/` clonado como hermano de los dos repos
  (mismo padre en disco); `python3 server.py` (sin dependencias externas).
- **Convención de nomenclatura:** casos agrupados `TC-M0<N>-G<n>` (dos dígitos
  para G01-G09), carpeta `RF-XX`, carpeta vacía = `.gitkeep`. Ver el patrón ya
  usado en M01/M09 antes de crear una carpeta nueva.
- **Regla de no-daño al ambiente compartido:** está prohibido provocar caídas
  reales de BD, red o contenedores contra TEST. Si una prueba necesita ese
  escenario (fallos transaccionales, timeouts), se resuelve con **mocks o un
  mecanismo de inyección de fallo controlado y reversible** — ver el criterio
  fijado en `INC-M02-88-G81` y el patrón ya aplicado en M01
  (`test_tc_m01_044...`, `INC-M01-06-024`).
- **`CONTRIBUTING.md`:** si un caso requiere un commit propio (fixtures,
  scripts de prueba) sobre `dev`/`test`, sigue el mismo formato de commits que
  usa Desarrollo — de lo contrario el cambio queda invisible para el pipeline
  de versionamiento y el CHANGELOG.

---

## 6. Flujo de trabajo por caso de prueba individual

1. **Tomar el caso** asignado en `asignaciones.csv` (columna Responsable) y
   abrir su ficha en el plan consolidado del módulo.
2. **Revisar precondiciones, datos de prueba y valores límite** definidos en
   la ficha antes de ejecutar — no improvisar el dato de entrada.
3. **Ejecutar con la herramienta indicada** en "Herramienta QA sugerida" (§4).
4. **Guardar el reporte crudo** de la herramienta en la carpeta oficial del
   caso (§4), sin renombrar ni convertir a un formato que el escáner no
   reconozca.
5. **Verificar en el panel QA** que el caso se leyó y el estado es el
   esperado.
   - Si aparece `no_reconocido` o `sin_datos` habiendo evidencia real →
     confirmar si el formato ya está soportado en `scanner.py`; si no, pedir
     que se extienda el parser (ha pasado con mochawesome-HTML, k6, logs de
     consola de Cypress) o declarar el veredicto a mano en
     `declarados_sin_evidencia.csv` con la nota justificando la fuente.
6. **Si Aprobado** → queda cerrado; no requiere acción adicional.
7. **Si Rechazado:**
   1. Descartar que sea un falso positivo de automatización (placeholder sin
      reemplazar, cuenta de prueba mal aprovisionada, plugin de Cypress no
      cargado) — si lo es, se corrige la prueba y se reejecuta, **no** se
      abre incidencia contra el producto.
   2. Si el fallo es real, registrar **incidencia formal** en
      `incidencias.csv` (o un `.md` de análisis de causa raíz si lo amerita)
      con severidad, categoría, equipo responsable y fecha límite según el
      SLA (§7).
   3. Notificar al equipo responsable (Desarrollo, Desarrollo + DBA,
      Implementación) según la categoría del defecto (§8).
8. **Si Bloqueado** (no ejecutable por el ambiente o por falta de
   testabilidad):
   1. Documentar la causa concreta (adaptador *stub*, dato no disponible en
      TEST, mecanismo de inyección de fallo ausente, funcionalidad no
      construida aún en la interfaz).
   2. Clasificar si es un **defecto funcional confirmado** (cuenta como
      hallazgo real) o una **limitación de ambiente/testabilidad** (no cuenta
      igual contra el % de aprobación, pero sí debe quedar resuelta antes del
      cierre del módulo) — mismo criterio usado en
      `inc_m09_monitoreo_umbral_efectivo_bloqueado.md`.
9. **Tras la corrección de Desarrollo** (§2.3): reejecutar con el mismo
   procedimiento. Si pasa, el estado cambia a Aprobado y la incidencia queda
   referenciada como corregida — **no se cierra la incidencia sin retest**.
10. **Cierre del módulo:** cuando todos los casos del RF/módulo están en
    estado terminal, se aplica §2.1 y se redacta el informe consolidado.

---

## 7. SLA de incidencias por severidad

| Severidad | Tiempo máximo de solución | Ejemplo del proyecto |
|---|---|---|
| Crítico | 4 horas (mismo día) | INC-M01-01-01 (500 en activación de cuenta), INC-M01-03-119 (500 al eliminar rol) |
| Severo | 1 día hábil | INC-M01-06-024 (sin reintentos de conexión a BD) |
| Medio | 2 días hábiles | INC-M01-05-035, INC-M01-07-43, INC-M02-88-G81 |
| Bajo *(propuesto, sin precedente registrado aún)* | 5 días hábiles o próxima iteración | Hallazgos de mensajes/cosmética |

---

## 8. Categorías de defecto y equipo responsable

| Categoría | Significado | Equipo responsable típico |
|---|---|---|
| `FLUJO` | La lógica de negocio no sigue la secuencia o regla definida por el RF | Desarrollo |
| `HTTP_COM` | El código de respuesta HTTP no corresponde al definido por el RF (la regla de negocio puede estar bien; el contrato, no) | Desarrollo |
| `INFRAESTRUC` | Falla un componente externo (BD, SMTP, colas), no la lógica de negocio | Implementación (TEST) o Despliegue (producción) |
| `Unicidad` | Falta una restricción de unicidad/duplicado esperada por el RF | Desarrollo (+ DBA si requiere migración) |
| `Funcional / Paginación` | Defectos específicos de listados/paginación (orden, duplicados en el borde) | Desarrollo |
| `Capacidad de prueba / Testability` | QA no puede verificar el criterio con las herramientas/accesos actuales | Desarrollo (construir el mecanismo) + Implementación (habilitarlo en TEST) — ver §5 |
| Seguridad (`OWASP APIx` / `ASVS Vx`) | Hallazgo de seguridad clasificado contra OWASP API Top 10 o ASVS | Desarrollo; Alta severidad si hay exposición de datos entre usuarios/fincas (BOLA) |

---

## 9. Roles y responsabilidades

| Rol | Responsabilidad |
|---|---|
| **QA** | Ejecutar los casos, guardar evidencia en el formato reconocido, clasificar y formalizar incidencias, mantener `asignaciones.csv`/`incidencias.csv`, redactar y firmar el informe de cierre |
| **Desarrollo** | Corregir los defectos de producto, seguir `CONTRIBUTING.md` para trazabilidad, avisar cambios de contrato/RF antes de que rompan pruebas ya escritas, entregar mecanismos de testabilidad cuando QA los solicite |
| **Implementación / DevOps** | Mantener el ambiente TEST desplegado y sincronizado con `dev`, aplicar migraciones, habilitar en TEST los mecanismos que Desarrollo entregue (ej. flags de inyección de fallo) |
| **Coordinación / PM** | Recibir el informe de cierre, decidir sobre excepciones al umbral del 85 %, priorizar entre módulos |

---

## 10. Control del documento

| Versión | Fecha | Autor | Cambios |
|---|---|---|---|
| 1.0 | 2026-09-11 | Equipo QA | Versión inicial — consolida la práctica usada en M01 y M09 |

**Firmas de adopción**

| Rol | Nombre | Fecha | Firma |
|---|---|---|---|
| Responsable QA | | | |
| Líder de Desarrollo | | | |
| Implementación / DevOps | | | |
| Coordinación / PM | | | |
