# Especificación de Requerimientos — Módulo 2

_Convertido de `Especificacion de requerimiento (1).xlsx`, hoja "Modulo 2". Original en `backups/1-analisis/`._

## RF-33 — Registro de Activos Biológicos

**Código Identificación:** RF-33 -- Versión -- 1.2

**Fuente:** Productor / Administrador del sistema / Ingeniero de campo

**Descripción:** El sistema debe permitir la creación y registro de activos biológicos como entidades persistentes dentro del sistema, representando recursos vivos sujetos a procesos de transformación biológica (crecimiento, producción y reproducción).

El registro debe soportar dos tipos de activos:

Activo individual: entidad única con identificación irrepetible dentro del sistema.
Activo poblacional: entidad agregada que representa múltiples individuos gestionados colectivamente bajo condiciones homogéneas.


Durante el registro, el sistema deberá capturar y persistir información estructural del activo, incluyendo:

Tipo de activo (INDIVIDUAL / POBLACIONAL)
Especie asociada (definida en RF-15)
Identificación única (obligatoria para individuales)
Cantidad inicial (obligatoria para lotes)
Fecha de inicio del ciclo productivo
El estado del activo será asignado automáticamente por el sistema con valor ACTIVO al momento del registro y no es configurable por el usuario.
Procedencia
Infraestructura productiva asociada (RF-20)
Atributos dinámicos definidos por especie (RF-16)

El sistema deberá garantizar que los datos ingresados cumplan las reglas de negocio, integridad y consistencia antes de ser persistidos.


**Justificación:** El registro de activos biológicos constituye la base funcional del sistema, ya que permite modelar los recursos vivos sobre los cuales se ejecutan los procesos de monitoreo, análisis, predicción y valoración financiera.

Este requerimiento es fundamental para:

Garantizar trazabilidad del ciclo de vida del activo
Permitir la integración con sensores IoT (M03)
Alimentar modelos predictivos (M04)
Soportar procesos de valoración bajo NIC 41 (M06)

**Precondiciones:** El usuario debe estar autenticado en el sistema (RF-02).

El usuario debe tener permisos para registrar activos biológicos (M01).

Debe existir al menos una especie registrada (RF-15).

Debe existir al menos una infraestructura productiva registrada (RF-20).

Deben existir parámetros configurados por especie (RF-16).

**Restricciones:** El tipo de activo es obligatorio y no puede modificarse después del registro.

Para activos individuales:

El identificador es obligatorio y único en todo el sistema.

Para activos tipo poblacionales:

La cantidad inicial es obligatoria y debe ser mayor a cero.

La fecha_inicio_ciclo es obligatoria, no puede ser posterior a la fecha actual del sistema ni inferior a una fecha mínima válida (1970-01-01).

La especie debe existir en el sistema y estar activa.

La infraestructura debe existir y estar activa.

Los atributos dinámicos deben cumplir con la configuración definida por especie (tipo de dato, obligatoriedad y rango).

El estado del activo es asignado automáticamente por el sistema con valor ACTIVO al momento de la creación y no puede ser modificado durante el registro.

Todos los datos deben ser validados antes de persistirse; no se permiten registros parciales.

Los atributos_dinamicos deben cumplir estrictamente con la configuración definida en RF-16:

- Cada clave debe existir en la configuración de la especie.
- No se permiten atributos adicionales no configurados.
- El valor de cada atributo debe cumplir:
  - Tipo de dato definido
  - Restricción de obligatoriedad
  - Rango mínimo y máximo (si aplica)

La validación se realiza contra la metadata almacenada en RF-16, no contra el payload recibido.

**(RFC-004)** Precisión de la validación anterior, contra los campos de RF-16 definidos en ese mismo RFC:

- Si una métrica activa aplicable a la especie/tipo_activo tiene `es_obligatorio = true`, el atributo dinámico correspondiente debe estar presente en el payload y no ser `null`. Si falta o es `null`, el sistema rechaza el registro.
- El valor de cada atributo debe ser compatible con el `tipo_dato` configurado en RF-16 (NUMERICO, ENTERO, TEXTO o BOOLEANO) para esa métrica.
- Si la métrica tiene `valor_min`/`valor_max` definidos (solo aplica a NUMERICO/ENTERO), el valor recibido debe estar dentro de ese rango, inclusive.
- Código de respuesta HTTP: cuando la validación de un atributo dinámico falla por cualquiera de los tres motivos anteriores (obligatorio faltante/`null`, tipo incompatible, o fuera de rango), el sistema responde **HTTP 422** — se trata de una violación de una regla de negocio que depende de configuración externa (RF-16), consistente con el mismo criterio ya aplicado en este RF a la coherencia `origen_financiero_activo`/`costo_adquisicion`. El resto de validaciones de `atributos_dinamicos` no cubiertas por RFC-004 (clave no configurada para la especie, atributo no reconocido) mantienen **HTTP 400**, por ser errores de formato/entrada sobre datos que el cliente no debería haber podido enviar en primer lugar (no dependen de una regla de negocio configurable, sino de que la clave exista o no en el catálogo).

Reglas de coherencia por tipo de activo:

- Si tipo_activo = INDIVIDUAL:
  - identificador es obligatorio
  - cantidad_inicial debe ser null

- Si tipo_activo = POBLACIONAL:
  - cantidad_inicial es obligatoria
  - identificador debe ser null

El sistema debe rechazar cualquier combinación inválida.

No se permite el envío simultáneo de identificador y cantidad_inicial.

No se permite que ambos campos sean nulos.

Para activos tipo POBLACIONAL, el campo cantidad_actual debe inicializarse con el valor de cantidad_inicial y no puede ser menor a cero.

Debe cumplirse exclusividad según tipo_activo.   

El campo origen_financiero_activo es obligatorio, no tiene valor por defecto y no puede modificarse después del registro.

Si origen_financiero_activo = COMPRA o DONACION:
  costo_adquisicion es obligatorio y debe ser > 0.
  soporte_documental_costo es obligatorio.

Si origen_financiero_activo = NACIMIENTO:
  costo_adquisicion debe ser nulo.
  soporte_documental_costo debe ser nulo.

Si origen_financiero_activo = TRANSFERENCIA_INTERNA:
  costo_adquisicion es opcional. Si se registra, 
  debe ser > 0 y llevar soporte_documental_costo.

El costo_adquisicion registrado en RF-33 es INMUTABLE. RF-82 lo consume directamente; ningún módulo puede modificarlo después del registro inicial.

Este campo no representa el valor contable del activo (responsabilidad de RF-82); representa el costo histórico pagado, que es la base de la valoración alternativa de RF-88.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 – Autenticación de usuarios
RF-04 – Gestión de permisos
RF-15 – Catálogo de especies productivas
RF-16 – Configuración de parámetros por especie
RF-20 – Gestión de infraestructura productiva

**Actores:** Productor, Administrador del sistema, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| tipo_activo | varchar(10) | Tipo de activo: INDIVIDUAL o POBLACIONAL |
| especie_id | integer | Identificador de la especie |
| identificador | varchar(50) | Identificador funcional del activo (ej. arete bovino), obligatorio para tipo INDIVIDUAL y único a nivel de sistema. |
| cantidad_inicial | integer | Cantidad de individuos (solo para poblacional) |
| fecha_inicio_ciclo | date | Fecha de inicio del ciclo productivo |
| detalles_procedencia | varchar(100) | Comentarios o detalles adicionales sobre el origen del activo. |
| origen_financiero_activo | Enum (COMPRA, NACIMIENTO, DONACION, TRANSFERENCIA_INTERNA) | Origen del activo biológico. Determina la contrapartida del asiento contable inicial en RF-82. El Productor o Administrador lo selecciona al momento del registro. No puede modificarse después. |
| costo_adquisicion | Decimal(18,4) | Valor pagado por el activo en pesos colombianos (COP). Obligatorio si origen_financiero_activo = COMPRA o DONACION. Nulo si NACIMIENTO. Opcional si TRANSFERENCIA_INTERNA. |
| soporte_documental | Varchar(150) | Referencia al documento que respalda el costo_adquisicion: número de factura, número de contrato, acta de donación, etc. Obligatorio cuando costo_adquisicion no es nulo. |
| infraestructura_id | integer | Identificador de la infraestructura asociada |
| atributos_dinamicos | json | Objeto JSON de tipo clave-valor donde cada clave corresponde a un parámetro definido en RF-16 y el valor representa el dato ingresado para el activo. No debe incluir metadata (tipo, rango, obligatoriedad), ya que esta se valida contra la configuración existente. **(RFC-004)** La ausencia de una clave marcada `es_obligatorio=true` en RF-16 se trata igual que un valor `null` explícito — ambos casos se rechazan con HTTP 422. |

**Proceso:**

El usuario accede al módulo de Gestión de Activos Biológicos.

El sistema valida autenticación y permisos del usuario.

El usuario selecciona la opción “Registrar activo biológico”.

El sistema solicita el tipo de activo (INDIVIDUAL o POBLACIONAL).

El usuario selecciona la especie.

El sistema consulta la configuración de la especie (RF-16) y carga dinámicamente los atributos requeridos.

El usuario ingresa la información del activo:

Identificación o cantidad
Fecha de inicio
Procedencia

Infraestructura
Atributos dinámicos

El sistema valida en backend:

Existencia de especie
Existencia de infraestructura
Unicidad del identificador (si aplica)
Cantidad válida (si poblacional)
Formato de fecha
Cumplimiento de atributos dinámicos (tipo, rango, obligatoriedad)

Si alguna validación falla:

El sistema rechaza el registro
Retorna errores por campo

Si las validaciones son exitosas:
El sistema inicia una transacción.

Registra el activo biológico en la base de datos 
con todos sus campos.

Asigna estado inicial = ACTIVO.

Para activos tipo POBLACIONAL:
  Inicializa cantidad_actual = cantidad_inicial.
  Persiste cantidad_inicial como campo inmutable 
  en la entidad del activo. Este campo no puede 
  ser modificado en ningún momento posterior 
  por ningún módulo ni proceso del sistema.
  Persiste peso_promedio_inicial si fue 
  proporcionado, también como campo inmutable. 
  Este valor sirve como referencia histórica 
  para RF-36 (Gestión Poblacional), que lo 
  muestra siempre al usuario como punto de 
  comparación frente al peso_promedio actual.

Registra un snapshot inicial del activo en la tabla historial_activos (Evento 0 del historial), incluyendo:
  Todos los campos persistidos del activo.
  version = 1
  tipo_evento = CREACION
  fecha_registro y usuario_registro
  Para activos POBLACIONAL: cantidad_inicial, 
  peso_promedio_inicial, cantidad_actual = 
  cantidad_inicial

Este snapshot actúa como el punto de origen inmutable del historial del activo. Todos los cambios posteriores en cantidad_actual o peso_promedio se registrarán como eventos subsiguientes en historial_activos, no como modificaciones del registro original.

**Salida:**

Registro del activo biológico almacenado en la base de datos

Evento inicial de creación del activo

Asociación con infraestructura productiva

Registro en auditoría

ID técnico del activo generado (clave primaria en base de datos) y, en caso de activo individual, el identificador funcional validado.

**Postcondiciones:**

El activo queda disponible para gestión dentro del sistema

El activo puede recibir eventos biológicos (RF-39 en adelante)

El activo puede ser asociado a sensores IoT (RF-49)

El activo puede ser utilizado por módulos analíticos y financieros

Para activos tipo POBLACIONAL: los campos cantidad_inicial y peso_promedio_inicial quedan persistidos de forma inmutable en la entidad del activo. Ningún módulo posterior (RF-36, RF-45, RF-48) puede modificar estos valores. 

Son consultables en cualquier momento por RF-36 para mostrar la referencia histórica al usuario.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite registrar activos individuales y por poblacion

El sistema valida correctamente todos los campos de entrada

El sistema impide identificadores duplicados

El sistema impide registrar cantidades inválidas

El sistema valida correctamente los atributos dinámicos por especie

El sistema asocia correctamente el activo a infraestructura y especie

El sistema crea el activo en estado ACTIVO

El sistema genera automáticamente el evento de creación

El sistema registra la acción en auditoría

El sistema responde en un tiempo menor o igual a 2 segundos

Para activos POBLACIONAL, el sistema persiste cantidad_inicial como campo inmutable junto con el registro del activo.

El sistema registra un snapshot inicial (Evento 0) en historial_activos en el mismo momento del registro del activo, incluyendo todos los campos y marcado con tipo_evento = CREACION.

El campo cantidad_inicial no puede ser modificado por ningún módulo posterior; su valor original es permanente y siempre consultable como referencia histórica.

El sistema debe validar que si el origen financiero es 'Compra', el campo costo_adquisicion no sea nulo ni menor a cero 

El sistema valida que si origen_financiero_activo = COMPRA o DONACION, el campo costo_adquisicion sea mayor a cero y soporte_documental esté completo. En ausencia de cualquiera, el sistema rechaza el registro con HTTP 422.

El sistema valida que si origen_financiero_activo = NACIMIENTO, los campos costo_adquisicion y soporte_documental sean nulos. Si se envían con valor, el sistema los rechaza.

El campo origen_financiero_activo no puede modificarse después del registro bajo ninguna circunstancia.

**Requerimientos no funcionales:**

Seguridad

Validación de permisos en backend

Registro obligatorio en auditoría

Rendimiento

Tiempo de respuesta menor o igual a 2 segundos

Consistencia

Uso de transacciones para garantizar integridad de datos

Usabilidad

Formularios dinámicos basados en tipo de activo y especie

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-34 — Asociación del Activo Biológico a Infraestructura Productiva

**Código Identificación:** RF-34 -- Versión -- 1.1

**Fuente:** Productor / Administrador

**Descripción:** El sistema debe permitir consultar y visualizar la asociación activa e historial de asociaciones de un activo biológico con su infraestructura productiva, con el fin de conocer en todo momento la ubicación operativa del activo dentro de la finca.

Este requerimiento es exclusivamente de lectura. 
No contempla la creación, modificación ni desactivación de asociaciones, las cuales son responsabilidad de otros requerimientos:

  Creación de la asociación inicial: RF-33 
    (Registro de Activos Biológicos)
  Cambio de infraestructura: RF-48 
    (Transferencia Interna de Activos Biológicos)

El sistema debe exponer dos vistas de consulta:

Vista 1 — Asociación Activa:
  Muestra la infraestructura productiva donde 
  se encuentra el activo en el momento de la 
  consulta, obtenida del registro con 
  fecha_fin = null en la entidad 
  historial_infraestructura_activo.

Vista 2 — Historial de Asociaciones:
  Muestra la secuencia cronológica completa de 
  todas las infraestructuras en las que ha 
  estado el activo, incluyendo las fechas de 
  inicio y fin de cada periodo.

La información expuesta por este RF es consumida 
por RF-49 (Asociación con Sensores IoT) y RF-61 
(Vinculación de Lecturas con Activos Biológicos) 
para resolver el contexto de ubicación del activo 
en cada momento.

La entidad historial_infraestructura_activo 
almacena los siguientes campos:
  activo_id
  infraestructura_id
  fecha_inicio
  fecha_fin (nullable; null = asociación activa)
  usuario_registro

Regla de integridad: solo puede existir un 
registro con fecha_fin = null por activo en 
un momento dado.

**Justificación:** Contextualización de Datos IoT y Analíticos:
Sin conocer la infraestructura actual del activo, 
RF-49 no puede validar la coherencia de ubicación 
al asociar sensores, y RF-61 no puede resolver 
automáticamente a qué activo corresponde una 
lectura de telemetría. RF-34 provee la consulta 
que habilita ambos procesos.

Trazabilidad Operativa y Sanitaria:
El historial de infraestructuras recorridas por 
el activo es parte de su historia productiva. 
El veterinario y el productor necesitan saber 
en qué galpón o potrero estuvo el animal durante 
un evento sanitario para correlacionar condiciones 
ambientales con su estado de salud.

Soporte a la Valoración NIC 41:
M06 requiere correlacionar la ubicación del activo 
con los datos de telemetría que sustentan su 
transformación biológica. RF-34 provee el contexto 
espacial necesario para esa correlación.

Separación Clara de Responsabilidades:
Al limitar RF-34 a lectura, se evita duplicidad 
con RF-33 (que crea la asociación) y RF-48 
(que la modifica), garantizando que cada RF 
tiene una responsabilidad única y verificable.

**Precondiciones:** 1. Activo Biológico Registrado (RF-33)
El activo_id consultado debe existir en el 
sistema. El registro del activo en RF-33 
incluye obligatoriamente la creación de su 
primera asociación con infraestructura.

2. Usuario Autenticado con Permisos de Lectura (RF-02, M01)
El usuario debe tener sesión activa y permisos 
de lectura sobre el activo biológico consultado, 
conforme al RBAC de M01. No se requieren 
permisos de escritura para esta operación.

3. Infraestructura Productiva Registrada (RF-20)
Debe existir al menos una infraestructura 
registrada en el sistema a la cual el activo 
está o estuvo asociado. Esta condición se 
cumple siempre que RF-33 haya operado 
correctamente.

**Restricciones:** 1. Solo Lectura — Sin Modificación
Este RF no permite crear, modificar ni 
desactivar asociaciones bajo ninguna 
circunstancia. Es una operación de lectura pura.

2. Sin Redirección a Operaciones de Escritura 
   desde Este RF
RF-34 puede informar al usuario que los cambios 
de infraestructura se gestionan en RF-48, pero 
no ejecuta ni inicia ese proceso directamente.

3. Visibilidad Limitada por Granja y Rol (RBAC)
El usuario solo puede consultar la asociación 
de activos pertenecientes a las granjas a las 
que tiene acceso según su perfil en M01.

4. Integridad del Historial Consultado
El sistema debe garantizar que el historial 
devuelto es coherente:
  Solo un registro con fecha_fin = null 
  por activo (asociación activa)
  fecha_fin > fecha_inicio en registros cerrados
  Sin solapamiento de periodos para el mismo activo

Si el historial presenta inconsistencias, el 
sistema las reporta como advertencia técnica 
sin bloquear la consulta.

5. Sin Transacción ACID
Al ser una operación de solo lectura, no aplica 
manejo transaccional ACID ni rollback. Se 
elimina este elemento del requerimiento original 
por ser innecesario para una consulta.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-20 – Gestión de infraestructura productiva
RF-33 – Registro de activos biológicos
RF-48 – Transferencia interna de activos biológicos
RF-22 – Asociación de sensores a infraestructura

**Actores:** Productor, Administrador del sistema, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_activo_biologico | integer | Identificador del activo biológico (obligatorio) |
| tipo_consulta | enum | Determina qué vista retorna el sistema: ACTIVA (solo la asociación vigente con fecha_fin = null) o HISTORIAL (todas las asociaciones ordenadas cronológicamente). Default: ACTIVA. |
| fecha_referencia | Date (opcional) | Fecha en la que se desea conocer la asociación vigente del activo. Útil para RF-61 al resolver vinculaciones históricas. Si se omite, retorna la asociación activa actual. |

**Proceso:**

Fase 1: Autenticación y Validación de Permisos

El sistema valida la sesión del usuario (RF-02) 
y verifica que tiene permisos de lectura sobre 
el activo_id consultado, conforme al RBAC de M01.

Resultado:
  Autorizado → continúa
  No autorizado → HTTP 403 Forbidden

Fase 2: Validación de Existencia del Activo

El sistema verifica que el activo_id existe 
en M02 (RF-33).

Resultado:
  Existe → continúa
  No existe → flujo alterno E1

Fase 3: Ejecución de la Consulta según Tipo

Caso A — tipo_consulta = ACTIVA 
(o fecha_referencia especificada):

  El sistema consulta historial_infraestructura_activo 
  filtrando por:
    activo_id = activo_id solicitado
    fecha_fin = null (si no hay fecha_referencia)
    O: fecha_inicio ≤ fecha_referencia Y 
       (fecha_fin > fecha_referencia O fecha_fin = null)
       (si hay fecha_referencia)

  Si no existe registro activo:
    → flujo alterno E2

  Si existe:
    El sistema obtiene los datos de la 
    infraestructura asociada desde RF-20:
      nombre, tipo, capacidad, ubicación, estado
    El sistema obtiene los sensores IoT instalados 
    en esa infraestructura desde RF-22 (opcional, 
    enriquecimiento)

Caso B — tipo_consulta = HISTORIAL:

  El sistema consulta historial_infraestructura_activo 
  filtrando por activo_id, ordenado por 
  fecha_inicio ASC.

  Para cada registro, obtiene los datos de 
  la infraestructura desde RF-20.

  Incluye tanto registros cerrados (fecha_fin 
  con valor) como el activo (fecha_fin = null).

Fase 4: Verificación de Integridad del Historial

El sistema verifica que el historial consultado 
sea coherente:
  Solo un registro con fecha_fin = null
  Sin solapamiento de periodos

Si se detecta inconsistencia:
  Se incluye un campo advertencia_integridad 
  en la respuesta
  Se registra en RF-63 para diagnóstico técnico
  La consulta no se bloquea

Fase 5: Registro en Bitácora de Auditoría (RF-63)

Se registra:
  tipo_operacion: CONSULTA_ASOCIACION_ACTIVA o 
    CONSULTA_HISTORIAL_ASOCIACIONES
  activo_id consultado
  id_usuario_responsable
  tipo_consulta y fecha_referencia (si aplica)
  Resultado: EXITOSO
  Timestamp

Fase 6: Retorno de la Respuesta

El sistema responde HTTP 200 OK con la 
información solicitada según tipo_consulta.

**Salida:**

Vista 1 — Asociación Activa (tipo_consulta = ACTIVA):
{
  "activo_id": 1047,
  "tipo_consulta": "ACTIVA",
  "asociacion_activa": {
    "infraestructura_id": 5,
    "nombre": "Galpón Norte",
    "tipo": "GALPON",
    "capacidad_maxima": 200,
    "ubicacion": "Sector A, Finca El Prado",
    "estado": "ACTIVO",
    "fecha_inicio_asociacion": "2024-03-15",
    "fecha_fin_asociacion": null,
    "usuario_registro": "admin_01"
  },
  "sensores_en_infraestructura": [
    {
      "sensor_id": 23,
      "tipo_variable": "TEMPERATURA_AMBIENTAL",
      "estado": "ACTIVO"
    },
    {
      "sensor_id": 24,
      "tipo_variable": "HUMEDAD_RELATIVA",
      "estado": "ACTIVO"
    }
  ],
  "advertencia_integridad": null
}
Vista 2 — Historial de Asociaciones (tipo_consulta = HISTORIAL):
{
  "activo_id": 1047,
  "tipo_consulta": "HISTORIAL",
  "total_registros": 3,
  "historial": [
    {
      "infraestructura_id": 3,
      "nombre": "Galpón Sur",
      "tipo": "GALPON",
      "fecha_inicio": "2023-01-10",
      "fecha_fin": "2023-08-20",
      "usuario_registro": "productor_01"
    },
    {
      "infraestructura_id": 4,
      "nombre": "Potrero B",
      "tipo": "POTRERO",
      "fecha_inicio": "2023-08-20",
      "fecha_fin": "2024-03-15",
      "usuario_registro": "productor_01"
    },
    {
      "infraestructura_id": 5,
      "nombre": "Galpón Norte",
      "tipo": "GALPON",
      "fecha_inicio": "2024-03-15",
      "fecha_fin": null,
      "usuario_registro": "admin_01"
    }
  ],
  "advertencia_integridad": null
}
Adicionalmente, el sistema genera:
  Registro en bitácora RF-63 con:
    tipo_operacion, activo_id, id_usuario,
    tipo_consulta, resultado, timestamp

**Postcondiciones:**

1. Sin Modificación de Datos
La operación de consulta no ha creado, 
modificado ni eliminado ningún registro en 
el sistema. El estado de la base de datos 
es idéntico antes y después de la consulta.

2. Información de Ubicación Disponible para Consumidores
RF-49 y RF-61 pueden consumir el resultado 
de esta consulta para sus procesos de 
validación y vinculación sin necesidad de 
acceder directamente a historial_infraestructura_activo.

3. Trazabilidad de la Consulta Registrada
RF-63 contiene el registro de la consulta 
realizada con el usuario, el activo consultado, 
el tipo de consulta y el timestamp.

4. Coherencia del Historial Verificada
El sistema ha verificado la integridad del 
historial y, si detectó inconsistencias, 
las ha reportado como advertencia sin 
bloquear la consulta.

**Criterios de aceptación:**

CA-1: Consulta de asociación activa exitosa
Dado un activo con asociación activa registrada,
cuando el usuario consulte con tipo_consulta = ACTIVA,
entonces el sistema debe retornar HTTP 200 con 
los datos de la infraestructura activa 
(infraestructura_id, nombre, tipo, fecha_inicio) 
y los sensores instalados en ella.

CA-2: Consulta de historial completo
Dado un activo con múltiples asociaciones históricas,
cuando el usuario consulte con tipo_consulta = HISTORIAL,
entonces el sistema debe retornar todos los registros 
ordenados cronológicamente por fecha_inicio ASC, 
incluyendo registros cerrados y el activo.

CA-3: Consulta por fecha de referencia
Dado un activo y una fecha_referencia en el pasado,
cuando el usuario consulte con esa fecha,
entonces el sistema debe retornar la infraestructura 
que estaba activa en esa fecha específica, no la 
asociación actual.

CA-4: Rechazo ante activo inexistente
Dado un activo_id que no existe en el sistema,
cuando se realice la consulta,
entonces el sistema debe responder HTTP 404 
con el mensaje correspondiente.

CA-5: Manejo de activo sin asociación activa
Dado un activo sin registro de fecha_fin = null 
en historial_infraestructura_activo,
cuando se consulte su asociación activa,
entonces el sistema debe responder HTTP 404 
con mensaje de inconsistencia y generar alerta 
técnica al administrador.

CA-6: Control de acceso por granja y rol
Dado un usuario sin permisos sobre la granja 
a la que pertenece el activo,
cuando intente consultarlo,
entonces el sistema debe responder HTTP 403 
sin exponer ningún dato del activo.

CA-7: Rechazo de operaciones de escritura
Dado cualquier intento de modificar la asociación 
directamente a través de este endpoint,
cuando el sistema lo detecte,
entonces debe responder HTTP 405 e indicar 
que los cambios deben hacerse mediante RF-48.

CA-8: Único registro activo por activo
Dado el historial de cualquier activo biológico,
cuando el sistema lo consulte,
entonces no debe existir más de un registro 
con fecha_fin = null para el mismo activo.

CA-9: Registro en bitácora de toda consulta
Dado cualquier consulta exitosa o fallida a RF-34,
cuando sea procesada,
entonces RF-63 debe contener el registro con 
tipo_operacion, activo_id, id_usuario, 
tipo_consulta, resultado y timestamp.

CA-10: Tiempo de respuesta
Dado cualquier consulta válida a RF-34,
cuando sea procesada,
entonces el sistema debe responder en ≤ 2 segundos 
bajo condiciones normales de operación.

CA-11: Sin modificación de datos
Dado cualquier consulta realizada por cualquier 
usuario o sistema consumidor,
cuando sea procesada,
entonces no debe haberse creado, modificado ni 
eliminado ningún registro en la base de datos.

**Requerimientos no funcionales:**

Seguridad

Validación de permisos en backend

Registro en auditoría obligatorio

Rendimiento

Tiempo de respuesta ≤ 2 segundos

Consistencia

La operación debe ejecutarse en una transacción ACID

Integridad

No deben existir activos sin infraestructura asociada

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-35 — Gestión Individual de Activos Biológicos 

**Código Identificación:** RF-35 -- Versión -- 1.0

**Fuente:** Productor / Veterinario / Ingeniero de Campo

**Descripción:** El sistema debe permitir la gestión integral de activos biológicos de tipo individual, entendidos como aquellos que requieren seguimiento unitario y trazabilidad específica durante todo su ciclo de vida productivo.

Este tipo de gestión aplica a especies o contextos donde cada individuo es relevante desde el punto de vista productivo, sanitario, reproductivo o contable.

El sistema deberá soportar:

Identificación única del individuo dentro del sistema.
Asociación con especie productiva configurada previamente.
Registro y actualización de atributos específicos del individuo.
Seguimiento detallado de su evolución biológica.
Vinculación con eventos (crecimiento, sanitarios, reproductivos, productivos).
Control del estado del activo en cada momento del ciclo de vida.

La gestión individual permitirá trazabilidad completa desde el registro inicial hasta su baja o cierre de ciclo productivo.

**Justificación:** La gestión individual es fundamental en activos biológicos donde el control unitario impacta directamente:

La toma de decisiones productivas.
El seguimiento sanitario.
La trazabilidad reproductiva.
La valoración financiera bajo normativa contable.

Permite una visión precisa del comportamiento y evolución de cada activo, garantizando consistencia en los datos utilizados por otros módulos del sistema.

**Precondiciones:** El usuario debe estar autenticado (RF-02).

Debe existir al menos una especie productiva configurada (RF-15).

Debe existir infraestructura productiva registrada (RF-20).

El activo biológico debe haber sido registrado previamente (RF-33).

El usuario debe tener permisos para gestionar activos (RF-04).

**Restricciones:** Cada activo individual debe tener un identificador único irrepetible dentro del sistema.

No se permite convertir un activo individual en tipo poblacion.

La especie del activo no puede modificarse después del registro.

No se permite eliminar activos, solo marcar su estado (Activo, Inactivo, Cerrado, Baja).

Todos los cambios deben quedar registrados en auditoría (M01).

Los datos deben cumplir validaciones por tipo de especie definidas en M09.

Un activo individual debe estar asociado a una única infraestructura a la vez.

El estado del activo no puede ser modificado directamente en este requerimiento.

Todo cambio de estado debe realizarse exclusivamente a través de RF-44.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-33 — Registro de Activos Biológicos
RF-15 — Catálogo de especies productivas
RF-20 — Gestión de infraestructura productiva
RF-04 — Gestión de permisos
M01 — Usuarios, roles y acceso
M09 — Configuración y personalización

**Actores:** Productor, Veterinario, Ingeniero de Campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_activo_biologico | integer | Identificador único del activo biológico |
| identificador_individual | varchar(50) | Identificación física (chapeta, código, etc.) |
| especie_id | integer | Especie productiva |
| raza | varchar(50) | Raza del individuo (opcional según especie) |
| sexo | varchar(10) | Sexo del individuo |
| fecha_nacimiento | date | Fecha de nacimiento |
| peso_inicial | decimal | Peso inicial del activo |
| estado_activo | varchar(20) | Estado actual del activo (solo lectura, no editable en este requerimiento) |
| infraestructura_id | integer | Ubicación actual |

