# Estado de cumplimiento — Módulo 9 (Configuración)

**Fecha de la auditoría:** 2026-08-05
**Alcance:** RF-15 a RF-32, contra el código real de `src/configuration/` y el estado real de
la base de datos (schema `modulo9`), verificado con exploración de código, lectura de la
documentación previa del módulo y consultas directas vía MCP de Postgres (catálogos,
triggers, constraints, permisos sembrados).

**Nota metodológica importante:** a diferencia del audit de Módulo 1, para Módulo 9 ya
existía documentación previa en `anotaciones/modulo_9/` — `api_reference_configuration.md`,
seis documentos de gaps de BD por caso de uso (`cu02_gaps_bd_rf16.md` … `cu07_gaps_bd_rf30_rf31_rf32.md`),
siete documentos de curls, y `inconsistencias_permisos_m09.md`. Esos documentos son de buena
calidad y siguen vigentes en su mayoría — el código no ha cambiado sustancialmente desde que
se escribieron (última modificación relevante de `src/configuration`: 2026-06-21). Este
documento **no repite** ese trabajo: lo usa como evidencia, lo cita explícitamente donde
corresponde, y se concentra en contrastarlo contra el texto de los RF-15 a RF-32 tal como se
entregaron — que es el ángulo que los documentos de gaps de BD no cubren (esos comparan RF
vs. esquema de BD, no RF vs. comportamiento final del sistema).

Los porcentajes son una estimación orientativa de cuánto del RF está cubierto, no una
medición exacta — sirven para priorizar, no como cifra oficial.

---

## Resumen ejecutivo

| RF | Título | Veredicto | Cobertura aprox. |
|----|--------|-----------|-------------------|
| RF-15 | Catálogo de especies productivas | ⚠️ Cumple parcialmente | ~85% |
| RF-16 | Etapas, patologías y métricas productivas por especie | ⚠️ Cumple parcialmente | ~80% |
| RF-17 | Umbrales de monitoreo y niveles de alerta ambiental | ⚠️ Cumple parcialmente | ~90% |
| RF-18 | Parámetros operativos del sistema (frecuencia/heartbeat) | ✅ Cumple | ~95% |
| RF-19 | Registro y gestión de datos de la finca | ⚠️ Cumple parcialmente | ~85% |
| RF-20 | Gestión de infraestructura productiva | ⚠️ Cumple parcialmente | ~80% |
| RF-21 | Registro de dispositivos IoT | ✅ Cumple | ~95% |
| RF-22 | Asociación de sensores a estructuras productivas | ✅ Cumple | ~90% |
| RF-23 | Configuración remota de dispositivos IoT | ✅ Cumple (MVP síncrono) | ~90% |
| RF-24 | Calibración de dispositivos IoT | ⚠️ Cumple parcialmente | ~65% |
| RF-25 | Adaptación de interfaz operativa | ⚠️ Cumple parcialmente | ~60% |
| RF-26 | Personalización de identidad visual del sistema | ✅ Cumple | ~90% |
| RF-27 | Configuración visual del sistema (tema) | ✅ Cumple | ~90% |
| RF-28 | Personalización del dashboard | ⚠️ Cumple parcialmente | ~65% |
| RF-29 | Configuración de idioma | ⚠️ Cumple parcialmente | ~50% |
| RF-30 | Plantillas de configuración | ✅ Cumple | ~90% |
| RF-31 | Creación de plantilla de configuración | ✅ Cumple | ~90% |
| RF-32 | Aplicación de plantilla de configuración | ⚠️ Cumple parcialmente | ~80% |

**Lectura rápida:** módulo 9 es, en general, el más maduro de los auditados hasta ahora —
los 18 RFs tienen implementación real en `src/configuration/` (entidades, use cases,
repositorios, routers con RBAC), con triggers de base de datos como segunda capa de defensa
en casi todos los agregados. Los gaps más serios no son de "código faltante" sino de
**reglas de negocio que existen pero están gateadas por un adaptador stub que siempre
responde "sin dependencias"** (afecta RF-15, RF-16, RF-19, RF-20), de **integraciones
externas nunca conectadas** (MQTT real para RF-23 — resuelto 2026-08-20, ver su sección —,
motor de traducción para RF-29), y de un **posible bug de concurrencia en RF-32** que compara
el campo equivocado.

---

## RF-15 — Catálogo de especies productivas

**Veredicto: ⚠️ Cumple parcialmente (~85%)** — CRUD completo y sólido; el hueco real es que
la regla "no desactivar si hay proceso crítico activo" nunca bloquea nada hoy, y hay una
inconsistencia de permisos ya documentada por el propio equipo.

### Qué SÍ cumple

- CRUD completo: `registrar_especie_use_case.py`, `consultar_catalogo_use_case.py`,
  `editar_especie_use_case.py`, `desactivar_especie_use_case.py`,
  `reactivar_especie_use_case.py` — los cinco flujos que pide el RF (registro, consulta,
  edición, desactivación lógica, reactivación) están implementados.
- **Nombre único case-insensitive**, longitud 3–50, solo letras/espacios/tildes/ñ (sin
  dígitos ni símbolos): validado en el value object `domain/value_objects/nombre_especie.py`
  con regex `^[A-Za-zÁÉÍÓÚáéíóúÑñ][A-Za-zÁÉÍÓÚáéíóúÑñ ]*$`, y reforzado en DB con
  `modulo9.especies.nombre UNIQUE` + trigger `trg_especies_nombre_unique_ci`.
- **Eliminación física imposible**: trigger `trg_especies_no_delete` en la tabla bloquea
  cualquier `DELETE`, independiente de lo que haga el código de aplicación.
- **Reactivación sin pérdida de integridad**: existe `reactivar_especie_use_case.py` como
  flujo separado de la edición normal.
- El bloqueo de desactivación por "proceso crítico activo" **sí está codificado** en
  `desactivar_especie_use_case.py:60-64`, delegando en `ProcesoCriticoPort`.
- Auditoría completa vía `AuditoriaEspecieRepository`, con `valores_anteriores`/`valores_nuevos`
  en cada operación (CREATE/UPDATE/DEACTIVATE), consistente con lo que pide "Salida" del RF.
- RBAC coherente con el texto del RF para creación y desactivación: `admin_crear_especie`,
  `admin_eliminar_especie` (recurso `especies`, id=8) — exclusivos de Administrador.

### Qué NO cumple / gaps