**Proceso:**

El usuario accede al módulo de gestión de activos biológicos.

El sistema permite seleccionar un activo registrado.

El sistema valida:

Existencia del activo.
Tipo de activo (debe ser individual).
Permisos del usuario.

El sistema muestra la información actual del activo.

El usuario puede realizar operaciones como:

Actualizar atributos del individuo.
Registrar eventos asociados (crecimiento, sanitarios, etc.).
Solicitar cambio de estado del activo mediante el módulo de gestión de estados (RF-44).
Transferir ubicación.

Antes de solicitar el cambio de estado, el sistema valida:

- Que el activo no tenga eventos pendientes sin cerrar
- Que no existan inconsistencias en el historial del activo

El sistema valida:

Integridad de datos.
Reglas por especie.
Consistencia del estado.

El sistema guarda los cambios.

El sistema registra la operación en auditoría.

La operación de actualización debe ejecutarse dentro de una transacción que garantice consistencia entre los datos del activo, eventos asociados e historial.

**Salida:**

Información actualizada del activo biológico individual.

Confirmación de la operación.

Registro en el historial del activo.

**Postcondiciones:**

El activo mantiene su trazabilidad completa.

Los cambios quedan almacenados en la base de datos.

La información queda disponible para otros módulos:

M04 (Predicción)
M05 (Costos)
M06 (Valoración NIC 41)
M08 (Reportes)

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite gestionar activos individuales.

El sistema valida que el activo sea de tipo individual.

El sistema garantiza identificadores únicos.

El sistema permite actualizar información del activo.

El sistema permite registrar eventos asociados.

El sistema mantiene historial completo del activo.

El sistema valida reglas por especie.

El sistema impide cambios no permitidos (tipo, especie).

El sistema registra todas las acciones en auditoría.

El sistema no permite modificar directamente el estado del activo

El sistema redirige la gestión de estado al RF-44

El sistema valida condiciones previas antes de solicitar cambio de estado

**Requerimientos no funcionales:**

Seguridad

Validación de permisos en backend.

Control de acceso por rol.

Rendimiento

Operaciones de consulta y actualización < 2 segundos.

Integridad

Consistencia en datos del activo durante todo su ciclo de vida.

Trazabilidad

Registro completo de cambios y eventos asociados.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-36 — Gestión Poblacional de Activos Biológicos 

**Código Identificación:** RF-36 -- Versión -- 1.1

**Fuente:** Productor, Veterinario, Ingeniero de Campo

**Descripción:** El sistema debe permitir la gestión integral de activos biológicos de tipo poblacional, entendidos como agrupaciones de individuos homogéneos que son administrados y monitoreados como una unidad productiva.

Este tipo de gestión aplica a especies o contextos donde el seguimiento individual no es viable ni necesario, y la operación se realiza sobre métricas agregadas del conjunto.

El sistema deberá soportar:

Registro de un activo poblacional con atributos colectivos.
Control de cantidad inicial de individuos.
Asociación del activo poblacional a una infraestructura productiva específica.
Seguimiento del ciclo productivo del activo poblacional.
Registro de eventos agregados (crecimiento, sanitarios, productivos).
Actualización dinámica de la cantidad de individuos (altas/bajas).
Cálculo de métricas agregadas como biomasa total, peso promedio y densidad.

El activo poblacional será tratado como una entidad única, pero con comportamiento dinámico basado en la evolución de sus individuos.

**Justificación:** La gestión poblacional es necesaria para escenarios productivos donde:

El volumen de individuos es alto.

El control individual no es eficiente.

Las decisiones se toman sobre indicadores grupales.

Permite optimizar el registro de información, reducir la complejidad operativa y mantener consistencia en la modelación del dominio productivo.

**Precondiciones:** El usuario debe estar autenticado (RF-02).

Debe existir al menos una especie productiva configurada (RF-15).

Debe existir infraestructura productiva registrada (RF-20).

El activo biológico debe haber sido registrado como tipo poblacional (RF-33).

El usuario debe tener permisos para gestionar activos (RF-04).

**Restricciones:** Un activo poblacional no puede convertirse en activo individual.

Todos los individuos del activo poblacional deben pertenecer a la misma especie.

El activo poblacional debe mantener coherencia en sus atributos (edad, fase, condiciones productivas).

La cantidad de individuos debe ser un número entero positivo.

No se permite eliminar el activo poblacional, solo cambiar su estado (Activo, Cerrado, Baja).

Los eventos registrados afectan al activo poblacional completo o a subconjuntos cuantificados.

Los datos deben cumplir validaciones definidas en M09.

Todas las modificaciones deben registrarse en auditoría.

Las validaciones por especie deben definirse en M09 e incluyen:

- Rangos permitidos de peso promedio
- Densidad máxima por infraestructura
- Tipos de eventos permitidos por especie

El estado del activo poblacional no puede ser modificado directamente en este requerimiento.

Todo cambio de estado debe realizarse exclusivamente a través del módulo de gestión de estados (RF-44).

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-33 — Registro de Activos Biológicos
RF-15 — Catálogo de especies productivas
RF-20 — Gestión de infraestructura productiva
RF-04 — Gestión de permisos
M01 — Usuarios, roles y acceso
M09 — Configuración y personalización

**Actores:** Productor, Veterinario, Ingeniero de Campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_id | Integer | Identificador del activo poblacional. Obligatorio. Debe existir en el sistema con tipo POBLACIONAL (RF-33). |
| infraestructura_id | Integer | Infraestructura a la que se transfiere el activo poblacional. Solo aplica en la operación de transferencia. Debe estar activa y pertenecer a la misma finca. |
| especie_id | Integer | Dato persistido en RF-33. El sistema lo carga automáticamente. No editable en este módulo. |
| fecha_inicio | Date | Dato persistido en RF-33. El sistema lo carga automáticamente. No editable en este módulo. |
| cantidad_inicial | Integer | Dato persistido en RF-33. Valor de referencia histórica. No editable nunca. |
| peso_promedio_inicial | Decimal | Dato persistido en RF-33. Valor de referencia histórica. No editable nunca. |
| cantidad_actual | Integer | Calculado automáticamente por el sistema a partir de la cantidad_inicial más ingresos registrados, menos bajas registradas. No editable directamente. Se modifica únicamente mediante eventos de tipo BAJA o mediante registros de ingresos asociados a eventos. |
| peso_promedio | Decimal | Calculado automáticamente a partir de los eventos de crecimiento registrados. No editable directamente. |
| biomasa_total | Decimal | Calculado por el sistema: cantidad_actual × peso_promedio. No es entrada del usuario ni editable. |
| densidad | Decimal | Calculado por el sistema: cantidad_actual / superficie_infraestructura. La superficie se obtiene de RF-20. No es entrada del usuario ni editable. |
| estado_activo | Varchar(20) | Estado actual del activo poblacional. Solo lectura en este módulo. Solo modificable mediante RF-44. |

**Proceso:**

El usuario accede al módulo de gestión de activos biológicos.

El sistema permite seleccionar un activo tipo poblacional.

El sistema valida:

Existencia del activo poblacional.
Tipo de activo (debe ser poblacional).
Permisos del usuario.

El sistema muestra la ficha del activo poblacional con:
  Datos estructurales de solo lectura (cargados 
  desde RF-33): especie, fecha de inicio.
  Valores iniciales de referencia histórica 
  (siempre visibles, no editables): 
  cantidad_inicial y peso_promedio_inicial.
  Métricas operativas calculadas en tiempo real: 
  cantidad_actual, peso_promedio, biomasa_total 
  y densidad.
Estado actual del activo poblacional (solo lectura en este 
  módulo; modificable únicamente mediante RF-44).
  Historial de eventos registrados.

El usuario puede realizar las siguientes 
operaciones. Ninguna de ellas permite edición 
directa de cantidad_actual, peso_promedio, 
biomasa_total ni densidad:

  Registrar eventos agregados:
    Los eventos son el único mecanismo válido 
    para modificar las métricas del activo poblacional. La 
    edición directa de estos campos está 
    prohibida en este módulo.
    Ver estructura de eventos más abajo.

  Solicitar cambio de estado del activo poblacional:
    Se invoca RF-44 pasando obligatoriamente 
    modulo_origen = 'RF-36' y motivo_cambio.
    RF-36 no modifica el estado directamente.

  Transferir el activo poblacional a otra infraestructura:
    Se invoca RF-48 con la infraestructura 
    destino seleccionada.

Registro de eventos:

Estructura de eventos agregados:

Cada evento debe registrar:

- tipo_evento (CRECIMIENTO, SANITARIO, PRODUCTIVO, BAJA)
- cantidad_afectada (opcional según tipo)
- fecha_evento
- datos_asociados (ej. peso, producción, tratamiento)
- usuario_registro

Eventos de crecimiento:
Actualización de peso promedio.
Recalculación de biomasa total.

Reglas de cálculo:

Biomasa total:
biomasa_total = cantidad_actual * peso_promedio

Densidad:
densidad = cantidad_actual / superficie

La densidad es un valor calculado automáticamente por el sistema y no puede ser modificada manualmente por el usuario.

La superficie se obtiene desde la infraestructura productiva definida en RF-20.

Validación de densidad:
densidad no debe superar la densidad_maxima_por_especie definida en M09.

Peso promedio:
Se actualiza mediante eventos de crecimiento registrados
 
Eventos sanitarios:
  
  Registro de tratamientos aplicados al activo poblacional.
  Registro de afectación parcial 
  (número de individuos).

  Impacto en métricas:
  Los eventos sanitarios son registros 
  informativos y de trazabilidad clínica. 
  No modifican directamente la biomasa_total 
  ni el peso_promedio del activo poblacional.

  La excepción es cuando el evento sanitario 
  incluye una cantidad_afectada que representa 
  muertes o bajas por enfermedad. En ese caso, 
  el sistema no registra la baja desde el evento 
  sanitario directamente; el veterinario debe 
  registrar adicionalmente un evento de tipo BAJA 
  para que el sistema actualice cantidad_actual y 
  recalcule las métricas derivadas.

  Esta separación garantiza que la trazabilidad 
  clínica (evento sanitario) y la trazabilidad 
  productiva (baja) queden en registros distintos 
  e independientes.

Eventos productivos:

Producción generada (ej: huevos, leche).
Registro de rendimiento.

Eventos de bajas:

Reglas de actualización de cantidad:

- cantidad_actual no puede ser mayor a cantidad_inicial + ingresos registrados
- cantidad_actual no puede ser menor a 0
- Toda modificación de cantidad debe estar asociada a un evento registrado

Reducción de cantidad_actual.
Recalculo de métricas.

El sistema valida:

Que la infraestructura asociada esté en estado ACTIVO.

Que la infraestructura pertenezca a la misma finca del activo poblacional.

Que la cantidad no sea negativa.
Coherencia entre métricas (biomasa, peso promedio).
Reglas por especie.

El sistema actualiza:

cantidad_actual
biomasa_total
indicadores derivados

El sistema guarda los cambios.

El sistema registra la operación en auditoría.

**Salida:**

Información actualizada del activo poblacional.

Indicadores agregados recalculados.

Confirmación de la operación.

Registro en historial del activo poblacional.

**Postcondiciones:**

El activo poblacional mantiene consistencia en sus métricas agregadas.

La información queda disponible para:

M04 (Predicción)

M05 (Costos)

M06 (Valoración NIC 41)

M08 (Reportes)

El historial del activo poblacional refleja todos los eventos.

El requerimiento se limita al cálculo operativo de métricas básicas del activo poblacional.

Los análisis avanzados y proyecciones son responsabilidad de los módulos M04, M05 y M08.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite gestionar activos tipo poblacional.

El sistema valida correctamente el tipo de activo.

El sistema permite actualizar cantidad de individuos.

El sistema recalcula biomasa y métricas automáticamente.

El sistema registra eventos agregados correctamente.

El sistema valida coherencia de datos.

El sistema impide cantidades negativas.

El sistema mantiene historial completo del activo poblacional.

El sistema registra todas las operaciones en auditoría.

El sistema calcula correctamente la biomasa total (cantidad_actual * peso_promedio)

El sistema calcula correctamente la densidad del activo poblacional

El sistema actualiza métricas automáticamente tras eventos

El sistema valida coherencia entre métricas calculadas

**Requerimientos no funcionales:**

Seguridad

Control de acceso por roles.

Validación de permisos en backend.

Rendimiento

Actualización de métricas en menos de 2 segundos.

Integridad

Consistencia entre cantidad, peso y biomasa.

Escalabilidad

Soporte para grandes volúmenes de individuos en activos poblacionales.

Trazabilidad

Registro completo de eventos y cambios.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-37 — Gestión de Fases del Ciclo Productivo del Activo Biológico

**Código Identificación:** RF-37 -- Versión -- 1.1

**Fuente:** Productor / Veterinario / Administrador

**Descripción:** El sistema debe permitir registrar, gestionar y mantener el historial de las fases del ciclo productivo de los activos biológicos, independientemente de su tipo (individual o poblacional), a lo largo de su ciclo de vida.

Las fases productivas corresponden a etapas definidas previamente en el sistema mediante RF-16, configuradas por especie y propósito productivo.

Definición operativa de fase:

Una fase productiva es una unidad temporal del ciclo de vida del activo biológico, representada como un registro persistente que contiene:

- activo_biologico_id
- fase_id (definida en RF-16)
- fecha_inicio
- fecha_fin (nullable)
- estado_fase (ACTIVA / FINALIZADA)
- usuario_responsable

Las fases configuradas en RF-16 actúan únicamente como plantillas o catálogo, mientras que RF-37 gestiona las instancias reales de dichas fases en cada activo.

Cada activo biológico debe cumplir estrictamente:

Tener exactamente una fase activa en todo momento.
Mantener un historial completo de fases.
Registrar fechas de inicio y fin de cada fase.

El sistema deberá:

Gestionar el cambio manual de fases.
Garantizar consistencia temporal.
Permitir trazabilidad completa del ciclo productivo.
Proveer información estructurada para:
Indicadores zootécnicos (RF-51)
Valoración financiera (M06)

El cambio de fase es exclusivamente manual, nunca automático.

**Justificación:** Las fases del ciclo productivo representan la transformación biológica del activo, base fundamental para:

Seguimiento técnico del activo.

Análisis productivo.

Cálculo de indicadores.

Cumplimiento de la normativa contable (NIC 41 en M06).

Sin este control, no es posible determinar el estado productivo ni su impacto económico.

**Precondiciones:** El activo biológico debe existir (RF-33).

El activo debe estar en estado ACTIVO.

Debe existir al menos una fase configurada en RF-16.

El usuario debe estar autenticado (RF-02).

El usuario debe tener permisos de actualización (RF-04).

El activo debe tener una fase actual definida.

**Restricciones:** Solo puede existir una fase activa por activo.

No se permite cambio de fase en activos:

CERRADOS
DADOS DE BAJA

La fase destino debe ser distinta a la actual.

La fecha no puede:

Ser futura
Ser anterior al inicio de la fase actual

Las fases deben pertenecer a la especie del activo.

Las transiciones fuera de secuencia requieren confirmación explícita.

El historial no puede modificarse ni eliminarse (inmutable).

No se permite la existencia de fases con rangos de fechas superpuestos para un mismo activo.

La fecha_inicio de la nueva fase debe ser mayor o igual a la fecha_fin de la fase anterior, garantizando continuidad temporal sin solapamientos.


**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación
RF-04 — Gestión de permisos
RF-16 — Parámetros por especie (fases)
RF-33 — Registro de activos
RF-35 — Activos individuales
RF-36 — Activos tipo poblacional
M01 — Seguridad / Auditoría
M09 — Configuración

**Actores:** Productor, Veterinario, Administrador

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador del activo |
| tipo_activo | varchar(10) | Tipo de activo. Valores: INDIVIDUAL o POBLACIONAL. |
| fase_destino_id | integer | FK a la fase del ciclo productivo destino (RF-16). Debe corresponder a la especie y propósito del activo. |
| fecha_cambio_fase | date | Fecha en la que el activo pasa a la nueva fase. debe ser mayor o igual a la fecha_inicio de la fase actual y menor o igual a la fecha actual del sistema. |
| motivo_cambio | text | Justificación del cambio de fase. Texto libre, máx. 300 caracteres. |
| responsable_id | integer | FK al usuario que registra el cambio de fase. Debe ser un usuario activo. |
| confirmacion_no_estandar | boolean | true si el usuario confirma explícitamente una transición fuera de la secuencia estándar de RF-16. |

**Proceso:**

El usuario accede al módulo de gestión de activos biológicos y selecciona un activo específico.

El sistema muestra la fase productiva actual del activo y las fases disponibles según la especie y configuración definida.

El usuario selecciona la nueva fase productiva e ingresa la fecha de cambio junto con el motivo correspondiente.

El sistema valida la existencia del activo, su estado (activo), la validez de la fase destino y la coherencia de la fecha ingresada.

El sistema verifica que la nueva fase sea diferente a la fase actual y que no genere inconsistencias en la línea temporal del activo.

El sistema valida si la transición de fase sigue la secuencia estándar definida; en caso contrario, solicita confirmación al usuario.

Una vez validados los datos, el sistema:

- Actualiza la fase actual estableciendo fecha_fin y cambiando su estado a FINALIZADA.
- Crea un nuevo registro de fase con estado ACTIVA y fecha_inicio correspondiente.

Modelo de transición de fases:

Las fases deben seguir una secuencia lógica definida en RF-16 mediante un orden o flujo configurado.

Reglas de transición:

- La transición estándar corresponde al paso a la siguiente fase definida en la secuencia.
- Si la fase destino no corresponde a la siguiente en la secuencia, se considera transición no estándar.
- Las transiciones no estándar requieren confirmación explícita del usuario (confirmacion_no_estandar = true).
- No se permite retroceder a fases anteriores sin confirmación explícita.

El sistema actualiza la referencia a la fase productiva activa del activo biológico.

El sistema registra la operación en el historial y en el módulo de auditoría.

El sistema confirma al usuario la ejecución del cambio de fase.

La operación de cambio de fase debe ejecutarse como una transacción atómica que garantice:

- Cierre de la fase actual (actualización de fecha_fin).
- Creación de la nueva fase como activa.
- Actualización del estado de fase del activo.

El sistema debe aplicar control de concurrencia mediante bloqueo optimista o pesimista para evitar modificaciones simultáneas del historial de fases del mismo activo.

En caso de error, se debe realizar rollback completo de la operación.

**Salida:**

Actualización de la fase productiva actual del activo biológico.

Registro del cambio en el historial de fases del activo, incluyendo fase anterior, nueva fase, fechas y responsable.

Confirmación de la operación realizada al usuario.

Disponibilidad de la información actualizada para módulos dependientes.

**Postcondiciones:**

El activo biológico queda asociado a una única fase productiva activa.

El historial de fases del activo queda actualizado con la transición registrada.

La fase anterior queda cerrada con fecha de finalización.

La nueva fase queda registrada como activa sin fecha de finalización.

La información queda disponible para procesos de análisis, trazabilidad y valoración financiera.

**Criterios de aceptación:**

El sistema permite registrar cambios de fase para activos biológicos activos.

El sistema valida que la nueva fase sea diferente a la fase actual.

El sistema valida que la fecha de cambio no sea futura ni inconsistente con la fase actual.

El sistema registra correctamente la finalización de la fase anterior.

El sistema registra correctamente la nueva fase como activa.

El sistema mantiene un único registro de fase activa por activo biológico.

El sistema solicita confirmación cuando la transición no sigue la secuencia definida.

El sistema registra el cambio en el historial del activo.

El sistema registra la operación en el módulo de auditoría.

El sistema impide cambios de fase en activos con estado cerrado o dado de baja.

El sistema confirma al usuario la ejecución del cambio de fase.

El sistema no permite solapamiento de fases.

El sistema ejecuta el cambio de fase de forma transaccional.

El sistema valida correctamente transiciones estándar y no estándar.

El sistema solicita confirmación en transiciones fuera de secuencia.

El sistema mantiene integridad temporal del historial de fases.

**Requerimientos no funcionales:**

Integridad

UNIQUE: una fase activa por activo

Fiabilidad

Transacción atómica

Seguridad

RBAC en backend

Trazabilidad

Historial inmutable

Concurrencia

Control de versiones o bloqueo

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-38 — Cierre del Ciclo Productivo del Activo Biológico

**Código Identificación:** RF-38 -- Versión -- 1.0

**Fuente:** Productor / Veterinario / Administrador del sistema

**Descripción:** El sistema debe permitir registrar el cierre del ciclo productivo de un activo biológico, ya sea de tipo individual o poblacional, cuando este ha finalizado su propósito productivo dentro del sistema.

El cierre del ciclo implica que el activo deja de generar eventos productivos, biológicos o económicos dentro del sistema, y queda disponible para pasar a un estado final (BAJA) que puede corresponder a venta, sacrificio, finalización del activo poblacional, muerte u otro motivo definido por el usuario (RF-44).

Definición operativa de fase:

Una fase productiva es una unidad temporal del ciclo de vida del activo biológico, representada como un registro persistente que contiene:

- activo_biologico_id
- fase_id (definida en RF-16)
- fecha_inicio
- fecha_fin (nullable)
- estado_fase (ACTIVA / FINALIZADA)
- usuario_responsable

El requerimiento se centra en la gestión estructural del activo, garantizando que las fases y la información básica estén correctamente registradas al momento del cierre.

El cierre del ciclo productivo constituye un evento clave para la valoración financiera (M06), ya que marca el punto final de la transformación biológica del activo.

**Justificación:** El cierre del ciclo productivo de un activo biológico es necesario para reflejar de forma precisa el estado final del activo dentro del sistema productivo. Este proceso permite detener la generación de nuevos eventos asociados al activo, garantizar la integridad de su historial y establecer un punto final claro para su seguimiento operativo.

Además, el registro formal del cierre permite que la información del activo sea utilizada correctamente en procesos de análisis, control productivo y valoración financiera, asegurando la trazabilidad completa de su ciclo de vida.


**Precondiciones:** El activo biológico debe existir en el sistema.

El activo debe encontrarse en estado ACTIVO.

El activo debe tener al menos una fase productiva registrada.

El usuario debe tener sesión activa y permisos para gestionar activos biológicos.

**Restricciones:** No se permite cerrar el ciclo productivo de un activo que ya se encuentre en estado CERRADO o BAJA.

El cierre del ciclo debe registrar obligatoriamente un motivo de finalización.

La fecha de cierre no puede ser futura.

La fecha de cierre no puede ser anterior a la última actualización relevante del activo.

No se permite registrar eventos adicionales sobre un activo una vez cerrado su ciclo.

El sistema debe garantizar la integridad del historial del activo posterior al cierre.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-16 --- Configuración de Etapas Productivas y Patologías por Especie
RF-33 — Registro de Activos Biológicos
RF-37 — Gestión de Fases del Ciclo Productivo
RF-44 — Gestión del Estado del Activo Biológico

**Actores:** Productor, Veterinario, Adminsitrador del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador único del activo biológico (individual o poblacional). |
| tipo_activo | varchar | Tipo de activo: INDIVIDUAL o POBLACIONAL. |
| fecha_cierre | date | Fecha en la que se realiza el cierre del ciclo productivo. |
| motivo_cierre | varchar | Motivo del cierre (venta, sacrificio, muerte, finalización de activo poblacional, otro). |
| descripcion_cierre | text | Observaciones adicionales del cierre. |
| responsable_id | integer | Usuario que realiza el cierre del ciclo productivo. |

**Proceso:**

El usuario accede al módulo de gestión de activos biológicos y selecciona el activo a cerrar.

El sistema muestra la información actual del activo, incluyendo su estado y fase productiva.

El usuario selecciona la opción de cierre de ciclo productivo e ingresa los datos requeridos.

El sistema valida la existencia del activo y que se encuentre en estado activo.

El sistema valida la coherencia de la fecha de cierre y el motivo ingresado.

El sistema verifica que no existan inconsistencias en el historial del activo.

El sistema actualiza el estado del activo a CERRADO.

El sistema registra el evento de cierre en el historial del activo biológico.

El sistema actualiza la fase productiva activa, estableciendo su fecha de finalización.

El sistema registra la operación en el módulo de auditoría.

El sistema confirma la ejecución del cierre al usuario.

**Flujo alterno:**

Activo no encontrado:

El sistema no localiza el activo_biologico_id solicitado en los registros maestros.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error de búsqueda: El activo biológico con ID [ID_SOLICITADO] no existe en el sistema. Verifique el identificador."

Estado inválido para cierre:

El usuario intenta cerrar un activo que ya tiene estado CERRADO o BAJA.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Operación redundante: El activo biológico ya se encuentra en estado [ESTADO_ACTUAL]. No es posible realizar un nuevo cierre de ciclo."

Inconsistencia en la fecha de cierre:

El usuario ingresa una fecha futura o una fecha que es anterior al último evento sanitario o de pesaje registrado para ese activo.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error cronológico: La fecha de cierre no puede ser futura ni anterior al último registro de actividad del activo ([FECHA_ULTIMO_EVENTO])."

Ausencia de motivo obligatorio:

El campo motivo_cierre se envía vacío o nulo.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Información incompleta: Debe seleccionar obligatoriamente un motivo de cierre (Venta, Sacrificio, Muerte, etc.) para proceder."

Inexistencia de fase activa:

El sistema detecta que el activo no tiene ninguna fase con estado_fase: ACTIVA, lo que impide realizar el cierre técnico de la etapa actual.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Inconsistencia de fases: El activo no presenta una fase productiva activa. Contacte al administrador para verificar la integridad del ciclo de vida."

Acceso no autorizado:

Un usuario con rol 'Operario' o similar intenta ejecutar el cierre administrativo.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Privilegios insuficientes: Solo el Productor, Veterinario o Administrador pueden formalizar el cierre del ciclo productivo."

Fallo en la persistencia atómica (Error de Sistema):

Ocurre un error al intentar actualizar simultáneamente el estado del activo y la fecha de fin de la fase.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Fallo crítico: No se pudo completar el cierre del ciclo debido a un error de base de datos. Se ha realizado un rollback para mantener la integridad de la información."

**Salida:**

Actualización del estado del activo biológico a CERRADO.

Registro del evento de cierre en el historial del activo.

Actualización de la fase productiva final del activo.

Confirmación de la operación realizada al usuario.

Disponibilidad de la información para módulos financieros y analíticos.

**Postcondiciones:**

El activo biológico queda en estado CERRADO.

No se permite registrar nuevos eventos sobre el activo.

El historial del activo queda completo e inmutable.

La fase productiva activa queda finalizada.

El activo queda disponible para procesos de valoración financiera y análisis histórico.

**Criterios de aceptación:**

El sistema permite cerrar el ciclo productivo de un activo biológico activo.

El sistema valida que el activo exista y esté en estado activo antes del cierre.

El sistema valida que la fecha de cierre sea válida.

El sistema exige el registro de un motivo de cierre.

El sistema actualiza correctamente el estado del activo a CERRADO.

El sistema registra el evento de cierre en el historial del activo.

El sistema finaliza correctamente la fase productiva activa.

El sistema impide el registro de nuevos eventos sobre activos cerrados.

El sistema registra la operación en el módulo de auditoría.

El sistema confirma al usuario la ejecución del cierre.

**Requerimientos no funcionales:**

Integridad: El historial del activo no debe permitir modificaciones posteriores al cierre.

Seguridad: Solo usuarios autorizados pueden ejecutar el cierre del ciclo productivo.

Fiabilidad: La operación debe ejecutarse de forma consistente sin pérdida de información.

Trazabilidad: El cierre debe quedar registrado con todos los datos asociados (fecha, motivo, usuario).

Disponibilidad: La operación debe estar disponible durante la operación normal del sistema.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-39 — Registro de Eventos Biológicos del Activo

**Código Identificación:** RF-39 -- Versión -- 1.1

**Fuente:** Productor / Veterinario / Ingeniero de campo / Administrador

**Descripción:** El sistema debe permitir registrar eventos biológicos asociados a los activos biológicos (individuales o poblacionales), los cuales representan cualquier cambio relevante en su estado físico, sanitario, reproductivo o productivo durante su ciclo de vida.

Los eventos biológicos constituyen la base de la trazabilidad del activo y permiten registrar su transformación biológica en el tiempo. Cada evento debe estar asociado a un activo específico, tener una fecha de ocurrencia y un tipo de evento definido.

El sistema debe permitir clasificar los eventos en diferentes categorías (crecimiento, sanitario, reproductivo, productivo), las cuales serán especializadas en requerimientos posteriores.

Cada evento registrado debe quedar almacenado de forma permanente en el historial del activo biológico, sin posibilidad de eliminación, garantizando trazabilidad completa.

El registro de eventos biológicos alimenta directamente a los módulos analíticos (M04), financieros (M06) y de reportes (M08).

**Justificación:** Los eventos biológicos son la evidencia operativa de la transformación de los activos, lo que permite realizar seguimiento técnico, análisis productivo y valoración económica conforme a la normativa.

Sin el registro estructurado de eventos, no es posible construir un historial confiable ni alimentar los modelos analíticos y financieros del sistema.

**Precondiciones:** El activo biológico debe existir en el sistema.

El activo debe encontrarse en un estado operativo que permita el registro de eventos. Los estados operativos válidos son:
  ACTIVO
  EN_TRATAMIENTO
  AISLADO

No se permite registrar eventos sobre activos en estado CERRADO o BAJA.

Justificación: Los estados EN_TRATAMIENTO y AISLADO representan condiciones sanitarias activas donde el activo sigue siendo objeto de seguimiento clínico. 
Bloquear el registro de eventos en estos estados impediría documentar la evolución del tratamiento, la administración de medicamentos y la recuperación del activo, lo cual viola el principio de 
trazabilidad completa del ciclo de vida.

El activo debe estar asociado a una infraestructura productiva.

El usuario debe tener sesión activa y permisos para registrar eventos.

**Restricciones:** No se permite registrar eventos sobre activos en estado CERRADO o BAJA. Los estados EN_TRATAMIENTO y AISLADO sí permiten el registro de eventos, dado que corresponden a condiciones operativas activas que requieren seguimiento continuo.

La fecha del evento no puede ser futura.

La fecha del evento no puede ser anterior a la fecha de registro del activo.

Cada evento debe estar asociado a un tipo de evento válido definido en el sistema.

No se permite la eliminación de eventos registrados; solo se permite su consulta.

Los eventos deben mantener coherencia temporal dentro del historial del activo.