- **El chequeo de "proceso crítico activo" nunca bloquea nada en la práctica.** El
  `ProcesoCriticoPort` que usa `desactivar_especie_use_case.py` está implementado por
  `infrastructure/adapters/proceso_critico_stub.py`, que retorna `False` siempre ("hasta que
  el módulo de Predicción/IA — M04 — esté implementado"). El flujo alterno del RF que pide
  `HTTP 422` cuando hay un reentrenamiento de IA en curso está descrito en código pero no
  puede dispararse hoy con ningún dato real.
- **Inconsistencia de permisos — RESUELTA (2026-08-22, issue #1634).** El rol Veterinario
  tenía permiso `U` (`vet_actualizar_especie`, id_permiso=48) sobre especies, pese a que
  RF-15 solo autoriza edición a Administrador e Ingeniero de Campo. El equipo de análisis
  confirmó que debe revocarse: se aplicó `UPDATE modulo1.permisos SET es_activo=false WHERE
  id_recurso=8 AND id_accion=3 AND id_rol=3;`. El Veterinario ya no puede editar especies
  (recibe `403`). Ver `anotaciones/modulo_9/inconsistencias_permisos_m09.md` y
  `rf15-19-20-rbac-mod9/resumen_rbac_1634.md`.
- **No existe ningún mecanismo de modo offline / sincronización diferida.** El RF pide
  explícitamente (paso 9 del proceso, y como NFR de disponibilidad) que las operaciones se
  almacenen localmente sin conexión y se sincronicen al reconectar, incluyendo un flujo
  alterno específico de "conflicto de sincronización" con notificación de UI. No hay rastro
  de esto en `src/configuration/` ni en ningún otro módulo — confirmado por búsqueda
  (`grep -rniE "offline|sincroniz" src/configuration/`); los únicos resultados corresponden a
  un concepto distinto (conectividad de dispositivos IoT en RF-23). Este es, por diseño de
  arquitectura, un gap que probablemente le corresponde al frontend/PWA resolver, pero el
  backend tampoco expone ningún soporte para ello (endpoint de sincronización en lote,
  detección de conflictos por lote, etc.).
- El RF pide rechazar nombres "con caracteres especiales no permitidos" citando el valor
  ingresado en el mensaje de error — el mensaje real (`NOMBRE_ESPECIE_FORMATO_INVALIDO`) es
  genérico y no interpola el valor recibido; diferencia menor de forma, no de fondo.

---

## RF-16 — Configuración de etapas productivas, patologías y métricas por especie

**Veredicto: ⚠️ Cumple parcialmente (~80%)** — de los tres sub-catálogos que pide el RF, las
**etapas** tienen el chequeo de dependencias real (consulta una vista SQL), mientras que
**patologías** y **métricas** lo tienen stubbeado a la espera de M04. (La discrepancia de
"patologías global vs. por especie" fue **resuelta** en #1633, 2026-08-23 — ver abajo.)

### Qué SÍ cumple

- Los tres sub-recursos existen con CRUD completo: etapas vía `ciclos_biologicos`
  (`application/use_cases/ciclos/*`), patologías vía `application/use_cases/patologias/*`,
  métricas vía `application/use_cases/metricas/*`.
- **Etapas**: nombre único por especie (case-insensitive), `duracion_dias` entero > 0
  validado en value object, sin eliminación física (trigger de BD), y — a diferencia de
  patologías/métricas — el chequeo de "no desactivar si hay activos biológicos en la etapa"
  (`desactivar_ciclo_use_case.py:60-64`) **es una implementación real**, no un stub: consulta
  la vista `modulo9.vw_rf16_dependencias_ciclos` contra `modulo9.ciclos_productivos_biologicos`
  (`infrastructure/repositories/dependencia_ciclo_repository.py`).
- **Métricas**: tras el gap doc `cu02_gaps_bd_rf16.md` (que documentó la estructura de DB
  como insuficiente — sin `id_especie`, sin `aplica_a_tipo_activo`, sin `es_activo` real), se
  aplicó la "Opción A" recomendada: `modulo9.metricas_produccion` hoy sí tiene `id_especie`
  (nullable, para métricas globales), `aplica_a_tipo_activo`, `es_activo` y
  `fecha_actualizacion` — confirmado contra el esquema real.
- Concurrencia optimista (412) implementada en los tres: `editar_ciclo_use_case.py`,
  `editar_patologia_use_case.py`, `editar_metrica_use_case.py` usan `PreconditionFailedError`.
- RBAC coherente con el RF: recursos `ciclos_biologicos` (17), `patologias` (18) y
  `metricas_produccion` (19) solo tienen permisos activos para Administrador y Veterinario
  (CRUD completo para ambos, confirmado vía consulta directa a `modulo1.permisos`) — coincide
  exactamente con los actores que declara RF-16 ("Administrador del sistema / Veterinario").
  Productor, Ingeniero de Campo y Contador no tienen ningún acceso a estos tres recursos, ni
  siquiera de lectura.

### Qué NO cumple / gaps

- ~~**Patologías es un catálogo global, no "único por especie".**~~ **RESUELTO (#1633,
  2026-08-23).** Ahora patologías es **por especie**: la entidad M09 vive en
  `modulo9.especies_patologias` con `nombre`/`descripcion`/`es_activo` propios y unicidad
  `(id_especie, lower(nombre))` (índice `uq_especie_patologia_nombre`). `modulo9.patologias`
  (catálogo clínico de M04) y su `uq_enfermedad_nombre` quedaron intactos; el vínculo
  `id_patologia` es opcional/NULL. M09 ya **no escribe** el catálogo M04 (antes lo hacía —
  mezcla de responsabilidades corregida). Ver `rf16-patologias-por-especie-mod9/resumen.md`
  y la migración `alembic/versions/192872fafd40_...py`.
- **Los chequeos de dependencia de patologías y métricas nunca bloquean nada.**
  `desactivar_patologia_use_case.py` usa `DependenciaPatologiaPort`, implementado por
  `infrastructure/adapters/dependencia_patologia_stub.py` (siempre `False`, pendiente de
  M04). `desactivar_metrica_use_case.py` usa `DependenciaMetricaPort`, implementado por
  `dependencia_metrica_stub.py` (mismo patrón). Los flujos alternos de RF-16 que piden
  `HTTP 422` al intentar desactivar una patología con historial clínico o una métrica con
  registros productivos existen en código pero no se disparan con ningún dato real hoy.
- **`modulo9.patologias` mezcla campos propios de M09 (RF-16) con campos de M04**
  (`nombre_tecnico`, `etiologia`, `categoria`, `codigo_cie`, `es_base`, `version_catalogo`,
  `descripcion_clinica`) — confirma que la tabla fue diseñada como catálogo compartido entre
  módulos, no exclusiva de configuración. No es un bug, pero si el RF se lee de forma
  aislada, la tabla tiene más responsabilidad de la que el RF-16 le asigna.
- Mismo gap de modo offline que RF-15 (el RF-16 lo pide igual en su flujo de proceso).

---

## RF-17 — Configuración de umbrales de monitoreo y niveles de alerta ambiental

**Veredicto: ⚠️ Cumple parcialmente (~90%)** — de los RFs de este bloque, es el mejor
resuelto: los ocho gaps de BD detectados antes de implementar quedaron todos aplicados y
verificados contra el esquema real.

### Qué SÍ cumple

- CRUD completo (`application/use_cases/umbrales/*`): registrar, consultar, editar,
  desactivar. Value object `nivel_alerta.py` para la semaforización.
- **Los 8 gaps documentados en `cu03_gaps_bd_rf17.md` están aplicados y confirmados en la
  DB real**: `fecha_actualizacion` agregada, `nombre`/`descripcion` nullable (correctamente,
  porque el RF no los define como entrada del usuario), constraint
  `UNIQUE(id_especie, id_variable_ambiental)` (impide duplicar la configuración para la misma
  combinación — cumple el flujo alterno de "configuración duplicada" con `409`), constraint
  `UNIQUE(id_umbral_ambiental, nivel)` en niveles de alerta, tabla de auditoría
  `auditorias_umbrales_ambientales` creada, recurso RBAC `umbrales_ambientales` (id=20) y
  permisos sembrados.
- **Rango mínimo < máximo** validado (`valor_min < valor_max`), **niveles de alerta sin
  solapamiento** reforzado por trigger `trg_niveles_alerta_solapamiento` en
  `modulo9.niveles_alerta_ambientales` — cumple el flujo alterno de "solapamiento de niveles"
  con `400`.
- **RBAC exacto según el RF**: "Solo los usuarios con rol Administrador o Veterinario podrán
  modificar estos parámetros" — confirmado, solo esos dos roles tienen permisos (C/R/U/D)
  sobre el recurso 20.
- Concurrencia optimista (412) vía `fecha_actualizacion` en `editar_umbral_use_case.py`.
- El catálogo de variables ambientales (`modulo9.variables_ambientales`) **no tiene endpoint
  de CRUD propio** — esto coincide exactamente con lo que pide el RF: *"Los usuarios finales
  no podrán crear, modificar ni eliminar variables ambientales desde este módulo"*. No es un
  gap, es el comportamiento correcto.

### Qué NO cumple / gaps

- **Los niveles de alerta están fijos a exactamente tres valores** (`enum_nivel_alerta`:
  `normal`/`precaucion`/`critico`) mediante un enum de Postgres cerrado. Esto coincide con lo
  que describe el RF en su cuerpo (los tres niveles que menciona son exactamente esos), pero
  lo hace estructuralmente no extensible sin una migración — vale la pena señalarlo si en el
  futuro se necesita un cuarto nivel.
- **Ningún rol aparte de Administrador y Veterinario puede siquiera consultar los umbrales**
  (no hay permisos `R` sembrados para Productor, Ingeniero de Campo ni Contador sobre el
  recurso 20). El RF no dice explícitamente que otros roles deban poder leer los umbrales,
  pero si un Productor necesita ver por qué se disparó una alerta ambiental en su finca, hoy
  no tiene forma de consultar el umbral configurado a través de este módulo.
- La validación de "valores dentro de rangos físicamente aceptables según la variable" (ej.
  pH entre 0–14) se apoya en `modulo9.variables_ambientales.valor_fisico_min/max`, que sí
  existe en DB — no se verificó a nivel de código si el use case de registro de umbral
  efectivamente compara contra esos límites físicos de la variable o solo contra
  `valor_min < valor_max` de forma relativa (evidencia insuficiente para afirmar con
  certeza; recomendable revisar `registrar_umbral_use_case.py` en detalle antes de dar esto
  por cerrado).
- Mismo gap de modo offline que RF-15/RF-16 no aplica aquí de forma explícita — RF-17 no lo
  menciona en su texto, por lo que no se cuenta como gap para este RF específico.

---

## RF-18 — Configuración de parámetros operativos del sistema

**Veredicto: ✅ Cumple (~95%)** — el RF más simple del bloque y el mejor resuelto; no se
detectaron gaps de fondo.

### Qué SÍ cumple

- Singleton reforzado en tres capas: value objects `frecuencia_muestreo.py`/`heartbeat.py`
  (ambos validan entero > 0), trigger `trg_configuracion_global_unicidad` en
  `modulo9.configuraciones_globales`, y lógica de "actualizar si ya existe" en
  `actualizar_configuracion_use_case.py` en vez de permitir múltiples `INSERT`.
- **`heartbeat >= frecuencia_muestreo`** validado, reforzado por trigger
  `trg_configuracion_global_heartbeat_valido` — doble capa, igual que el patrón usado en
  otros módulos del proyecto.
- **RBAC exacto**: recurso `configuraciones_globales` (id=21) solo tiene permisos C/R/U para
  Administrador — sin `D` (coherente, es un singleton que se actualiza, no se elimina) y sin
  ningún acceso para otros roles, tal como pide el RF ("Solo el Administrador puede modificar
  estos parámetros").
- Auditoría: tabla `auditorias_configuraciones_globales` creada específicamente para este RF
  (no existía antes de `cu04_gaps_bd_rf18_rf19_rf20.md`), con `valores_anteriores`/`nuevos`.
- El RF pide mantener historial de cambios "reconstruible desde auditoría" en vez de
  restauración automática — coincide con el diseño (no hay endpoint de rollback, solo lectura
  de auditoría), que es exactamente lo que el RF permite.

### Qué NO cumple / gaps

- No se verificó si existe control de concurrencia optimista (412) específico para este
  recurso — el RF lo pide como flujo alterno ("dos administradores cambian la frecuencia al
  mismo tiempo"). `actualizar_configuracion_use_case.py` apareció en la búsqueda de
  `PreconditionFailedError`, lo que sugiere que sí está implementado, pero no se leyó el
  archivo completo para confirmar el mecanismo exacto.
- Ningún hallazgo adicional de peso — es el RF con menos superficie de gaps de todo el bloque.

---

## RF-19 — Registro y gestión de datos de la finca

**Veredicto: ⚠️ Cumple parcialmente (~85%)** — CRUD y validaciones geográficas/textuales
completas y correctas; el gap real es, otra vez, el patrón de dependencia stub y un acceso
más amplio del que el RF autoriza explícitamente.

### Qué SÍ cumple

- CRUD completo (`application/use_cases/fincas/*`): registrar, consultar, editar, desactivar.
- **Validación de nombre** (`nombre_finca.py`): solo letras/espacios/tildes/ñ, 1–55
  caracteres — coincide con el RF.
- **Validación de ubicación** (`ubicacion_finca.py`): `departamento`/`municipio`/`vereda`
  restringidos al mismo patrón de solo-letras; **latitud validada en [-90, 90]** y
  **longitud en [-180, 180]** exactamente como pide el RF, con mensajes de error específicos
  por campo (`LATITUD_FUERA_RANGO`, `LONGITUD_FUERA_RANGO`).
- **`tamaño_h > 0`** validado (mismo patrón que `Superficie` de RF-20).
- **Sin eliminación física**: trigger `trg_finca_no_delete` bloquea `DELETE` si existen
  dependencias — reforzado en DB, no solo en aplicación.
- Auditoría vía `auditorias_fincas` (creada específicamente para este RF).
- RBAC: recurso `fincas` (id=9) con Administrador en C/R/U/D — coincide con "Solo el
  Administrador puede registrar, editar o desactivar fincas".

### Qué NO cumple / gaps

- **El chequeo de "no desactivar finca con infraestructura/activos asociados" está
  stubbeado.** `finca_stub_adapter.py` siempre retorna `False`. El comentario del propio
  adaptador dice "hasta que RF-21 (IoT) y RF-33 (Activos Biológicos) estén implementados" —
  pero **ambos módulos ya existen** en el repo (`src/configuration` tiene dispositivos IoT
  completos desde RF-21, y `src/biological_assets` ya está implementado). El comentario está
  desactualizado y el stub nunca fue reemplazado por la consulta real, pese a que las tablas
  necesarias para hacerla ya están disponibles.
- **El acceso de solo-lectura es más amplio que el texto literal del RF — DECISIÓN DE DISEÑO
  APROBADA (2026-08-22, issue #1634).** El RF dice: *"Los usuarios con rol Productor solo
  pueden consultar la información de las fincas a las que están asignados"* — listando a
  Productor como único actor de consulta además del Administrador. En la práctica,
  `modulo1.permisos` da `R` sobre `fincas` también a Veterinario e Ingeniero de Campo. El
  equipo de análisis resolvió **mantener** esta lectura como decisión explícita de RBAC
  dinámico: es solo lectura y es operativamente defendible (un veterinario/ingeniero necesita
  saber en qué finca está un activo). Ya no es una desviación silenciosa. Ver
  `rf15-19-20-rbac-mod9/resumen_rbac_1634.md`.
- No se verificó si el `R` de Productor está filtrado a "las fincas a las que está asignado"
  (via `fincas.id_usuario`) o si un Productor puede ver el listado completo de todas las
  fincas del sistema — este es un punto de aislamiento de datos entre productores que vale la
  pena confirmar directamente en `consultar_fincas_use_case.py` antes de darlo por cumplido.
- Mismo gap de unicidad "global y por productor" del nombre — no se confirmó si la
  restricción `UNIQUE` de `modulo9.fincas.nombre` es global (lo más probable, dado que no se
  encontró columna compuesta con `id_usuario`) o si además hay una unicidad específica por
  productor como pide el RF de forma redundante ("de manera global y por productor").

---

## RF-20 — Gestión de infraestructura productiva

**Veredicto: ⚠️ Cumple parcialmente (~80%)** — mismo patrón de calidad que RF-19; el gap más
concreto frente al texto del RF es que el catálogo de tipos de área no es administrable como
el RF describe.

### Qué SÍ cumple

- CRUD completo (`application/use_cases/infraestructuras/*`).
- **Nombre único por finca** (case-insensitive, reforzado en DB), **superficie > 0**
  validado en `Superficie` value object.
- **Sin eliminación física**, con `fecha_actualizacion` agregada específicamente para este RF
  (gap documentado y resuelto en `cu04_gaps_bd_rf18_rf19_rf20.md`).
- Auditoría vía `auditorias_infraestructuras`.
- RBAC: recurso `infraestructuras` (id=10), Administrador C/R/U/D.

### Qué NO cumple / gaps

- **`tipos_area` no es el catálogo administrable que describe el RF.** El RF dice
  explícitamente: *"el catálogo incluye por defecto: galpón, corral, potrero, estanque,
  invernadero, pero el Administrador puede agregar nuevos tipos o desactivar los existentes
  desde el módulo de Configuración"*. La implementación real es un **enum cerrado de
  Postgres** (`enum_tipo_infraestructura`, exactamente esos 5 valores fijos) en la columna
  `modulo9.infraestructuras.tipo` — no existe una tabla `tipos_area` gestionable. Ampliar el
  catálogo hoy requiere una migración de esquema, no una operación de Administrador desde la
  interfaz, contradiciendo directamente esa restricción del RF.
- **Mismo patrón de stub que RF-19**: `infraestructura_stub_adapter.py` siempre retorna
  `False` para el chequeo de "no desactivar área con dispositivos/activos asociados", con el
  mismo comentario desactualizado sobre módulos "aún no implementados" que de hecho ya
  existen.
- Mismo acceso de lectura más amplio que el texto del RF (Productor/Vet/Ing con `R`, cuando
  el RF solo lista "Administrador del sistema, Productor (consulta)") — **DECISIÓN DE DISEÑO
  APROBADA (2026-08-22, issue #1634)**: se mantiene como RBAC dinámico, igual que en RF-19.
  Ver `rf15-19-20-rbac-mod9/resumen_rbac_1634.md`.
- El RF menciona `capacidad_maxima` de forma indirecta (vía RF-33/activos biológicos, no en
  su propia tabla de entradas) — la columna sí existe en DB
  (`infraestructuras.capacidad_maxima int`) aunque no aparece en la lista de "Entradas" del
  RF-20 tal como se entregó; no es un gap, es un campo adicional útil para módulos aguas
  abajo.

---

## RF-21 — Registro de dispositivos IoT

**Veredicto: ✅ Cumple (~95%)** — de los RFs de hardware IoT, el más completo; los gaps de BD
detectados antes de implementar (serial sin UNIQUE, sin FK a infraestructura) ya están
resueltos y verificados.

### Qué SÍ cumple

- CRUD completo (`registrar_dispositivo_iot_use_case.py`,
  `consultar_dispositivos_iot_use_case.py`, `desactivar_dispositivo_iot_use_case.py`).
- **Serial único**: `modulo9.dispositivos_iot.serial UNIQUE` (doblemente indexado:
  `uq_dispositivo_serial` y `uq_dispositivo_iot_serial`) + trigger `trg_dispositivo_serial_unique`.
- **Asociación obligatoria a área productiva**: `id_infraestructura` es `NOT NULL` con FK a
  `modulo9.infraestructuras` — este gap fue detectado y corregido explícitamente
  (`cu05_gaps_bd_rf21_rf24.md`, gap 2): la tabla originalmente no tenía esta columna.
- **Sin eliminación física**: trigger `trg_dispositivo_no_delete` bloquea `DELETE` si existe
  historial — coincide con el flujo alterno de RF-21 que pide `405 Method Not Allowed`.
- Auditoría vía `auditorias_dispositivos_iot` (creada específicamente para CU05).
- **RBAC exacto según el RF**: recurso `dispositivos_iot` (id=11) — Administrador e Ingeniero
  de Campo con C/R/U/D, Productor con solo `R`. Coincide con los actores que declara el RF
  ("Administrador del sistema, Ingeniero de campo") y con la restricción de que otros roles
  ("Productor, Veterinario o Contador") no pueden registrar dispositivos — Veterinario y
  Contador no tienen ningún permiso sobre este recurso.

### Qué NO cumple / gaps

- Identificador interno (`id_dispositivo_iot`) vs. serial físico: cumple la distinción que
  pide el RF, pero no se verificó el manejo específico del flujo alterno de sincronización
  offline ("conflicto de serial tomado durante desconexión") — dado que no existe ningún
  mecanismo de sincronización offline en todo el módulo (ver RF-15), este flujo alterno
  tampoco puede materializarse hoy.
- No se verificó en detalle si el mensaje de error de "serial duplicado" interpola el
  `ID_INTERNO` del dispositivo existente como pide el RF, o si es un mensaje genérico.

---

## RF-22 — Asociación de sensores a estructuras productivas

**Veredicto: ✅ Cumple (~90%)**

### Qué SÍ cumple

- `asociar_sensor_area_use_case.py` implementa el flujo completo: valida existencia de
  dispositivo, sensor y área, que el área esté activa, y que el sensor no tenga ya una
  asociación activa.
- **Un sensor solo puede tener una asociación activa a la vez**: trigger
  `trg_sensor_asociacion_unica_activa` en `modulo9.sensores_areas_asociadas` — refuerzo de DB
  para la regla "uno a uno" que pide el RF.
- **Reasignación soportada**: la tabla tiene `fecha_finalizacion` nullable, permitiendo cerrar
  una asociación anterior y abrir una nueva sin perder el historial — coincide con el flujo
  alterno de "conflicto de reasignación" del RF.
- Auditoría vía `auditorias_sensores_areas` (creada específicamente para CU05).
- **RBAC exacto según el RF**: recurso `sensores` (id=12) — Administrador e Ingeniero de
  Campo con C/R/U, Productor y Veterinario con `R`. Coincide con los actores del RF
  (Administrador, Ingeniero de Campo para escritura) y permite lectura razonable a roles
  operativos sin darles capacidad de modificar la topología física.

### Qué NO cumple / gaps

- No se verificó si la validación "el sensor pertenece al dispositivo especificado" (flujo
  alterno de "inconsistencia de hardware", `422`) está implementada explícitamente o se
  asume implícita por la relación FK — evidencia insuficiente, revisar
  `asociar_sensor_area_use_case.py` en detalle si se necesita certeza total.
- Mismo gap de modo offline no aplica de forma tan directa aquí (el RF-22 no lo menciona
  explícitamente en su texto), por lo que no se cuenta como gap propio de este RF.

---

## RF-23 — Configuración remota de dispositivos IoT

**Veredicto: ✅ Cumple (~95%), MVP síncrono (2026-08-20) + rangos por tipo (2026-08-24)** —
se reemplazó el stub por integración MQTT real vía `BROKER-MQTT-SGPMP` (repo hermano),
verificado end-to-end con backend + broker + Mosquitto reales. El 2026-08-24 (issue #1632) se
agregaron los **rangos de configuración por tipo de dispositivo**, cerrando ese gap. Detalle
del MVP en `anotaciones/modulo_9/cu08_gaps_bd_rf23_mqtt.md` y de los rangos por tipo en
`anotaciones/modulo_9/cu08_gaps_bd_rf23_rangos_tipo.md`. Queda fuera de esta entrega el
reenvío automático cuando un dispositivo `PENDIENTE` reconecta más tarde (ver "Qué NO cumple").

### Qué SÍ cumple

- `configurar_remotamente_use_case.py` implementa el flujo: valida existencia y estado activo
  del dispositivo, impide una segunda configuración mientras hay una `PENDIENTE`
  (`ConflictError`, ahora blindado además por un índice único parcial en BD — antes era solo
  un `SELECT` sin bloqueo, TOCTOU real bajo requests concurrentes), persiste la configuración,
  hace `commit()`, y **después** del commit llama al broker MQTT real (bloqueante, hasta
  ~35s) — respeta el patrón "notificaciones después de confirmar en DB" del proyecto.
- `MqttHttpAdapter` (`infrastructure/adapters/mqtt_http_adapter.py`) llama a
  `POST /v1/commands` del broker, autenticado con un token de servicio validado contra
  `modulo1.credenciales_servicio` (hash sha256, no un secreto estático compartido). El broker
  publica en Mosquitto y espera de forma acotada el ACK del dispositivo antes de responder.
- Endpoint retorna `200 APLICADA` (ACK confirmado), `202 PENDIENTE` (dispositivo offline o
  broker inalcanzable, sin esperar) o `504 NO_CONF` (se publicó pero no hubo ACK a tiempo,
  vía la nueva clase `GatewayTimeoutError` en `src/shared/errors.py`) — cubre los tres flujos
  alternos relevantes del RF ("dispositivo fuera de línea", "timeout de confirmación ACK") con
  el código HTTP exacto que pide el documento de análisis.
- Estados de la configuración remota (`PENDIENTE`/`APLICADA`/`CANCELADA`/`NO_CONF`) modelados
  con `CHECK` constraint en `modulo9.configuraciones_remotas.estado` — `NO_CONF` agregado por
  la migración Alembic `7e2d5f3bf17a_rf23_mqtt_integracion.py` (primera migración real del
  proyecto; hasta ahora los gaps de Paso 0 se aplicaban directo a la BD vía MCP postgres).
- Historial de configuración por dispositivo consultable
  (`ConsultarConfiguracionesUseCase.listar_por_dispositivo`).
- Trigger `trg_configuracion_remota_tiempos_validos` valida los tiempos de
  `frecuencia_captura`/`intervalo_transmision` a nivel de DB; el DTO además valida
  `intervalo_transmision >= frecuencia_captura` con un `model_validator` de Pydantic.
- **Rangos por tipo de dispositivo (issue #1632, 2026-08-24):** nueva tabla
  `modulo9.tipos_dispositivo_iot` (nombre + min/max de cada parámetro, con `CHECK`), FK
  `dispositivos_iot.id_tipo_dispositivo` (NOT NULL, existentes backfilled a `GENERICO`). El
  registro de dispositivo (RF-21) ahora exige `id_tipo_dispositivo`; `ConfigurarRemotamenteUseCase`
  valida `frecuencia_captura`/`intervalo_transmision` contra el rango del tipo del dispositivo y
  responde `400 PARAMETRO_FUERA_DE_RANGO` con el mensaje exacto del FA (min/max/valor). Nuevo
  `GET /configuracion/tipos-dispositivo-iot` (solo lectura, RBAC 11/R) expone el catálogo para el
  front. Los rangos se gestionan por seed/SQL (sin CRUD de escritura por ahora).
- Corrección de ownership: el broker ya no escribe `modulo9.configuraciones_remotas` (antes
  insertaba una fila duplicada con `id_usuario=NULL` cada vez que despachaba un comando,
  colisionando con la fila que este backend ya persiste). El backend es el único escritor.

### Qué NO cumple / gaps

- **No hay reenvío automático cuando un dispositivo `PENDIENTE` reconecta más tarde.** El RF
  pide que la configuración pendiente se envíe sola cuando el dispositivo recupera
  conectividad; eso requeriría un webhook broker→backend inverso, y el equipo IoT aún no ha
  cerrado el contrato de topics para ese flujo. Decisión explícita de alcance (confirmada con
  el usuario): MVP síncrono solamente para esta entrega, este ítem queda como ticket de
  seguimiento. Hoy, si un dispositivo queda `PENDIENTE`, un humano debe reintentar
  manualmente (el índice único de BD permite un nuevo intento en cuanto el anterior deja de
  estar `PENDIENTE`).
- ~~No hay rangos de configuración por tipo de dispositivo.~~ **Resuelto (issue #1632,
  2026-08-24)** — ver "Qué SÍ cumple". Nota de alcance: los rangos seed son ilustrativos
  (perilla de calibración, `# ponytail:` en la migración) y no hay CRUD de escritura de tipos;
  ambos se ajustan por seed/SQL hasta que la UI lo requiera. El FA lista además un input
  `estado_dispositivo` (boolean) para el endpoint de configurar que #1632 no menciona y no
  está en el DTO — desviación conocida, fuera de alcance de esta entrega.
- **El ACK del dispositivo no está autenticado más allá del token de servicio del backend.**
  Mosquitto corre con `allow_anonymous true` en dev — cualquier cliente en la red podría
  publicar en `sgpmp/<serial>/status` y falsificar un ACK. Mismo nivel de gap que el `serial`
  reusado como credencial débil de telemetría en módulo 3 (ya documentado ahí); no es
  específico de esta entrega ni se resuelve acá.

---

## RF-24 — Calibración de dispositivos IoT

**Veredicto: ⚠️ Cumple parcialmente (~65%)** — el flujo CRUD y de trazabilidad está completo,
pero el modelo de calibración en sí es más simple que lo que pide el RF.

### Qué SÍ cumple

- `registrar_calibracion_use_case.py` (endpoints en `sensor_router.py`:
  `POST/GET /sensores/{id}/calibrar`, `/calibraciones`).
- **Solo se calibran sensores de dispositivos activos**: trigger
  `trg_calibracion_dispositivo_activo` en `modulo9.calibraciones` — refuerzo de DB, coincide
  con el flujo alterno de "dispositivo inactivo" (`422`).
- Cada calibración registra dispositivo, sensor, usuario, fecha y valor de referencia —
  coincide con lo que pide "Salida" del RF.
- `valor_referencia` y `id_usuario` se hicieron `NOT NULL` explícitamente (gap detectado y
  corregido en `cu05_gaps_bd_rf21_rf24.md`, punto 5) — evita registros de calibración
  incompletos.
- RBAC sobre recurso `sensores` (id=12), coherente con los roles que el RF autoriza para esta
  operación (Ingeniero de Campo/Administrador).

### Qué NO cumple / gaps

- **No existe validación de rango de calibración por tipo de sensor.** El RF pide rechazar
  valores "fuera del rango de seguridad para la variable" (ej. offset de temperatura de
  500°C). La validación real es una comparación genérica `valor_referencia > 0`, sin ninguna
  tabla de rangos físicos por tipo de sensor — documentado explícitamente como simplificación
  conocida en `cu05_gaps_bd_rf21_rf24.md`. Un valor absurdo pero positivo (ej. 999999) pasaría
  la validación sin problema.
- **`modulo9.calibraciones` no tiene ganancia/offset**, solo `valor_referencia` — el
  adaptador `src/telemetry/infrastructure/adapters/calibracion_m09_adapter.py` (consumidor
  cross-módulo) tiene que aproximar `ganancia=1.0, offset=valor_referencia` porque el modelo
  de datos de M09 no captura una calibración de dos parámetros, lo cual sugiere que el modelo
  actual es más simple de lo que otros módulos del sistema necesitan.
- La restricción del RF de "no se permiten valores no numéricos" está cubierta por el tipo de
  columna (`numeric`) y por Pydantic a nivel de DTO — no se verificó el mensaje de error
  exacto para ese caso.

---

## RF-25 — Adaptación de interfaz operativa

**Veredicto: ⚠️ Cumple parcialmente (~60%)** — el backend resuelve la parte que le
corresponde (contexto de usuario consultable), pero la mayoría de los flujos alternos del RF
describen comportamiento de frontend que este módulo no puede — ni debería — implementar por
sí solo.

### Qué SÍ cumple

- `contexto_interfaz_router.py` expone `GET /configuracion/interfaz/contexto`
  (RBAC recurso 22, todos los roles con `R`), respaldado por
  `obtener_contexto_use_case.py`, que retorna rol, finca activa y especies configuradas.
- Resuelve el problema real de que `modulo1.usuarios` no tiene columna `id_finca`: usa la
  vista `vw_rf25_contexto_usuario`, que hace el join contra `modulo9.fincas.id_usuario` — una
  solución funcionalmente equivalente al mapeo que sugiere la tabla de "Entradas" del RF
  (aunque implementada como vista derivada, no como columna directa).
- Al estar accesible para todos los roles, cumple el requisito de que cada actor
  (Administrador, Ingeniero de Campo, Productor) pueda consultar su propio contexto.

### Qué NO cumple / gaps

- Es un **único endpoint de lectura**. La mayoría de los flujos alternos que describe el RF
  son responsabilidad de la capa de presentación, no del backend, y no tienen contraparte en
  `src/configuration/`:
  - "Forzar recarga de interfaz cuando cambian los permisos en sesión activa" — el backend no
    empuja ningún evento; el cliente tendría que re-consultar por su cuenta.
  - "Intento de acceso a módulo no autorizado (URL bypass) → 403 + redirección al dashboard"
    — la parte de redirección es inherentemente de frontend; el 403 en sí ya lo cubre RBAC de
    forma transversal en cada router, no como parte de este endpoint específico.
  - "Error de ID de finca inválido (manipulación de parámetros) → 401" — el endpoint de
    contexto no acepta `id_finca` como parámetro (deriva la finca del usuario autenticado),
    así que este escenario de manipulación no aplica tal como está diseñado — lo cual es en
    realidad una mitigación más robusta que la que describe el RF, no un gap.
- No se verificó si existe algún filtrado de "indicadores compatibles con la especie
  configurada" (el flujo alterno de "inconsistencia especie-indicador") — dado que el
  contexto solo devuelve datos, no lógica de qué widgets mostrar, esa responsabilidad recae
  en RF-28 (dashboard) o en el frontend.
- El RF fue redactado pensando en un flujo bastante más rico (timeouts de carga, vista de
  bienvenida sin finca asociada, etc.) del que un solo endpoint de contexto puede cubrir por
  diseño — el veredicto de 60% refleja que la mitad conceptual del RF (adaptación real de
  interfaz) no es responsabilidad de este módulo, más que "código faltante" en sentido
  estricto.

---

## RF-26 — Personalización de identidad visual del sistema

**Veredicto: ✅ Cumple (~90%)**

### Qué SÍ cumple

- `guardar_identidad_visual_use_case.py`, `actualizar_identidad_visual_use_case.py`,
  `obtener_identidad_visual_use_case.py` cubren alta/edición/consulta.
- **Validación de archivo**: MIME type (`png`/`jpeg`/`svg`) y tamaño máximo 2MB validados en
  `_guardar_logo` dentro del use case, coincidiendo con el flujo alterno de "formato de
  imagen no compatible" (`415`) y "archivo excede tamaño" del RF.
- **Colores en formato hexadecimal validado**: value object `color_hex.py`.
- **Identidad visual por finca** (no singleton global de sistema) — decisión documentada
  explícitamente en `cu06_gaps_bd_rf25_rf29.md`; el RF no especifica si es por finca o
  global, así que esta interpretación es razonable dado que cada finca puede tener su propia
  identidad institucional.
- **Concurrencia optimista vía columna `version`** (entero), no `fecha_actualizacion` —
  mismo patrón alternativo que documenta `CLAUDE.md` como válido para este tipo de conflicto.
- **RBAC exacto**: recurso `identidad_visual` (id=23), solo Administrador con C/R/U —
  coincide exactamente con "Solo los usuarios con rol Administrador podrán modificar la
  identidad visual del sistema".
- Auditoría vía `auditorias_visuales`, con `valor_anterior`/`valor_nuevo`.

### Qué NO cumple / gaps

- El logo se guarda en disco local (`uploads/logos/{uuid}.ext`) mediante lógica escrita a
  mano dentro del use case — no existe ningún utilitario reusable de subida de archivos en
  `src/shared/`. No es un incumplimiento del RF (que no exige un backend de almacenamiento en
  particular), pero si el despliegue es multi-instancia o efímero (contenedores sin volumen
  persistente), el logo se perdería — vale la pena señalarlo como riesgo operativo, no como
  gap funcional.
- No se verificó si existe el flujo de "vista previa antes de confirmar" que pide el RF como
  paso obligatorio del proceso (pasos 6-8) — es plausible que esto sea enteramente responsabilidad
  de frontend (aplicar los cambios de forma temporal en el cliente antes de hacer `POST`/`PATCH`),
  en cuyo caso no hay nada que el backend deba exponer adicionalmente; no se encontró evidencia
  de un endpoint de "preview" separado, lo cual es consistente con esa lectura.
- **Sin `UNIQUE(id_finca)` en `modulo9.identidad_visuales`** (ver hallazgos transversales) —
  nada en la base de datos impide, por sí sola, que una condición de carrera cree dos filas
  "vigentes" para la misma finca; la integridad depende de que el use case siempre lea la
  versión más alta antes de escribir.

---

## RF-27 — Configuración visual del sistema (tema claro/oscuro)

**Veredicto: ✅ Cumple (~90%)**

### Qué SÍ cumple

- `guardar_tema_personal_use_case.py`, `guardar_tema_global_use_case.py`,
  `obtener_tema_resuelto_use_case.py` — cubren los tres niveles que pide el RF: preferencia
  individual, tema global de administrador, y resolución con fallback.
- **Jerarquía de resolución correcta**: personal → global → claro por defecto, implementada
  en `obtener_tema_resuelto_use_case.py` según `cu06_gaps_bd_rf25_rf29.md`.
- **Persistencia en base de datos**, no en sesión de navegador — cumple la restricción
  explícita del RF de que la preferencia "persiste entre sesiones".
- **RBAC de dos niveles, exacto según el RF**: recurso `tema_visual` (id=24) con todos los
  roles en `R`/`U` para la preferencia personal; recurso `configuracion_ui_global` (id=27)
  solo Administrador en `R`/`U` para el tema por defecto del sistema — coincide con "Solo el
  Administrador del sistema puede definir el tema visual predeterminado".

### Qué NO cumple / gaps

- **Sin `UNIQUE(id_usuario)`** en `modulo9.temas_visuales` para el caso personal (sí hay un
  índice único parcial para el caso `es_global=true`) — el modelo de datos permite,
  técnicamente, más de una fila personal por usuario; la resolución "toma la más reciente por
  `fecha_actualizacion`" depende de que el use case siempre haga upsert correctamente, sin
  respaldo de un constraint de DB.
- No se verificó si existe verificación de contraste WCAG 2.1 AA que pide el RF como NFR de
  accesibilidad (comparar el color institucional de RF-26 contra el tema oscuro) — no se
  encontró evidencia de esta lógica en el código explorado; es plausible que no esté
  implementada, dado que requeriría cálculo de luminancia relativa, algo que no apareció en
  ninguna búsqueda de los value objects de color.
- El flujo alterno de "modo automático sin soporte del dispositivo → fallback a claro" es
  inherentemente de frontend (depende de `prefers-color-scheme` del navegador); el backend
  solo necesita aceptar `theme_mode=3` como valor válido, lo cual sí ocurre.

---

## RF-28 — Personalización del dashboard

**Veredicto: ⚠️ Cumple parcialmente (~65%)** — el guardado/consulta de layout funciona, pero
no se encontró evidencia de que el backend valide las reglas de negocio específicas de la
grilla que pide el RF (límite de 12 widgets, solapamiento de posiciones, span fuera de rango).

### Qué SÍ cumple

- `guardar_dashboard_use_case.py`, `obtener_dashboard_use_case.py`,
  `restaurar_dashboard_use_case.py` cubren guardar, consultar y restaurar configuración por
  defecto — los tres verbos que pide el RF.
- Estructura de datos (`modulo9.dashboard_layouts.config` JSONB con clave `"grid"`,
  `active_widget` como array) es compatible con el modelo de grilla 4×3 con posiciones que
  describe el RF.
- **RBAC exacto**: recurso `dashboard_layout` (id=25), todos los roles con `R`/`U` — coincide
  con que los tres actores (Administrador, Ingeniero de Campo, Productor) puedan personalizar
  su propio dashboard.

### Qué NO cumple / gaps

- **No se encontró evidencia de validación del límite de 12 widgets activos**, ni de
  detección de solapamiento de posiciones en la grilla (`fila`/`columna` ya ocupada), ni de
  la regla de "un widget con `span_columnas=2` no puede ir en la columna 4" — el RF describe
  estas tres validaciones como flujos alternos explícitos con `400`/`409`. El use case de
  guardado no fue leído línea por línea para confirmar su ausencia total, pero no apareció
  ninguna referencia a estos términos (`span`, límite de 12, solapamiento de grilla) durante
  la exploración del módulo — es la señal más fuerte de que esta validación vive del lado del
  cliente, si es que existe en algún lugar.
- **Sin `UNIQUE(id_usuario)`** en `modulo9.dashboard_layouts` — mismo patrón de gap que
  RF-27/RF-29, la tabla permite múltiples filas por usuario sin constraint de DB.
- El manejo de "widget sin datos disponibles → mostrar mensaje sin romper los demás" es,
  otra vez, responsabilidad de renderizado en frontend; el backend solo necesita devolver el
  layout guardado, lo cual sí hace.
- La responsividad por tamaño de pantalla (escritorio/tableta/móvil) es 100% frontend y no
  aplica a este módulo — se menciona aquí solo para dejar explícito que no es un gap de
  backend.

---

## RF-29 — Configuración de idioma

**Veredicto: ⚠️ Cumple parcialmente (~50%)** — el almacenamiento y la resolución jerárquica
de la preferencia de idioma están completos, pero el RF trata fundamentalmente de traducir la
interfaz, y esa mitad — el motor de i18n en sí — no existe en ninguna parte del repositorio.

### Qué SÍ cumple

- `guardar_idioma_personal_use_case.py`, `guardar_idioma_global_use_case.py`,
  `obtener_idioma_resuelto_use_case.py` — misma estructura de tres niveles que RF-27
  (personal → global → español por defecto), consistente con lo que pide el RF.
- **RBAC de dos niveles, exacto**: recurso `preferencia_idioma` (id=26) todos los roles
  `R`/`U`; recurso `configuracion_ui_global` (id=27, compartido con RF-27) solo Administrador
  `R`/`U` — coincide con "Solo el Administrador del sistema puede definir el idioma
  predeterminado global".
- Persistencia en base de datos (no en sesión), cumpliendo la misma restricción de
  persistencia entre sesiones que RF-27.

### Qué NO cumple / gaps

- **No existe ningún motor de traducción/i18n en todo el repositorio.** `src/shared/` no
  tiene ningún archivo de catálogo de mensajes, cargador de traducciones, ni middleware
  relacionado — se verificó explícitamente listando el contenido completo de `src/shared/`.
  Todo lo que existe hoy es una tabla que guarda un `locale_code` (string tipo `"es"`/`"en"`)
  por usuario. El RF, sin embargo, exige que "menús de navegación, etiquetas de formularios,
  mensajes del sistema, paneles informativos, mensajes de error y confirmación, títulos de
  módulos" se traduzcan — nada de eso ocurre a nivel de backend (los mensajes de error de
  todo el proyecto, incluidos los de este mismo módulo, están hardcodeados en español). Este
  es, en magnitud, un gap de alcance comparable al de CAPTCHA ausente en RF-01 de Módulo 1:
  la parte de "guardar la preferencia" está resuelta, pero la funcionalidad central del RF
  (que la interfaz efectivamente cambie de idioma) no.
- **No hay validación de `locale_code` contra una lista blanca de idiomas soportados.** El RF
  restringe explícitamente a español e inglés (`es-CO`/`en-US`) y pide rechazar cualquier
  otro valor con `400`. No se encontró ningún `CHECK` constraint en
  `modulo9.preferencias_idiomas.locale_code` ni validación de dominio cerrado en el value
  object correspondiente — un cliente podría enviar cualquier string como locale y quedaría
  persistido sin rechazo.
- Mismo gap de `UNIQUE(id_usuario)` ausente que RF-27/RF-28.
- Si se decide implementar el motor de i18n real, el cambio no se limita a este RF: impacta
  transversalmente todos los mensajes de error/éxito de **todos** los módulos del backend
  (hoy hardcodeados en español vía `src/shared/errors.py` y cada use case), lo cual excede
  por mucho el alcance de "Módulo 9 — Configuración" tal como está delimitado hoy.

---

## RF-30 — Plantillas de configuración

**Veredicto: ✅ Cumple (~90%)**

### Qué SÍ cumple

- El listado (`consultar_plantillas_use_case.py`) muestra nombre, especie y versión, con
  acceso a los flujos de creación (RF-31) y aplicación (RF-32) desde el mismo router
  (`plantilla_router.py`).
- **Alcance correctamente limitado**: el `params_snapshot` solo cubre `ciclos_biologicos`,
  `patologias` (por referencia), `metricas_produccion` y `umbrales_ambientales` — exactamente
  las categorías que el RF autoriza (parámetros productivos por especie + umbrales
  ambientales), sin dispositivos IoT, infraestructura, dashboard ni identidad visual, como
  exige explícitamente la restricción de "alcance no permitido".
- **Nombre único + versión inmutable**: constraint `UNIQUE(template_name, version)` en
  `modulo9.plantillas`, reforzado por trigger `trg_plantilla_inmutable` que bloquea
  `UPDATE`/`DELETE` a nivel de DB — doble capa para la regla "una plantilla guardada no puede
  modificarse".
- **RBAC exacto**: recurso `plantillas` (id=28), solo Administrador e Ingeniero de Campo, con
  acciones C/R/E (sin U/D, coherente con la inmutabilidad) — coincide exactamente con los
  actores del RF.

### Qué NO cumple / gaps

- No se encontró evidencia de control de versión de esquema JSON *documentado hacia el
  usuario* más allá de la constante `_SCHEMA_VERSION_ACTUAL = 1` embebida en el código — el
  RF pide que "cualquier actualización del esquema debe documentarse con el número de versión
  correspondiente" como NFR de mantenibilidad; hoy ese versionado existe en código pero no
  hay un changelog o tabla de versiones de esquema consultable.
- Todo lo demás relevante para este RF se detalla en las secciones RF-31 y RF-32.

---

## RF-31 — Creación de plantilla de configuración

**Veredicto: ✅ Cumple (~90%)**

### Qué SÍ cumple

- `registrar_plantilla_use_case.py`: valida que la especie exista y esté activa, arma el
  `params_snapshot` a partir del DTO, **embebe `schema_version=1` automáticamente en el
  snapshot** (`snapshot['schema_version'] = _SCHEMA_VERSION_ACTUAL`, línea 55) — confirmado
  leyendo el archivo completo, no es un TODO ni un valor hardcodeado a mano por el cliente.
- **Versión auto-incremental correcta**: `version = (version_max or 0) + 1`, consultando
  `obtener_version_maxima(template_name)` antes de insertar — cumple "asigna el número de
  versión inicial (1)" para nombres nuevos y versiona correctamente actualizaciones bajo el
  mismo nombre.
- **Atomicidad ante fallo de persistencia**: el `guardar()` + `registrar()` de auditoría +
  `commit()` están en el mismo bloque `try/except` con `rollback()` en caso de error — cumple
  la restricción de "no se almacena ningún registro parcial".
- Auditoría con tabla dedicada `auditorias_plantillas` (creada específicamente para CU07,
  solo permite `tipo_operacion='CREATE'` vía `CHECK`, coherente con que las plantillas nunca
  se editan).
- **Claves del snapshot validadas contra una lista blanca** (`schema_version`,
  `ciclos_biologicos`, `patologias`, `metricas_produccion`, `umbrales_ambientales`) — rechaza
  con `BusinessRuleError` cualquier clave fuera de ese conjunto, que es la implementación
  concreta de la restricción de "alcance no permitido" de RF-30.

### Qué NO cumple / gaps

- No se verificó si existe la validación de "al menos un parámetro seleccionado" (rechazar
  plantilla vacía con `400`) al nivel del DTO o del use case — no se leyó
  `registrar_plantilla_dto.py` para confirmarlo con certeza.
- El RF pide mensajes de error que detallen "la lista de campos inválidos" en caso de fallo
  de esquema — no se confirmó si `BusinessRuleError` para claves fuera de la lista blanca
  interpola la lista específica de claves rechazadas o da un mensaje genérico.

---

## RF-32 — Aplicación de plantilla de configuración

**Veredicto: ⚠️ Cumple parcialmente (~80%)** — el flujo de validación, resumen before/after,
atomicidad y auditoría está completo y bien resuelto; el hallazgo de peso es que el chequeo
de concurrencia optimista compara un campo que nunca cambia, por lo que no puede cumplir su
propósito real.

### Qué SÍ cumple

- `aplicar_plantilla_use_case.py`: valida que la plantilla exista, que la especie destino
  exista y esté activa, verifica **compatibilidad de `schema_version`** contra
  `_SCHEMA_VERSION_ACTUAL` (`PreconditionFailedError` si no coincide — cumple el flujo
  alterno de "incompatibilidad de versión de esquema" con `412`).
- **Reemplazo total, no fusión parcial**: desactiva/elimina todos los ciclos, métricas,
  umbrales y patologías existentes de la especie destino antes de insertar los del snapshot —
  coincide con "reemplaza en su totalidad los parámetros correspondientes".
- **Registro `before_snapshot`/`after_snapshot`** capturado explícitamente
  (`_capturar_estado`) antes y después de aplicar — cumple el requisito de auditoría de
  "estado anterior y posterior de cada parámetro modificado", algo más detallado que el
  patrón `valores_anteriores`/`valores_nuevos` usado en el resto del módulo.
- **Atomicidad**: todo el reemplazo (desactivaciones + inserciones + registro de auditoría)
  ocurre dentro de un único bloque `try/except` con `rollback()` ante cualquier excepción —
  cumple "rollback completo y automático" ante fallo durante la aplicación.
- Los parámetros de la especie destino no cubiertos por la plantilla (ej. si el snapshot no
  trae umbrales) permanecen intactos, porque solo se desactivan/reinsertan las categorías
  presentes en el `params_snapshot` recibido.

### Qué NO cumple / gaps

- **La concurrencia optimista compara el campo equivocado — probable bug silencioso.** El
  código (`aplicar_plantilla_use_case.py:88-99`) compara
  `especie_destino.fecha_creacion` (fecha de alta de la especie, **inmutable**, se fija una
  sola vez al crear el registro) contra `dto.fecha_creacion_especie_destino` enviado por el
  cliente, y si difieren lanza `PreconditionFailedError` con el mensaje "La especie destino
  fue modificada. Recarga y reintenta." El problema: `fecha_creacion` **nunca cambia** tras el
  alta de la especie, así que esta comparación jamás puede detectar el escenario real que se
  supone debe cubrir (que otro usuario editó la especie destino mientras el actual revisaba el
  resumen de aplicación). El patrón correcto, documentado en `CLAUDE.md` y usado en el resto
  del proyecto (incluyendo `editar_especie_use_case.py` de este mismo módulo), es comparar
  `fecha_actualizacion`. Tal como está, el chequeo de 412 en RF-32 solo puede fallar si el
  cliente envía una `fecha_creacion` distinta a la real (un error de integración del cliente),
  nunca por una edición concurrente genuina — el flujo alterno "conflicto de modificación
  concurrente" del RF, en la práctica, no se cumple.
- No se verificó si existe el `HTTP 409` específico para el escenario que describe el RF de
  "otro administrador modificó la configuración destino mientras el usuario revisaba el
  resumen" — dado el bug anterior, es posible que este código de error nunca se alcance con
  datos reales tampoco.
- El `target_config` en `aplicaciones_plantillas` se guarda como `{"id_especie": id_dest}` —
  un JSONB libre, sin FK real hacia `especies`/`fincas`. Funciona para trazabilidad de lectura
  pero no tiene integridad referencial reforzada por la DB.

---

## Hallazgos transversales (afectan a varios RFs)

1. **Patrón de "adaptador stub que siempre dice que no hay dependencias".** Cinco puertos de
   dependencia (`proceso_critico_stub.py` para RF-15, `dependencia_patologia_stub.py` y
   `dependencia_metrica_stub.py` para RF-16, `finca_stub_adapter.py` para RF-19,
   `infraestructura_stub_adapter.py` para RF-20) retornan `False`/"sin dependencias" de forma
   permanente. Para RF-15/RF-16 el motivo es real (esperan al módulo de Predicción/IA — M04
   — que efectivamente no existe aún). Para RF-19/RF-20 el motivo documentado en el código
   ("hasta que RF-21 e IoT existan") ya **no aplica** — esos módulos ya están implementados —
   y sin embargo el stub nunca fue reemplazado por la consulta real. Es la corrección más
   barata y de mayor impacto de todo este audit: dos de los cinco stubs podrían resolverse
   hoy mismo sin esperar a ningún módulo externo. *(Afecta RF-15, RF-16, RF-19, RF-20.)*

2. **Cero mecanismo de modo offline / sincronización diferida en todo el módulo.** RF-15 y
   RF-16 lo piden explícitamente en su flujo de proceso; no existe ningún endpoint de
   sincronización en lote, cola de cambios pendientes, ni resolución de conflictos por lote
   en `src/configuration/` ni en ningún otro módulo del backend. *(Afecta RF-15, RF-16; en
   menor medida RF-21 vía su flujo alterno de "conflicto de sincronización offline".)*

3. **Integraciones externas nunca conectadas más allá de los stubs de dependencia.**
   *(Resuelto para RF-23 el 2026-08-20 — ver su sección arriba. Sigue afectando a RF-29.)*
   El motor de traducción/i18n (RF-29) es la pieza central del RF que representa, y no existe.
   A diferencia de los stubs del punto 1 (donde el flujo alrededor sí está completo), este gap
   deja el RF estructuralmente incompleto en su propósito principal.

4. **Sin constraint `UNIQUE` de "una fila por usuario/finca" en cuatro tablas.**
   `modulo9.temas_visuales`, `modulo9.dashboard_layouts` y `modulo9.preferencias_idiomas` no
   tienen `UNIQUE(id_usuario)` (para el caso personal); `modulo9.identidad_visuales` no tiene
   `UNIQUE(id_finca)`. En los cuatro casos el sistema resuelve "cuál es la fila vigente" leyendo
   la más reciente por timestamp/versión desde la aplicación (vistas SQL o lógica de use case),
   sin una segunda capa de defensa en la base de datos como sí existe en la mayoría de los
   demás agregados del módulo (especies, fincas, plantillas, etc. sí tienen sus invariantes
   reforzadas por constraints o triggers). *(Afecta RF-26, RF-27, RF-28, RF-29.)*

5. **RBAC más permisivo que el texto de cada RF — RESUELTO (2026-08-22, issue #1634).** El
   patrón recurrente afectaba a RF-15 (Veterinario con `U` sobre especies), RF-19 y RF-20
   (Veterinario e Ingeniero de Campo con `R` sobre fincas/infraestructuras, cuando el RF solo
   lista "Productor (consulta)"). El equipo de análisis decidió, caso por caso:
   - **RF-15 → revocado.** La `U` del Veterinario sobre especies es escritura y contradice los
     actores del RF; se aplicó `es_activo=false` al permiso id=48.
   - **RF-19 y RF-20 → mantenidos como decisión de diseño.** Las `R` de Vet/Ing sobre
     fincas/infraestructuras son solo lectura y operativamente defendibles; se conservan como
     RBAC dinámico explícito, ya no como desviación silenciosa.

   Detalle y verificación en `rf15-19-20-rbac-mod9/resumen_rbac_1634.md`. *(Afecta RF-15, RF-19, RF-20.)*

6. **Posible bug de concurrencia optimista en RF-32** (`aplicar_plantilla_use_case.py`):
   compara `fecha_creacion` (inmutable) en vez de `fecha_actualizacion`, por lo que el chequeo
   de "la especie destino cambió mientras revisabas el resumen" no puede detectar ediciones
   concurrentes reales. Es el único caso de los patrones de concurrencia optimista revisados
   en todo el módulo que usa el campo equivocado — el resto (especies, ciclos, patologías,
   métricas, umbrales, fincas, infraestructuras, identidad visual) sigue el patrón correcto
   documentado en `CLAUDE.md`. *(Afecta solo a RF-32.)*

7. **Documentación previa de módulo 9 (`anotaciones/modulo_9/`) es confiable y sigue
   vigente.** A diferencia de lo que ocurrió con `CLAUDE.md` en el audit de Módulo 1, los seis
   documentos de gaps de BD (`cu02`…`cu07`) describen con precisión decisiones que efectivamente
   están aplicadas hoy en la base de datos real — se verificó cruzando cada uno contra el
   esquema vivo vía MCP de Postgres y no se encontraron discrepancias. La única corrección que
   vale la pena anotar es de vigencia temporal, no de exactitud: los comentarios "hasta que
   RF-21/RF-33 estén implementados" en los stubs de RF-19/RF-20 (punto 1 de esta sección)
   quedaron desactualizados porque esos módulos sí se completaron después.

8. **Acoplamiento cruzado de schema — nota de modularidad, no bloqueante.**
   `modulo9.sensores.categoria` reutiliza un tipo enum (`enum_reglas_alertas_tipo_sensor`) cuyo
   dueño real es el schema `modulo3`, no `modulo9`. Para un módulo que se llama
   "Configuración" y que en teoría debería ser la fuente de catálogos para el resto del
   sistema, depender de un enum externo invierte esa relación en este punto específico. No
   afecta ningún RF de forma directa, pero es una dependencia de esquema que otro equipo
   debería tener presente si alguna vez se modifica `modulo3`.

---

## Si se implementa el motor de i18n real (RF-29)

RF-29 es, de los 18 RFs auditados, el que tiene la brecha más grande entre "lo que el texto
pide" y "lo que existe" — comparable en naturaleza al gap de CAPTCHA de RF-01 en Módulo 1,
aunque de mayor alcance técnico. Vale la pena dimensionar qué cambiaría si se decide cerrarlo:

- **No es un cambio local a `src/configuration/`.** Los mensajes de error de todo el backend
  (`src/shared/errors.py`, y cada `raise ValidationError(...)`/`BusinessRuleError(...)` de
  cada use case, en los 9 módulos del proyecto) están hardcodeados en español. Un motor de
  i18n real requeriría externalizar esos strings a catálogos de mensajes (`es.json`/`en.json`
  o equivalente) y resolverlos según el `locale_code` que ya guarda `preferencia_idioma`.
- **El backend ya tiene la pieza de "saber qué idioma prefiere el usuario"** resuelta
  (RF-29 actual) — lo que falta es el mecanismo de traducción en sí, que podría vivir como un
  middleware en `src/shared/` que intercepte la respuesta de error/éxito y la traduzca antes
  de enviarla, usando el `locale_code` resuelto vía `obtener_idioma_resuelto_use_case.py`.
- **Alcance del cambio**: a diferencia del ejemplo de CAPTCHA en Módulo 1 (que solo afectaba
  RF-01), aquí el cambio toca la totalidad de la superficie de mensajes del sistema — es un
  proyecto transversal de infraestructura, no una función aislada de Módulo 9, aunque el
  requerimiento que lo origina esté catalogado ahí.