El sistema debe validar que los datos ingresados correspondan al tipo de evento seleccionado.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-33 — Registro de Activos Biológicos
RF-34 — Asociación del Activo a Infraestructura
RF-44 — Gestión del Estado del Activo Biológico

**Actores:** Veterinario, Productor, Ingeniero de Campo, Administrador del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador único del activo biológico. |
| tipo_activo | varchar | Tipo de activo: INDIVIDUAL o POBLACIONAL. |
| tipo_evento | varchar | Tipo de evento biológico (crecimiento, sanitario, reproductivo, productivo). |
| fecha_evento | date | Fecha en la que ocurre el evento. |
| descripcion_evento | text | Descripción general del evento registrado. |
| datos_evento | json | Estructura con datos específicos según el tipo de evento. |
| responsable_id | integer | Usuario que registra el evento. |
| El campo datos_evento es un JSON cuya estructura 
varía según el tipo_evento. La validación del 
sistema se realiza contra el esquema 
correspondiente al tipo seleccionado.

Para activos tipo INDIVIDUAL, los campos son 
unitarios. Para activos tipo POBLACIONAL, los campos 
marcados con (*POBLACIONAL) son obligatorios cuando 
el evento afecta a un subconjunto del activo poblacional.

Tipo CRECIMIENTO:
{
  "tipo_medicion": "PESO" | "TALLA" | "BIOMASA",
  "valor_medicion": decimal (positivo, mayor a 0),
  "unidad_medida": "kg" | "g" | "cm" | "m" | ...,
  "nuevo_peso_promedio": decimal,   
    /* Obligatorio para POBLACIONAL. Es el peso promedio 
    resultante tras la medición. El sistema usa 
    este valor para recalcular biomasa_total. */
  "cantidad_medida": integer,        
    /* Obligatorio para POBLACIONAL. Número de individuos 
    incluidos en la medición. */
  "tipo_agregacion": "PROMEDIO" | "TOTAL" | "DENSIDAD"
    /* Obligatorio para POBLACIONAL. Define cómo interpretar 
    el valor de la medición. */
}

Tipo SANITARIO:
{
  "tipo_evento_sanitario": "DIAGNOSTICO" | 
    "TRATAMIENTO" | "VACUNACION" | 
    "CONTROL_PREVENTIVO",
  "diagnostico": "string",
  "medicamento": "string",          /* Si aplica */
  "dosis": decimal,                  /* Si aplica */
  "unidad_dosis": "string",          /* Si aplica */
  "frecuencia": "string",            /* Si aplica */
  "duracion_dias": integer,          /* Si aplica */
  "cantidad_afectada": integer,      
    /* Obligatorio para POBLACIONAL. Número de individuos 
    afectados. No modifica cantidad_actual; si hay 
    muertes, debe registrarse un evento de BAJA 
    adicional. */
  "observaciones": "text"
}

Tipo REPRODUCTIVO:
{
  "tipo_evento_reproductivo": "SERVICIO" | 
    "INSEMINACION" | "DIAGNOSTICO_GESTACION" | 
    "PARTO" | "ABORTO" | "NACIMIENTO",
  "activo_relacionado_id": integer,  /* Si aplica */
  "resultado_evento": "string",
  "numero_crias": integer,           /* Si aplica */
  "observaciones": "text"
}

Tipo PRODUCTIVO:
{
  "tipo_producto": "string",         
    /* Debe pertenecer al catálogo RF-16 para 
    la especie. */
  "cantidad_producida": decimal (positivo > 0),
  "unidad_medida": "string",         
    /* Debe coincidir con la definida en RF-16 
    para el tipo_producto. */
  "condiciones_produccion": "text"   /* Opcional */
}

Tipo BAJA:
{
  "tipo_baja": "MUERTE" | "VENTA" | 
    "SACRIFICIO" | "PERDIDA" | 
    "DESCARTE_SANITARIO",
  "cantidad_afectada": integer,      
    /* Obligatorio para POBLACIONAL. Número de individuos 
    dados de baja. El sistema descuenta este valor 
    de cantidad_actual y recalcula biomasa_total 
    y densidad. */
  "motivo_baja": "text"
} |  |  |

**Proceso:**

El usuario accede al módulo de gestión de activos biológicos y selecciona un activo.

El sistema muestra la información general del activo y su historial de eventos.

El usuario selecciona la opción de registrar evento biológico.

El sistema presenta las categorías de eventos disponibles.

El usuario selecciona el tipo de evento e ingresa la información correspondiente.

El sistema valida la existencia del activo y su estado.

El sistema valida la coherencia de la fecha del evento.

El sistema valida que el tipo de evento sea válido y que los datos ingresados correspondan a la categoría seleccionada.

El sistema registra el evento en el historial del activo biológico.

El sistema asocia el evento al activo y al usuario responsable.

El sistema registra la operación en el módulo de auditoría.

El sistema confirma la creación del evento al usuario.

**Flujo alterno:**

Activo no existe - HTTP: 404 Not Found
Precondición no cumplida: El activo no está registrado.
Mensaje: "El activo biológico no existe."
Postcondición: No se registra el evento ni se modifica información.

Activo en estado no operativo - HTTP: 409 Conflict
Precondición no cumplida: El activo se encuentra 
en estado CERRADO o BAJA.
Mensaje: "No es posible registrar eventos sobre 
este activo. El activo se encuentra en estado 
[ESTADO_ACTUAL], el cual no permite nuevos 
registros de eventos. Los estados que permiten 
registro de eventos son: ACTIVO, EN_TRATAMIENTO, 
AISLADO."
Postcondición: No se registra el evento.

Fecha inválida - HTTP: 400 Bad Request
Precondición no cumplida: Fecha futura o incoherente.
Mensaje: "La fecha del evento es inválida o inconsistente con el historial."
Postcondición: No se registra el evento.

Datos obligatorios faltantes - HTTP: 400 Bad Request
Precondición no cumplida: Campos requeridos no diligenciados.
Mensaje: "Faltan datos obligatorios para registrar el evento."
Postcondición: No se registra el evento.

**Salida:**

Registro del evento biológico en el historial del activo.

Actualización del historial de eventos del activo biológico.

Confirmación de la operación realizada al usuario.

Disponibilidad del evento para módulos analíticos, financieros y de reportes.

**Postcondiciones:**

El activo biológico cuenta con un nuevo evento registrado en su historial.

El historial del activo mantiene la trazabilidad completa de eventos.

La información queda disponible para análisis y procesamiento en módulos dependientes.

El evento queda asociado al usuario que lo registró.

**Criterios de aceptación:**

El sistema permite registrar eventos biológicos para activos activos.

El sistema rechaza eventos sobre activos con el estado CERRADO o BAJA.

El sistema impide el registro de eventos con fechas inconsistentes.

El sistema impide el registro de eventos con datos incompletos segun la categoria.

El sistema valida que el activo exista antes de registrar el evento.

El sistema registra correctamente el evento en el historial del activo.

El sistema asocia el evento al usuario responsable.

El sistema impide la eliminación de eventos registrados.

El sistema registra la operación en el módulo de auditoría.

El sistema confirma al usuario la creación del evento.

El sistema permite registrar eventos sobre activos en estado EN_TRATAMIENTO y AISLADO, además del estado ACTIVO.

El sistema rechaza el JSON de datos_evento cuando no cumple el esquema definido para el tipo_evento seleccionado, con mensaje de error específico por campo faltante o inválido.

Para eventos de tipo CRECIMIENTO sobre activos POBLACIONAL, el sistema rechaza el evento si nuevo_peso_promedio, cantidad_medida o tipo_agregacion están ausentes.

Para eventos de tipo BAJA sobre activos POBLACIONAL, el sistema rechaza el evento si cantidad_afectada está ausente o es mayor a cantidad_actual.

**Requerimientos no funcionales:**

Integridad: Los eventos registrados no deben ser eliminados ni alterados.

Seguridad: Solo usuarios autorizados pueden registrar eventos.

Fiabilidad: El registro de eventos debe ejecutarse sin pérdida de información.

Trazabilidad: Cada evento debe quedar completamente identificado (fecha, tipo, usuario, activo).

Disponibilidad: El registro de eventos debe estar disponible durante la operación del sistema.

Escalabilidad: El sistema debe soportar múltiples eventos por activo sin degradación del rendimiento.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-40 — Registro de Eventos de Crecimiento

**Código Identificación:** RF-40 -- Versión -- 1.1

**Fuente:** Productor / Veterinario / Administrador

**Descripción:** El sistema debe permitir registrar eventos de crecimiento asociados a activos biológicos, definidos como mediciones cuantitativas estructuradas del desarrollo físico del activo en el tiempo.

Se establece un modelo configurable de mediciones, donde cada tipo de activo o especie define:

- Tipos de medición permitidos (peso, talla, biomasa, etc.)
- Unidades válidas (Kg, lb, gr)
- Frecuencia de medición (Diaria, Semanal, Quincenal, Mensual)

Los eventos pueden aplicarse a:

- Activos individuales
- Activos poblacionales (con valores agregados: promedio, total o densidad)

Cada evento de crecimiento debe quedar registrado en el historial del activo biológico y debe ser utilizado como insumo para el cálculo de indicadores zootécnicos, modelos predictivos (M04) y valoración financiera (M06).

**Justificación:** El crecimiento de los activos biológicos es uno de los principales indicadores de transformación biológica y es fundamental para evaluar el desempeño productivo y económico.

El registro estructurado de estos eventos permite medir eficiencia, detectar anomalías y sustentar procesos de análisis técnico y contable.

**Precondiciones:** El activo biológico debe existir en el sistema.

El activo debe encontrarse en estado ACTIVO.

El activo debe tener una fase productiva activa.

El usuario debe tener sesión activa y permisos para registrar eventos.

**Restricciones:** No se permite registrar eventos de crecimiento en activos en estado CERRADO o BAJA.

La fecha del evento no puede ser futura.

La fecha del evento no puede ser anterior al último registro de crecimiento, si se requiere mantener orden cronológico.

Los valores registrados deben ser numéricos, positivos y representar un unico dato escalar.

Los valores deben estar dentro de rangos válidos definidos por el sistema o por la especie.

El sistema debe validar coherencia entre tipo de activo y tipo de medición.

La unidad de medidad debe coincidir con el tipo de medicion que se realice:

- peso -> kg, gr, lb
- altura -> cm, m 
- densidad -> kg/m^2

Para activos poblacionales, los valores deben representar agregaciones válidas (promedio, total o densidad según corresponda).

No se permite eliminar registros de crecimiento.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-33 — Registro de Activos Biológicos
RF-37 — Gestión de Fases del Ciclo Productivo
RF-39 — Registro de Eventos Biológicos

**Actores:** Productor, Veterinario, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador del activo biológico. |
| tipo_activo | varchar | Tipo de activo: INDIVIDUAL o POBLACIONAL. |
| fecha_evento | date | Fecha en la que se realiza la medición. |
| tipo_medicion | varchar | Tipo de medición (peso, biomasa, tamaño u otro definido). |
| valor_medicion | decimal | Valor registrado de la medición. |
| unidad_medida | varchar | Unidad asociada (kg, g, cm, etc.). |
| tipo_agregacion | varchar | Promedio, total, densidad (Disponible solo para el activo de tipo poblacional) |
| frecuencia | varchar | Frecuencia con la que se estan tomando las medidas (Diaria, Semanal, Quincenal, Mensual)  |
| descripcion | text | Observaciones adicionales del evento. |
| responsable_id | integer | Usuario que registra el evento. |

**Proceso:**

1. El usuario accede al módulo de activos biológicos y selecciona un activo.

2. El sistema muestra la información del activo y su historial de crecimiento.

3. El usuario selecciona la opción de registrar evento de crecimiento.

4. El sistema solicita los datos de medición correspondientes.

-tipo_activo
-tipo_medicion
-valor_medicion
-unidad_medida
-(tipo_agregacion si aplica)
-fecha_evento
-metodo_medicion

6. El sistema valida la existencia del activo y su estado.

7. El sistema valida la coherencia de la fecha del evento.

8. El sistema valida todos los datos ingresados.

9. El sistema registra el evento de crecimiento en el historial del activo.

10. El sistema asocia el evento al usuario responsable.

11. El sistema registra la operación en el módulo de auditoría.

12. El sistema confirma la creación del evento al usuario.

**Flujo alterno:**

Activo no existe - HTTP: 404 Not Found
Precondición no cumplida: El activo no está registrado.
Mensaje: "El activo biológico no existe."
Postcondición: No se registra el evento ni se modifica información.

Activo no está en estado ACTIVO - HTTP: 409 Conflict
Precondición no cumplida: Estado diferente de ACTIVO.
Mensaje: "El activo no se encuentra en estado ACTIVO."
Postcondición: No se registra el evento.

Fecha inválida - HTTP: 400 Bad Request
Precondición no cumplida: Fecha futura o incoherente.
Mensaje: "La fecha del evento es inválida o inconsistente con el historial."
Postcondición: No se registra el evento.

Datos obligatorios faltantes - HTTP: 400 Bad Request
Precondición no cumplida: Campos requeridos no diligenciados.
Mensaje: "Faltan datos obligatorios para registrar el evento."
Postcondición: No se registra el evento.

Datos invalidos - HTTP: 400 Bad Request
Precondición no cumplida: Datos diferentes al sistema numerico en los campos del valor_medición.
Mensaje: "Los datos ingresados no son de caracter numerico."
Postcondición: No se registra el evento.

Unidad no correspondiente al tipo de medición - HTTP: 400 Bad Request
Precondición no cumplida: La unidad de medida diligenciada no corresponde al tipo de medición que se esta realizando.
Mensaje: "La unidad de medida que ingresó no corresponde al tipo de medición actual."
Postcondición: No se registra el evento.

**Salida:**

Registro del evento de crecimiento en el historial del activo biológico.

Actualización del historial de crecimiento del activo.

Confirmación de la operación realizada al usuario.

Disponibilidad de la información para análisis zootécnico, predicción y valoración financiera.

**Postcondiciones:**

El activo biológico cuenta con un nuevo registro de crecimiento.

El historial de crecimiento del activo se mantiene actualizado y ordenado.

La información queda disponible para el cálculo de indicadores y análisis posteriores.

El evento queda asociado al usuario que lo registró.

**Criterios de aceptación:**

El sistema permite registrar eventos de crecimiento únicamente para activos en estado ACTIVO.

El sistema valida que el activo exista antes de permitir el registro del evento.

El sistema valida que el activo tenga una fase productiva activa.

El sistema valida que la fecha del evento no sea futura y que respete el orden cronológico respecto a registros anteriores.

El sistema valida que el valor de medición sea numérico, positivo y represente un único valor escalar.

El sistema valida la coherencia entre tipo de activo:

- Para activos INDIVIDUALES no se permite tipo_agregacion.
- Para activos POBLACIONAL el campo tipo_agregacion es obligatorio.

El sistema valida que el tipo de agregación sea compatible con el tipo de medición.

El sistema valida que la unidad de medida corresponda al tipo de medición y, si aplica, al tipo de agregación.

El sistema valida que todos los campos obligatorios estén diligenciados antes de registrar el evento.

El sistema registra correctamente el evento en el historial del activo biológico con todos sus atributos.

El sistema garantiza que el historial de crecimiento se mantenga ordenado cronológicamente.

El sistema impide la edición y eliminación de registros de crecimiento una vez creados.

El sistema registra la operación en el módulo de auditoría, incluyendo usuario, fecha y datos del evento.

El sistema asocia correctamente el evento al usuario responsable.

El sistema muestra mensajes de error claros y específicos cuando ocurre una validación fallida.

**Requerimientos no funcionales:**

Integridad: Los registros de crecimiento no deben ser alterados ni eliminados.

Seguridad: Solo usuarios autorizados pueden registrar eventos de crecimiento.

Fiabilidad: El registro debe ejecutarse sin pérdida de datos.

Trazabilidad: Cada medición debe quedar identificada con fecha, valor, unidad y responsable.

Disponibilidad: El módulo debe permitir el registro continuo de mediciones.

Escalabilidad: El sistema debe soportar grandes volúmenes de registros de crecimiento.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-41 — Registro de eventos sanitarios

**Código Identificación:** RF-41 -- Versión -- 1.1

**Fuente:** Veterinario / Productor / Ingeniero de campo

**Descripción:** El sistema debe permitir registrar eventos sanitarios asociados a los activos biológicos, con el fin de documentar cualquier intervención, diagnóstico, tratamiento o condición de salud que afecte al activo durante su ciclo de vida.

Los eventos sanitarios incluyen: vacunación, tratamiento médico, diagnóstico clínico, control preventivo y registro de enfermedad.

El sistema debe soportar el registro de eventos sanitarios para activos INDIVIDUALES y POBLACIONAL.

Cada evento sanitario debe estructurarse bajo un modelo definido por tipo de evento, donde se establecen campos obligatorios y/o opcionales.

Algunos eventos sanitarios pueden implicar cambios de estado del activo, los cuales deben ejecutarse exclusivamente a través de RF-44, respetando las reglas de transición definidas. Por ejemplo, un tratamiento puede generar el estado EN_TRATAMIENTO o aislamiento sanitario AISLADO.

El registro debe formar parte del historial sanitario del activo y ser utilizado para análisis clínico, modelos predictivos (M04) y valoración (M06).

**Justificación:** La gestión sanitaria es un componente crítico en la administración de activos biológicos, ya que impacta directamente en la productividad, bienestar animal y valor económico.

El registro detallado de eventos sanitarios permite mantener trazabilidad clínica, facilitar la toma de decisiones y garantizar la calidad de la información utilizada en análisis técnicos y financieros.

**Precondiciones:** El activo biológico debe existir en el sistema.

El activo debe encontrarse en estado ACTIVO.

El activo debe tener una fase productiva activa.

El usuario debe tener sesión activa y permisos para registrar eventos sanitarios.

**Restricciones:** No se permite registrar eventos sanitarios en activos en estado CERRADO o BAJA.

La fecha del evento no puede ser futura.

La fecha del evento no puede ser anterior a la fecha de registro del activo.

El tipo de evento sanitario debe corresponder a una categoría válida definida en el sistema.

Datos requeridos por tipo de evento:

VACUNACIÓN
- medicamento (obligatorio)
- dosis (obligatorio)

TRATAMIENTO
- medicamento (obligatorio)
- dosis (obligatorio)
- frecuencia (obligatorio)
- duracion (obligatorio)

DIAGNÓSTICO
- diagnostico preliminar (obligatorio)

CONTROL PREVENTIVO
- observaciones (obligatorio)

No se permite registrar eventos de tratamiento y/o vacunación sin un evento previo de diagnostico.

Los eventos TRATAMIENTO o CONTROL PREVENTIVO pueden generar estados como EN_TRATAMIENTO o AISLADO.

No se permite la eliminación de eventos sanitarios registrados.

El sistema debe garantizar la coherencia temporal del historial sanitario.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-33 — Registro de Activos Biológicos
RF-37 — Gestión de Fases del Ciclo Productivo
RF-39 — Registro de Eventos Biológicos

**Actores:** Veterinario, Productor, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador del activo biológico. |
| tipo_activo | varchar | Tipo de activo: INDIVIDUAL o POBLACIONAL. |
| fecha_evento | date | Fecha en la que ocurre el evento sanitario. |
| tipo_evento_sanitario | varchar | Tipo de evento (vacunación, tratamiento, diagnóstico, control preventivo, otro). |
| diagnostico | varchar | Diagnóstico clínico asociado al evento (si aplica). |
| medicamento | varchar | Nombre del medicamento aplicado (si aplica). |
| dosis | decimal | Cantidad administrada del medicamento. |
| unidad_dosis | varchar | Unidad de la dosis (ml, mg, etc.). |
| frecuencia | varchar | Frecuencia de administración (si aplica). |
| duracion | integer | Duración del tratamiento en días (si aplica). |
| observaciones | text | Comentarios adicionales del evento. |
| responsable_id | integer | Usuario que registra el evento. |

**Proceso:**

1. El usuario accede al módulo de activos biológicos.

2. El usuario selecciona un activo.

3. El sistema valida:

- Existencia del activo.
- Estado ACTIVO.
- Permisos del usuario.

4. El sistema muestra historial sanitario.

5. El usuario selecciona registrar evento sanitario.

6. El sistema muestra tipos de eventos disponibles.

7. El usuario selecciona el tipo de evento.

8. El sistema solicita únicamente los campos definidos para ese tipo de evento.

9. El usuario ingresa los datos.

10. El sistema valida:

- Campos obligatorios según tipo.
- Formato de datos.
- Fecha válida y coherente.

11. El sistema valida coherencia del historial sanitario.

12. El sistema registra el evento sanitario.

13. El sistema evalúa si el evento genera cambio de estado del activo (RF-44):

- Si aplica, actualiza el estado sanitario del activo.

14. El sistema asocia el evento al usuario.

15. El sistema registra en auditoría.

16. El sistema confirma la operación.

**Flujo alterno:**

Activo no existe - HTTP: 404 Not Found
Precondición no cumplida: El activo no está registrado.
Mensaje: "El activo biológico no existe."
Postcondición: No se registra el evento ni se modifica información.

Activo no está en estado ACTIVO - HTTP: 409 Conflict
Precondición no cumplida: Estado diferente de ACTIVO.
Mensaje: "El activo no se encuentra en estado ACTIVO."
Postcondición: No se registra el evento.

Fecha inválida - HTTP: 400 Bad Request
Precondición no cumplida: Fecha futura o incoherente.
Mensaje: "La fecha del evento es inválida o inconsistente con el historial."
Postcondición: No se registra el evento.

Violación de secuencia lógica HTTP: 422 Unprocessable Entity
Precondición no cumplida: Orden incorrecto de eventos.
Mensaje: "El evento no cumple la secuencia lógica del ciclo sanitario."
Postcondición: No se registra el evento.

Datos obligatorios faltantes - HTTP: 400 Bad Request
Precondición no cumplida: Campos requeridos no diligenciados.
Mensaje: "Faltan datos obligatorios para registrar el evento."
Postcondición: No se registra el evento.

**Salida:**

Registro del evento sanitario en el historial del activo biológico.

Actualización del historial sanitario del activo.

Confirmación de la operación realizada al usuario.

Disponibilidad de la información para módulos analíticos, clínicos y financieros.

**Postcondiciones:**

El activo biológico cuenta con un nuevo evento sanitario registrado.

El historial sanitario del activo se mantiene actualizado.

La información queda disponible para análisis clínico y predicción.

Si aplica, el estado sanitario del activo es actualizado conforme a RF-44.

El evento queda asociado al usuario responsable.

**Criterios de aceptación:**

El sistema registra un evento sanitario únicamente si:

- El activo existe y está en estado ACTIVO.
- El tipo de evento es válido.
- Los datos cumplen el modelo definido por tipo de evento.
- La fecha es válida y coherente.

El sistema garantiza que:

- Al registrar eventos de TRATAMIENTO o CONTROL PREVENTIVO se puedan generar los estados EN_TRATAMIENTO o  AISLADO.
- Solo se solicitan los campos definidos para cada tipo de evento.
- No se permiten datos inconsistentes entre tipo de evento y campos.
- El historial sanitario mantiene coherencia temporal.

El sistema registra correctamente:

- El evento en el historial.
- El usuario responsable.
- La auditoría del evento.

El sistema confirma al usuario la creación del evento.

El sistema muestra mensajes de error claros y específicos cuando ocurre una validación fallida.

**Requerimientos no funcionales:**

Integridad: Los eventos sanitarios no deben ser modificados ni eliminados.

Seguridad: Solo usuarios autorizados pueden registrar eventos sanitarios.

Fiabilidad: El sistema debe garantizar el almacenamiento correcto de la información clínica.

Trazabilidad: Cada evento debe quedar registrado con todos sus datos asociados.

Disponibilidad: El sistema debe permitir el registro continuo de eventos sanitarios.

Escalabilidad: Debe soportar múltiples registros sanitarios por activo sin degradación del rendimiento.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-42 — Registro de Eventos Reproductivos

**Código Identificación:** RF-42 -- Versión -- 1.1

**Fuente:** Veterinario / Productor

**Descripción:** El sistema debe permitir registrar eventos reproductivos asociados a los activos biológicos, con el fin de documentar los procesos relacionados con la reproducción y continuidad del ciclo biológico.

Los eventos reproductivos incluyen, Servicio (monta), inseminación, diagnósticos de gestación, partos, abortos y nacimientos.

El sistema debe soportar el registro de eventos reproductivos para activos individuales y, cuando aplique, para agrupaciones (lotes) que representen procesos reproductivos controlados (Nacimientos).

Cada evento reproductivo debe permitir establecer relaciones entre activos biológicos (madre, padre o cría), permitiendo la construcción de trazabilidad genealógica.

El sistema debe definir explícitamente las relaciones genealógicas bajo la siguiente estructura:

Madre → Cría(s): Relación 1:N.
Padre → Cría(s): Relación 1:N.
Cría → Madre/Padre: Relación N:1 (cada cría tiene máximo una madre y un padre).

Estas relaciones deben ser persistentes y consultables.

El registro de estos eventos debe integrarse al historial del activo biológico y servir como base para análisis zootécnicos, predicción (M04) y valoración financiera (M06).

**Justificación:** La reproducción es un proceso fundamental en la transformación biológica de los activos, ya que impacta directamente en la producción, crecimiento del inventario y valor económico.

El registro estructurado de eventos reproductivos permite mantener control sobre la eficiencia reproductiva, garantizar trazabilidad y soportar la toma de decisiones técnicas.

**Precondiciones:** El activo biológico debe existir en el sistema.

El activo debe encontrarse en estado ACTIVO.

El activo debe estar en una fase productiva compatible con reproducción.

El usuario debe tener sesión activa y permisos para registrar eventos reproductivos.

**Restricciones:** No se permite registrar eventos reproductivos en activos en estado CERRADO o BAJA.

La fecha del evento debe ser coherente con la fase productiva del activo.

La fecha del evento no puede ser anterior a la fecha de registro del activo.

Los activos de tipo poblacional solo tendran disponible registrar el evento de tipo Nacimiento.

Los activos de tipo Individual tendran disponible registrar cualquier evento de los disponibles (Servicio (Monta),  inseminación, diagnósticos de gestación, partos, abortos y nacimientos).

Para eventos que impliquen relación entre activos (ej. reproducción), los activos relacionados deben existir y estar activos.

No se permite registrar nacimientos sin un evento previo de inseminación y diagnostico de gestación.

No se permite la eliminación de eventos reproductivos.

El sistema debe garantizar la coherencia temporal de los eventos reproductivos (Fechas de eventos).

Una madre puede tener múltiples eventos reproductivos (1:N) (Servicio (Monta), Inseminación, Diagnostico de gestación, Parto, Aborto.

Un padre puede participar en múltiples eventos (1:N) (Servicio (Monta), Inseminación).

Un evento de parto puede generar múltiples crías (1:N).

Cada cría tiene exactamente 1 madre y 1 padre.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-33 — Registro de Activos Biológicos
RF-37 — Gestión de Fases del Ciclo Productivo
RF-39 — Registro de Eventos Biológicos

**Actores:** Veterinario / Productor

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador del activo principal (ej. hembra reproductora). |
| tipo_activo | varchar(10) | (Obligatorio) Tipo de activo: INDIVIDUAL o POBLACIONAL. Determina si la cantidad es unitaria o agregada |
| tipo_evento_reproductivo | varchar | Tipo de evento (servicio (monta), inseminación, diagnóstico, parto, aborto, nacimiento). |
| fecha_evento | date | Fecha en la que ocurre el evento. |
| activo_relacionado_id | integer | Identificador del otro activo involucrado (ej. padre o cría, si aplica). |
| resultado_evento | varchar | Resultado del evento (exitoso, fallido, en proceso). |
| numero_crias | integer | Número de crías generadas (si aplica). |
| observaciones | text | Información adicional relevante. |
| responsable_id | integer | Usuario que registra el evento. |

**Proceso:**

1. El usuario accede al módulo de activos biológicos.

2. El usuario selecciona un activo biológico.

3. El sistema obtiene y muestra la información del activo, incluyendo tipo (INDIVIDUAL o POBLACIONAL), estado y fase productiva.

4. El usuario selecciona la opción de registrar evento reproductivo.

5. El sistema valida que el usuario tenga permisos para registrar eventos.

6. El sistema valida que el activo exista.

7. El sistema valida que el activo se encuentre en estado ACTIVO.

8. El sistema identifica el tipo de activo:

- Si el activo es tipo POBLACIONAL: El sistema solo habilita el tipo de evento NACIMIENTO.
- Si el activo es tipo INDIVIDUAL: El sistema habilita todos los tipos de eventos reproductivos.

9. El usuario selecciona el tipo de evento reproductivo.

10. El sistema solicita los datos obligatorios según el tipo de evento:

Servicio / Inseminación:
activo_relacionado_id,  obligatorio.

Diagnóstico de gestación:
resultado_evento obligatorio.

Parto:
numero_crias obligatorio (≥ 1).

Aborto:
numero_crias obligatorio (≥ 1).

Nacimiento:
numero_crias obligatorio (≥ 1).

11. El usuario ingresa los datos.

12. El sistema valida:

Formato y obligatoriedad de los datos.
Que la fecha_evento no sea futura.
Coherencia temporal con eventos previos del activo.
Existencia y estado del activo relacionado (si aplica).

13. El sistema valida reglas de negocio:

No permite diagnóstico sin evento previo de inseminación o servicio.
No permite parto sin diagnóstico positivo previo.
No permite nacimiento sin inseminación y diagnóstico previo.
No permite inconsistencias genealógicas.

14. El sistema registra el evento reproductivo.

Si el evento es parto o nacimiento:

El sistema registra el número de crías.
El sistema crea relaciones:
madre → cría(s)
padre → cría(s) (si aplica)

15. El sistema asocia el evento al usuario responsable.

16. El sistema registra la operación en el módulo de auditoría.

17. El sistema confirma la creación del evento.

**Flujo alterno:**

Activo no existe - HTTP: 404 Not Found
Precondición no cumplida: El activo no está registrado.
Mensaje: "El activo biológico no existe."
Postcondición: No se registra el evento ni se modifica información.

Activo no está en estado ACTIVO - HTTP: 409 Conflict
Precondición no cumplida: Estado diferente de ACTIVO.
Mensaje: "El activo no se encuentra en estado ACTIVO."
Postcondición: No se registra el evento.

Fase productiva incompatible - HTTP: 409 Conflict
Precondición no cumplida: Fase no apta para reproducción.
Mensaje: "La fase productiva del activo no permite registrar este tipo de evento."
Postcondición: No se registra el evento.

Tipo de evento inválido para el tipo de activo - HTTP: 422 Unprocessable Entity
Precondición no cumplida: Evento no permitido según tipo (POBLACIONAL/INDIVIDUAL).
Mensaje: "El tipo de evento no está permitido para el tipo de activo."
Postcondición: No se registra el evento.

Fecha inválida - HTTP: 400 Bad Request
Precondición no cumplida: Fecha futura o incoherente.
Mensaje: "La fecha del evento es inválida o inconsistente con el historial."
Postcondición: No se registra el evento.

Activo relacionado inválido - HTTP: 404 Not Found
Precondición no cumplida: Padre o cría no existe o no está activo.
Mensaje: "El activo relacionado no existe o no está activo.
Postcondición: No se registra el evento.

Violación de secuencia lógica HTTP: 422 Unprocessable Entity
Precondición no cumplida: Orden incorrecto de eventos.
Mensaje: "El evento no cumple la secuencia lógica del ciclo reproductivo."
Postcondición: No se registra el evento.

Datos obligatorios faltantes - HTTP: 400 Bad Request
Precondición no cumplida: Campos requeridos no diligenciados.
Mensaje: "Faltan datos obligatorios para registrar el evento."
Postcondición: No se registra el evento.

**Salida:**

Registro del evento reproductivo en el historial del activo biológico.

Actualización del historial reproductivo del activo.

Confirmación de la operación realizada al usuario.

Disponibilidad de la información para análisis zootécnico y módulos dependientes.

**Postcondiciones:**

El activo biológico cuenta con un nuevo evento reproductivo registrado.

Las relaciones entre activos (si existen) quedan registradas.

El historial reproductivo del activo se mantiene actualizado.

La información queda disponible para análisis y trazabilidad.

**Criterios de aceptación:**

El sistema registra eventos reproductivos únicamente si:

El activo existe.
El activo está en estado ACTIVO.
La fase productiva permite el evento.
El tipo de evento corresponde al tipo de activo:
- POBLACIONAL → solo NACIMIENTO.
- INDIVIDUAL → todos los eventos.

El sistema valida que:

- No existan fechas futuras.
- Las fechas sean cronológicamente coherentes.
- Los datos obligatorios estén completos.

El sistema garantiza que:

- No se registra diagnóstico sin servicio o inseminación previa.
- No se registra parto sin diagnóstico positivo previo.
- No se registra nacimiento sin inseminación y diagnóstico previo.
- No se registran eventos fuera de secuencia lógica.

El sistema valida relaciones:

- Cada cría tiene exactamente una madre.
- Cada cría tiene exactamente un padre.
- Los activos relacionados existen y están activos.

El sistema registra correctamente:

- El evento en el historial del activo.
- Las relaciones genealógicas cuando aplique.
- El usuario responsable del registro.
- El evento en el módulo de auditoría.

El sistema impide:

- Eliminación de eventos reproductivos.
- Registro de eventos inconsistentes.

El sistema muestra mensajes de error claros y específicos cuando ocurre una validación fallida.

**Requerimientos no funcionales:**

Integridad: Los eventos reproductivos no deben ser alterados ni eliminados.

Seguridad: Solo usuarios autorizados pueden registrar eventos reproductivos.

Fiabilidad: El sistema debe garantizar el almacenamiento correcto de la información.

Trazabilidad: Debe mantenerse la relación entre activos involucrados.

Disponibilidad: El sistema debe permitir el registro continuo de eventos.

Escalabilidad: Debe soportar múltiples eventos reproductivos por activo.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-43 — Registro de Eventos Productivos

**Código Identificación:** RF-43 -- Versión -- 1.0

**Fuente:** Productor / Veterinario

**Descripción:** El sistema debe permitir registrar eventos productivos asociados a los activos biológicos (individuales o poblacionales), documentando la generación de productos derivados de los mismos durante las fases productivas activas de su ciclo de vida.

DEFINICIÓN FORMAL: Un evento productivo es la captura estructurada de la salida productiva generada por un activo biológico en una fecha específica, caracterizada por un tipo de producto catalogado, una cantidad medible y una unidad de medida válida, ocurrida durante una fase productiva activa del activo (RF-37). No se permite registrar eventos productivos fuera de una fase productiva habilitada.

MODELO DE DATOS: El modelo es configurable por especie. Los tipos de producto, sus unidades de medida válidas y las fases productivas en las que aplican son parametrizados en RF-16 (Configuración de parámetros por especie). No se aceptan tipos de producto ni unidades fuera del catálogo configurado.

CLASIFICACIÓN DE TIPOS DE EVENTO PRODUCTIVO POR MODELO PRODUCTIVO:
— Modelo bovino leche: tipo LECHE (unidad: litros). Fase aplicable: PRODUCCIÓN.
— Modelo bovino carne: tipo CARNE (unidad: kg). Fase aplicable: ENGORDE/FINALIZACIÓN.
— Modelo avícola postura: tipo HUEVOS (unidad: unidades). Fase aplicable: POSTURA.
— Modelo avícola carne: tipo CARNE_AVE (unidad: kg). Fase aplicable: ENGORDE.
— Modelo apícola: tipo MIEL (unidad: kg). Fase aplicable: COSECHA.
— Modelo ovino/caprino: tipo LANA (unidad: kg), LECHE_MENOR (unidad: litros). Fase aplicable: según especie.
— Otros modelos: tipos definidos en el catálogo RF-16 para la especie correspondiente.

RELACIÓN CON RF-37: El registro de un evento productivo está condicionado a que el activo biológico se encuentre en una fase productiva habilitada para el tipo de producto a registrar, según configuración en RF-16. Si el activo no está en una fase productiva válida para el tipo de producto, el sistema rechaza el registro.

Cada evento productivo queda almacenado de forma permanente e inmutable en el historial del activo biológico (RF-46). No se permite eliminación ni modificación posterior.

**Justificación:** Los eventos productivos representan la salida económica del activo biológico, siendo fundamentales para medir rendimiento, eficiencia y rentabilidad. El registro estructurado y formal de estos eventos permite evaluar el desempeño productivo, soportar decisiones operativas y alimentar los procesos de indicadores zootécnicos (RF-51) y valoración financiera (M06).

**Precondiciones:** 1. El activo biológico debe existir en el sistema (RF-33).
2. El activo debe encontrarse en estado ACTIVO (RF-44).
3. El activo debe estar en una fase productiva habilitada para el tipo de producto a registrar, según configuración RF-16 y RF-37. Si no existe fase productiva activa compatible, el sistema no permite el registro.
4. El usuario debe tener sesión activa (RF-02) y permisos para registrar eventos productivos (RF-04).

**Restricciones:** RESTRICCIONES DE ESTADO Y FASE:
— No se permite registrar eventos productivos en activos con estado CERRADO o BAJA.
— El tipo de producto debe corresponder a una fase productiva activa del activo, según catálogo RF-16. Si la fase activa no habilita el tipo de producto solicitado, el sistema rechaza el registro.

RESTRICCIONES DE DATOS (MODELO CONFIGURABLE RF-16):
— El tipo de producto debe pertenecer al catálogo configurado para la especie del activo en RF-16. No se aceptan tipos de producto ingresados libremente.
— La unidad de medida debe ser la definida en RF-16 para el tipo de producto. No se aceptan unidades fuera del catálogo.
— El valor de cantidad_producida debe ser un número decimal positivo mayor a cero. No se aceptan valores negativos, nulos ni igual a cero.

RESTRICCIONES TEMPORALES:
— La fecha del evento no puede ser futura (posterior a la fecha del sistema).
— La fecha del evento no puede ser anterior a la fecha de inicio del activo en el sistema (RF-33).
— La fecha del evento debe estar comprendida dentro del período de la fase productiva activa del activo (RF-37).

RESTRICCIÓN DE DUPLICIDAD:
— No se permite registrar dos eventos productivos del mismo tipo_producto para el mismo activo en la misma fecha. El sistema verifica duplicidad antes de persistir.

INMUTABILIDAD:
— Los eventos productivos registrados no pueden ser eliminados ni modificados. El historial es inmutable.

**Prioridad:** [ ] Alta/Must  [X] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-04 — Gestión de permisos
RF-16 — Configuración de parámetros por especie (catálogo de tipos de producto y unidades válidas)
RF-33 — Registro de Activos Biológicos
RF-37 — Gestión de Fases del Ciclo Productivo (condición de fase activa para el registro)
RF-39 — Registro de Eventos Biológicos (modelo base del evento)
RF-44 — Gestión del Estado del Activo Biológico (condición de estado ACTIVO)
RF-46 — Consulta de Historial del Activo Biológico (destino de los eventos registrados)
RF-51 — Generación de Indicadores Zootécnicos (consumidor de los datos)
M06 — Valoración financiera (consumidor de los datos)

**Actores:** Productor, Veterinario

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | (Obligatorio) Identificador único del activo biológico sobre el que se registra el evento. |
| tipo_activo | varchar(10) | (Obligatorio) Tipo de activo: INDIVIDUAL o POBLACIONAL. Determina si la cantidad es unitaria o agregada. |
| fecha_evento | date | (Obligatorio) Fecha del evento. No puede ser futura, anterior al inicio del activo, ni fuera del período de la fase productiva activa. |
| tipo_producto | varchar(50) | (Obligatorio) Tipo de producto generado. Debe pertenecer al catálogo de RF-16 configurado para la especie del activo. Ej: LECHE, HUEVOS, CARNE, LANA, MIEL. |
| cantidad_producida | decimal(12,3) | (Obligatorio) Cantidad generada del producto. Debe ser un valor numérico positivo mayor a cero. |
| unidad_medida | varchar(20) | (Obligatorio) Unidad de medida del producto. Debe corresponder a la unidad definida en RF-16 para el tipo_producto registrado. |
| condiciones_produccion | text | (Opcional) Descripción de las condiciones bajo las que se generó el producto (temperatura, estado sanitario, etc.). |
| observaciones | text | (Opcional) Comentarios adicionales del responsable del registro. |
| responsable_id | integer | (Obligatorio) Identificador del usuario que registra el evento (RF-02). |

**Proceso:**

FLUJO PRINCIPAL:

1. El usuario accede al módulo de activos biológicos, selecciona un activo y elige la opción 'Registrar evento productivo'.

2. El sistema verifica, antes de mostrar el formulario:
   — Existencia del activo (RF-33).
   — Estado del activo = ACTIVO (RF-44). Si no cumple → ERROR E-01.
   — Existencia de al menos una fase productiva activa (RF-37). Si no existe fase activa → ERROR E-02.

3. El sistema presenta el formulario con los tipos de producto disponibles según la fase productiva activa del activo (catálogo RF-16), bloqueando la selección de tipos no habilitados para la fase actual.

4. El usuario ingresa: tipo_producto, fecha_evento, cantidad_producida, unidad_medida y datos opcionales.

5. El sistema ejecuta las validaciones de negocio:
   a) Que tipo_producto pertenezca al catálogo RF-16 para la especie del activo → si no: ERROR E-03.
   b) Que tipo_producto esté habilitado para la fase productiva activa del activo (RF-37) → si no: ERROR E-04.
   c) Que fecha_evento no sea futura → si es futura: ERROR E-05.
   d) Que fecha_evento no sea anterior a la fecha de inicio del activo → si no cumple: ERROR E-05.
   e) Que fecha_evento esté dentro del período de la fase productiva activa → si no: ERROR E-05.
   f) Que cantidad_producida > 0 → si no: ERROR E-06.
   g) Que unidad_medida sea la definida en RF-16 para tipo_producto → si no: ERROR E-07.
   h) Que no exista ya un evento del mismo tipo_producto para el mismo activo en la misma fecha_evento (duplicidad) → si existe: ERROR E-08.

6. Si todas las validaciones son exitosas, el sistema ejecuta de forma transaccional:
   a) Persiste el evento productivo en el historial del activo (inmutable).
   b) Asocia el evento al usuario responsable y registra fecha/hora del sistema.
   c) Registra la operación en el módulo de auditoría.

7. El sistema confirma la creación del evento al usuario con código de respuesta HTTP 201 y mensaje: 'Evento productivo registrado exitosamente para el activo [identificador] en fecha [fecha_evento].'


**Flujo alterno:**


E-01 | Estado no ACTIVO:
  Código: HTTP 409 / Error de negocio
  Mensaje: 'El activo [identificador] se encuentra en estado [estado_actual]. Solo se pueden registrar eventos productivos en activos con estado ACTIVO.'
  Recuperación: El sistema no muestra el formulario. Redirige a la vista del activo.
  Estado final: Operación cancelada. Sin cambios en el sistema.

E-02 | Sin fase productiva activa:
  Código: HTTP 422 / Error de negocio
  Mensaje: 'El activo no tiene una fase productiva activa que permita el registro de eventos productivos. Verifique el ciclo productivo del activo (RF-37).'
  Recuperación: El sistema no muestra el formulario. Sugiere al usuario revisar la gestión de fases.
  Estado final: Operación cancelada. Sin cambios en el sistema.

E-03 | Tipo de producto fuera de catálogo:
  Código: HTTP 422 / Error de validación
  Mensaje: 'El tipo de producto ingresado no está definido en el catálogo para la especie [especie]. Seleccione un tipo de producto válido.'
  Recuperación: El formulario permanece activo. El campo tipo_producto se resalta con indicador de error. El sistema muestra la lista de tipos válidos disponibles.
  Estado final: No se persiste ningún dato. El usuario puede corregir y reintentar.

E-04 | Tipo de producto no habilitado en la fase activa:
  Código: HTTP 422 / Error de negocio
  Mensaje: 'El tipo de producto [tipo_producto] no está habilitado para la fase productiva activa [nombre_fase] del activo. Verifique la configuración de fases (RF-37).'
  Recuperación: Igual que E-03.
  Estado final: No se persiste ningún dato.

E-05 | Fecha del evento inválida:
  Código: HTTP 422 / Error de validación
  Mensaje (futura): 'La fecha del evento [fecha_evento] es posterior a la fecha actual del sistema. No se permiten registros con fecha futura.'
  Mensaje (anterior al inicio): 'La fecha del evento es anterior a la fecha de inicio del activo en el sistema. No se permiten registros previos al registro del activo.'
  Mensaje (fuera de fase): 'La fecha del evento está fuera del período de la fase productiva activa [nombre_fase] ([fecha_inicio_fase] – [fecha_fin_fase o "en curso"]).'
  Recuperación: El campo fecha_evento se resalta. El usuario puede corregirlo y reintentar.
  Estado final: No se persiste ningún dato.

E-06 | Cantidad inválida:
  Código: HTTP 422 / Error de validación
  Mensaje: 'La cantidad producida debe ser un valor numérico positivo mayor a cero. Valor ingresado: [cantidad_producida].'
  Recuperación: El campo cantidad_producida se resalta. El usuario puede corregirlo y reintentar.
  Estado final: No se persiste ningún dato.

E-07 | Unidad de medida incompatible:
  Código: HTTP 422 / Error de validación
  Mensaje: 'La unidad de medida [unidad_medida] no es válida para el tipo de producto [tipo_producto]. La unidad válida es: [unidad_esperada_RF16].'
  Recuperación: El campo unidad_medida se resalta y el sistema muestra la unidad correcta. El usuario puede corregirlo y reintentar.
  Estado final: No se persiste ningún dato.

E-08 | Duplicidad:
  Código: HTTP 409 / Error de negocio
  Mensaje: 'Ya existe un evento productivo de tipo [tipo_producto] registrado para el activo [identificador] en la fecha [fecha_evento]. No se permiten registros duplicados.'
  Recuperación: El formulario permanece activo. El usuario puede modificar la fecha o el tipo de producto.
  Estado final: No se persiste ningún dato.

E-09 | Fallo transaccional del sistema:
  Código: HTTP 500 / Error del sistema
  Mensaje: 'El evento productivo no pudo ser registrado por un error interno del sistema. Intente nuevamente. Si el problema persiste, contacte al administrador.'
  Recuperación: Rollback completo. El sistema registra el fallo en auditoría. El usuario puede reintentar.
  Estado final: No se persiste ningún dato. El historial del activo permanece sin cambios.

**Salida:**

Evento productivo registrado de forma permanente e inmutable en el historial del activo biológico (RF-46).
Confirmación al usuario con código HTTP 201 y mensaje de éxito.
Registro de la operación en el módulo de auditoría (usuario, fecha/hora, activo, tipo de producto, cantidad).
Disponibilidad del dato para: indicadores zootécnicos (RF-51), reportes analíticos (M04, M08) y valoración financiera (M06).

**Postcondiciones:**

El activo biológico cuenta con un nuevo evento productivo registrado e inmutable en su historial.
El historial productivo del activo refleja correctamente el nuevo registro.
El dato queda disponible para RF-51, M04, M06 y M08.
El evento queda asociado al usuario responsable y registrado en auditoría.

**Criterios de aceptación:**

El sistema registra exitosamente un evento productivo cuando: el activo existe y está ACTIVO, el tipo de producto pertenece al catálogo RF-16 para la especie, la fase productiva activa habilita ese tipo de producto (RF-37), la fecha es válida (no futura, no anterior al inicio del activo, dentro del período de la fase), la cantidad es > 0 y la unidad de medida corresponde al tipo de producto en RF-16.

El sistema rechaza el registro si el activo está en estado CERRADO o BAJA, mostrando mensaje E-01.

El sistema rechaza el registro si no existe fase productiva activa compatible con el tipo de producto, mostrando mensaje E-02.

El sistema rechaza el registro si el tipo de producto no pertenece al catálogo RF-16 de la especie del activo, mostrando mensaje E-03.

El sistema rechaza el registro si el tipo de producto no está habilitado para la fase productiva activa, mostrando mensaje E-04.

El sistema rechaza el registro si la fecha del evento es futura, anterior al inicio del activo, o fuera del período de la fase activa, mostrando el mensaje E-05 correspondiente.

El sistema rechaza el registro si la cantidad producida es cero o negativa, mostrando mensaje E-06.

El sistema rechaza el registro si la unidad de medida no corresponde al tipo de producto en RF-16, mostrando mensaje E-07.

El sistema rechaza el registro si ya existe un evento del mismo tipo para el mismo activo en la misma fecha, mostrando mensaje E-08.

El sistema ejecuta rollback completo ante fallos transaccionales (E-09), conservando el historial sin cambios.

El sistema impide la eliminación y modificación de eventos productivos ya registrados.

Cada operación exitosa queda registrada en el módulo de auditoría con: usuario, fecha/hora, activo, tipo de producto y cantidad.

El sistema responde con código HTTP 201 ante registro exitoso y con el código HTTP correspondiente ante cada tipo de error.

**Requerimientos no funcionales:**

Integridad: Los eventos productivos son inmutables una vez registrados. El sistema garantiza esta restricción mediante controles a nivel de base de datos (sin operaciones UPDATE/DELETE sobre eventos registrados).
Seguridad: Solo usuarios autorizados según RF-04 pueden registrar eventos. Validación RBAC obligatoria en backend.
Fiabilidad: El registro se ejecuta de forma completamente transaccional. Ante cualquier fallo, se garantiza rollback sin registros parciales.
Trazabilidad: Cada evento queda identificado con: activo, especie, tipo de producto, cantidad, unidad, fase productiva activa, fecha del evento, usuario responsable, fecha/hora de registro en sistema.
Escalabilidad: El sistema soporta múltiples registros productivos concurrentes por activo sin degradación de rendimiento.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-44 — Gestión del Estado del Activo Biológico

**Código Identificación:** RF-44 -- Versión -- 1.1

**Fuente:** Productor / Veterinario / Administrador

**Descripción:** El sistema debe gestionar y actualizar el estado operativo del activo biológico como punto de control centralizado y único, para activos individuales y poblacionales, durante todo su ciclo de vida.

PRINCIPIO DE CENTRALIZACIÓN OBLIGATORIA: Todo cambio de estado de un activo biológico en el sistema —independientemente del proceso que lo origine— debe ejecutarse exclusivamente a través de la lógica de gestión de estados definida en este requerimiento. Ningún módulo externo puede modificar directamente el campo de estado del activo. Los procesos de cierre del ciclo productivo (RF-38) y registro de bajas (RF-45) deben invocar explícitamente la interfaz de cambio de estado definida aquí para realizar las transiciones a CERRADO y BAJA respectivamente.

ESTADOS VÁLIDOS DEL ACTIVO BIOLÓGICO:
— ACTIVO: el activo está en producción o seguimiento normal.
— INACTIVO: el activo está temporalmente fuera de operación.
— EN_TRATAMIENTO: el activo se encuentra bajo intervención sanitaria.
— AISLADO: el activo ha sido separado por condiciones sanitarias o de manejo.
— CERRADO: el activo ha finalizado su ciclo productivo. Transición originada por RF-38.
— BAJA: el activo ha sido retirado definitivamente del sistema. Transición originada por RF-45.

REGLAS DE TRANSICIÓN DE ESTADO:
— Desde ACTIVO: puede transitar a INACTIVO, EN_TRATAMIENTO, AISLADO, CERRADO, BAJA.
— Desde INACTIVO: puede transitar a ACTIVO, EN_TRATAMIENTO, CERRADO, BAJA.
— Desde EN_TRATAMIENTO: puede transitar a ACTIVO, INACTIVO, AISLADO, CERRADO, BAJA.
— Desde AISLADO: puede transitar a ACTIVO, INACTIVO, EN_TRATAMIENTO, CERRADO, BAJA.
— Desde CERRADO: solo puede transitar a BAJA. No se permite retorno a estados operativos.
— Desde BAJA: no se permite ninguna transición. Estado final irreversible.

Cada activo debe tener exactamente un estado vigente en todo momento. El sistema mantiene historial completo e inmutable de todos los cambios de estado.

**Justificación:** El estado del activo biológico es el eje de control de toda la operación del sistema:
— Determina qué operaciones están disponibles sobre el activo.
— Restringe el registro de eventos biológicos, productivos y sanitarios.
— Governa la disponibilidad del activo para procesos financieros (M06).
— Mantiene la trazabilidad completa del ciclo de vida del activo.
La centralización en un único punto de control garantiza coherencia, elimina inconsistencias entre módulos y permite auditoría completa de todos los cambios.

**Precondiciones:** 1. El activo biológico debe existir en el sistema (RF-33).
2. El activo debe tener un estado actual definido y vigente.
3. El solicitante del cambio (usuario manual, RF-38 o RF-45) debe tener sesión activa (RF-02) y permisos para modificar el estado del activo (RF-04).
4. El activo no debe estar en estado BAJA (estado final irreversible).
5. Si el cambio es originado por RF-38 (→ CERRADO): el proceso RF-38 debe haber completado todas sus validaciones previas antes de invocar este requerimiento.
6. Si el cambio es originado por RF-45 (→ BAJA): el proceso RF-45 debe haber completado el registro del evento de baja antes de invocar este requerimiento para el cambio final de estado.

**Restricciones:** RESTRICCIONES DE TRANSICIÓN:
— Un activo solo puede tener un estado vigente en todo momento (restricción UNIQUE en base de datos).
— No se permite ninguna transición desde estado BAJA.
— Las transiciones desde estado CERRADO están limitadas exclusivamente a BAJA.
— No se permiten transiciones de estado no incluidas en la matriz de transiciones definida en la Descripción.
— No se permite el cambio de estado a un valor igual al estado actual (cambio redundante).

RESTRICCIONES DE INTEGRACIÓN (CENTRALIZACIÓN):
— Ningún módulo externo (incluyendo RF-38 y RF-45) puede modificar directamente el campo de estado del activo biológico en la base de datos. Toda modificación de estado debe pasar por la interfaz de cambio de estado de este requerimiento.
— RF-38 invoca este requerimiento para la transición → CERRADO, una vez completadas sus propias validaciones.
— RF-45 invoca este requerimiento para la transición → BAJA, una vez completado el registro del evento de baja.

RESTRICCIONES DE REGISTRO:
— Cada cambio de estado debe registrar obligatoriamente: estado_anterior, estado_nuevo, fecha_cambio, usuario_responsable, motivo_cambio y modulo_origen (MANUAL / RF-38 / RF-45).
— No se permite registrar cambios de estado con fecha futura.
— El historial de estados es inmutable (sin UPDATE ni DELETE sobre registros históricos).
— El campo motivo_cambio es obligatorio para todos los cambios de estado.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-04 — Gestión de permisos
RF-33 — Registro de Activos Biológicos
RF-35 — Gestión de Activos Individuales
RF-36 — Gestión de Activos Poblacionales
RF-38 — Cierre del Ciclo Productivo (proceso invocante para transición → CERRADO)
RF-45 — Registro de Bajas (proceso invocante para transición → BAJA)

**Actores:** Usuarios del sistema: Productor, Administrador del sistema, Veterinario (cambio manual).
Procesos invocantes: RF-38 (cierre de ciclo → CERRADO), RF-45 (registro de baja → BAJA).

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | (Obligatorio) Identificador del activo cuyo estado se va a cambiar. |
| tipo_activo | varchar(10) | (Obligatorio) INDIVIDUAL o POBLACIONAL. |
| estado_nuevo | varchar(20) | (Obligatorio) Estado destino. Debe ser un valor del catálogo de estados definidos: ACTIVO, INACTIVO, EN_TRATAMIENTO, AISLADO, CERRADO, BAJA. |
| fecha_cambio_estado | date | (Obligatorio) Fecha del cambio de estado. No puede ser futura. |
| motivo_cambio | text | (Obligatorio) Justificación del cambio de estado. Campo requerido para todos los cambios. |
| usuario_responsable_id | integer | (Obligatorio) Identificador del usuario o proceso que solicita el cambio (usuario manual, RF-38 o RF-45). |
| modulo_origen | varchar(20) | (Obligatorio) Identifica el origen del cambio: MANUAL (acción del usuario), RF-38 (cierre de ciclo), RF-45 (registro de baja). Permite trazabilidad del origen del cambio. |

**Proceso:**

FLUJO PRINCIPAL:

1. El solicitante (usuario o proceso RF-38/RF-45) invoca la interfaz de cambio de estado con los parámetros requeridos.

2. El sistema valida:
   a) Existencia del activo (RF-33) → si no existe: ERROR E-01.
   b) Que el activo no esté en estado BAJA → si está en BAJA: ERROR E-02.
   c) Que el estado_nuevo sea diferente al estado actual → si son iguales: ERROR E-03.
   d) Que la transición (estado_actual → estado_nuevo) esté permitida en la matriz de transiciones → si no es válida: ERROR E-04.
   e) Que la fecha_cambio_estado no sea futura → si es futura: ERROR E-05.
   f) Que el campo motivo_cambio esté completado → si está vacío: ERROR E-06.
   g) Que el módulo invocante (RF-38 o RF-45) haya completado sus propias validaciones previas antes de invocar este proceso → si no: ERROR E-07.

3. Si todas las validaciones son exitosas, el sistema ejecuta de forma transaccional:
   a) Cierra el registro de estado vigente (registra fecha_fin = fecha_cambio_estado).
   b) Crea el nuevo registro de estado como vigente (fecha_inicio = fecha_cambio_estado, estado = estado_nuevo).
   c) Actualiza el estado actual del activo.
   d) Registra el evento en auditoría: estado_anterior, estado_nuevo, fecha_cambio, usuario_responsable, motivo, modulo_origen.

4. El sistema retorna confirmación de la operación al solicitante.

CONTRATO DE INTEGRACIÓN CON RF-38 (→ CERRADO):
RF-38 invoca este proceso con: estado_nuevo='CERRADO', modulo_origen='RF-38', motivo='Cierre de ciclo productivo'. RF-38 no modifica directamente el estado del activo; delega esa responsabilidad exclusivamente a este proceso.

CONTRATO DE INTEGRACIÓN CON RF-45 (→ BAJA):
RF-45 invoca este proceso con: estado_nuevo='BAJA', modulo_origen='RF-45', motivo='Baja del activo: [tipo_baja]'. RF-45 no modifica directamente el estado del activo; delega esa responsabilidad exclusivamente a este proceso.




**Flujo alterno:**


E-01 | Activo inexistente:
  Código: HTTP 404
  Mensaje: 'El activo biológico con ID [id] no fue encontrado en el sistema.'
  Recuperación: Operación cancelada. El solicitante recibe el código de error.
  Estado final: Sin cambios en el sistema.

E-02 | Estado BAJA irreversible:
  Código: HTTP 409 / Error de negocio
  Mensaje: 'El activo [identificador] se encuentra en estado BAJA. No se permite modificar el estado de activos dados de baja definitivamente.'
  Recuperación: Operación cancelada. El solicitante recibe el código de error.
  Estado final: Sin cambios en el sistema. El activo permanece en BAJA.

E-03 | Estado redundante:
  Código: HTTP 409 / Error de negocio
  Mensaje: 'El activo ya se encuentra en estado [estado_nuevo]. No se realizó ningún cambio.'
  Recuperación: Operación cancelada sin error crítico. El estado actual no se modifica.
  Estado final: Sin cambios en el sistema.

E-04 | Transición de estado no permitida:
  Código: HTTP 422 / Error de negocio
  Mensaje: 'La transición de estado [estado_actual] → [estado_nuevo] no está permitida por las reglas del sistema. Transiciones válidas desde [estado_actual]: [lista de estados válidos].'
  Recuperación: El formulario permanece activo. El usuario puede seleccionar un estado válido.
  Estado final: Sin cambios en el sistema.

E-05 | Fecha futura:
  Código: HTTP 422 / Error de validación
  Mensaje: 'La fecha del cambio de estado [fecha_cambio] es posterior a la fecha actual del sistema. No se permiten registros con fecha futura.'
  Recuperación: El campo fecha se resalta. El usuario puede corregirlo y reintentar.
  Estado final: Sin cambios en el sistema.

E-06 | Motivo vacío:
  Código: HTTP 422 / Error de validación
  Mensaje: 'El campo motivo del cambio de estado es obligatorio. Ingrese una justificación para continuar.'
  Recuperación: El campo motivo se resalta. El usuario debe completarlo y reintentar.
  Estado final: Sin cambios en el sistema.

E-07 | Módulo invocante sin validaciones previas:
  Código: HTTP 422 / Error de negocio
  Mensaje: 'El proceso [modulo_origen] no completó las validaciones previas requeridas antes de invocar el cambio de estado. Operación rechazada.'
  Recuperación: El módulo invocante debe completar su propio flujo antes de reinvocar.
  Estado final: Sin cambios en el sistema.

E-08 | Fallo transaccional:
  Código: HTTP 500
  Mensaje: 'El cambio de estado no pudo completarse por un error interno del sistema. El activo conserva su estado anterior. Intente nuevamente.'
  Recuperación: Rollback completo. El activo conserva su estado anterior. El fallo queda registrado en auditoría.
  Estado final: El activo permanece en su estado anterior sin inconsistencias. Sin registros parciales.

**Salida:**

Estado del activo actualizado de forma consistente y registrado en el historial.
Registro completo del cambio: estado_anterior, estado_nuevo, fecha_cambio, usuario_responsable, motivo, modulo_origen.
Confirmación de la operación con código HTTP 200 al solicitante.
Disponibilidad inmediata del estado actualizado para todos los módulos dependientes (M03, M04, M06, M08).

**Postcondiciones:**

El activo tiene exactamente un estado vigente.
El historial de estados contiene el nuevo registro, incluyendo modulo_origen.
El estado anterior tiene fecha_fin registrada.
El nuevo estado tiene fecha_inicio registrada.
La operación queda registrada en auditoría con todos los campos requeridos.
Los módulos dependientes (M03, M04, M06, M08) reflejan el estado actualizado.

**Criterios de aceptación:**

El sistema permite el cambio de estado cuando el activo existe, no está en BAJA, la transición es válida según la matriz de transiciones, la fecha no es futura, el motivo está completado y el módulo invocante ha cumplido sus precondiciones.

El sistema rechaza todo cambio de estado en activos con estado BAJA, sin excepción y sin importar el módulo invocante (E-02).

El sistema rechaza transiciones no incluidas en la matriz de transiciones (E-04). En particular: CERRADO → ACTIVO, CERRADO → INACTIVO, CERRADO → EN_TRATAMIENTO, CERRADO → AISLADO, BAJA → cualquier estado.

El sistema rechaza cambios redundantes (estado_nuevo igual al estado actual) (E-03).

El sistema exige el campo motivo como obligatorio antes de registrar cualquier cambio (E-06).

Los cambios de estado originados desde RF-38 (→ CERRADO) y RF-45 (→ BAJA) se registran en el historial con modulo_origen = 'RF-38' y 'RF-45' respectivamente, verificando que el cambio pasó por la lógica centralizada de este requerimiento.

El sistema garantiza que RF-38 y RF-45 no puedan modificar directamente el estado del activo sin invocar este proceso (restricción a nivel de arquitectura/base de datos).

El sistema ejecuta rollback completo ante fallos transaccionales (E-08), conservando el estado anterior del activo sin inconsistencias.

El historial de estados es inmutable: no se permiten DELETE ni UPDATE sobre registros de estado ya registrados.

El sistema mantiene un único estado vigente por activo en todo momento (restricción de unicidad).

**Requerimientos no funcionales:**

Integridad: Un único estado activo por activo garantizado por restricción UNIQUE en base de datos. El historial de estados es inmutable.
Trazabilidad: Todos los cambios de estado son auditables, incluyendo módulo de origen, usuario y fecha.
Fiabilidad: Operación completamente transaccional. Ante fallos: rollback total garantizado.
Seguridad: Validación de permisos RBAC (RF-04). Los procesos RF-38 y RF-45 deben autenticarse para invocar la interfaz de cambio de estado.
Consistencia: Ningún módulo externo puede modificar directamente el campo de estado del activo. El cumplimiento de esta restricción debe verificarse a nivel de arquitectura.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-45 — Registro de Bajas del Activo Biológico

**Código Identificación:** RF-45 -- Versión -- 1.0

**Fuente:** Productor / Veterinario / Administrador

**Descripción:** El sistema debe permitir registrar la baja definitiva de un activo biológico, tanto individual como poblacional, cuando este deja de existir dentro del sistema productivo.

La baja representa la salida permanente del activo del sistema y puede deberse a diferentes causas, tales como:

Muerte

Venta

Sacrificio

Pérdida

Descarte sanitario

Finalización productiva con retiro físico

Al registrar una baja:

El activo cambia su estado a BAJA

El activo deja de estar disponible para cualquier operación futura

Se registra un evento de baja con información completa del contexto

Se mantiene el historial completo del activo para trazabilidad

La baja es una operación irreversible dentro del sistema.

**Justificación:** El registro de bajas es necesario para:

Mantener la consistencia del inventario biológico

Evitar el uso de activos que ya no existen

Registrar pérdidas o salidas económicas del sistema productivo

Soportar la valoración contable (M06)

Garantizar trazabilidad completa del ciclo de vida

**Precondiciones:** El activo biológico debe existir

El activo debe estar en estado diferente de BAJA

El usuario debe tener sesión activa

El usuario debe tener permisos para registrar bajas

El activo no debe tener una baja previamente registrada

**Restricciones:** No se permite registrar baja sobre un activo ya dado de baja

La operación es irreversible

La fecha de baja no puede ser futura

La fecha de baja debe ser coherente con el historial del activo

Se debe registrar obligatoriamente:

tipo de baja

fecha de baja

motivo

usuario responsable

En activos tipo poblacional:

se debe permitir baja total o parcial

El activo dado de baja no puede:

recibir nuevos eventos

cambiar de estado

participar en procesos productivos

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios

RF-33 — Registro de Activos Biológicos

RF-44 — Gestión del Estado del Activo Biológico

RF-38 — Cierre del Ciclo Productivo

**Actores:** Productor, Administrador del sistema, Veterinario

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador del activo |
| tipo_activo | string | INDIVIDUAL o POBLACIONAL |
| tipo_baja | string | Tipo de baja (muerte, venta, sacrificio, etc.) |
| fecha_baja | date | Fecha en la que ocurre la baja |
| motivo_baja | string | Justificación detallada |
| cantidad_afectada | integer | Cantidad afectada (solo para lotes en baja parcial) |
| usuario_responsable_id | integer | Usuario que registra la baja |

**Proceso:**

El usuario accede al activo biológico y selecciona la opción "Registrar baja".

El sistema muestra la información actual del activo (estado, cantidad, fase).

El usuario ingresa los datos de la baja.

El sistema valida:

existencia del activo

estado actual (no debe ser BAJA)

coherencia del tipo de activo

fecha de baja válida

tipo de baja válido

Si el activo es individual:

se registra la baja completa

se cambia el estado a BAJA

Si el activo es poblacional:

el sistema valida la cantidad afectada

si la baja es total:

se cambia el estado del activo poblacional a BAJA

si la baja es parcial:

se descuenta la cantidad del activo poblacional

se mantiene el activo poblacional activo

El sistema registra el evento de baja en el historial

Se actualiza el estado del activo según corresponda

Se registra la operación en auditoría

El sistema confirma la operación al usuario

**Flujo alterno:**

Activo no encontrado:

El sistema no localiza el activo_biologico_id en la base de datos de activos registrados.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error de identificación: El activo biológico solicitado no existe. Verifique el ID antes de proceder con la baja."

Intento de baja sobre activo ya retirado:

El usuario intenta registrar una baja sobre un activo que ya tiene el estado BAJA. Debido a que la operación es irreversible, no puede duplicarse.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Operación inválida: El activo ya ha sido dado de baja previamente. No se pueden registrar múltiples salidas definitivas para el mismo individuo o activo poblacional."

Inconsistencia en la fecha de baja:

El usuario ingresa una fecha futura o una fecha anterior al último evento registrado (ej: intentar dar de baja un animal con fecha de ayer, pero que hoy registró un pesaje).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error cronológico: La fecha de baja no puede ser futura ni anterior al último registro de actividad registrado el [FECHA_ULTIMO_EVENTO]."

Cantidad de baja superior a la existencia (Lotes):

En una baja parcial de un activo poblacional, el usuario ingresa una cantidad_afectada mayor al número de individuos actuales en el activo poblacional ($Cantidad_{Baja} > Cantidad_{Actual}$).

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Inconsistencia de inventario: La cantidad a dar de baja ([CANTIDAD_AFECTADA]) es superior a la existencia actual del activo poblacional ([CANTIDAD_ACTUAL])."

Falta de datos obligatorios:

El usuario intenta procesar la baja sin seleccionar el tipo_baja o sin escribir el motivo_baja.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Información incompleta: El tipo de baja y la justificación son campos obligatorios para garantizar la trazabilidad del descarte."

Acceso denegado (Restricción de Rol):

Un usuario con un rol no administrativo o no veterinario intenta forzar el registro de una baja.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Privilegios insuficientes: Solo el Productor, el Veterinario o el Administrador están autorizados para retirar activos del sistema productivo."

Error en la persistencia transaccional:

El sistema falla al intentar actualizar el estado del activo y descontar la cantidad en el activo poblacional de forma simultánea.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Fallo crítico de integridad: No se pudo completar la transacción de baja. Se ha realizado un rollback automático para evitar inconsistencias en el inventario."

**Salida:**

Registro del evento de baja

Estado actualizado del activo

Actualización de cantidad (en caso de lotes)

Confirmación de la operación

Disponibilidad del registro para módulos financieros y analíticos

**Postcondiciones:**

El activo queda en estado BAJA si la baja es total

El activo no puede ser utilizado en nuevas operaciones

El historial del activo contiene el registro de baja

En lotes con baja parcial:

la cantidad del activo poblacional queda actualizada

el activo poblacional continúa activo

La información queda disponible para procesos contables (M06)

**Criterios de aceptación:**

El sistema permite registrar la baja de un activo existente

El sistema rechaza la baja si el activo no existe

El sistema rechaza la baja si el activo ya está en estado BAJA

El sistema valida correctamente la fecha de baja

El sistema registra el tipo y motivo de la baja

El sistema cambia el estado a BAJA en bajas totales

El sistema actualiza correctamente la cantidad en bajas parciales

El sistema impide operaciones posteriores sobre activos dados de baja

El sistema registra el evento en el historial

El sistema registra la operación en auditoría

**Requerimientos no funcionales:**

Integridad

No se permite reutilizar activos dados de baja

Trazabilidad

Todas las bajas deben quedar registradas con detalle

Fiabilidad

La operación debe ser transaccional

Seguridad

Solo usuarios autorizados pueden registrar bajas

Consistencia

La información debe reflejar correctamente la salida del activo

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-46 — Consulta de Historial del Activo Biológico

**Código Identificación:** RF-46 -- Versión -- 1.1

**Fuente:** Productor / Veterinario / Administrador

**Descripción:** El sistema debe permitir consultar el historial del activo biológico (individual o poblacional), consolidando en una única consulta cronológica todos los registros que conforman la línea de vida del activo en el módulo M02.

NOTA ESTRUCTURAL: El evaluador identificó que este requerimiento requeriría una dependencia de un RF de historial general del sistema definido en M09. Dado que ese RF no existe aún en el sistema, este requerimiento define las reglas de historial específicas para el módulo M02. Cuando se defina el RF de historial general en M09, este requerimiento deberá alinearse con él.

DEFINICIÓN FORMAL DE 'HISTORIAL COMPLETO DEL ACTIVO (M02)': Es el conjunto ordenado cronológicamente de todos los registros generados por el activo biológico en el módulo M02, incluyendo sin excepción:

Categoría ESTADO: cambios de estado del activo (RF-44), con estado_anterior, estado_nuevo, fecha, usuario y modulo_origen.
Categoría FASE: cambios de fases del ciclo productivo (RF-37), con nombre_fase, fecha_inicio y fecha_fin de cada fase.
Categoría EVENTO_BIOLOGICO: eventos biológicos base (RF-39).
Categoría CRECIMIENTO: eventos de crecimiento (RF-40), con variables de medición y valores registrados.
Categoría SANITARIO: eventos sanitarios (RF-41).
Categoría REPRODUCTIVO: eventos reproductivos (RF-42).
Categoría PRODUCTIVO: eventos productivos (RF-43), con tipo_producto, cantidad y unidad.
Categoría BAJA: registros de baja (RF-45).
Categoría TRANSFERENCIA: transferencias internas (RF-48), cuando aplique.

ALINEACIÓN CON MÓDULOS FUENTE:
— RF-37: el historial incluye la fase activa al momento de cada evento registrado, permitiendo correlacionar eventos con fases.
— RF-40: los eventos de crecimiento incluyen las variables de medición y sus valores.
— RF-43: los eventos productivos incluyen tipo de producto, cantidad y unidad de medida.

La información se presenta en orden cronológico ascendente por fecha de evento como orden por defecto. El historial es de solo lectura: no se permite ninguna modificación desde esta interfaz. Los registros del historial son inmutables.

**Justificación:** El historial del activo es el mecanismo de trazabilidad central del módulo M02:
— Permite analizar la evolución biológica, sanitaria y productiva del activo.
— Soporta decisiones operativas y sanitarias con base en datos históricos.
— Sirve como base para valoración financiera (M06) y reportes analíticos (M08).
— Garantiza la auditabilidad completa del ciclo de vida del activo.

**Precondiciones:** 1. El activo biológico debe existir en el sistema (RF-33).
2. El usuario debe tener sesión activa (RF-02).
3. El usuario debe tener permisos de consulta sobre el activo según su rol (RF-04):
   — Productor: puede consultar el historial de sus propios activos.
   — Veterinario: puede consultar el historial de activos de la finca asignada.
   — Administrador: puede consultar el historial de todos los activos del sistema.
4. El activo debe tener al menos un registro en el sistema.

**Restricciones:** INMUTABILIDAD Y AUDITORÍA:
— El historial es de solo lectura; no se permite ninguna operación de escritura, modificación o eliminación desde esta interfaz.
— Los registros del historial son inmutables: no se pueden alterar después de ser generados.
— La consulta del historial queda registrada en el módulo de auditoría (quién consultó, cuándo, qué activo).

CONTROL DE ACCESO:
— La consulta está limitada por los permisos del rol del usuario (RBAC – RF-04).
— El sistema no debe exponer registros de categorías no autorizadas para el rol del usuario.

PAGINACIÓN:
— La paginación de resultados se rige por el estándar de paginación definido para el sistema (referencia: M01). El comportamiento por defecto (tamaño de página, parámetros) sigue ese estándar.

RENDIMIENTO:
— El sistema debe responder la consulta sin filtros en un tiempo máximo de 3 segundos para activos con hasta 500 registros en el historial.
— Para activos con más de 500 registros, la paginación es obligatoria.

CONSISTENCIA:
— Los datos mostrados deben ser consistentes con los registros originales de cada módulo fuente (RF-37, RF-39 a RF-45, RF-48).
— El historial no puede ocultar eventos registrados dentro de los permisos del usuario.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-04 — Gestión de permisos (control de acceso por rol)
RF-33 — Registro de Activos Biológicos (fuente: datos base del activo)
RF-37 — Gestión de Fases del Ciclo Productivo (fuente: categoría FASE y correlación con eventos)
RF-39 — Registro de Eventos Biológicos (fuente: categoría EVENTO_BIOLOGICO)
RF-40 — Registro de Eventos de Crecimiento (fuente: categoría CRECIMIENTO)
RF-41 — Registro de Eventos Sanitarios (fuente: categoría SANITARIO)
RF-42 — Registro de Eventos Reproductivos (fuente: categoría REPRODUCTIVO)
RF-43 — Registro de Eventos Productivos (fuente: categoría PRODUCTIVO)
RF-44 — Gestión del Estado del Activo (fuente: categoría ESTADO)
RF-45 — Registro de Bajas (fuente: categoría BAJA)
RF-48 — Transferencia Interna (fuente: categoría TRANSFERENCIA, cuando aplique)
M01 — Módulo de Usuarios (referencia: estándar de paginación del sistema)

**Actores:** Productor, Administrador del sistema, Veterinario

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | (Obligatorio) Identificador del activo cuyo historial se desea consultar. |
| tipo_activo | varchar(10) | (Obligatorio) INDIVIDUAL o POBLACIONAL. |
| fecha_inicio | date | (Opcional) Límite inferior del rango de fecha para filtro. Si se suministra, debe ser anterior o igual a fecha_fin. |
| fecha_fin | date | (Opcional) Límite superior del rango de fecha para filtro. Si se suministra, debe ser posterior o igual a fecha_inicio. |
| categoria_evento | varchar(30) | (Opcional) Filtro por categoría: ESTADO, FASE, EVENTO_BIOLOGICO, CRECIMIENTO, SANITARIO, REPRODUCTIVO, PRODUCTIVO, BAJA, TRANSFERENCIA. |
| pagina | integer | (Opcional) Número de página. Sigue el estándar de paginación de M01. Default: 1. |
| usuario_consulta_id | integer | (Obligatorio) Identificador del usuario que realiza la consulta. Determina el nivel de visibilidad según su rol (RF-04). |

**Proceso:**

FLUJO PRINCIPAL:

1. El usuario accede al módulo de activos biológicos, selecciona un activo y elige la opción 'Consultar historial'.

2. El sistema valida:
   a) Existencia del activo (RF-33) → si no existe: ERROR E-01.
   b) Permisos del usuario para consultar el historial del activo según su rol (RF-04) → si no tiene permisos: ERROR E-02.
   c) Si se suministran filtros de fecha: que fecha_inicio no sea posterior a fecha_fin → si no cumple: ERROR E-03.

3. El sistema obtiene los registros históricos de cada módulo fuente:
   — Estados del activo (RF-44): todos los cambios de estado registrados.
   — Fases productivas (RF-37): todas las fases con fecha_inicio, fecha_fin y estado de la fase al momento de cada evento.
   — Eventos biológicos (RF-39 a RF-43): todos los eventos de cada categoría.
   — Bajas (RF-45) y Transferencias (RF-48): si aplican para el activo.

4. El sistema aplica los filtros ingresados (fecha_inicio, fecha_fin, categoria_evento) si fueron suministrados.

5. El sistema ordena todos los registros cronológicamente por fecha de evento (ascendente por defecto).

6. El sistema aplica la paginación según el estándar de M01.

7. El sistema registra la consulta en el módulo de auditoría (usuario, fecha/hora, activo consultado).

8. El sistema presenta el historial consolidado con el formato de salida definido.

**Flujo alterno:**


E-01 | Activo inexistente:
  Código: HTTP 404
  Mensaje: 'El activo biológico con ID [id] no fue encontrado en el sistema.'
  Recuperación: Se cancela la consulta. El usuario es redirigido a la lista de activos.
  Estado final: Sin cambios. Ningún dato es expuesto.

E-02 | Sin permisos de consulta:
  Código: HTTP 403
  Mensaje: 'No tiene permisos para consultar el historial de este activo.'
  Recuperación: Se cancela la consulta. El usuario es redirigido sin exponer información del activo.
  Estado final: Sin cambios.

E-03 | Filtro de fecha inválido:
  Código: HTTP 422 / Error de validación
  Mensaje: 'La fecha de inicio del filtro [fecha_inicio] no puede ser posterior a la fecha de fin [fecha_fin]. Corrija el rango de fechas.'
  Recuperación: El formulario de filtros permanece activo con los campos de fecha resaltados. El usuario puede corregir y reintentar.
  Estado final: No se ejecuta ninguna consulta.

E-04 | Sin registros en el rango/categoría seleccionados:
  Código: HTTP 200 (no es error crítico, resultado vacío válido)
  Mensaje: 'No se encontraron eventos para el activo [identificador] con los filtros aplicados. Puede ampliar el rango de fechas o cambiar la categoría de evento.'
  Recuperación: El sistema muestra el mensaje informativo y permite al usuario modificar los filtros.
  Estado final: Sin cambios. La ausencia de resultados no es un error del sistema.

E-05 | Fallo de carga del historial:
  Código: HTTP 500
  Mensaje: 'El historial del activo no pudo cargarse en este momento. Intente nuevamente. Si el problema persiste, contacte al administrador.'
  Recuperación: El sistema muestra el mensaje de error con opción de reintento. Los filtros ingresados se conservan.
  Estado final: Sin cambios en el sistema. El fallo queda registrado en auditoría.

**Salida:**

FORMATO DE SALIDA ESTRUCTURADO:
El historial se presenta como una lista paginada de registros. Cada registro contiene obligatoriamente:

Campo              | Tipo         | Descripción
categoria          | varchar(30)  | Categoría del evento: ESTADO, FASE, EVENTO_BIOLOGICO, CRECIMIENTO, SANITARIO, REPRODUCTIVO, PRODUCTIVO, BAJA, TRANSFERENCIA.
fecha_evento       | datetime     | Fecha y hora del evento.
descripcion        | text         | Descripción legible del evento.
detalle_especifico | json/text    | Datos propios de la categoría (ej: para PRODUCTIVO: tipo_producto, cantidad, unidad; para ESTADO: estado_anterior, estado_nuevo; para FASE: nombre_fase, duración).
usuario_responsable| varchar(100) | Nombre del usuario o proceso que generó el evento.
modulo_origen      | varchar(20)  | Módulo del sistema que generó el registro.

Información de paginación (según estándar M01): total_registros, pagina_actual, total_paginas, registros_por_pagina.

**Postcondiciones:**

El usuario visualiza el historial completo (o filtrado) del activo en orden cronológico.
La información es consistente con los registros originales de cada módulo fuente.
Ningún dato del sistema fue modificado como resultado de la consulta.
La consulta queda registrada en el módulo de auditoría.

**Criterios de aceptación:**

El sistema presenta el historial de un activo existente con al menos un registro, consolidando todas las categorías definidas.

El sistema rechaza la consulta si el activo no existe, retornando HTTP 404 con mensaje E-01.

El sistema rechaza la consulta si el usuario no tiene permisos para el activo, retornando HTTP 403 con mensaje E-02, sin exponer ningún dato.

El sistema muestra exclusivamente los registros que corresponden al nivel de visibilidad del rol del usuario.

El sistema incluye en el historial: cambios de estado (RF-44 con modulo_origen), fases productivas (RF-37 con correlación de fase activa en eventos), eventos biológicos (RF-39), de crecimiento con variables (RF-40), sanitarios (RF-41), reproductivos (RF-42), productivos con tipo/cantidad/unidad (RF-43), bajas (RF-45) y transferencias (RF-48).

El historial se presenta en orden cronológico ascendente por fecha de evento por defecto.

El sistema aplica paginación obligatoria para activos con más de 500 registros, siguiendo el estándar de M01.

El sistema responde la consulta sin filtros en un máximo de 3 segundos para activos con hasta 500 registros.

El sistema aplica correctamente los filtros por rango de fechas y por categoría de evento cuando son suministrados.

El sistema rechaza filtros con fecha_inicio posterior a fecha_fin, retornando HTTP 422 con mensaje E-03.

El sistema retorna HTTP 200 con mensaje informativo (E-04) cuando no existen registros para el rango o categoría seleccionados.

El sistema no permite ninguna operación de escritura o modificación desde la interfaz del historial.

Cada registro del historial incluye los campos obligatorios definidos en la sección Salida.

La consulta queda registrada en el módulo de auditoría.

**Requerimientos no funcionales:**

Usabilidad: La información debe presentarse con indicadores visuales diferenciados por categoría de evento. Navegación intuitiva entre páginas del historial.
Rendimiento: Máximo 3 segundos para activos con hasta 500 registros. Paginación obligatoria para volúmenes mayores.
Integridad: Los datos mostrados son consistentes con los registros originales. El historial es inalterable desde esta interfaz.
Seguridad: Acceso controlado por RBAC (RF-04). Cada consulta se registra en auditoría.
Trazabilidad: El historial es completo, inmutable e incluye el módulo de origen de cada registro.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-47 — Ficha Integral del Activo Biológico

**Código Identificación:** RF-47 -- Versión -- 1.1

**Fuente:** Productor / Veterinario / Administrador

**Descripción:** El sistema debe permitir consultar la ficha integral de un activo biológico (individual o poblacional), consolidando en una única vista de solo lectura la información operativa, sanitaria, productiva y analítica más relevante del activo en el momento de la consulta.

━━━━ DEFINICIÓN FUNCIONAL (REQUERIMIENTOS OBLIGATORIOS) ━━━━
Los siguientes elementos son requisitos funcionales del sistema, no recomendaciones de diseño:

A. DATOS MÍNIMOS OBLIGATORIOS QUE LA FICHA DEBE CONSOLIDAR:

Sección 1 — Identificación:
  • identificador del activo (RF-33)
  • tipo (INDIVIDUAL / POBLACIONAL) (RF-33)
  • especie (RF-33)
  • fecha de registro en el sistema (RF-33)

Sección 2 — Estado y fase actual:
  • estado actual del activo (RF-44) ← dato en tiempo real al momento de la consulta
  • fase productiva activa (RF-37) ← dato en tiempo real al momento de la consulta

Sección 3 — Ubicación:
  • infraestructura productiva actualmente asociada (RF-34)

Sección 4 — Datos biológicos:
  • edad o tiempo en sistema (calculado desde fecha de registro)
  • peso actual o biomasa estimada cuando el activo tenga evento de crecimiento registrado (RF-40)

Sección 5 — Eventos recientes (últimos 5 por categoría):
  • Sanitarios (RF-41): tipo de evento y fecha
  • Productivos (RF-43): tipo de producto, cantidad y fecha
  • Crecimiento (RF-40): variable de medición, valor y fecha
  • Reproductivos (RF-42): tipo de evento y fecha

Sección 6 — Indicadores básicos (RF-51):
  • indicadores zootécnicos disponibles para la especie y fase del activo

Sección 7 — Solo para activos tipo POBLACIONAL:
  • cantidad actual de individuos
  • densidad (calculada con base en RF-34)
  • fecha de inicio del activo poblacional

Sección 8 — Accesos directos funcionales:
  • Historial completo → RF-46
  • Registrar evento → RF-39 a RF-43
  • Cambiar estado → RF-44
  • Registrar baja → RF-45

━━━━ REGLAS DE SINCRONIZACIÓN ENTRE MÓDULOS FUENTE ━━━━
Los datos de las Secciones 2 (estado/fase), 3 (ubicación), 5 (eventos recientes) y 6 (indicadores) son consultados en tiempo real al cargar la ficha. El sistema garantiza que la información presentada en cada sección corresponda al estado más reciente del módulo fuente en el momento de la consulta.

REGLA DE INCONSISTENCIA DETECTADA: Si al consolidar los datos el sistema detecta una inconsistencia entre módulos fuente (ej. estado=CERRADO pero fase=PRODUCCIÓN aún activa), el sistema debe:
a) Mostrar la ficha completa con los datos disponibles.
b) Mostrar una advertencia visible al usuario en la sección afectada: 'Se detectó una inconsistencia en [sección]. Verifique el estado o la fase del activo.'
c) No bloquear la visualización de la ficha.

━━━━ CRITERIO DE DISEÑO (NO ES REQUERIMIENTO FUNCIONAL) ━━━━
La distribución visual de las secciones (disposición de columnas, colores, iconografía) es una decisión de diseño de la capa de presentación, fuera del alcance de este requerimiento funcional.

**Justificación:** La ficha integral permite:
Visión rápida y consolidada del estado operativo del activo.
Toma de decisiones en campo con información actualizada y consistente.
Reducción de la navegación en el sistema al centralizar accesos a funcionalidades relacionadas.
Punto de entrada único para la gestión completa del activo.

**Precondiciones:** 1. El activo biológico debe existir en el sistema (RF-33).
2. El usuario debe tener sesión activa (RF-02) y permisos de consulta para el activo según su rol (RF-04).
3. El activo debe tener al menos el registro base (Sección 1 – Identificación). Las demás secciones pueden estar vacías sin impedir la visualización de la ficha.

**Restricciones:** RESTRICCIONES FUNCIONALES:
— La ficha es de solo lectura. No permite edición directa de ningún campo.
— Solo se muestran los campos autorizados según el rol del usuario (RBAC – RF-04).
— Para activos tipo POBLACIONAL: la Sección 7 es obligatoria. Los campos de Sección 4 (peso individual) no aplican; se reemplazan por biomasa agregada si está disponible.
— La Sección 8 (accesos directos) solo muestra las acciones para las que el usuario tiene permisos (RF-04).

REGLAS DE SINCRONIZACIÓN (obligatorias en implementación):
— Los datos de las Secciones 2, 3, 5 y 6 deben reflejar el estado en tiempo real de sus módulos fuente en el momento de la consulta.
— Si RF-44 y RF-37 presentan datos inconsistentes (ej. estado y fase incompatibles), el sistema muestra ambos con indicador de advertencia, sin bloquear la ficha ni ocultar datos.
— Si RF-51 no devuelve indicadores para la especie/fase del activo, la Sección 6 muestra: 'No hay indicadores disponibles para la fase y especie actuales.'

COMPORTAMIENTO ANTE DATOS INCOMPLETOS O NO DISPONIBLES:
— Si una sección no tiene datos porque aún no se han registrado (ej. sin eventos productivos): la sección muestra 'Sin información registrada.' Sin error.
— Si una sección no se puede cargar por fallo de un módulo fuente: la sección muestra 'Información no disponible. [Actualizar]'. Las demás secciones se cargan normalmente.
— No se deben mostrar secciones en blanco sin indicador descriptivo.

**Prioridad:** [ ] Alta/Must  [X] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-04 — Gestión de permisos (visibilidad de secciones y accesos directos por rol)
RF-33 — Registro de Activos Biológicos (Sección 1: Identificación)
RF-34 — Asociación a infraestructura (Sección 3: Ubicación)
RF-37 — Fases del ciclo productivo (Sección 2: fase activa)
RF-39 a RF-43 — Eventos biológicos (Sección 5: eventos recientes)
RF-44 — Estado del activo (Sección 2: estado actual)
RF-45 — Registro de Bajas (Sección 8: acceso directo)
RF-46 — Historial del activo (Sección 8: acceso directo)
RF-51 — Indicadores zootécnicos (Sección 6)

**Actores:** Productor, Administrador del sistema, Veterinario

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | (Obligatorio) Identificador del activo cuya ficha se desea consultar. |
| tipo_activo | varchar(10) | (Obligatorio) INDIVIDUAL o POBLACIONAL. Determina qué secciones aplican (ej. Sección 7 solo para POBLACIONAL). |
| usuario_consulta_id | integer | (Obligatorio) Identificador del usuario. Determina el nivel de visibilidad de secciones y accesos directos según rol (RF-04). |

**Proceso:**

FLUJO PRINCIPAL:

1. El usuario accede al módulo de activos biológicos y selecciona un activo.

2. El sistema valida:
   a) Existencia del activo (RF-33) → si no existe: ERROR E-01.
   b) Permisos de consulta del usuario (RF-04) → si no tiene permisos: ERROR E-02.

3. El sistema consulta, en paralelo, los módulos fuente de cada sección:
   — Sección 1: datos base del activo (RF-33).
   — Sección 2: estado actual (RF-44) + fase productiva activa (RF-37).
   — Sección 3: infraestructura asociada (RF-34).
   — Sección 4: último evento de crecimiento (RF-40) para peso/biomasa.
   — Sección 5: últimos 5 eventos por categoría (RF-39 a RF-43).
   — Sección 6: indicadores zootécnicos (RF-51).
   — Sección 7 (solo POBLACIONAL): cantidad actual, densidad (cálculo con RF-34 y RF-33).

4. Para cada sección, el sistema evalúa el resultado:
   — Si el módulo fuente devuelve datos: se incluyen en la sección.
   — Si no hay datos registrados para la sección: se muestra 'Sin información registrada.'
   — Si el módulo fuente falla al responder: se muestra 'Información no disponible. [Actualizar]' en esa sección. Las demás secciones siguen cargando normalmente.

5. VERIFICACIÓN DE CONSISTENCIA ENTRE MÓDULOS FUENTE:
   El sistema evalúa la consistencia entre los datos recibidos:
   — Si estado (RF-44) y fase activa (RF-37) son incompatibles (ej. CERRADO + fase PRODUCCIÓN vigente): muestra advertencia en Secciones 2.
   — Si las fechas de eventos recientes (Sección 5) son anteriores a la fecha de registro del activo: muestra advertencia de inconsistencia.
   Las advertencias no bloquean la visualización de la ficha.

6. El sistema aplica el filtro de visibilidad por rol (RF-04): oculta los campos o secciones no autorizados para el rol del usuario.

7. El sistema presenta la ficha consolidada al usuario.

**Flujo alterno:**

E-01 | Activo inexistente:
  Código: HTTP 404
  Mensaje: 'El activo biológico con ID [id] no fue encontrado en el sistema.'
  Recuperación: Se cancela la carga de la ficha. El usuario es redirigido a la lista de activos.
  Estado final: Sin cambios. Ningún dato es expuesto.

E-02 | Sin permisos de consulta:
  Código: HTTP 403
  Mensaje: 'No tiene permisos para visualizar la ficha de este activo.'
  Recuperación: Se cancela la carga sin exponer ningún dato del activo.
  Estado final: Sin cambios.

E-03 | Módulo fuente no disponible (fallo parcial):
  Código: HTTP 200 (la ficha se carga parcialmente, no es un error crítico)
  Mensaje en la sección afectada: 'La sección [nombre_sección] no pudo cargarse en este momento. [Actualizar sección]'
  Recuperación: Las demás secciones se cargan y muestran con normalidad. El usuario puede intentar actualizar la sección específica sin recargar toda la ficha.
  Estado final: La ficha se muestra con los datos disponibles. Ningún dato del activo es modificado.

E-04 | Inconsistencia entre módulos fuente:
  Código: HTTP 200 (advertencia, no error)
  Mensaje en la sección afectada: 'Se detectó una inconsistencia en los datos del activo: [descripción de la inconsistencia]. Se recomienda revisar el [módulo afectado].'
  Recuperación: La ficha se muestra completa con los datos de ambos módulos fuente y la advertencia visible. Los accesos directos siguen disponibles.
  Estado final: Ningún dato es modificado. El usuario puede usar los accesos directos para corregir la inconsistencia desde el módulo correspondiente.

E-05 | Fallo total de carga:
  Código: HTTP 500
  Mensaje: 'La ficha del activo no pudo cargarse. Intente nuevamente. Si el problema persiste, contacte al administrador.'
  Recuperación: El usuario puede reintentar la carga completa.
  Estado final: Sin cambios en el sistema. El fallo queda registrado en auditoría.

**Salida:**

Ficha integral del activo presentada en las 8 secciones funcionales definidas en la Descripción, con:
— Datos actualizados de cada módulo fuente.
— Indicadores de 'Sin información registrada' en secciones sin datos.
— Indicadores de 'Información no disponible' en secciones con fallo de carga.
— Advertencias de inconsistencia cuando apliquen.
— Accesos directos habilitados según permisos del usuario (RF-04).

**Postcondiciones:**

El usuario visualiza la ficha integral del activo con información actualizada.
Los datos de cada sección son consistentes con el estado más reciente de su módulo fuente.
Ningún dato del sistema fue modificado.
El activo puede ser gestionado desde los accesos directos habilitados según el rol del usuario.

**Criterios de aceptación:**

El sistema muestra la ficha con las 8 secciones definidas para un activo con registro completo.

El sistema muestra 'Sin información registrada' en secciones sin datos (ej. sin eventos sanitarios), sin generar error ni ocultar la sección.

El sistema carga la ficha parcialmente cuando un módulo fuente falla, mostrando las secciones disponibles y marcando la sección afectada con 'Información no disponible. [Actualizar]'.

El sistema muestra advertencia de inconsistencia cuando detecta datos contradictorios entre módulos fuente (ej. estado CERRADO con fase productiva aún activa), sin bloquear la visualización.

El sistema rechaza la consulta si el activo no existe, retornando HTTP 404 con mensaje E-01.

El sistema rechaza la consulta si el usuario no tiene permisos, retornando HTTP 403 con mensaje E-02, sin exponer ningún dato.

La Sección 2 (estado/fase) refleja el estado más reciente de RF-44 y RF-37 en el momento de la consulta.

La Sección 7 (datos poblacionales) es mostrada exclusivamente para activos tipo POBLACIONAL y omitida para activos INDIVIDUALES.

Los accesos directos de la Sección 8 solo están habilitados para las acciones que el usuario tiene permisos según su rol (RF-04).

La ficha no permite edición directa de ningún campo.

La ficha se carga en un máximo de 3 segundos para activos con información completa en todos los módulos fuente.

**Requerimientos no funcionales:**

Usabilidad: Secciones funcionales con indicadores visuales diferenciados para: datos disponibles, sin información, módulo no disponible e inconsistencia detectada. Diseño adaptable para uso en campo.
Rendimiento: Carga completa de la ficha en máximo 3 segundos para activos con información en todos los módulos fuente.
Seguridad: Acceso controlado por RBAC (RF-04). Solo se muestran secciones y accesos autorizados para el rol del usuario.
Consistencia: Los datos de las Secciones 2, 3, 5 y 6 reflejan el estado en tiempo real de sus módulos fuente. Ante inconsistencias, el sistema advierte sin bloquear.
Accesibilidad: La ficha debe ser funcional en dispositivos de campo con pantallas reducidas.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-48 — Transferencia Interna de Activos Biológicos

**Código Identificación:** RF-48 -- Versión -- 1.1

**Fuente:** Productor / Administrador

**Descripción:** El sistema debe permitir registrar y gestionar la transferencia interna de activos biológicos entre unidades de infraestructura productiva dentro de la misma finca (corrales, galpones, potreros u otras estructuras definidas en RF-20).

La transferencia implica el cambio de ubicación física y lógica del activo biológico, manteniendo su identidad, historial y trazabilidad completa. Cada transferencia queda registrada como evento inmutable en el historial del activo (RF-46).

El sistema soporta transferencias para activos individuales y para activos gestionados por población. Para activos tipo POBLACIONAL: la transferencia aplica sobre la totalidad de la población. No se permite transferencia parcial de población en la versión actual del sistema.

TRANSFERENCIA PARCIAL DE POBLACIÓN (VERSIÓN FUTURA): En una versión posterior del sistema, se evaluará la implementación de transferencia parcial de población, que implicaría dividir la población en dos unidades productivas independientes. Este comportamiento no está disponible en la versión actual y su implementación requerirá la definición de nuevos requerimientos.

**Justificación:** La movilidad de los activos biológicos dentro de la finca es una práctica operativa común (por crecimiento, manejo sanitario, optimización de espacio o cambio de fase productiva). Registrar las transferencias mantiene la trazabilidad del activo, asegura coherencia operativa y garantiza la correcta interpretación de datos en módulos analíticos y financieros.

**Precondiciones:** 1. El activo biológico debe existir en el sistema (RF-33).
2. El activo debe encontrarse en estado ACTIVO (RF-44).
3. Debe existir al menos una infraestructura productiva activa diferente a la actual del activo (RF-20).
4. El activo debe estar previamente asociado a una infraestructura origen registrada en el sistema (RF-34).
5. El usuario debe estar autenticado (RF-02) y tener permisos de transferencia (RF-04).
6. No debe existir otra operación de transferencia en progreso para el mismo activo al momento de iniciar la operación (control de concurrencia).

**Restricciones:** RESTRICCIONES DE ESTADO:
— No se permite transferir activos con estado CERRADO o BAJA.

REGLAS DE COMPATIBILIDAD ENTRE ACTIVO E INFRAESTRUCTURA DESTINO (obligatorias, no opcionales):
Las siguientes tres reglas deben cumplirse simultáneamente para que la infraestructura destino sea válida:

Regla C1 — Compatibilidad por especie: La infraestructura destino debe estar habilitada para la especie del activo, según la configuración de infraestructura en RF-20. Una infraestructura para bovinos no acepta aves, ni una piscicultura acepta bovinos.

Regla C2 — Compatibilidad por tipo de infraestructura: El tipo de infraestructura destino debe ser adecuado para el tipo de activo. Ejemplos: corral para bovinos individuales, galpón para lotes avícolas, estanque para peces. Los tipos válidos están definidos en RF-20.

Regla C3 — Capacidad disponible: La suma de la cantidad actual de activos en la infraestructura destino más la cantidad del activo a transferir no debe superar la capacidad máxima configurada para esa infraestructura en RF-20.

OTRAS RESTRICCIONES:
— La infraestructura destino debe existir y estar activa en el sistema.
— La infraestructura destino debe ser diferente a la infraestructura origen.
— Para activos tipo POBLACIONAL: la transferencia aplica sobre la totalidad de la población. No se permite transferencia parcial en la versión actual.
— La fecha de transferencia no puede ser futura.
— Cada transferencia es un evento inmutable en el historial del activo.
— El sistema implementa control de concurrencia para impedir transferencias simultáneas del mismo activo.

**Prioridad:** [ ] Alta/Must  [X] Media/Should  [ ] Baja/Could

**Dependencia:** RF-04 — Gestión de permisos
RF-20 — Gestión de infraestructura productiva (reglas de compatibilidad C1, C2, C3 y capacidad)
RF-33 — Registro de Activos Biológicos
RF-34 — Asociación del activo a infraestructura (origen de la transferencia)
RF-44 — Gestión del estado del activo biológico

**Actores:** Productor, Administrador del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | (Obligatorio) Identificador del activo individual o poblacional a transferir. |
| tipo_activo | varchar(10) | (Obligatorio) INDIVIDUAL o POBLACIONAL. Para POBLACIONAL: la transferencia aplica sobre la totalidad. |
| infraestructura_origen_id | integer | (Obligatorio) Identificador de la infraestructura actual del activo. Debe coincidir con la asociación vigente en RF-34. |
| infraestructura_destino_id | integer | (Obligatorio) Identificador de la infraestructura destino. Debe ser activa, diferente al origen y cumplir las reglas C1, C2 y C3. |
| fecha_transferencia | date | (Obligatorio) Fecha de la transferencia. No puede ser futura. |
| motivo_transferencia | text | (Obligatorio) Justificación de la transferencia. |
| responsable_id | integer | (Obligatorio) Identificador del usuario que registra la operación. |

**Proceso:**

FLUJO PRINCIPAL:

1. El usuario accede al activo biológico y selecciona la opción 'Transferencia interna'.

2. CONTROL DE CONCURRENCIA (paso previo a cualquier otra validación):
   El sistema verifica que no exista otra operación de transferencia en progreso para el mismo activo. Si existe → ERROR E-01.

3. El sistema verifica:
   a) Existencia del activo (RF-33) → si no existe: ERROR E-02.
   b) Estado del activo = ACTIVO (RF-44) → si no es ACTIVO: ERROR E-03.
   c) Que el activo esté asociado a una infraestructura origen activa (RF-34) → si no: ERROR E-04.

4. El sistema muestra la infraestructura origen actual del activo y las infraestructuras disponibles, filtrando previamente las que no cumplan las reglas C1, C2 y C3.

5. El usuario selecciona la infraestructura destino, ingresa fecha_transferencia y motivo_transferencia.

6. El sistema valida:
   a) Que la infraestructura destino exista y esté activa (RF-20) → si no: ERROR E-05.
   b) Que la infraestructura destino sea diferente a la origen → si son iguales: ERROR E-06.
   c) Compatibilidad C1 — especie: la infraestructura destino debe estar habilitada para la especie del activo (RF-20) → si no: ERROR E-07.
   d) Compatibilidad C2 — tipo de infraestructura: el tipo debe ser adecuado para el activo (RF-20) → si no: ERROR E-08.
   e) Compatibilidad C3 — capacidad: (activos_actuales_destino + cantidad_activo) ≤ capacidad_máxima_destino (RF-20) → si supera: ERROR E-09.
   f) Que fecha_transferencia no sea futura → si es futura: ERROR E-10.

7. Si todas las validaciones son exitosas, el sistema ejecuta de forma transaccional:
   a) Actualiza la asociación del activo a la nueva infraestructura (RF-34): desvincula origen, vincula destino.
   b) Registra el evento de transferencia como entrada inmutable en el historial del activo (RF-46): origen, destino, fecha, motivo, usuario.
   c) Actualiza los contadores de ocupación de infraestructura origen (−) y destino (+) en RF-20.
   d) Registra la operación en el módulo de auditoría.

8. El sistema confirma la operación al usuario con código HTTP 200 y mensaje: 'Transferencia registrada exitosamente. El activo [identificador] fue transferido a [nombre_infraestructura_destino] en fecha [fecha_transferencia].'

9. MANEJO DE FALLO TRANSACCIONAL: Si en cualquier paso del punto 7 ocurre un fallo del sistema, se ejecuta rollback completo:
   — El activo conserva su asociación a la infraestructura origen.
   — No se registra ningún evento en el historial.
   — Los contadores de ocupación no se modifican.
   — El fallo queda registrado en el módulo de auditoría.

**Flujo alterno:**



E-01 | Transferencia concurrente en progreso:
  Código: HTTP 409 / Conflicto de concurrencia
  Mensaje: 'Existe una operación de transferencia en progreso para el activo [identificador]. Espere a que finalice e intente nuevamente.'
  Recuperación: Operación rechazada inmediatamente. El usuario puede reintentar en unos segundos.
  Estado final: Sin cambios.

E-02 | Activo inexistente:
  Código: HTTP 404
  Mensaje: 'El activo biológico con ID [id] no fue encontrado en el sistema.'
  Recuperación: Operación cancelada.
  Estado final: Sin cambios.

E-03 | Estado del activo no ACTIVO:
  Código: HTTP 409 / Error de negocio
  Mensaje: 'El activo [identificador] se encuentra en estado [estado_actual]. Solo se pueden transferir activos en estado ACTIVO.'
  Recuperación: Operación cancelada. No se muestra el formulario de transferencia.
  Estado final: Sin cambios.

E-04 | Sin infraestructura origen:
  Código: HTTP 422 / Error de negocio
  Mensaje: 'El activo [identificador] no tiene una infraestructura productiva origen registrada. Asocie el activo a una infraestructura antes de realizar la transferencia (RF-34).'
  Recuperación: El usuario es dirigido a la funcionalidad de asociación (RF-34).
  Estado final: Sin cambios.

E-05 | Infraestructura destino inexistente o inactiva:
  Código: HTTP 422 / Error de validación
  Mensaje: 'La infraestructura con ID [id] no existe o no se encuentra activa en el sistema.'
  Recuperación: El formulario permanece activo. El campo de infraestructura destino se resalta. El usuario puede seleccionar otra infraestructura.
  Estado final: Sin cambios.

E-06 | Destino igual al origen:
  Código: HTTP 422 / Error de validación
  Mensaje: 'La infraestructura destino debe ser diferente a la infraestructura origen del activo.'
  Recuperación: El campo de infraestructura destino se resalta. El usuario puede seleccionar otra infraestructura.
  Estado final: Sin cambios.

E-07 | Incompatibilidad C1 — especie:
  Código: HTTP 422 / Error de negocio
  Mensaje: 'La infraestructura [nombre_destino] no está habilitada para la especie [especie] del activo. Seleccione una infraestructura compatible con la especie.'
  Recuperación: El sistema filtra la lista de infraestructuras disponibles mostrando solo las compatibles con la especie del activo.
  Estado final: Sin cambios.

E-08 | Incompatibilidad C2 — tipo de infraestructura:
  Código: HTTP 422 / Error de negocio
  Mensaje: 'El tipo de infraestructura [tipo_destino] no es compatible con el tipo de activo [tipo_activo / especie]. Seleccione una infraestructura del tipo adecuado.'
  Recuperación: Igual que E-07.
  Estado final: Sin cambios.

E-09 | Capacidad excedida (C3):
  Código: HTTP 422 / Error de negocio
  Mensaje: 'La infraestructura [nombre_destino] no tiene capacidad disponible para recibir el activo. Capacidad máxima: [capacidad_max], ocupación actual: [ocupacion_actual]. Seleccione otra infraestructura.'
  Recuperación: El sistema muestra las infraestructuras con capacidad disponible.
  Estado final: Sin cambios.

E-10 | Fecha futura:
  Código: HTTP 422 / Error de validación
  Mensaje: 'La fecha de transferencia [fecha] no puede ser posterior a la fecha actual del sistema.'
  Recuperación: El campo fecha se resalta. El usuario puede corregirlo y reintentar.
  Estado final: Sin cambios.

E-11 | Fallo transaccional:
  Código: HTTP 500
  Mensaje: 'La transferencia no pudo completarse por un error interno del sistema. El activo conserva su ubicación original. Intente nuevamente.'
  Recuperación: Rollback completo garantizado. El activo conserva su infraestructura origen. El fallo queda en auditoría.
  Estado final: El activo permanece en infraestructura origen sin inconsistencias. Sin registros parciales.

**Salida:**

El activo queda asociado a la nueva infraestructura productiva.
Evento de transferencia registrado como entrada inmutable en el historial del activo (RF-46): origen, destino, fecha, motivo, usuario.
Contadores de ocupación de infraestructura origen e infraestructura destino actualizados (RF-20).
Confirmación visible al usuario con código HTTP 200 y mensaje de éxito.
Registro de la operación en el módulo de auditoría.

**Postcondiciones:**

El activo queda asociado exclusivamente a la nueva infraestructura destino.
La infraestructura origen refleja la reducción de ocupación.
La infraestructura destino refleja el incremento de ocupación.
El historial completo del activo (RF-46) conserva el evento de transferencia y todos los registros anteriores.
La trazabilidad del activo no se interrumpe.
El sistema mantiene coherencia de datos para módulos analíticos y financieros.

**Criterios de aceptación:**

El sistema registra exitosamente la transferencia cuando: el activo existe y está ACTIVO, la infraestructura destino existe, está activa y es diferente al origen, cumple C1 (especie), C2 (tipo) y C3 (capacidad), la fecha no es futura y no existe transferencia concurrente en progreso.

El sistema rechaza la transferencia si existe una operación de transferencia en progreso para el mismo activo (E-01).

El sistema rechaza la transferencia si el activo no existe (E-02) o no está en estado ACTIVO (E-03).

El sistema rechaza la transferencia si la infraestructura destino no cumple la Regla C1 (especie incompatible), mostrando mensaje E-07.

El sistema rechaza la transferencia si la infraestructura destino no cumple la Regla C2 (tipo incompatible), mostrando mensaje E-08.

El sistema rechaza la transferencia si la infraestructura destino no cumple la Regla C3 (capacidad excedida), mostrando mensaje con capacidad_max y ocupacion_actual (E-09).

El sistema rechaza la transferencia si destino es igual al origen (E-06).

El sistema rechaza la transferencia si la fecha es futura (E-10).

El sistema ejecuta rollback completo ante fallos transaccionales (E-11): el activo conserva su infraestructura origen, no se registra ningún evento en el historial y los contadores de ocupación permanecen sin cambios.

El evento de transferencia queda registrado como entrada inmutable en el historial del activo (RF-46) con: origen, destino, fecha, motivo y usuario responsable.

Los contadores de ocupación de infraestructura origen e infraestructura destino son actualizados correctamente tras la transferencia exitosa.

La trazabilidad del activo no se interrumpe: el historial conserva todos los registros anteriores y posteriores a la transferencia.

**Requerimientos no funcionales:**

Integridad: La operación es completamente transaccional. Ante cualquier fallo: rollback total garantizado sin dejar al activo en estado inconsistente.
Trazabilidad: Todas las transferencias quedan registradas en el historial del activo (RF-46) como eventos inmutables con origen, destino, fecha, motivo y usuario.
Fiabilidad: Ante fallos del sistema durante la operación, se garantiza rollback completo y registro del fallo en auditoría.
Seguridad: Control de acceso RBAC (RF-04). Solo usuarios autorizados pueden ejecutar transferencias.
Consistencia: La ubicación del activo y los contadores de ocupación de infraestructuras deben ser únicos y coherentes. El sistema implementa mecanismos de control de concurrencia para impedir transferencias simultáneas del mismo activo.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-49 — Asociación de Activos Biológicos con Sensores IoT

**Código Identificación:** RF-49 -- Versión -- 1.2

**Fuente:** Productor Agropecuario / Administrador del Sistema / Ingeniero de Campo 

**Descripción:** El sistema debe permitir establecer, gestionar y 
mantener la asociación formal entre activos biológicos 
registrados en M02 y los sensores IoT registrados en 
el sistema (RF-21), con el fin de que cada lectura de 
telemetría quede contextualizada con el activo 
biológico al que corresponde.

El sistema debe soportar los siguientes tipos de 
asociación, formalizados según la cardinalidad 
definida:

Tipo A — Asociación Directa Individual:
  Un sensor biométrico se asocia a un único activo 
  biológico de gestión individual (ej. bovino con 
  arete). Cardinalidad: 1 sensor → 1 animal.
  Un animal puede tener múltiples sensores asociados 
  simultáneamente (ej. sensor de temperatura corporal 
  + sensor de actividad).

Tipo B — Asociación Ambiental Compartida:
  Un sensor ambiental (temperatura, humedad, NH3, CO2) 
  o hídrico (pH, TDS, oxígeno disuelto) se asocia a 
  una infraestructura productiva y, a través de ella, 
  a todos los activos biológicos que residen en dicha 
  estructura. Cardinalidad: 1 sensor → N activos 
  (mediada por la infraestructura).

Tipo C — Asociación Poblacional:
Un sensor se asocia a un activo poblacional o grupo productivo 
  (ej. grupo avícola). Cardinalidad: 1 sensor → 1 activo poblacional 
  (que representa N animales).

La asociación debe definir explícitamente la relación 
entre los siguientes elementos:

  activo_biologico_id o id_lote
  tipo_activo: INDIVIDUAL o POBLACIONAL
  tipo_asociacion: DIRECTA / AMBIENTAL / POBLACIONAL
  dispositivo_iot_id (nodo Edge que contiene el sensor)
  sensor_id (sensor físico específico)
  id_infraestructura (galpón, potrero, estanque)
  fecha_inicio_asociacion
  fecha_fin_asociacion (nulo si activa)
  estado_asociacion: ACTIVA / INACTIVA / SUPERADA

El sistema debe gestionar el ciclo de vida completo 
de cada asociación: creación, modificación, 
desactivación e historial inmutable, garantizando 
que la trazabilidad temporal esté disponible para 
los módulos RF-61 (vinculación de lecturas), M04 
(inferencia) y M06 (valoración NIC 41).

Las variables capturadas por los sensores incluyen, 
sin estar limitadas a: temperatura ambiental, humedad 
relativa, pH del agua, NH3, CO2, temperatura corporal, 
frecuencia cardíaca, frecuencia respiratoria y 
actividad, según el catálogo I3P-1 definido en M09. 
El catálogo de variables es la fuente de verdad; 
no se permiten variables no definidas en él.

**Justificación:** Contextualización del Dato para la Toma de Decisiones:
Una lectura de sensor sin asociación a un activo 
biológico carece de valor operativo. La asociación 
formalizada convierte el dato físico en información 
accionable para el productor y el veterinario.

Requisito para la Valoración NIC 41:
M06 requiere trazabilidad directa entre las lecturas 
de telemetría y el activo biológico específico para 
calcular el valor razonable conforme al párrafo 12 
de la NIC 41. RF-49 establece el vínculo estructural 
que hace posible esa trazabilidad.

Habilitación del Motor de Inferencia (M04):
Los modelos predictivos requieren lecturas etiquetadas 
con el contexto del activo (especie, fase productiva) 
para generar predicciones precisas. Sin la asociación 
de RF-49, M04 no puede contextualizar los datos.

Integración de las Capas IoT y Dominio:
RF-49 es el puente que conecta la capa de percepción 
(M03 / RF-53) con la capa de dominio (M02), 
permitiendo que el ecosistema IoT opere de forma 
integrada con la gestión biológica y contable.

Integridad Temporal del Historial:
Los animales se trasladan entre estructuras a lo largo 
de su ciclo productivo. El registro del periodo de 
validez de cada asociación garantiza que los datos 
históricos reflejen correctamente qué sensor 
monitoreaba a qué activo en cada momento.

**Precondiciones:** 1. Activo Biológico Registrado y Activo (RF-33, RF-44)
El activo biológico (individual o poblacional) debe estar 
previamente registrado en M02 con estado ACTIVO. 
No se permite asociar sensores a activos en estado 
BAJA, VENDIDO o FALLECIDO.

2. Dispositivo IoT Registrado y Activo (RF-21)
El dispositivo IoT que contiene el sensor debe 
estar registrado en el sistema con estado ACTIVO 
y con su identificador único válido.

3. Sensor Asociado a Infraestructura Productiva (RF-22)
El sensor debe estar previamente asociado a una 
estructura productiva (galpón, potrero, estanque) 
mediante RF-22. Esta asociación es la base de 
la coherencia de ubicación.

4. Activo Asignado a la Misma Infraestructura (RF-34)
El activo biológico debe estar asignado a la misma 
infraestructura productiva a la que pertenece el 
sensor, o a una infraestructura dentro de la misma 
granja, para garantizar coherencia de ubicación.

5. Catálogo de Variables Configurado (RF-15, RF-16, M09)
El catálogo I3P-1 de variables del sistema debe 
estar configurado para que el sistema pueda validar 
la compatibilidad entre el tipo de sensor y la 
especie del activo biológico.

6. Usuario Autenticado con Permisos (RF-02, M01)
El usuario que realiza la operación debe tener 
sesión activa y permisos de gestión sobre el 
activo biológico y la infraestructura involucrada, 
conforme al RBAC de M01.

7. Sistema de Auditoría Disponible (RF-63)
El mecanismo de registro de auditoría debe estar 
operativo. Si no es posible registrar la operación 
en la bitácora, la asociación debe revertirse 
(ver flujo alterno E7).

**Restricciones:** 1. Prohibición de Asociación a Activos Inactivos
No se permite crear ni reactivar asociaciones 
para activos en estado BAJA, VENDIDO o FALLECIDO.

2. Coherencia Obligatoria de Ubicación
El sensor y el activo biológico deben pertenecer 
a la misma granja. No se permiten asociaciones 
entre activos y sensores de granjas distintas.

3. Compatibilidad de Especie
El sensor debe ser compatible con la especie 
del activo biológico según el catálogo I3P-1 
(M09). No se permite asociar un sensor 
parametrizado para bovinos a un activo avícola, 
ni viceversa.

4. Cardinalidad según Tipo de Asociación
  Tipo DIRECTA: un sensor biométrico no puede 
    estar activo para más de un activo individual 
    simultáneamente. Debe desactivarse la 
    asociación previa antes de crear una nueva.
  Tipo AMBIENTAL: un sensor ambiental o hídrico 
    puede estar activo para múltiples activos 
    que comparten la misma infraestructura.
  Tipo POBLACIONAL: un sensor se asocia a un 
    único activo poblacional activo a la vez.

5. Ciclo de Vida Formal de la Asociación
Las asociaciones tienen los siguientes estados 
válidos con sus transiciones permitidas:
  ACTIVA → INACTIVA (desactivación manual)
  ACTIVA → SUPERADA (reemplazada por nueva 
    asociación al mismo activo, o por reasignación 
    del sensor a otra área productiva cuando la 
    asociación es de tipo AMBIENTAL o POBLACIONAL 
    —premisa espacial— según RF-22 versión 1.1; 
    la de tipo DIRECTA no se supera por este motivo)
  INACTIVA → ACTIVA (reactivación)
No se permite eliminar registros de asociación; 
solo cambiar su estado.

6. Registro Obligatorio de Campos de Trazabilidad
Toda asociación debe registrar obligatoriamente:
  id_activo o id_lote
  tipo_activo y tipo_asociacion
  dispositivo_iot_id y sensor_id
  id_infraestructura
  fecha_inicio_asociacion
  id_usuario_responsable
El campo id_infraestructura es obligatorio en 
todos los tipos de asociación, no opcional.

7. Protocolos de Comunicación IoT
La integración técnica entre el sensor y el 
backend opera mediante el protocolo MQTT sobre 
LoRaWAN, conforme a la arquitectura definida 
en M03. El formato de los datos de telemetría 
es JSON estructurado según el esquema de RF-53.

8. Inmutabilidad del Historial
El historial de asociaciones es append-only. 
No se permite modificar ni eliminar registros 
históricos; solo añadir nuevas entradas o 
cambiar el estado de las existentes.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-21 — Registro de dispositivos IoT
RF-22 — Asociación de sensores a estructuras productivas
RF-33 — Registro de Activos Biológicos
RF-34 — Asociación a infraestructura
RF-44 — Estado del activo

**Actores:** 1. Productor Agropecuario (Actor Principal — Humano)
Solicita la asociación de sensores a sus activos 
biológicos. Toma decisiones sobre qué sensores 
monitorean qué animales o lotes en su finca.

2. Administrador del Sistema (Actor Principal — Humano)
Gestiona las asociaciones desde la perspectiva 
administrativa. Puede crear, modificar, 
desactivar y consultar el historial de 
asociaciones de cualquier granja.

3. Ingeniero de Campo (Actor Secundario — Humano)
Ejecuta asociaciones durante la instalación 
y mantenimiento de dispositivos IoT. Valida 
que la asociación técnica es coherente con 
la ubicación física del sensor.

4. Veterinario (Actor de Consulta — Humano)
Consulta las asociaciones activas para 
identificar qué sensores están monitoreando 
a un activo biológico específico durante 
el seguimiento clínico.

5. Sistema M02 — Gestión de Activos Biológicos
(Actor Sistema — Bidireccional)
Provee el catálogo de activos biológicos 
y consume las asociaciones activas para 
enriquecer la ficha integral del activo.

6. Sistema M03 — Telemetría e IoT (Actor Sistema — Consumidor)
Consume las asociaciones para contextualizar 
cada lectura de telemetría con el activo 
biológico correspondiente (vía RF-61).

7. Sistema RF-63 — Auditoría (Actor Sistema)
Recibe y persiste el registro inmutable de 
cada operación de asociación realizada.

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | Integer | Identificador del activo biológico individual (RF-33). Obligatorio en tipo_activo = INDIVIDUAL. |
| id_poblacion | Integer | Identificador del activo poblacional. Obligatorio en tipo_activo = POBLACIONAL. |
| tipo_activo | Enum | Clasificación del activo: INDIVIDUAL o POBLACIONAL. Determina la lógica de cardinalidad aplicable. |
| tipo_asociacion | Enum | Tipo formal de la asociación: DIRECTA (biométrica 1→1), AMBIENTAL (compartida 1→N por infraestructura), POBLACIONAL (1→activo poblacional). |
| dispositivo_iot_id | Integer | Identificador del nodo IoT que contiene el sensor (RF-21). Permite validar el estado del dispositivo. |
| sensor_id | Integer | Identificador del sensor físico específico dentro del dispositivo. Debe estar registrado en RF-21 y asociado a infraestructura en RF-22. |
| id_infraestructura | Integer | Identificador de la estructura productiva (galpón, potrero, estanque) a la que pertenece el sensor. Obligatorio en todos los tipos de asociación. |
| fecha_inicio_asociacion | Date (ISO-8601) | Fecha desde la cual la asociación es válida. Por defecto: fecha actual del sistema. |
| fecha_fin_asociacion | Date (opcional) | Fecha de finalización planificada. Nulo si la asociación es indefinida. |
| id_usuario_responsable | Integer | Identificador del usuario que realiza la operación. Requerido para auditoría. |
| motivo_cambio | String (condicional) | Descripción del motivo cuando la operación es una actualización o desactivación de una asociación existente. |

**Proceso:**

El usuario accede al activo biológico.

Selecciona la opción de asociar sensores IoT.

El sistema muestra los dispositivos y sensores disponibles según la infraestructura.

El usuario selecciona el sensor a asociar.

El sistema valida:

existencia del activo

estado del activo (no BAJA)

existencia del dispositivo y sensor

coherencia con la infraestructura

El sistema registra la asociación entre el activo y el sensor.

Se actualiza el estado de asociación si existía una previa.

Se registra la operación en auditoría.

El sistema confirma la asociación al usuario.

**Flujo alterno:**

Activo Biológico No Válido (Inexistente o Baja)
Condición: El ID no existe o el campo estado es 'BAJA'.

Respuesta del Sistema:

HTTP 422 Unprocessable Entity

Mensaje: "Operación denegada. El activo [ID_ACTIVO] se encuentra en estado 'BAJA' desde el [FECHA_BAJA] y no admite nuevas asociaciones."

Conflicto de Ubicación (Fincas Distintas)
Condición: El finca_id del activo no coincide con el finca_id del sensor.

Respuesta del Sistema:

HTTP 409 Conflict

Mensaje: "Error de ubicación. El activo está registrado en 'Finca A' y el sensor en 'Finca B'. La asociación solo es permitida dentro de la misma unidad territorial."

Sensor Ya Vinculado (Exclusividad Individual)
Condición: El sensor es de tipo 'Individual' y ya tiene una asociación activa con otro activo_id.

Respuesta del Sistema:

HTTP 409 Conflict

Mensaje: "Conflicto de asignación. El sensor [ID_SENSOR] ya está vinculado al activo [ID_ACTIVO_EXISTENTE]. Debe desvincularlo primero o elegir la opción 'Reasignar'."

Incompatibilidad de Especie (Parámetros Biológicos)
Condición: El sensor está configurado para 'Aves' y el activo es 'Bovino'.

Respuesta del Sistema:

HTTP 400 Bad Request

Mensaje: "Incompatibilidad biológica. El sensor [ID_SENSOR] está parametrizado para [ESPECIE_A], no es compatible con el activo [ID_ACTIVO] de tipo [ESPECIE_B]."

Dispositivo IoT Fuera de Línea (Warning)
Condición: El dispositivo padre del sensor no ha enviado un heartbeat en los últimos 30 minutos.

Respuesta del Sistema:

HTTP 201 Created (con Warning)

Mensaje: "Asociación registrada exitosamente. Advertencia: El dispositivo [ID_DISPOSITIVO] se encuentra desconectado desde las [HH:mm:ss]. Las lecturas podrían no verse reflejadas de inmediato."

Error de Persistencia en Auditoría
Condición: Falla la escritura en el Log de Auditoría inmutable.

Respuesta del Sistema:

HTTP 500 Internal Server Error

Mensaje: "Fallo crítico de seguridad. No se pudo generar el registro de auditoría obligatorio. La operación ha sido revertida por integridad de datos."

**Salida:**

Asociación activa entre activo biológico y sensor IoT

Registro del evento de asociación

Confirmación de la operación

Disponibilidad de datos de sensores asociados al activo

**Postcondiciones:**

El activo queda vinculado al sensor IoT

Las lecturas del sensor pueden ser asociadas al activo

El historial de asociaciones queda actualizado

La información queda disponible para módulos M03, M04 y M08

**Criterios de aceptación:**

El sistema permite asociar un sensor a un activo válido

El sistema rechaza la operación si el activo no existe

El sistema valida el estado del activo antes de asociar

El sistema valida la existencia del sensor y dispositivo

El sistema valida coherencia con la infraestructura

El sistema registra correctamente la asociación

El sistema permite múltiples asociaciones cuando aplique

El sistema permite actualizar o cambiar asociaciones

El sistema registra la operación en el historial

El sistema refleja la asociación en consultas posteriores

**Requerimientos no funcionales:**

Integración

Debe garantizarse la correcta vinculación con el módulo IoT (M03)

Trazabilidad

Todas las asociaciones deben quedar registradas

Fiabilidad

La operación debe ejecutarse correctamente sin pérdida de datos

Seguridad

Control de acceso basado en roles

Consistencia

La asociación debe ser coherente con la ubicación del activo

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-50 — Disponibilidad de Datos para Módulos Analíticos

**Código Identificación:** RF-50 -- Versión -- 1.0

**Fuente:** Módulos analíticos del sistema (M03, M04, M06, M08) / Arquitectura del sistema

**Descripción:** El sistema debe garantizar la disponibilidad, estructuración y acceso controlado a los datos generados en el módulo M02 – Gestión de Activos Biológicos, mediante un conjunto de interfaces internas estandarizadas basadas en servicios (API REST) que permitan su consumo por los módulos analíticos del sistema (M03, M04, M06, M08).

Los datos deberán ser expuestos en formato estructurado JSON, siguiendo contratos de servicio definidos (DTOs), versionados y documentados, que aseguren consistencia semántica y técnica para su procesamiento.

El sistema debe soportar dos modalidades de acceso:

Consulta en tiempo casi real: disponibilidad de datos con una latencia máxima de 5 segundos desde su registro en el sistema.

Consulta diferida: acceso a datos históricos consolidados mediante filtros por rango de fechas, tipo de dato y activo biológico.

El acceso a los datos se realizará exclusivamente a través de endpoints internos autenticados, bajo control de permisos y scopes definidos, evitando acceso directo a base de datos por parte de los módulos consumidores.

El sistema deberá exponer, como mínimo, los siguientes conjuntos de datos:

Información base del activo biológico:

Identificador

Tipo de activo (INDIVIDUAL / AGRUPACIÓN)

Especie

Estado actual

Infraestructura asociada

Historial de fases productivas:

Fase actual

Historial completo con fechas de inicio y fin

Historial de eventos biológicos:

Eventos de crecimiento

Eventos sanitarios

Eventos reproductivos

Eventos productivos

Estado operativo del activo:

Estado actual (ACTIVO, INACTIVO, BAJA, CERRADO)

Fecha de cambio de estado

Métricas derivadas:

Variables de crecimiento (peso, biomasa)

Indicadores productivos disponibles

El sistema debe garantizar que los datos expuestos cumplan las siguientes condiciones:

Integridad referencial: todos los registros deben estar correctamente vinculados (activo, evento, fase, infraestructura).

Consistencia temporal: no deben existir solapamientos ni incoherencias en fechas.

Completitud mínima: los datos requeridos por el módulo consumidor deben existir; en caso contrario, se debe rechazar la solicitud.

Normalización: los datos deben estar transformados a estructuras homogéneas listas para consumo analítico.

El sistema debe implementar políticas de consistencia fuerte para consultas críticas (por ejemplo, M06 – valoración financiera) y consistencia eventual para consultas no críticas (por ejemplo, dashboards en M08).

El sistema debe soportar control de concurrencia y volumen mediante:

Límite de solicitudes por módulo (rate limiting configurable)

Manejo de múltiples solicitudes concurrentes sin degradación significativa del servicio

Paginación obligatoria para consultas de alto volumen

Adicionalmente, el sistema debe registrar cada acceso a los datos en un log de auditoría, incluyendo:

Módulo solicitante

Tipo de datos consultados

Fecha y hora de la solicitud

Resultado de la operación

El sistema no debe permitir:

Exposición de datos inconsistentes, incompletos o corruptos

Modificación de datos por parte de módulos consumidores

Acceso a datos sin autenticación y autorización válida

En caso de error o inconsistencia, el sistema debe responder mediante códigos de estado estandarizados (HTTP 4xx y 5xx), con mensajes claros que permitan identificar la causa del fallo y evitar interpretaciones ambiguas en los módulos consumidores.

**Justificación:** El valor del sistema depende directamente de la capacidad de transformar datos operativos en información útil para la toma de decisiones. Sin disponibilidad estructurada de datos, los módulos analíticos no pueden ejecutar predicciones, cálculos financieros ni generación de reportes, afectando el objetivo central del sistema.

**Precondiciones:** Deben existir activos biológicos registrados en el sistema (RF-33).

Deben existir registros de eventos, fases y estados asociados al activo (RF-37 a RF-45).

El sistema debe contar con usuarios autenticados con permisos de acceso a datos (RF-02, RF-04).

**Restricciones:** Solo los módulos internos autorizados pueden consumir los datos mediante interfaces definidas.

Los datos expuestos deben cumplir integridad referencial y consistencia temporal.

No se permite exponer datos incompletos o en estado inconsistente.

Los datos deben respetar las reglas de acceso según rol del usuario.

La información histórica no puede ser modificada por los módulos consumidores.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios
RF-04 — Gestión de permisos
RF-33 — Registro de Activos Biológicos
RF-37 — Gestión de fases
RF-39 a RF-45 — Registro de eventos y estado

**Actores:** Sistema (módulos M03, M04, M06, M08)

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador del activo biológico |
| tipo_activo | string | Tipo de activo (INDIVIDUAL / POBLACIONAL) |
| rango_fechas | date_range | Intervalo de tiempo para consulta de datos |
| tipo_dato | string | Tipo de información requerida (eventos, fases, estado, métricas) |

**Proceso:**

El módulo consumidor realiza una solicitud a la API interna.

El sistema valida:

autenticación del módulo

permisos de acceso según tipo de dato

parámetros de entrada

El sistema identifica las fuentes de datos:

eventos
fases
estado
métricas

El sistema consulta los datos en repositorios internos.

El sistema valida:

integridad referencial
coherencia temporal
consistencia de datos

El sistema transforma los datos a formato JSON estructurado.

El sistema aplica reglas de normalización:

unidades consistentes
formatos de fecha
tipado de campos

El sistema consolida la respuesta según el tipo de consulta.

El sistema aplica control de carga (rate limit y concurrencia).

El sistema retorna la respuesta al módulo solicitante.

**Flujo alterno:**

Activo Biológico no encontrado:

El sistema no localiza el activo_biologico_id en la base de datos maestra.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error: El activo biológico con ID [ID_SOLICITADO] no existe en los registros del sistema. Verifique el identificador."

Rango de fechas inválido o inconsistente:

La fecha_inicio proporcionada es posterior a la fecha_fin o se solicitan datos de fechas futuras.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error en parámetros temporales: La fecha de inicio [FECHA_A] no puede ser superior a la fecha fin [FECHA_B]. La consulta ha sido rechazada."

Datos insuficientes para proceso crítico (NIC 41):

El módulo M06 solicita datos de valoración, pero el activo no registra eventos de peso o crecimiento en el periodo consultado.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Información incompleta: El activo [ID_ACTIVO] no registra métricas de peso necesarias para el cálculo de transformación biológica en el rango de fechas solicitado."

Acceso de módulo no autorizado:

El módulo que realiza la petición no cuenta con los permisos o el scope necesario para el tipo_dato solicitado.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: El módulo solicitante no tiene autorización para consumir datos de tipo [TIPO_DATO]."

Saturación de peticiones analíticas (Rate Limit):

El módulo (especialmente M04 de predicción) excede el límite de 100 consultas por minuto.

El sistema responde con:

HTTP 429: Too Many Requests

Mensaje: "Límite de tasa excedido. Por seguridad del sistema, espere [X] segundos. Podrá reintentar la consulta a las [HH:mm:ss]."

Conflicto de integridad referencial:

Los datos recuperados presentan inconsistencias (ej. registros vinculados a una infraestructura que fue eliminada lógicamente sin cierre de ciclo).

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de integridad: Los registros del activo [ID_ACTIVO] presentan inconsistencias en su jerarquía operativa. Se requiere conciliación de datos antes de permitir el consumo analítico."

Fallo de normalización de datos:

El sistema detecta valores fuera de los rangos físicos posibles (ej. peso negativo) que impedirían el procesamiento en otros módulos.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Error de consistencia interna: Se detectaron métricas corruptas para el activo [ID_ACTIVO]. La exportación de datos se ha cancelado para proteger la integridad de los modelos analíticos."

**Salida:**

Datos estructurados del activo biológico listos para consumo analítico.

Conjunto de información consolidada que puede incluir:

Estado actual del activo

Historial de eventos

Historial de fases

Métricas de crecimiento y producción

Respuesta de servicio con estado de la operación.

**Postcondiciones:**

Los módulos analíticos reciben datos consistentes y completos.

La información entregada refleja el estado real del activo en el sistema.

Se mantiene la integridad de los datos sin alteraciones por parte de los consumidores.

**Criterios de aceptación:**

El sistema expone datos mediante API REST interna.

El sistema entrega datos en formato JSON estructurado válido.

El sistema responde en:

≤ 2 segundos para consultas simples
≤ 5 segundos para consultas complejas

El sistema soporta al menos:

100 solicitudes por minuto por módulo

El sistema valida permisos antes de entregar datos.

El sistema rechaza:

parámetros inválidos
accesos no autorizados
activos inexistentes

El sistema no entrega datos:

incompletos
inconsistentes
corruptos

El sistema mantiene integridad referencial en todas las respuestas.

El sistema permite consultas por:

rango de fechas
tipo de dato

El sistema maneja correctamente concurrencia sin pérdida de datos.

**Requerimientos no funcionales:**

Rendimiento
El sistema debe responder a consultas de datos en tiempos adecuados para consumo analítico.

Integridad
Los datos deben mantenerse consistentes y sin duplicidades.

Disponibilidad
La información debe estar disponible para los módulos analíticos cuando el sistema esté operativo.

Seguridad
El acceso a los datos debe estar controlado mediante autenticación y autorización.

Escalabilidad
El sistema debe soportar crecimiento en volumen de datos sin afectar el acceso a la información.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-51 — Generación de Indicadores Zootécnicos

**Código Identificación:** RF-51 -- Versión -- 1.1

**Fuente:** Productor / Veterinario / Módulo de Inteligencia de Negocio (M08) / Módulo de Predicción (M04)

**Descripción:** El sistema debe permitir calcular, generar y exponer indicadores zootécnicos a partir de la información registrada en los activos biológicos, utilizando datos históricos y actuales provenientes de eventos, fases del ciclo productivo y estado del activo, con el fin de evaluar de manera cuantitativa su desempeño productivo, sanitario y de crecimiento.

El sistema debe implementar un catálogo de indicadores zootécnicos definido, parametrizado desde el módulo de configuración (M09), donde cada indicador incluye:

Nombre del indicador

Tipo de activo aplicable (INDIVIDUAL / AGRUPACIÓN)

Especie aplicable

Unidad de medida

Fórmula de cálculo

Variables requeridas

Reglas de validación de datos

El sistema debe soportar como mínimo los siguientes indicadores:

Crecimiento:

Ganancia diaria de peso = (peso_final - peso_inicial) / días

Producción:

Producción promedio = total_producido / días

Sanitario:

Tasa de morbilidad = (eventos_sanitarios / población_total) * 100

Tasa de mortalidad = (bajas / población_total) * 100

Eficiencia:

Conversión alimenticia = alimento_consumido / ganancia_peso

El sistema debe permitir el cálculo:

En tiempo real (on-demand)

De forma diferida (batch)

Los indicadores deben poder generarse por:

Activo individual

Agrupación de activos

Infraestructura

Rango de fechas

Los resultados deben ser entregados en formato estructurado (JSON), incluyendo valor, unidad, periodo, variables utilizadas y fecha de cálculo.

**Justificación:** Los indicadores zootécnicos permiten medir el rendimiento real de los activos biológicos y son fundamentales para la toma de decisiones en producción pecuaria. Estos indicadores también sirven como insumo clave para análisis predictivos y valoración financiera, asegurando una gestión basada en datos.

**Precondiciones:** Deben existir activos biológicos registrados en el sistema (RF-33).

Deben existir eventos asociados al activo (crecimiento, sanitarios, productivos, reproductivos).

Debe existir historial de fases del ciclo productivo (RF-37).

El usuario debe tener permisos de consulta sobre los activos biológicos.

**Restricciones:** Deben existir activos biológicos registrados en el sistema (RF-33).

Deben existir eventos asociados al activo (crecimiento, sanitarios, productivos, reproductivos).

Debe existir historial de fases del ciclo productivo (RF-37).

El usuario debe tener permisos de consulta sobre los activos biológicos.

**Prioridad:** [ ] Alta/Must  [X] Media/Should  [ ] Baja/Could

**Dependencia:** RF-33 — Registro de Activos Biológicos
RF-37 — Gestión de Fases del Ciclo Productivo
RF-39 — Registro de Eventos Biológicos
RF-40 — Registro de Eventos de Crecimiento
RF-41 — Registro de Eventos Sanitarios
RF-43 — Registro de Eventos Productivos
RF-50 — Disponibilidad de Datos para Módulos Analíticos

**Actores:** Productor, Veterinario, Sistema (M08, M04)

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador del activo individual o poblacional |
| tipo_activo | string | INDIVIDUAL o POBLACIONAL |
| rango_fechas | date_range | Periodo sobre el cual se calculan los indicadores |
| tipo_indicador | string | Tipo de indicador a calcular |
| parametros_calculo | json | Parámetros adicionales según indicador |

**Proceso:**

El usuario o módulo solicita la generación de indicadores zootécnicos.

El sistema valida la existencia del activo y permisos de acceso.

El sistema identifica los datos necesarios según el tipo de indicador.

Se recupera la información del activo (eventos, fases, estado, métricas).

El sistema valida consistencia y suficiencia de los datos.

Se ejecutan los cálculos correspondientes para cada indicador solicitado.

El sistema consolida los resultados por activo individual o por activo poblacional.

Se almacenan los resultados para consulta posterior (si aplica).

El sistema retorna los indicadores generados.

**Flujo alterno:**

Activo Biológico no encontrado:

El sistema no identifica el activo_biologico_id en la base de datos de activos biológicos.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error: El identificador del activo [ID_SOLICITADO] no existe. No se pueden generar indicadores para entidades inexistentes."

Datos insuficientes para el cálculo (Mínimo requerido):

Se solicita un indicador de crecimiento (ej. Ganancia Diaria de Peso), pero el activo solo cuenta con un único registro de peso en el sistema.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Muestra insuficiente: El indicador [TIPO_INDICADOR] requiere al menos dos mediciones temporales. El activo [ID_ACTIVO] solo cuenta con un registro el día [FECHA_REGISTRO]."

Incompatibilidad biológica del indicador:

Se intenta calcular un indicador no apto para la especie o sexo del activo (ej. Producción de leche en un ejemplar macho o tasa de postura en bovinos).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Incompatibilidad biológica: El indicador [TIPO_INDICADOR] no es aplicable a la especie [ESPECIE] o género del activo [ID_ACTIVO] según los parámetros de configuración (M09)."

Error de indeterminación matemática (División por cero):

Se intenta calcular indicadores de eficiencia (ej. Conversión Alimenticia) donde el denominador (consumo de alimento) es igual a cero en el registro.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Error de cálculo: No es posible generar el indicador [TIPO_INDICADOR] para el activo [ID_ACTIVO] debido a que el consumo registrado es 0. Verifique los datos de Gestión de Suministros (M05)."

Rango de fechas fuera del ciclo biológico:

El rango_fechas solicitado inicia antes de la fecha de nacimiento/ingreso del activo o finaliza después de su fecha de baja.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Conflicto temporal: El rango solicitado [FECHA_INICIO] a [FECHA_FIN] está fuera del ciclo de vida registrado para el activo [ID_ACTIVO] (Vida: [NACIMIENTO] a [BAJA/ACTUALIDAD])."

Inconsistencia de datos (Outliers críticos):

El sistema detecta valores que generarían indicadores físicamente imposibles (ej. Ganancia de peso de 500kg en un día) debido a errores de digitación o fallos en sensores.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Cálculo suspendido: Se detectaron valores atípicos (Outliers) en las métricas del activo [ID_ACTIVO]. El indicador resultante es biológicamente imposible. Revise los registros de telemetría o eventos manuales."

Fallo de autorización de acceso a datos:

El usuario o módulo solicitante no tiene permisos de lectura para el activo o el grupo de eventos necesarios (ej. un usuario sin permisos sanitarios intentando ver el índice de morbilidad).

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: No cuenta con permisos suficientes para consultar la dimensión de datos [TIPO_DATO] requerida para este indicador."

**Salida:**

Indicadores zootécnicos calculados para el activo individual o poblacional.

Resultados estructurados listos para visualización o análisis.

Conjunto de métricas que pueden incluir crecimiento, eficiencia productiva y comportamiento sanitario.

**Postcondiciones:**

Los indicadores quedan disponibles para consulta y análisis.

Los resultados pueden ser utilizados por módulos analíticos y de visualización.

La información generada refleja el comportamiento real del activo según los datos registrados.

**Criterios de aceptación:**

El sistema permite generar indicadores para activos individuales y lotes.

El sistema calcula indicadores utilizando datos registrados en el sistema.

El sistema valida la existencia y calidad de los datos antes del cálculo.

El sistema permite generar indicadores por rango de fechas.

Los resultados se entregan en formato estructurado y comprensible.

El sistema responde correctamente ante solicitudes simultáneas.

El sistema no genera indicadores cuando los datos son insuficientes.

Los indicadores son consistentes con la información histórica del sistema.

**Requerimientos no funcionales:**

Rendimiento
El cálculo de indicadores debe ejecutarse en tiempos adecuados para su uso en análisis y visualización.

Fiabilidad
Los resultados deben ser precisos y reproducibles a partir de los mismos datos.

Usabilidad
Los indicadores deben ser comprensibles y utilizables por el usuario final.

Escalabilidad
El sistema debe soportar el cálculo de indicadores para múltiples activos sin degradación significativa del rendimiento.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

> **⚠️ Nota de conversión:** el código `RF-51` está duplicado en el Excel
> original — este es el segundo bloque, idéntico al anterior. La
> inconsistencia terminológica que existía entre ambos bloques ("INDIVIDUAL
> o LOTE" vs "INDIVIDUAL o POBLACIONAL") quedó resuelta por RFC-003
> (`gestion-cambios/RFC-003-estandarizar-poblacional.md`): "POBLACIONAL" es
> el término vigente en todo el documento. Se conservan ambos bloques sin
> fusionar por ser responsabilidad de Análisis consolidarlos en el Excel
> origen (`backups/1-analisis/`) — pendiente aparte de este RFC.

## RF-51 — Generación de Indicadores Zootécnicos

**Código Identificación:** RF-51 -- Versión -- 1.1

**Fuente:** Productor / Veterinario / Módulo de Inteligencia de Negocio (M08) / Módulo de Predicción (M04)

**Descripción:** El sistema debe permitir calcular, generar y exponer indicadores zootécnicos a partir de la información registrada en los activos biológicos, utilizando datos históricos y actuales provenientes de eventos, fases del ciclo productivo y estado del activo, con el fin de evaluar de manera cuantitativa su desempeño productivo, sanitario y de crecimiento.

El sistema debe implementar un catálogo de indicadores zootécnicos definido, parametrizado desde el módulo de configuración (M09), donde cada indicador incluye:

Nombre del indicador

Tipo de activo aplicable (INDIVIDUAL / AGRUPACIÓN)

Especie aplicable

Unidad de medida

Fórmula de cálculo

Variables requeridas

Reglas de validación de datos

El sistema debe soportar como mínimo los siguientes indicadores:

Crecimiento:

Ganancia diaria de peso = (peso_final - peso_inicial) / días

Producción:

Producción promedio = total_producido / días

Sanitario:

Tasa de morbilidad = (eventos_sanitarios / población_total) * 100

Tasa de mortalidad = (bajas / población_total) * 100

Eficiencia:

Conversión alimenticia = alimento_consumido / ganancia_peso

El sistema debe permitir el cálculo:

En tiempo real (on-demand)

De forma diferida (batch)

Los indicadores deben poder generarse por:

Activo individual

Agrupación de activos

Infraestructura

Rango de fechas

Los resultados deben ser entregados en formato estructurado (JSON), incluyendo valor, unidad, periodo, variables utilizadas y fecha de cálculo.

**Justificación:** Los indicadores zootécnicos permiten medir el rendimiento real de los activos biológicos y son fundamentales para la toma de decisiones en producción pecuaria. Estos indicadores también sirven como insumo clave para análisis predictivos y valoración financiera, asegurando una gestión basada en datos.

**Precondiciones:** Deben existir activos biológicos registrados en el sistema (RF-33).

Deben existir eventos asociados al activo (crecimiento, sanitarios, productivos, reproductivos).

Debe existir historial de fases del ciclo productivo (RF-37).

El usuario debe tener permisos de consulta sobre los activos biológicos.

**Restricciones:** Deben existir activos biológicos registrados en el sistema (RF-33).

Deben existir eventos asociados al activo (crecimiento, sanitarios, productivos, reproductivos).

Debe existir historial de fases del ciclo productivo (RF-37).

El usuario debe tener permisos de consulta sobre los activos biológicos.

**Prioridad:** [ ] Alta/Must  [X] Media/Should  [ ] Baja/Could

**Dependencia:** RF-33 — Registro de Activos Biológicos
RF-37 — Gestión de Fases del Ciclo Productivo
RF-39 — Registro de Eventos Biológicos
RF-40 — Registro de Eventos de Crecimiento
RF-41 — Registro de Eventos Sanitarios
RF-43 — Registro de Eventos Productivos
RF-50 — Disponibilidad de Datos para Módulos Analíticos

**Actores:** Productor, Veterinario, Sistema (M08, M04)

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| activo_biologico_id | integer | Identificador del activo individual o poblacional |
| tipo_activo | string | INDIVIDUAL o POBLACIONAL |
| rango_fechas | date_range | Periodo sobre el cual se calculan los indicadores |
| tipo_indicador | string | Tipo de indicador a calcular |
| parametros_calculo | json | Parámetros adicionales según indicador |

**Proceso:**

El usuario o módulo solicita la generación de indicadores zootécnicos.

El sistema valida la existencia del activo y permisos de acceso.

El sistema identifica los datos necesarios según el tipo de indicador.

Se recupera la información del activo (eventos, fases, estado, métricas).

El sistema valida consistencia y suficiencia de los datos.

Se ejecutan los cálculos correspondientes para cada indicador solicitado.

El sistema consolida los resultados por activo individual o por activo poblacional.

Se almacenan los resultados para consulta posterior (si aplica).

El sistema retorna los indicadores generados.

**Flujo alterno:**

Activo Biológico no encontrado:

El sistema no identifica el activo_biologico_id en la base de datos de activos biológicos.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error: El identificador del activo [ID_SOLICITADO] no existe. No se pueden generar indicadores para entidades inexistentes."

Datos insuficientes para el cálculo (Mínimo requerido):

Se solicita un indicador de crecimiento (ej. Ganancia Diaria de Peso), pero el activo solo cuenta con un único registro de peso en el sistema.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Muestra insuficiente: El indicador [TIPO_INDICADOR] requiere al menos dos mediciones temporales. El activo [ID_ACTIVO] solo cuenta con un registro el día [FECHA_REGISTRO]."

Incompatibilidad biológica del indicador:

Se intenta calcular un indicador no apto para la especie o sexo del activo (ej. Producción de leche en un ejemplar macho o tasa de postura en bovinos).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Incompatibilidad biológica: El indicador [TIPO_INDICADOR] no es aplicable a la especie [ESPECIE] o género del activo [ID_ACTIVO] según los parámetros de configuración (M09)."

Error de indeterminación matemática (División por cero):

Se intenta calcular indicadores de eficiencia (ej. Conversión Alimenticia) donde el denominador (consumo de alimento) es igual a cero en el registro.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Error de cálculo: No es posible generar el indicador [TIPO_INDICADOR] para el activo [ID_ACTIVO] debido a que el consumo registrado es 0. Verifique los datos de Gestión de Suministros (M05)."

Rango de fechas fuera del ciclo biológico:

El rango_fechas solicitado inicia antes de la fecha de nacimiento/ingreso del activo o finaliza después de su fecha de baja.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Conflicto temporal: El rango solicitado [FECHA_INICIO] a [FECHA_FIN] está fuera del ciclo de vida registrado para el activo [ID_ACTIVO] (Vida: [NACIMIENTO] a [BAJA/ACTUALIDAD])."

Inconsistencia de datos (Outliers críticos):

El sistema detecta valores que generarían indicadores físicamente imposibles (ej. Ganancia de peso de 500kg en un día) debido a errores de digitación o fallos en sensores.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Cálculo suspendido: Se detectaron valores atípicos (Outliers) en las métricas del activo [ID_ACTIVO]. El indicador resultante es biológicamente imposible. Revise los registros de telemetría o eventos manuales."

Fallo de autorización de acceso a datos:

El usuario o módulo solicitante no tiene permisos de lectura para el activo o el grupo de eventos necesarios (ej. un usuario sin permisos sanitarios intentando ver el índice de morbilidad).

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: No cuenta con permisos suficientes para consultar la dimensión de datos [TIPO_DATO] requerida para este indicador."

**Salida:**

Indicadores zootécnicos calculados para el activo individual o poblacional.

Resultados estructurados listos para visualización o análisis.

Conjunto de métricas que pueden incluir crecimiento, eficiencia productiva y comportamiento sanitario.

**Postcondiciones:**

Los indicadores quedan disponibles para consulta y análisis.

Los resultados pueden ser utilizados por módulos analíticos y de visualización.

La información generada refleja el comportamiento real del activo según los datos registrados.

**Criterios de aceptación:**

El sistema permite generar indicadores para activos individuales y lotes.

El sistema calcula indicadores utilizando datos registrados en el sistema.

El sistema valida la existencia y calidad de los datos antes del cálculo.

El sistema permite generar indicadores por rango de fechas.

Los resultados se entregan en formato estructurado y comprensible.

El sistema responde correctamente ante solicitudes simultáneas.

El sistema no genera indicadores cuando los datos son insuficientes.

Los indicadores son consistentes con la información histórica del sistema.

**Requerimientos no funcionales:**

Rendimiento
El cálculo de indicadores debe ejecutarse en tiempos adecuados para su uso en análisis y visualización.

Fiabilidad
Los resultados deben ser precisos y reproducibles a partir de los mismos datos.

Usabilidad
Los indicadores deben ser comprensibles y utilizables por el usuario final.

Escalabilidad
El sistema debe soportar el cálculo de indicadores para múltiples activos sin degradación significativa del rendimiento.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-52 — Auditoría y Trazabilidad de Eventos de Transformación biologica

**Código Identificación:** RF-52 -- Versión -- 1.1

**Fuente:** Productor / Veterinario / Contador / Administrador del Sistema

**Descripción:** El sistema debe registrar de forma automática, 
continua e inmutable todos los eventos relevantes 
generados por los componentes del módulo M02 – 
Gestión de Activos Biológicos, constituyendo la 
capa transversal de trazabilidad de la transformación 
biológica de los activos a lo largo de su ciclo de vida.

Los eventos que deben registrarse incluyen, sin 
excepción:

  RF-33 — Registro de activos biológicos
  RF-34 — Consulta y asociación a infraestructura
  RF-35 — Gestión de activos individuales
  RF-36 — Gestión de activos poblacionales
  RF-37 — Cambios de fases del ciclo productivo
  RF-38 — Cierre del ciclo productivo
  RF-39 — Registro de eventos biológicos
  RF-40 — Registro de eventos de crecimiento
  RF-41 — Registro de eventos sanitarios
  RF-42 — Registro de eventos reproductivos
  RF-43 — Registro de eventos productivos
  RF-44 — Cambios de estado del activo
  RF-45 — Registro de bajas
  RF-46 — Consultas del historial del activo
  RF-47 — Consultas de la ficha integral
  RF-48 — Transferencias internas
  RF-49 — Asociación con sensores IoT
  RF-50 — Acceso de módulos analíticos a datos
  RF-51 — Generación de indicadores zootécnicos

La bitácora generada por RF-52 actúa como fuente 
de verdad técnica del módulo M02, siendo la 
evidencia central para:

  Procesos de valoración de activos biológicos 
  bajo la NIC 41 (M06), como registro de la 
  transformación biológica ocurrida entre dos 
  periodos contables.
  
  Auditorías técnicas ante el ICA y la UPRA.
  
  Análisis de patrones de comportamiento y 
  rendimiento de los activos por parte de M04 y M08.
  
  Diagnóstico de incidentes operativos por el 
  administrador del sistema.

Cada evento registrado debe identificar de forma 
inequívoca el activo biológico afectado, el RF que 
lo originó, el tipo de transformación biológica 
que representa (cuando aplica), el usuario o 
proceso responsable y el resultado de la operación.

El registro es append-only: los eventos no pueden 
ser modificados ni eliminados una vez persistidos.

**Justificación:** Evidencia de Transformación Biológica para NIC 41:
La NIC 41 exige que los cambios en el valor 
razonable del activo biológico sean reconocidos 
en los estados financieros conforme al párrafo 12, 
sustentados en la transformación biológica real 
del animal. RF-52 provee el registro continuo e 
inmutable de esa transformación — eventos de 
crecimiento, cambios de fase, eventos sanitarios, 
reproductivos y productivos — que M06 necesita 
para construir registros contables auditables. 
Sin RF-52, M06 no puede demostrar ante una 
auditoría externa que la valoración está respaldada 
por datos verificables.

Trazabilidad Completa del Ciclo de Vida del Activo:
El historial de RF-46 registra qué ocurrió con 
el activo. RF-52 registra quién lo hizo, cuándo, 
desde qué módulo y con qué resultado. Son 
complementarios: RF-46 es la historia biológica 
del activo; RF-52 es la cadena de custodia de 
esa historia. Sin RF-52, el historial de RF-46 
no es auditable.

Infraestructura Transversal Compartida:
Al centralizar el registro en RF-52, todos los 
demás RF del módulo delegan la responsabilidad 
de auditoría a un único componente, garantizando 
consistencia del formato, eliminando duplicación 
de lógica de logging y asegurando que ningún 
evento quede sin registro.

Soporte al Control Normativo Pecuario:
El ICA exige trazabilidad de eventos sanitarios 
por activo biológico para certificaciones y 
movilización de ganado. La UPRA exige evidencia 
de la transformación productiva para valoración 
de predios agropecuarios. RF-52 provee el 
registro estructurado que soporta ambos requerimientos 
sin procesamiento adicional.

Diagnóstico y Mejora Continua:
El registro de eventos fallidos, rechazos y errores 
con su causa permite al administrador identificar 
patrones de mal uso, inconsistencias en los datos 
y problemas operativos antes de que afecten los 
procesos contables o sanitarios.

**Precondiciones:** 1. Todos los RF del Módulo M02 Operativos
RF-52 es receptor pasivo de eventos. Su 
funcionamiento depende de que los demás 
componentes del módulo emitan correctamente 
los eventos que deben registrarse.

2. Almacenamiento Persistente Disponible
El repositorio de la bitácora debe estar 
operativo y con capacidad suficiente antes 
de que cualquier otro RF del módulo inicie 
operaciones. Sin repositorio disponible, 
ningún RF debe completar operaciones de 
escritura sobre activos biológicos.

3. Usuarios Autenticados para Consulta (RF-02, M01)
El acceso a la bitácora de auditoría está 
controlado por el RBAC de M01. Los roles 
con acceso de consulta son: Administrador 
(acceso total), Contador/Revisor Fiscal 
(eventos relacionados con transformación 
biológica y valoración NIC 41), Veterinario 
(eventos sanitarios, reproductivos y de 
crecimiento), Productor (eventos de sus 
propios activos, lectura limitada).

4. Sincronización de Tiempo (NTP)
Todos los eventos registrados deben tener 
timestamps coherentes con la misma fuente 
de tiempo, garantizando el orden cronológico 
correcto de la bitácora y la consistencia 
con los timestamps de RF-53 (M03) para 
correlación entre módulos.

5. Contrato de Integración con RF-63 (M03)
Para eventos que involucren simultáneamente 
datos biológicos y datos de telemetría 
(ej. RF-49 — asociación con sensores), 
ambas bitácoras (RF-52 y RF-63) deben 
registrar el evento de forma independiente 
con referencia cruzada mediante un 
id_evento_correlacionado cuando aplique.

**Restricciones:** 1. Inmutabilidad Absoluta de la Bitácora
Los registros de auditoría no pueden ser 
modificados, corregidos ni eliminados por 
ningún usuario ni proceso del sistema. 
La bitácora es append-only. Esta restricción 
debe estar implementada a nivel de base de 
datos, no solo a nivel de lógica de negocio.

2. Registro Obligatorio Sin Excepción
Todo evento definido en los RF del módulo 
debe registrarse independientemente de su 
resultado (exitoso, fallido o rechazado). 
Un evento no registrado constituye una 
violación de trazabilidad que invalida la 
cadena de custodia del activo biológico.

3. Sin Impacto en el Flujo Operativo
El registro en la bitácora debe ser 
asíncrono. Un fallo en RF-52 no puede 
bloquear ni retrasar las operaciones de 
los demás RF del módulo M02 sobre los 
activos biológicos, excepto en los casos 
donde el propio RF indique que la 
disponibilidad de auditoría es precondición 
obligatoria (ej. RF-49 revierte la 
operación si RF-52 no está disponible).

4. Separación del Repositorio
La bitácora de RF-52 debe almacenarse en 
un repositorio independiente del repositorio 
de activos biológicos y del repositorio de 
historial (RF-46), para garantizar que un 
fallo en el almacenamiento principal no 
afecte la integridad del registro de auditoría.

5. Retención Mínima Configurable
Los registros deben retenerse por periodos 
mínimos diferenciados:
  Eventos de transformación biológica 
  vinculados a NIC 41: mínimo 5 años.
  Eventos sanitarios vinculados al ICA: 
  mínimo 5 años.
  Eventos operativos y técnicos generales: 
  mínimo 2 años.
  Todos los periodos son configurables por 
  el administrador sin modificar código.

6. Acceso de Solo Lectura para Usuarios Finales
Ningún usuario, independientemente de su 
rol, puede escribir directamente en la 
bitácora. Solo los componentes internos 
del módulo M02 pueden emitir eventos 
de auditoría hacia RF-52.

7. Clasificación Obligatoria del Evento como 
   Transformación Biológica
Cada evento debe ser clasificado como:
  TRANSFORMACION_BIOLOGICA: si el evento 
    representa un cambio cuantitativo o 
    cualitativo en el activo biológico 
    (crecimiento, cambio de fase, evento 
    productivo, reproductivo). Estos eventos 
    son los que M06 consume directamente.
  GESTION_OPERATIVA: si el evento es de 
    administración sin impacto directo en 
    la biología del activo (consultas, 
    cambios de infraestructura, asociaciones).
  SANITARIO: si el evento corresponde a 
    intervención clínica o sanitaria.
  CONTROL_ESTADO: si corresponde a cambio 
    de estado del activo (RF-44, RF-45, RF-38).
  ACCESO_DATOS: si corresponde a consultas 
    de historial o ficha integral.

**Prioridad:** [X] Alta/Must  [ ] Media/Should  [ ] Baja/Could

**Dependencia:** RF-33 a RF-51 — Todos los RF del Módulo M02
Tipo: Dependencia de emisión de eventos
Cada RF emite eventos que RF-52 debe registrar. 
RF-52 no depende funcionalmente de ninguno 
en particular; depende de todos como fuentes 
de eventos.

RF-02 — Autenticación de Usuarios
Tipo: Dependencia de seguridad
El acceso de consulta a la bitácora está 
controlado por el RBAC de M01 en conjunción 
con RF-02.

RF-46 — Historial del Activo Biológico
Tipo: Dependencia de complementariedad
RF-46 y RF-52 son complementarios. RF-46 
registra qué ocurrió biológicamente; RF-52 
registra quién lo hizo y con qué resultado. 
Cada consulta de RF-46 queda registrada 
en RF-52.

RF-63 — Auditoría y Trazabilidad de M03
Tipo: Dependencia de correlación cruzada
Para eventos que involucran tanto datos 
biológicos (M02) como datos de telemetría 
(M03), ambas bitácoras registran el evento 
de forma independiente con referencia cruzada.

**Actores:** Productor, Veterinario, Sistema (M08, M04)

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_evento | UUID | Identificador único del evento de auditoría, generado automáticamente por RF-52 al recibir la emisión. |
| rf_origen | Enum | RF del módulo M02 que emite el evento: RF33, RF34, RF35, RF36, RF37, RF38, RF39, RF40, RF41, RF42, RF43, RF44, RF45, RF46, RF47, RF48, RF49, RF50, RF51. |
| tipo_evento | Enum | Categoría del evento según el catálogo definido (ver sección Proceso). |
| clasificacion_biologica | Enum | Clasificación del evento: TRANSFORMACION_BIOLOGICA, GESTION_OPERATIVA, SANITARIO, CONTROL_ESTADO, ACCESO_DATOS. |
| activo_biologico_id | Integer | Identificador del activo biológico afectado. Obligatorio cuando el evento corresponde a un activo específico. |
| tipo_activo | Enum | INDIVIDUAL o POBLACIONAL. Permite segmentar la bitácora por modelo de gestión. |
| timestamp_evento | Timestamp (ISO-8601 UTC) | Momento exacto en que ocurrió el evento en el RF emisor. |
| timestamp_registro | Timestamp (ISO-8601 UTC) | Momento en que RF-52 persiste el registro. Puede diferir del anterior en escenarios asíncronos. |
| resultado | Enum | Resultado de la operación: EXITOSO, FALLIDO, RECHAZADO, ADVERTENCIA. |
| descripcion | String | Descripción legible del evento. Máximo 500 caracteres. |
| detalle_tecnico | JSON | Información técnica adicional: campos afectados, valores antes/después, causa del error, motivo del rechazo. |
| id_usuario_responsable | Integer (opcional) | Usuario que desencadenó el evento. Nulo para eventos generados automáticamente por el sistema o por módulos consumidores. |
| modulo_consumidor | String (opcional) | Módulo externo que originó el evento (ej. M03, M04, M06) cuando el emisor es un módulo consumidor y no un usuario. |
| severidad_log | Enum | Nivel de severidad: INFO, WARNING, ERROR, CRITICAL. |
| id_evento_correlacionado | UUID (opcional) | Identificador del evento correspondiente en RF-63 (M03) para eventos que involucran simultáneamente datos biológicos y telemetría (ej. RF-49). |
| RF Origen	Tipos de Evento
RF-33	ACTIVO_REGISTRADO, ACTIVO_REGISTRO_FALLIDO, ACTIVO_REGISTRO_RECHAZADO
RF-34	INFRAESTRUCTURA_CONSULTADA, INFRAESTRUCTURA_CASO_ESPECIAL_REGISTRADO, HISTORIAL_INFRAESTRUCTURA_CONSULTADO, INCONSISTENCIA_INFRAESTRUCTURA_DETECTADA
RF-35	ACTIVO_INDIVIDUAL_ACTUALIZADO, ACTIVO_INDIVIDUAL_CONSULTA
RF-36	POBLACION_ACTUALIZADA, METRICA_POBLACIONAL_RECALCULADA, DENSIDAD_EXCEDIDA_DETECTADA
RF-37	FASE_CAMBIADA, FASE_CAMBIO_NO_ESTANDAR_CONFIRMADO, FASE_CAMBIO_RECHAZADO, SOLAPAMIENTO_FASE_DETECTADO
RF-38	CICLO_CERRADO, CIERRE_CICLO_FALLIDO, CIERRE_CICLO_RECHAZADO
RF-39	EVENTO_BIOLOGICO_REGISTRADO, EVENTO_BIOLOGICO_RECHAZADO
RF-40	EVENTO_CRECIMIENTO_REGISTRADO, EVENTO_CRECIMIENTO_RECHAZADO
RF-41	EVENTO_SANITARIO_REGISTRADO, EVENTO_SANITARIO_RECHAZADO, SECUENCIA_SANITARIA_VIOLADA
RF-42	EVENTO_REPRODUCTIVO_REGISTRADO, EVENTO_REPRODUCTIVO_RECHAZADO, RELACION_GENEALOGICA_REGISTRADA, SECUENCIA_REPRODUCTIVA_VIOLADA
RF-43	EVENTO_PRODUCTIVO_REGISTRADO, EVENTO_PRODUCTIVO_RECHAZADO, DUPLICADO_PRODUCTIVO_DETECTADO
RF-44	ESTADO_CAMBIADO, ESTADO_CAMBIO_RECHAZADO, ESTADO_REDUNDANTE_DETECTADO, TRANSICION_NO_PERMITIDA
RF-45	BAJA_REGISTRADA, BAJA_PARCIAL_REGISTRADA, BAJA_RECHAZADA
RF-46	HISTORIAL_CONSULTADO, HISTORIAL_EXPORTADO, HISTORIAL_SIN_RESULTADOS
RF-47	FICHA_CONSULTADA, FICHA_CARGA_PARCIAL, INCONSISTENCIA_FICHA_DETECTADA
RF-48	TRANSFERENCIA_REGISTRADA, TRANSFERENCIA_RECHAZADA, TRANSFERENCIA_CONCURRENTE_BLOQUEADA
RF-49	ASOCIACION_IOT_CREADA, ASOCIACION_IOT_DESACTIVADA, ASOCIACION_IOT_RECHAZADA, ASOCIACION_IOT_CORREGIDA
RF-50	DATOS_ANALITICOS_CONSULTADOS, DATOS_ANALITICOS_RECHAZADOS, RATE_LIMIT_EXCEDIDO
RF-51	INDICADOR_CALCULADO, INDICADOR_CALCULO_FALLIDO, INDICADOR_DATOS_INSUFICIENTES
 |  |  |

**Proceso:**

Fase 1: Recepción del Evento desde el RF Emisor

Cada RF del módulo M02 emite un evento a RF-52 
de forma asíncrona al finalizar una operación 
relevante (exitosa o fallida). El evento incluye 
todos los campos del esquema de entrada definido.

El servicio de auditoría recibe el evento mediante 
cola de mensajes interna para garantizar que el 
RF emisor no espere confirmación y su flujo 
operativo no sea bloqueado.

Fase 2: Validación y Enriquecimiento del Registro

RF-52 añade automáticamente:
  id_evento: UUID generado por RF-52
  timestamp_registro: momento de persistencia
  clasificacion_biologica: asignada automáticamente 
    según rf_origen y tipo_evento mediante tabla 
    de clasificación configurada en M09
  hash_integridad: hash del contenido completo 
    del registro para verificación posterior

Si el evento proviene de RF-49 y tiene evento 
correlacionado en RF-63 (M03), se registra 
id_evento_correlacionado.

Fase 3: Persistencia Inmutable

El registro se almacena con garantías de:
  Escritura atómica (todo o nada)
  Append-only (sin UPDATE ni DELETE)
  Indexación por: timestamp_evento, rf_origen, 
    tipo_evento, activo_biologico_id, 
    clasificacion_biologica, id_usuario_responsable, 
    resultado

Fase 4: Manejo de Fallo de Persistencia

Si el repositorio principal no está disponible:
  El evento se almacena en buffer temporal 
  (memoria o almacenamiento local)
  El RF emisor no es notificado del fallo 
  (salvo los RF que definen la disponibilidad 
  de auditoría como precondición obligatoria)
  Al recuperarse el repositorio, los eventos 
  en buffer se persisten en orden cronológico

Fase 5: Exposición para Consulta

El servicio expone una API de consulta con:
  Filtros: rango de fechas, rf_origen, 
    tipo_evento, activo_biologico_id, 
    clasificacion_biologica, id_usuario_responsable, 
    resultado, severidad_log
  Paginación obligatoria (estándar M01)
  Exportación en JSON o CSV
  Control de acceso diferenciado por rol (M01)
  Filtro adicional para M06: solo eventos con 
    clasificacion_biologica = TRANSFORMACION_BIOLOGICA 
    o SANITARIO en un rango de fechas específico

**Flujo alterno:**

E1. Fallo Persistente del Repositorio de Auditoría

Situación:
El repositorio de RF-52 no está disponible 
por un periodo extendido.

Comportamiento:
  Los eventos continúan acumulándose en buffer
  Se genera una alerta técnica al administrador
  Al recuperarse, se persisten en orden 
  cronológico sin pérdida
  Se registra el periodo de indisponibilidad 
  en el repositorio al recuperarse
  Los RF que definen auditoría como precondición 
  obligatoria (ej. RF-49) deben revertir sus 
  operaciones hasta que RF-52 esté disponible

E2. Evento con Esquema Incompleto

Situación:
Un RF emisor envía un evento sin todos los 
campos obligatorios (ej. sin activo_biologico_id 
en un evento que lo requiere).

Comportamiento:
  Se persiste igualmente con los campos 
  disponibles
  Se marca con flag: registro_incompleto = true
  Se registra la causa de la incompletitud
  No se rechaza el evento (principio: no 
  perder trazabilidad por error de formato)
  Se genera WARNING al administrador

E3. Tormenta de Eventos (Alta Carga)

Situación:
Se generan eventos a una tasa superior a 
la capacidad de procesamiento (ej. durante 
registro masivo de eventos de crecimiento 
para múltiples lotes simultáneamente).

Comportamiento:
  Se aplica control de tasa con priorización:
    CRITICAL y ERROR → procesamiento inmediato
    TRANSFORMACION_BIOLOGICA → alta prioridad
    INFO → encolados y procesados por lotes
  Ningún evento se descarta
  Se registra el inicio del evento de alta 
  carga como ADVERTENCIA en la bitácora

E4. Solicitud de Consulta sin Permisos

Situación:
Un usuario intenta consultar eventos de 
una clasificación o de activos a los que 
no tiene acceso según su rol.

Comportamiento:
  HTTP 403 Forbidden
  Mensaje: "No tiene permisos para consultar 
  eventos de tipo [clasificacion_biologica] 
  o del activo [activo_biologico_id]."
  El intento queda registrado en la propia 
  bitácora con tipo_evento = ACCESO_NO_AUTORIZADO

E5. Inconsistencia entre RF-52 y RF-46

Situación:
Al comparar el historial de RF-46 con la 
bitácora de RF-52, se detectan eventos en 
RF-46 sin su correspondiente registro en RF-52.

Comportamiento:
  Se genera una alerta CRITICAL al administrador
  Se registra el incidente con los 
  identificadores de los eventos inconsistentes
  La información de RF-46 no se modifica
  El administrador puede crear un registro 
  correctivo en RF-52 con tipo_evento = 
  REGISTRO_CORRECTIVO_AUDITORIA y el motivo

**Salida:**

1. Registro de Auditoría Persistido

Por cada evento recibido, un registro inmutable 
con todos los campos del esquema de entrada 
más los enriquecidos por RF-52:

  id_evento (UUID)
  rf_origen
  tipo_evento
  clasificacion_biologica
  activo_biologico_id / tipo_activo
  timestamp_evento / timestamp_registro
  resultado
  descripcion
  detalle_tecnico (JSON)
  id_usuario_responsable (si aplica)
  modulo_consumidor (si aplica)
  severidad_log
  id_evento_correlacionado (si aplica)
  hash_integridad
  registro_incompleto (Boolean, si aplica)

2. API de Consulta de Bitácora

Interfaz de solo lectura que retorna registros 
filtrados con paginación, accesible por 
usuarios autorizados según su rol en M01.

Vista especializada para M06 que retorna 
exclusivamente los eventos con 
clasificacion_biologica = TRANSFORMACION_BIOLOGICA 
o SANITARIO, con sus detalles de variables 
antes/después, ordenados cronológicamente.

3. Exportación de Registros

Conjunto de registros filtrados exportables 
en JSON o CSV para:
  Evidencia técnica de transformación biológica 
  para M06 (NIC 41)
  Reportes de trazabilidad sanitaria para 
  ICA (RF-41, RF-42)
  Reportes para UPRA (M08)
  Diagnóstico técnico del administrador

4. Indicadores de Actividad de la Bitácora

Métricas disponibles para M08:
  eventos_por_periodo_y_clasificacion
  eventos_por_rf_origen
  eventos_por_resultado
  eventos_transformacion_biologica_por_activo
  eventos_criticos_en_periodo
  activos_con_mayor_actividad_registrada
  periodos_sin_registro (para detectar vacíos)

**Postcondiciones:**

1. Registro Persistido de Forma Inmutable
Cada evento emitido por cualquier RF del 
módulo M02 tiene su registro correspondiente 
en la bitácora, sin posibilidad de modificación 
posterior.

2. Cadena de Custodia de Transformación Biológica 
   Disponible para NIC 41
M06 puede obtener de RF-52 la secuencia 
completa e inmutable de todos los eventos 
de transformación biológica de un activo 
en cualquier periodo, con el usuario o proceso 
responsable y el resultado de cada operación.

3. Trazabilidad Completa de Cualquier Activo
Dado cualquier activo_biologico_id, es posible 
consultar en RF-52 la secuencia completa 
de todos los eventos que le afectaron desde 
su registro (RF-33) hasta su baja (RF-45), 
en orden cronológico exacto.

4. Repositorio Operativo Sin Afectar el Sistema
El servicio de auditoría opera de forma 
asíncrona. Ningún fallo o lentitud en RF-52 
ha afectado las operaciones de los demás 
RF del módulo M02 sobre los activos biológicos, 
salvo los RF que definen auditoría como 
precondición obligatoria.

5. Integridad Verificable
El hash_integridad de cada registro permite 
verificar que no fue alterado desde su 
persistencia, garantizando la validez de 
la bitácora como evidencia técnica.

**Criterios de aceptación:**

CA-1: Registro de todos los eventos definidos
Dado cualquier operación realizada por RF-33 
a RF-51 del módulo M02,
cuando el RF emisor finalice la operación 
(exitosa o fallida),
entonces RF-52 debe persistir el evento en 
≤ 2 segundos con todos los campos requeridos 
y el hash_integridad generado.

CA-2: Clasificación correcta como transformación biológica
Dado un evento de crecimiento (RF-40), cambio 
de fase (RF-37), evento productivo (RF-43) o 
reproductivo (RF-42),
cuando sea registrado por RF-52,
entonces debe tener clasificacion_biologica = 
TRANSFORMACION_BIOLOGICA para que M06 pueda 
consumirlo como evidencia de valoración NIC 41.

CA-3: Inmutabilidad de la bitácora
Dado cualquier registro persistido en RF-52,
cuando cualquier proceso o usuario intente 
modificarlo o eliminarlo,
entonces el sistema debe rechazar la operación 
y registrar el intento en la propia bitácora.

CA-4: Continuidad ante fallo del repositorio
Dado un fallo en el repositorio de auditoría,
cuando los RF del módulo continúen emitiendo eventos,
entonces ningún evento debe perderse; deben 
acumularse en buffer y persistirse al 
recuperarse el repositorio en orden cronológico.

CA-5: No impacto en flujo operativo
Dado que el servicio de auditoría experimenta 
alta latencia o un fallo temporal,
cuando un RF del módulo M02 ejecute una 
operación sobre un activo biológico,
entonces dicho flujo no debe verse bloqueado 
ni retrasado por RF-52 (excepto los RF que 
definen auditoría como precondición).

CA-6: Consulta filtrada por activo y clasificación
Dado un activo_biologico_id específico,
cuando el contador consulte la bitácora con 
filtro clasificacion_biologica = 
TRANSFORMACION_BIOLOGICA,
entonces debe obtener exclusivamente los eventos 
de crecimiento, cambio de fase, eventos 
productivos y reproductivos del activo, en 
orden cronológico, con el usuario o módulo 
responsable de cada uno.

CA-7: Cadena de custodia completa para NIC 41
Dado el periodo entre dos cierres contables,
cuando M06 consulte la bitácora para un activo 
biológico en ese rango de fechas,
entonces debe poder rastrear: registro inicial 
(RF-33) → cambios de fase (RF-37) → eventos 
de crecimiento (RF-40) → eventos productivos 
(RF-43) → estado al cierre del periodo (RF-44), 
con timestamps y usuarios de cada etapa.

CA-8: Control de acceso diferenciado por rol
Dado un usuario con rol Productor,
cuando intente consultar eventos con 
clasificacion_biologica = ACCESO_DATOS 
de otros productores,
entonces el sistema debe denegar el acceso 
y registrar el intento en la bitácora.
Dado un Contador,
entonces debe tener acceso solo a eventos 
TRANSFORMACION_BIOLOGICA y SANITARIO.

CA-9: Correlación con RF-63 en eventos IoT
Dado una operación de asociación sensor-activo 
(RF-49) que genera eventos en ambos módulos,
cuando ambos eventos sean registrados,
entonces el registro en RF-52 debe contener 
el id_evento_correlacionado del registro 
correspondiente en RF-63, y viceversa.

CA-10: Registro de eventos fallidos y rechazados
Dado cualquier operación rechazada o fallida 
en cualquier RF del módulo M02,
cuando el RF emita el evento de fallo,
entonces RF-52 debe registrarlo con resultado = 
FALLIDO o RECHAZADO y el detalle_tecnico 
con la causa, igual que un evento exitoso.

CA-11: Integridad verificable por hash
Dado cualquier registro en la bitácora,
cuando el sistema verifique su hash_integridad 
al momento de una auditoría,
entonces debe coincidir con el contenido actual 
del registro, confirmando que no fue alterado 
desde su persistencia.

CA-12: Exportación para ICA y UPRA
Dado una solicitud de exportación de eventos 
sanitarios (RF-41) o de transformación 
biológica en un periodo específico,
cuando M08 o el contador la soliciten,
entonces el sistema debe generar el archivo 
JSON o CSV en ≤ 15 segundos para conjuntos 
de hasta 10,000 registros.

CA-13: Indicadores de actividad disponibles para M08
Dado el conjunto de eventos registrados 
en un periodo,
cuando M08 consulte los indicadores de 
actividad de la bitácora,
entonces debe obtener: eventos por clasificación, 
eventos por RF origen, activos con mayor 
actividad y periodos sin registro detectados.

**Requerimientos no funcionales:**

Latencia de Persistencia (Desempeño)
El registro de cada evento debe completarse 
en ≤ 2 segundos desde su recepción, operando 
de forma asíncrona sin impactar el RF emisor.

Disponibilidad del Servicio (Disponibilidad)
El servicio de auditoría debe mantener 
disponibilidad ≥ 99.5%. Ante caídas, el 
buffer temporal garantiza cero pérdida de 
eventos durante al menos 24 horas de 
indisponibilidad del repositorio.

Inmutabilidad Técnica (Confiabilidad)
El repositorio debe implementarse con garantías 
técnicas de append-only a nivel de base de 
datos (sin operaciones UPDATE/DELETE sobre 
registros de auditoría). La inmutabilidad 
debe ser verificable mediante hash de 
integridad por registro.

Retención Diferenciada (Cumplimiento)
Los eventos con clasificacion_biologica = 
TRANSFORMACION_BIOLOGICA y SANITARIO deben 
retenerse un mínimo de 5 años para cumplir 
requisitos de NIC 41 e ICA. Los eventos 
GESTION_OPERATIVA y ACCESO_DATOS se retienen 
un mínimo de 2 años. Ambos periodos son 
configurables por el administrador.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---
