# Especificación de Requerimientos — Módulo 9

_Convertido de `Especificacion de requerimiento (1).xlsx`, hoja "Modulo 9". Original en `backups/1-analisis/`._

## RF-15 — Catálogo de especies productivas

**Código Identificación:** RF-15 -- Versión -- 1.0

**Fuente:** Administrador / Ingeniero de campo

**Descripción:** El sistema deberá permitir gestionar el catálogo de especies productivas mediante operaciones de registro, consulta, edición y desactivación lógica (no eliminación física).

Cada especie deberá registrarse con un nombre único, sujeto a reglas de validación definidas (longitud, formato y normalización de mayúsculas/minúsculas).

El sistema deberá garantizar el control de estado (activo/inactivo) de cada especie para determinar su disponibilidad en los demás módulos del sistema.

Cuando una especie se encuentre inactiva:
- No podrá ser utilizada para registrar nuevos activos biológicos.
- No aparecerá en formularios de nuevos registros en otros módulos.
- Los datos históricos asociados (monitoreo, IA, valoración financiera bajo NIC 41) deberán mantenerse disponibles para consulta.

El sistema deberá permitir la reactivación de especies sin pérdida de integridad de la información asociada.

**Justificación:** El catálogo de especies constituye la base de configuración del sistema, ya que permite consultar los activos biológicos gestionados dentro de la plataforma.

La existencia de este catálogo facilita la parametrización de los módulos de monitoreo, predicción sanitaria y valoración financiera, permitiendo mantener la trazabilidad de los activos biológicos conforme a los lineamientos de valoración definidos en la NIC 41.

**Precondiciones:** El usuario debe tener una sesión activa dentro del sistema.

El usuario debe tener el rol Administrador o tener los permisos necesarios (Ingeniero de campo) dentro del sistema.

El sistema debe encontrarse disponible y operativo. |   

**Restricciones:** El nombre de la especie debe ser único dentro del catálogo, aplicando normalización case-insensitive (sin distinción entre mayúsculas y minúsculas).

El campo nombre es obligatorio y deberá tener una longitud entre 3 y 50 caracteres.

El campo descripción es opcional.

No se permite la eliminación física de especies; únicamente se permite su desactivación lógica mediante el campo activo.

Los usuarios con rol Administrador podrán crear, editar y desactivar especies.

Los usuarios con rol Ingeniero de Campo únicamente podrán editar especies existentes, pero no crearlas ni desactivarlas.

No se permite desactivar una especie si existen procesos críticos activos en ejecución que dependan de ella (ejemplo: entrenamiento activo de modelos IA).

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** Requisito base del sistema.

Genera dependencia para los siguientes módulos:
- Módulo de monitoreo IoT
- Módulo de inteligencia artificial (predicción sanitaria)
- Módulo financiero (valoración de activos biológicos bajo NIC 41)
- Módulo de infraestructura productiva

**Actores:** Administrador del sistema, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_especie | serial / integer | (Obligatorio) Identificador único de la especie dentro del sistema. |
| nombre_especie | varchar(50) | Nombre de la especie productiva registrada. |
| descripcion_especie | varchar(255) | (Opcional) Descripción general o información adicional de la especie. |
| fecha_creacion_especie | timestamp with time zone | Fecha y hora en que se registró la especie en el sistema. |
| fecha_actualizacion_especie | timestamp with time zone | Fecha y hora de la última modificación del registro (actualizado automáticamente por el sistema). |
| activo | boolean | (Default True) Indica si la especie se encuentra activa o disponible en el sistema. |

**Proceso:**

1. El usuario accede al módulo de Configuración.

2. El sistema valida que el usuario tenga sesión activa y permisos según su rol:
   - Administrador: crear, editar, desactivar
   - Ingeniero de Campo: solo editar

3. El sistema muestra el catálogo de especies registradas.

4. Registro de especie (solo Administrador):
   - El usuario ingresa nombre y descripción.
   - El sistema valida:
     - Nombre obligatorio
     - Longitud entre 3 y 50 caracteres
     - Unicidad (case-insensitive)
   - Si la validación falla, se rechaza la operación con mensaje de error.
   - Si es válida, se almacena la especie con estado activo.

5. Edición de especie:
   - El usuario modifica los datos permitidos.
   - El sistema valida las reglas de unicidad y formato.
   - Se actualiza fecha_actualizacion.

6. Desactivación de especie (solo Administrador):
   - El sistema valida que no existan procesos críticos activos.
   - Se cambia el estado a inactivo.

7. Control de concurrencia:
   - Si dos usuarios intentan editar simultáneamente, el sistema deberá rechazar la segunda operación con error de conflicto.

8. El sistema registra todas las operaciones en el historial de auditoría.

9. Modo offline:
   - Si no hay conexión, las operaciones se almacenan localmente.
   - Se sincronizan automáticamente al restablecer conexión.

**Flujo alterno:**

Nombre de especie duplicado (Normalización Case-Insensitive):

El usuario intenta registrar una especie con un nombre que ya existe (ej: intenta crear "BOVINO" cuando ya existe "bovino").

El sistema detecta la coincidencia tras normalizar el texto a minúsculas.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de duplicidad. La especie '[NOMBRE_INGRESADO]' ya se encuentra registrada en el catálogo. El nombre debe ser único independientemente de las mayúsculas o minúsculas."

Incumplimiento de longitud o formato de nombre:

El nombre ingresado tiene menos de 3 caracteres, más de 50, o contiene caracteres especiales no permitidos.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de validación. El nombre de la especie debe tener entre 3 y 50 caracteres y no puede contener símbolos especiales. Verifique la entrada '[NOMBRE_INGRESADO]'."

Acceso no autorizado (Ingeniero de Campo intentando Crear/Desactivar):

Un usuario con rol 'Ingeniero de Campo' intenta acceder al endpoint de creación (POST) o desactivación (PATCH/DELETE).

El sistema bloquea la acción basándose en la matriz de permisos.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Privilegios insuficientes. Su rol (Ingeniero de Campo) solo permite la edición de descripciones o nombres existentes, no la creación ni la desactivación de especies."

Desactivación bloqueada por proceso crítico activo:

El administrador intenta desactivar una especie (ej: "Porcino") mientras el Módulo de Predicción (M04) está ejecutando un reentrenamiento de modelos de IA para esa especie específica.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Operación denegada. La especie '[NOMBRE_ESPECIE]' no puede ser desactivada porque actualmente es requerida por el proceso crítico: [NOMBRE_PROCESO_IA]. Finalice el proceso antes de intentar de nuevo."

Conflicto de edición concurrente (Control Optimista):

Dos usuarios abren la misma especie para editarla; el primero guarda con éxito, el segundo intenta guardar después.

El sistema detecta que la fecha_actualizacion enviada por el segundo usuario es anterior a la almacenada en la base de datos.

El sistema responde con:

HTTP 412: Precondition Failed

Mensaje: "Conflicto de concurrencia. Los datos de la especie han sido modificados por otro usuario mientras usted realizaba los cambios. Por favor, recargue el catálogo y aplique sus ediciones sobre la versión más reciente."

Error de sincronización en modo offline:

El sistema intenta sincronizar una nueva especie creada localmente, pero al llegar al servidor, el nombre ya fue tomado por otro usuario durante el periodo de desconexión.

El sistema marca el registro local con error y notifica al usuario en la próxima conexión.

El sistema responde con:

Notificación UI: "Fallo de sincronización. La especie creada en modo offline '[NOMBRE_ESPECIE]' ya existe en el servidor. Por favor, resuelva el conflicto manualmente."

Especie no encontrada:

Se intenta editar o desactivar un id_especie que no existe en la base de datos (posible manipulación de la petición).

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Recurso no encontrado. La especie con ID [ID_SOLICITADO] no existe en el catálogo productivo." | B

**Salida:**

Especie registrada o actualizada dentro del catálogo del sistema.

Catálogo actualizado disponible para los demás módulos.

Registro de la operación en el historial de auditoría que incluye:
- Usuario
- Fecha y hora
- Tipo de operación (CREATE, UPDATE, DEACTIVATE)
- Valores anteriores y nuevos

**Postcondiciones:**

La especie queda disponible para su uso en módulos dependientes si está activa.

Las especies inactivas no podrán ser utilizadas en nuevos registros, pero sus datos históricos permanecerán accesibles.

Los cambios realizados quedan registrados en el sistema de auditoría.

La integridad de los datos asociados en módulos de monitoreo, IA y valoración financiera (NIC 41) se mantiene.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

- El sistema impide registrar especies con nombres duplicados (validación case-insensitive).
- El sistema valida correctamente los permisos por rol:
  - Administrador: puede crear, editar y desactivar.
  - Ingeniero de Campo: solo puede editar.
- El sistema permite consultar el catálogo en un tiempo de respuesta menor a 2 segundos.
- El sistema registra en auditoría:
  - Usuario
  - Fecha/hora
  - Tipo de operación (CREATE, UPDATE, DEACTIVATE)
  - Datos modificados
- El sistema impide la eliminación física de registros.
- El sistema permite desactivar especies sin afectar datos históricos.
- El sistema impide registrar nuevos activos con especies inactivas.
- El sistema maneja conflictos de concurrencia devolviendo error HTTP 409.
- En modo offline:
  - El sistema permite registrar cambios localmente.
  - Los cambios se sincronizan automáticamente al recuperar conexión.

**Requerimientos no funcionales:**

Usabilidad:
- El catálogo debe mostrarse en una tabla con paginación y búsqueda por nombre.

Seguridad:
- El acceso debe estar restringido mediante autenticación JWT válida.
- Validación de permisos basada en RBAC.

Fiabilidad:
- El sistema debe garantizar consistencia ante operaciones concurrentes.

Rendimiento:
- Tiempo de respuesta menor a 2 segundos en consultas.

Disponibilidad:
- El sistema debe soportar operación en modo offline con sincronización diferida.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-16 — Configuración de Etapas Productivas y Patologías por Especie

**Código Identificación:** RF-16 -- Versión -- 1.2

**Fuente:** Administrador del sistema / Veterinario

**Descripción:** El sistema deberá permitir configurar, por cada especie registrada, las etapas del ciclo productivo, las patologías asociadas y las métricas productivas medibles, como elementos estructurados de referencia para los módulos del sistema.

Las métricas productivas representan los tipos de medición que pueden registrarse para cada especie durante sus eventos de crecimiento y producción (ej. peso en bovinos, volumen de leche en vacas lecheras, número de huevos en aves). Cada métrica debe incluir nombre, unidad de medida válida, tipo de medición y estado (activo/inactivo).

**(RFC-004)** Además, cada métrica debe declarar de forma explícita su **tipo de dato**, su **obligatoriedad** y, cuando aplique, su **rango mínimo y máximo** — esta información es la que RF-33 (M02) consume para validar los `atributos_dinamicos` de un activo biológico contra la configuración de su especie. Ninguno de estos tres campos se infiere automáticamente de `tipo_medicion` ni de ningún otro campo: son valores que el Administrador/Veterinario configura de forma explícita al registrar o editar la métrica, precisamente para no introducir una regla de negocio no especificada (ej. asumir que `tipo_medicion = PESO` implica `tipo_dato = NUMERICO`).

Estos tres tipos de configuración (etapas, patologías y métricas productivas) son utilizados por los módulos de gestión productiva y de eventos biológicos (RF-39) para determinar qué tipos de medición solicitar al usuario según la especie del activo.

Las etapas del ciclo productivo representan fases definidas del desarrollo del animal (ej: crecimiento, engorde, producción), y deberán incluir nombre, duración estimada y estado (activo/inactivo).

Las patologías representan condiciones sanitarias asociadas a la especie, y deberán incluir nombre, descripción opcional y estado (activo/inactivo).

Estos elementos serán utilizados por los módulos de gestión productiva, monitoreo sanitario y valoración financiera, sin permitir la eliminación física de registros, garantizando la trazabilidad de la información.

**Justificación:** La definición del ciclo productivo por especie es fundamental para realizar la trazabilidad de los activos biológicos durante su desarrollo productivo.

Cada etapa del ciclo influye en la gestión operativa, el monitoreo sanitario y la valoración económica del activo, especialmente en el marco de valoración establecido por la NIC 41.

Por otra parte, la catalogación de patologías permite estandarizar el registro de eventos sanitarios que pueden afectar la productividad, el bienestar animal y el valor económico del activo biológico.

**Precondiciones:** El usuario debe tener sesión activa.

El usuario debe tener rol Administrador o Veterinario con permisos de configuración.

Debe existir al menos una especie registrada (RF-15).

**Restricciones:** El nombre de cada etapa debe ser obligatorio, único por especie y con longitud entre 3 y 50 caracteres.

La duración de la etapa debe ser un número entero positivo mayor a 0.

No se permite eliminación física de etapas; solo desactivación lógica.

No se puede desactivar una etapa si existen activos biológicos en dicha etapa.

El nombre de cada patología debe ser obligatorio, único por especie y con longitud entre 3 y 100 caracteres.

La descripción de la patología es opcional.

No se permite eliminación física de patologías; solo desactivación lógica.

No se puede desactivar una patología si existen eventos sanitarios asociados.

Todos los nombres deben validarse como case-insensitive.

El sistema debe rechazar cualquier dato inválido devolviendo mensaje de error.

El nombre de cada métrica productiva debe ser obligatorio, único por especie y con longitud entre 3 y 50 caracteres.

La unidad_medida y el tipo_medicion son obligatorios para métricas productivas.

No se permite eliminación física de métricas; solo desactivación lógica.

No se puede desactivar una métrica productiva si existen eventos de crecimiento o productivos registrados que la referencian.

La unidad_medida debe ser coherente con el 
tipo_medicion (ej. para PESO solo se permiten 
unidades de masa como kg, g, lb; para VOLUMEN 
solo litros, ml; para LONGITUD cm, m; para 
CONTEO solo "unidades").

**(RFC-004)** El tipo_dato de la métrica es obligatorio y debe ser uno de:
'NUMERICO', 'ENTERO', 'TEXTO', 'BOOLEANO'. Debe ser seleccionado
explícitamente por el usuario al registrar la métrica — el sistema no lo
infiere a partir de tipo_medicion ni de ningún otro campo.

**(RFC-004)** El campo es_obligatorio (booleano) indica si el atributo
dinámico correspondiente debe estar presente y no nulo al registrar un
activo biológico (RF-33) de la especie y tipo de activo a los que aplica
la métrica. Por defecto es `false`. Es independiente de aplica_a_tipo_activo
(que determina a qué tipo de activo aplica la métrica, no si es obligatoria).

**(RFC-004)** Los campos valor_min y valor_max son opcionales y solo
aplican cuando tipo_dato es 'NUMERICO' o 'ENTERO' — para 'TEXTO' o
'BOOLEANO' deben quedar nulos y el sistema los ignora si se envían. Cuando
ambos se definen, valor_min debe ser menor o igual a valor_max. Representan
el rango válido del valor ingresado para el atributo dinámico
correspondiente en RF-33.

**(RFC-004)** Retrocompatibilidad: las métricas productivas registradas
antes de este cambio no tienen tipo_dato asignado. El sistema no asigna
automáticamente un tipo_dato por inferencia — cada métrica existente debe
ser revisada y actualizada manualmente por un Administrador o Veterinario
antes de que la validación estricta de tipo_dato en RF-33 pueda aplicarse
sobre ella. Mientras una métrica no tenga tipo_dato configurado, es_obligatorio
se asume `false` (comportamiento actual, sin cambios retroactivos) y
valor_min/valor_max se asumen sin definir (sin rango aplicado).

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-15 — Catálogo de especies productivas

**Actores:** Administrador del sistema, Veterinario

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_parametro | serial  | Identificador único del parámetro productivo registrado. |
| especie_id | integer | Identificador de la especie a la que se asocia el parámetro. |
| tipo_parametro | varchar(20) | Identificador del tipo de parámetro que se está configurando. Campo obligatorio.
 Valores permitidos:
                               'ETAPA'
                               'PATOLOGIA'
                               'METRICA_PRODUCTIVA' |
| activo | boolean | (Default True) Indica si el parametro se encuentra activo o disponible en el sistema. |
| nombre_parametro | varchar(50)  | Nombre de parametro el cual debe tener entre 3 y 50 caracteres para etapas y para patologías.
No permite valores duplicados por especie (case-insensitive). |
| duracion_dias | integer  | (Solo para etapa) Duración estimada en días. 
Debe ser un número entero positivo mayor a 0.
No admite valores nulos ni negativos. |
| descripcion | varchar(255) | (Solo para patologia) Descripcion opcional
Máximo 255 caracteres. |
| unidad_medida | Varchar(20) | (Solo para METRICA_PRODUCTIVA) Unidad de medida de la métrica. Obligatorio. Ejemplos: kg, g, litros, unidades, cm, m. |
| tipo_medicion | Enum | (Solo para METRICA_PRODUCTIVA) Categoría de la medición. Valores permitidos: PESO, VOLUMEN, LONGITUD, CONTEO, OTRO. |
| aplica_a_tipo_activo | Enum | (Solo para METRICA_PRODUCTIVA) Indica si la métrica aplica a activos INDIVIDUAL, POBLACIONAL o AMBOS. |
| tipo_dato | Enum | **(RFC-004, solo para METRICA_PRODUCTIVA)** Tipo de dato del valor que se registrará para esta métrica en RF-33. Obligatorio, explícito. Valores permitidos: 'NUMERICO', 'ENTERO', 'TEXTO', 'BOOLEANO'. |
| es_obligatorio | boolean | **(RFC-004, solo para METRICA_PRODUCTIVA)** (Default False) Indica si el atributo dinámico correspondiente es obligatorio al registrar un activo biológico de la especie/tipo de activo al que aplica. |
| valor_min | Decimal(10,4) | **(RFC-004, solo para METRICA_PRODUCTIVA)** Opcional. Valor mínimo permitido. Solo aplica si tipo_dato es NUMERICO o ENTERO. |
| valor_max | Decimal(10,4) | **(RFC-004, solo para METRICA_PRODUCTIVA)** Opcional. Valor máximo permitido. Solo aplica si tipo_dato es NUMERICO o ENTERO. Si se define junto con valor_min, debe ser mayor o igual a este. |

**Proceso:**

1. El usuario accede al módulo de configuración.

2. El sistema valida sesión y permisos:
   - Administrador y Veterinario: crear, editar, desactivar.

3. El sistema muestra las especies disponibles.

4. El usuario selecciona una especie.

5. Registro de etapa:
   - El usuario ingresa nombre y duración.
   - El sistema valida:
     - Nombre obligatorio
     - Longitud (3–50)
     - Unicidad por especie (case-insensitive)
     - Duración > 0
   - Si falla, retorna error y no guarda.
   - Si es válido, guarda como activo.

6. Registro de patología:
   - El usuario ingresa nombre y descripción.
   - El sistema valida:
     - Nombre obligatorio
     - Unicidad
   - Si falla, retorna error.
   - Si es válido, guarda.

7. Registro de métrica productiva:
   El usuario ingresa nombre, unidad_medida, 
   tipo_medicion, aplica_a_tipo_activo, tipo_dato,
   es_obligatorio y, si aplica, valor_min/valor_max.
   
   El sistema valida:
     Nombre obligatorio
     Longitud entre 3 y 50 caracteres
     Unicidad del nombre por especie 
     (case-insensitive)
     Que unidad_medida no esté vacía
     Que tipo_medicion pertenezca al dominio 
     definido
     Que aplica_a_tipo_activo sea válido
     (RFC-004) Que tipo_dato pertenezca al dominio
     definido (NUMERICO, ENTERO, TEXTO, BOOLEANO)
     (RFC-004) Que valor_min/valor_max solo se
     definan si tipo_dato es NUMERICO o ENTERO, y
     que valor_min <= valor_max si ambos se envían
   Si falla → retorna error por campo.
   Si es válido → guarda como activo 
   con tipo_parametro = 'METRICA_PRODUCTIVA'.

8. Desactivación:
   - El sistema valida dependencias (activos/eventos).
   - Si existen, rechaza operación.
   - Si no, cambia estado a inactivo.

9. El sistema registra todas las acciones en auditoría.

**Salida:**

Configuración registrada o actualizada.

Listado actualizado de etapas y patologías por especie.

Registro en auditoría que incluye:
- Usuario
- Fecha/hora
- Tipo de operación
- Valores anteriores y nuevos

**Postcondiciones:**

Las etapas del ciclo productivo quedan disponibles para su uso en la gestión de lotes o activos biológicos.

Las patologías quedan disponibles para el registro de eventos sanitarios en los módulos de monitoreo y gestión sanitaria.

Las métricas productivas configuradas para cada especie quedan disponibles para el registro de eventos de crecimiento (tipo_medicion en RF-40) y eventos productivos (tipo_producto en RF-43), garantizando que RF-39 sepa qué tipos de medición son válidos para cada especie al momento de capturar el JSON datos_evento.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:
 
- El sistema impide duplicidad de nombres por especie (case-insensitive).
- El sistema valida duración > 0 para etapas.
- El sistema valida campos obligatorios.
- El sistema rechaza datos inválidos con HTTP 400.
- El sistema impide desactivar registros con dependencias.
- El sistema registra auditoría completa.
- El sistema responde en menos de 2 segundos.
- Los registros inactivos no aparecen en formularios.
- El sistema muestra mensajes de error claros y asociados al campo correspondiente en la interfaz de usuario.

El sistema permite registrar, editar y desactivar métricas productivas por especie.

El sistema valida que la unidad_medida sea coherente con el tipo_medicion de la métrica.

El sistema impide desactivar métricas que estén siendo referenciadas en eventos de crecimiento o productivos existentes.

Las métricas activas de una especie son consultables por RF-40 y RF-43 para validar el tipo de medición y la unidad durante el registro de eventos.

**Requerimientos no funcionales:**

Usabilidad:
- Interfaz con agrupación por especie.

Seguridad:
- Control RBAC.

Fiabilidad:
- Consistencia referencial.

Rendimiento:
- Respuesta < 2 segundos.

Trazabilidad:
- Auditoría obligatoria.

Disponibilidad:
- Compatible con operación offline (sincronización diferida).

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental

**Código Identificación:** RF-17 -- Versión -- 1.0

**Fuente:** Administrador / Veterinario

**Descripción:** El sistema debe permitir configurar los umbrales de monitoreo ambiental y los niveles de alerta asociados para las variables ambientales observadas en el entorno productivo, vinculados a cada especie registrada en el catálogo del sistema.

Los umbrales definidos representan los valores de referencia utilizados para evaluar las condiciones ambientales en las que se encuentran los activos biológicos, permitiendo identificar si dichas condiciones se encuentran dentro de los rangos aceptables o si representan una situación potencialmente riesgosa.

Cada especie podrá tener configurados umbrales específicos para distintas variables ambientales monitoreadas, tales como:

temperatura

humedad

pH del agua

Las variables ambientales deberán ser seleccionadas a partir de un catálogo predefinido en el sistema (ej: temperatura, humedad, pH), el cual podrá ser gestionado en el módulo correspondiente.

Adicionalmente, el sistema deberá permitir definir niveles de alerta ambiental basados en un esquema de semaforización, que clasifique el estado de las condiciones ambientales según los rangos configurados.

Los niveles de alerta permitirán clasificar las condiciones ambientales en diferentes estados operativos, por ejemplo:

Nivel normal (verde): condiciones dentro de los rangos óptimos.

Nivel de precaución (amarillo): condiciones cercanas a los límites aceptables.

Nivel crítico (rojo): condiciones fuera de los rangos permitidos.

Estos parámetros funcionarán como base para los módulos de monitoreo, análisis y visualización del sistema, permitiendo detectar condiciones adversas y activar mecanismos de alerta temprana.

El catálogo de variables ambientales será predefinido y gestionado exclusivamente por el sistema o mediante un requerimiento independiente. Los usuarios finales no podrán crear, modificar ni eliminar variables ambientales desde este módulo.

**Justificación:** La configuración de umbrales ambientales por especie permite establecer las condiciones óptimas para el desarrollo y bienestar de los activos biológicos, facilitando la supervisión del entorno productivo.

La incorporación de niveles de alerta ambiental permite clasificar automáticamente las condiciones monitoreadas y facilitar su interpretación mediante mecanismos visuales de alerta.

Estos parámetros sirven como base para:

la detección de condiciones ambientales adversas

el monitoreo continuo del entorno productivo

la generación de alertas tempranas

la visualización de indicadores ambientales en los paneles de control del sistema.

Adicionalmente, el registro de estos valores contribuye a mantener evidencia de las condiciones ambientales bajo las cuales se desarrollan los activos biológicos, información que puede respaldar procesos de trazabilidad y valoración conforme a los lineamientos establecidos en la NIC 41.

**Precondiciones:** Debe existir al menos una especie registrada en el catálogo del sistema (RF-15).

El usuario debe tener una sesión activa en el sistema.

El usuario debe contar con permisos para modificar configuraciones del sistema.

**Restricciones:** Los valores mínimos definidos para cada variable ambiental deben ser estrictamente menores que los valores máximos.

Los niveles de alerta deben configurarse dentro del rango ambiental definido.

Solo los usuarios con rol Administrador o Veterinario podrán modificar estos parámetros.

El sistema no permitirá guardar configuraciones donde los valores definidos generen inconsistencias en los rangos de monitoreo o en los niveles de alerta.

Los umbrales ambientales solo podrán configurarse para especies que se encuentren activas dentro del catálogo del sistema.

No se permitirá la existencia de múltiples configuraciones activas para la misma combinación de especie y variable ambiental.

Los rangos definidos para los niveles de alerta no deben solaparse entre sí y deben mantener coherencia lógica dentro del rango general definido.

El sistema validará que los valores ingresados se encuentren dentro de rangos físicamente aceptables según la variable (ej: temperatura no puede ser negativa en ciertos contextos definidos por el sistema).

Los niveles de alerta deben cubrir completamente el rango definido o quedar claramente delimitados sin ambigüedad.

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-15 — Catálogo de especies productivas

**Actores:** Administrador del sistema, Veterinario

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_parametro_ambiental | serial  | Identificador del registro de parámetros ambientales. |
| id_especie | integer  | FK que vincula el umbral a una especie (Bovino, Avícola, etc.). |
| tipo_variable | varchar(20) | FK que identifica si el parámetro es Temperatura, Humedad o pH. |
| valor_min | numeric(5,2) | Valor mínimo permitido para el parámetro ambiental.
Ejemplo: 35.50 para temperatura. |
| valor_max | numeric(5,2) | Valor máximo permitido para el parámetro ambiental monitoreado.
Ejemplo: 39.20 para temperatura. |
| activo | boolean | Indica si este umbral está vigente para las alertas actuales. |

**Proceso:**

El usuario accede al módulo Configuración del sistema.

El sistema muestra el catálogo de especies registradas.

El usuario selecciona la especie sobre la cual desea configurar los parámetros ambientales.

El sistema valida que la especie seleccionada se encuentre activa.

Si la especie está inactiva, se rechaza la operación con mensaje de error.

El usuario selecciona la variable ambiental monitoreada.

El sistema permite definir el rango ambiental aceptable (valor mínimo y máximo).

El usuario define los niveles de alerta ambiental asociados a dicho rango.

El sistema valida que:

el valor mínimo sea menor que el valor máximo

los niveles de alerta se encuentren dentro de los rangos definidos.

El sistema guarda la configuración asociada a la especie seleccionada.

El sistema registra la operación en el historial de auditoría.


**Flujo alterno:**

Inconsistencia de rango (Mínimo mayor al Máximo):

El usuario intenta guardar una configuración donde el valor_min es igual o superior al valor_max.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de lógica: El valor mínimo ([VALOR_MIN]) no puede ser mayor o igual al valor máximo ([VALOR_MAX]). Por favor, corrija el rango de la variable [TIPO_VARIABLE]."

Especie inactiva o no encontrada:

Se intenta asociar un umbral a un id_especie que no existe o que fue marcado como activo: false en el catálogo (RF-15).

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Error de referencia: No se pueden configurar umbrales para la especie seleccionada porque se encuentra inactiva o no existe en el catálogo productivo."

Configuración duplicada para la misma variable:

El administrador intenta crear un nuevo registro de "Temperatura" para la especie "Bovino" cuando ya existe uno activo. El sistema debe obligar a editar el existente o desactivarlo antes.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de configuración: Ya existe un umbral activo para la variable [TIPO_VARIABLE] en la especie [NOMBRE_ESPECIE]. Por favor, edite la configuración actual en lugar de crear una nueva."

Solapamiento de niveles de alerta (Semaforización):

Al definir los rangos de Precaución (Amarillo) y Crítico (Rojo), el usuario ingresa valores que se cruzan entre sí (ej: el rango amarillo termina en 38°C pero el rojo empieza en 37.5°C).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de semaforización: Los niveles de alerta presentan solapamientos. El límite superior del Nivel de Precaución debe ser exactamente igual al límite inferior del Nivel Crítico para garantizar una transición lineal."

Valores fuera de límites físicos biológicos:

El usuario ingresa un valor que, aunque matemáticamente válido, es físicamente imposible para la variable (ej: un pH de 18 cuando la escala es 0-14, o una humedad del 120%).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Valor fuera de rango físico: El valor ingresado para [TIPO_VARIABLE] no es válido para esta escala. (Límites permitidos: [MIN_FISICO] - [MAX_FISICO])."

Fallo de privilegios administrativos:

Un usuario con rol 'Productor' intenta acceder a la configuración de umbrales ambientales.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: Solo los usuarios con rol Administrador o Veterinario están autorizados para modificar los umbrales de seguridad ambiental."

Error de sincronización con el Nodo Edge:

El sistema guarda la configuración en el servidor central, pero falla al intentar propagar los nuevos umbrales hacia los dispositivos IoT en campo (M03) para el procesamiento local.

El sistema marca la configuración con un estado "Pendiente de Sincronización" y responde con:

HTTP 500: Internal Server Error

Mensaje: "Configuración guardada en la base de datos, pero falló la actualización de los nodos Edge. Es posible que las alertas en campo sigan operando con los valores anteriores hasta que se restablezca la conexión."

**Salida:**

Umbrales ambientales configurados para la especie seleccionada.

Niveles de alerta ambiental asociados a los rangos definidos.

Confirmación de guardado de la configuración.

Registro de la operación en el historial de auditoría.

**Postcondiciones:**

Los umbrales y niveles de alerta quedan disponibles para los módulos de monitoreo y análisis del sistema.

Los módulos de visualización podrán representar el estado ambiental mediante indicadores semafóricos.

El sistema conserva el historial de cambios realizados sobre la configuración ambiental.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite definir umbrales ambientales para cada especie registrada.

El sistema permite configurar niveles de alerta ambiental asociados a dichos umbrales.

El sistema impide guardar configuraciones donde el valor mínimo sea mayor o igual al valor máximo.

Cada especie puede tener configuraciones independientes para cada variable ambiental.

Los usuarios autorizados pueden consultar y modificar los parámetros configurados.

Todas las modificaciones quedan registradas en el historial de auditoría.

El sistema impide configurar umbrales para especies inactivas.

El sistema rechaza valores fuera de los rangos permitidos según la variable ambiental.

El sistema impide la creación de configuraciones duplicadas para la misma especie y variable ambiental.

El sistema valida que los niveles de alerta no presenten solapamientos entre rangos.

El sistema responde con códigos HTTP adecuados (400, 409) según el tipo de error.

**Requerimientos no funcionales:**

Exactitud: Almacenar correctamente los valores numéricos configurados.

Fiabilidad: Las configuraciones deben mantenerse consistentes dentro del sistema.

Usabilidad: La configuración debe ser fácilmente editable por los usuarios autorizados.

Seguridad: Solo usuarios autorizados podrán modificar los umbrales y niveles de alerta.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-18 — Configuración de Parámetros Operativos del Sistema

**Código Identificación:** RF-18 -- Versión -- 1.0

**Fuente:** Administrador del sistema

**Descripción:** El sistema debe permitir al Administrador configurar los parámetros operativos que definen el comportamiento esperado del flujo de datos provenientes de los dispositivos de monitoreo. La configuración de estos parámetros será única a nivel global del sistema, aplicando de manera transversal a todos los dispositivos de monitoreo registrados.

Estos parámetros permiten establecer:

la frecuencia esperada de recepción de datos del entorno productivo

el tiempo máximo permitido sin recepción de datos (heartbeat) antes de considerar una posible interrupción en la comunicación

Los valores configurados funcionan como parámetros de referencia para los módulos de monitoreo del sistema, permitiendo detectar inconsistencias o interrupciones en la transmisión de datos provenientes de los dispositivos IoT.

**Justificación:** La definición de parámetros operativos como la frecuencia de muestreo y el tiempo máximo permitido sin recepción de datos permite establecer el comportamiento esperado del sistema de monitoreo.

Estos parámetros son necesarios para identificar interrupciones en la transmisión de información, garantizar la continuidad del registro de datos ambientales y asegurar la integridad de los registros utilizados para el análisis productivo y la valoración de activos biológicos bajo el marco de la NIC 41.

**Precondiciones:** El usuario debe tener una sesión activa en el sistema.

El usuario debe contar con rol Administrador.

El sistema debe encontrarse operativo.

**Restricciones:** Los valores deben ser números enteros positivos expresados en minutos.

El valor de heartbeat debe ser mayor o igual que la frecuencia de muestreo configurada.

Solo el Administrador puede modificar estos parámetros.

Estos parámetros definen el comportamiento esperado del sistema, pero no controlan directamente la configuración de los dispositivos físicos.

Solo podrá existir una configuración activa de parámetros operativos en el sistema.

El sistema debe permitir actualizar la configuración existente, manteniendo un historial de cambios en el sistema de auditoría.

El sistema permitirá la modificación de los parámetros operativos en cualquier momento por el Administrador.

El sistema mantendrá un historial de cambios a través del módulo de auditoría.

No se permite la existencia de múltiples configuraciones activas simultáneamente.

La restauración de configuraciones anteriores no se realizará de forma automática, pero podrá ser reconstruida a partir del historial de auditoría.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-21 — Registro de dispositivos IoT

**Actores:** Administrador del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_configuracion | integer NOT NULL | Identificador único del registro de configuración global. |
| frecuencia_muestreo | integer NOT NULL | Valor en minutos que define la frecuencia esperada de recepción de datos. Debe ser un número entero mayor a 0. |
| heartbeat | integer NOT NULL | Tiempo máximo permitido sin recepción de datos en minutos. Debe ser mayor o igual a la frecuencia de muestreo. |
| fecha_actualizacion | timestamp | Fecha y hora en la que se realizó la última modificación de la configuración. |
| id_usuario | integer NOT NULL | Identificador del Administrador que realiza la configuración (FK para auditoría). |
| activo | boolean | Indica si la configuración se encuentra vigente. Solo puede existir un registro activo en el sistema. |

**Proceso:**

El Administrador accede al módulo Configuración del sistema.

El sistema muestra la sección Parámetros operativos.

El Administrador ingresa la frecuencia de muestreo esperada en minutos.

El Administrador ingresa el tiempo máximo permitido sin recepción de datos (heartbeat).

El sistema valida que ambos valores sean enteros positivos.

El sistema valida que el valor de heartbeat sea mayor o igual a la frecuencia de muestreo.

El sistema guarda los parámetros configurados.

Si existe una configuración previa, el sistema actualizará los valores existentes.

El sistema registrará el cambio en el historial de auditoría.

**Flujo alterno:**

Valores no permitidos (Cero o Negativos):

El Administrador ingresa un valor $\le 0$ en frecuencia_muestreo o heartbeat.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de validación: Los parámetros operativos deben ser números enteros positivos mayores a cero. El valor [VALOR_INGRESADO] no es válido."

Inconsistencia lógica entre Muestreo y Heartbeat:

El usuario intenta configurar un heartbeat menor a la frecuencia_muestreo (ej: esperar datos cada 10 minutos pero marcar error si no llegan en 5).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Conflicto de lógica operativa: El tiempo de espera (heartbeat) debe ser mayor o igual a la frecuencia de muestreo. No se puede esperar una señal en un tiempo menor al intervalo de envío configurado."

Intento de creación de múltiples configuraciones activas:

El sistema detecta un intento de insertar un nuevo registro (POST) en lugar de actualizar el existente (PUT/PATCH), violando la restricción de configuración única global.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Error de unicidad: Ya existe una configuración operativa activa. Utilice el método de actualización para modificar los valores vigentes."

Acceso no autorizado (Privilegios insuficientes):

Un usuario con rol 'Ingeniero de Campo' o 'Veterinario' intenta modificar estos parámetros globales.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: Solo el Administrador del sistema tiene permisos para modificar la frecuencia de muestreo y los tiempos de heartbeat globales."

Fallo en el registro de auditoría obligatorio:

El sistema actualiza los parámetros en la tabla de configuración, pero falla al insertar el registro histórico en el log de auditoría (RF-10).

El sistema realiza un rollback de la actualización y responde con:

HTTP 500: Internal Server Error

Mensaje: "Fallo de persistencia: No se pudo registrar la trazabilidad del cambio en el historial de auditoría. La configuración operativa no ha sido modificada para garantizar la integridad del sistema."

Conflicto de actualización concurrente (Control Optimista):

Dos administradores intentan cambiar la frecuencia de muestreo al mismo tiempo.

El sistema responde con:

HTTP 412: Precondition Failed

Mensaje: "Conflicto de concurrencia: Los parámetros operativos han sido modificados por otro administrador mientras usted realizaba los cambios. Por favor, recargue la configuración antes de intentar de nuevo."

Error de formato (Dato no entero):

El usuario ingresa valores con decimales (float) o caracteres alfabéticos en los campos de minutos.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Dato inválido: Los campos de tiempo deben ser exclusivamente números enteros. Verifique la entrada '[VALOR_INGRESADO]'."

**Salida:**

Parámetros operativos almacenados en el sistema.

Confirmación del guardado de la configuración.

Registro de la modificación en el historial de auditoría.

**Postcondiciones:**

Los parámetros operativos quedan disponibles para los módulos de monitoreo del sistema.

El sistema mantiene un historial de cambios de los parámetros configurados.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite configurar la frecuencia de muestreo esperada.

El sistema permite configurar el tiempo máximo permitido sin recepción de datos (heartbeat).

El sistema impide guardar valores negativos, cero o no enteros.

El sistema impide configurar un heartbeat menor que la frecuencia de muestreo.

Solo el usuario con rol Administrador puede modificar estos parámetros.

Todas las modificaciones quedan registradas en el historial de auditoría.

El sistema permite mantener una única configuración activa.

El sistema permite actualizar la configuración existente. 

El sistema registra el historial de cambios en auditoría.

El sistema garantiza que solo exista un registro activo en la base de datos.

**Requerimientos no funcionales:**

Disponibilidad: El sistema debe permitir consultar los parámetros operativos en todo momento.

Fiabilidad: Los valores configurados deben almacenarse correctamente y mantenerse consistentes.

Usabilidad: La configuración debe ser clara y editable desde el módulo de configuración.

Seguridad: Solo el Administrador puede modificar los parámetros operativos.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-19 — Registro y Gestión de Datos de la Finca

**Código Identificación:** RF-19 -- Versión -- 1.0

**Fuente:** Administrador del sistema / Productor

**Descripción:** El sistema debe permitir registrar y administrar la información general de las fincas donde se implementa la plataforma.

Cada finca representa una unidad organizacional independiente dentro del sistema, a la cual se asociarán los usuarios, la infraestructura productiva, los dispositivos de monitoreo y los activos biológicos gestionados.

El sistema deberá permitir registrar, consultar, editar y desactivar fincas, manteniendo la información general y de ubicación necesaria para la gestión productiva y la trazabilidad de los activos biológicos.

**Justificación:** El registro de las fincas permite organizar y aislar la información de cada unidad productiva dentro del sistema.

Esto es fundamental para garantizar que los registros de producción, monitoreo ambiental y valoración de activos biológicos se gestionen de forma independiente por cada explotación agropecuaria.

Adicionalmente, la información de la finca facilita la trazabilidad documental y el cumplimiento de los requisitos de registro exigidos por las entidades de control del sector agropecuario, así como el respaldo de la valoración de activos biológicos conforme al marco de la NIC 41.

**Precondiciones:** El usuario debe tener sesión activa en el sistema.

El usuario debe contar con rol Administrador.

Deben existir usuarios registrados para asociar a la finca (RF-01).

**Restricciones:** El nombre de la finca debe ser único (de manera global y por productor) dentro del sistema.

No se permite eliminar una finca que tenga registros asociados en el sistema; únicamente se permite cambiar su estado a inactiva.

Solo el usuario con rol Administrador puede registrar, editar o desactivar fincas.

El tamaño de la finca debe ser mayor a cero y puede manejar decimales.

latitud o longitud son valores numéricos decimales.

latitud se debe encontrar dentro del rango permitido (-90 a 90).

longitud se debe encontrar dentro del rango permitido (-180 a 180).

El nombre de la finca y los atributos de ubicacion_finca (departamento, ciudad, vereda) deben permitir letras del alfabeto (A–Z, a–z), espacios y caracteres propios del idioma español, tales como vocales acentuadas (á, é, í, ó, ú) y la letra ñ. No se permiten números ni caracteres especiales (simbolos) distintos a los mencionados

Los usuarios con rol Productor solo pueden consultar la información de las fincas a las que están asignados.

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-01 — Registro de usuarios.

**Actores:** Administrador del sistema, Productor (consulta)

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id | serial | Identificador único de la finca registrada. |
| nombre_finca | character(55) | Nombre de la finca registrada en el sistema. |
| ubicacion_finca | jsonb | Información de la ubicación geográfica de la finca siguiendo la estructura:
{
  "departamento": "string",
  "municipio": "string",
  "vereda": "string",
  "latitud": "decimal",
  "longitud": "decimal"
}   |
| tamaño_h | numeric(3) | Tamaño de la finca expresado en hectáreas. |
| fecha_creacion | timestamp with time zone | Fecha y hora en que se registró la finca en el sistema. |
| fecha_actualizacion | timestamp with time zone | Fecha y hora de la última actualización de la información de la finca. |
| activo | boolean | Indica si la finca se encuentra activa dentro del sistema. |
| productor_id | integer | Identificador de la entidad productor responsable de la finca.
La entidad productor representa la unidad organizacional asociada a un usuario del sistema responsable de la gestión de una o más fincas. |

**Proceso:**

1. El Administrador accede al módulo Configuración del sistema.

2. El sistema muestra el listado de fincas registradas.

3. El Administrador selecciona la opción Registrar nueva finca.

4. El Administrador ingresa los datos generales de la finca.

5. El sistema valida:
   - Que el campo ubicación y nombre no esten vacios.
   - Que los campo ubicación y nombre no se encuentren previamente registrado (de manera global y por productor).
   - Que el tamaño de la finca sea mayor a cero.

**Flujo alterno:**

Nombre o ubicación de finca duplicados:

El sistema detecta que la combinación de nombre_finca y los datos en ubicacion_finca ya existen para el mismo productor_id o a nivel global.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de registro: Ya existe una finca con el nombre '[NOMBRE_INGRESADO]' en la ubicación seleccionada. Por favor, verifique los datos o utilice un nombre distintivo."

Coordenadas geográficas fuera de rango:

El usuario ingresa una latitud fuera del rango (-90 a 90) o una longitud fuera de (-180 a 180).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de geolocalización: Las coordenadas ingresadas son inválidas. La latitud debe estar entre -90 y 90, y la longitud entre -180 y 180."

Tamaño de finca inválido:

El Administrador ingresa un valor $\le 0$ en el campo tamaño_h.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de superficie: El tamaño de la finca debe ser un valor numérico mayor a cero hectáreas. Valor recibido: [VALOR_INGRESADO]."

Caracteres no permitidos en campos de texto:

Se detectan números o símbolos especiales en nombre_finca, departamento, municipio o vereda.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de formato: Los campos de nombre y ubicación solo permiten letras y espacios. No se admiten números ni caracteres especiales en '[CAMPO_CON_ERROR]'."

Acceso denegado (Rol Productor intentando editar):

Un usuario con rol 'Productor' intenta enviar una petición POST, PUT o PATCH al endpoint de fincas.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Privilegios insuficientes: Los productores solo tienen permiso de consulta. La creación o modificación de fincas es responsabilidad exclusiva del Administrador."

Intento de desactivación con dependencias activas:

El Administrador intenta marcar una finca como activo: false, pero existen dispositivos IoT (RF-21) o Activos Biológicos (RF-33) vinculados a ella.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Operación denegada: No se puede desactivar la finca '[NOMBRE_FINCA]' porque aún cuenta con infraestructura o activos biológicos asociados. Debe reubicarlos o darlos de baja antes de desactivar la unidad productiva."

Error en la estructura de datos (JSON Inválido):

El objeto ubicacion_finca enviado no cumple con la estructura de claves requerida o faltan campos obligatorios como 'municipio'.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Estructura de datos incompleta: La información de ubicación no cumple con el formato requerido. Asegúrese de incluir departamento, municipio, vereda y coordenadas."

**Salida:**

Finca registrada en el sistema.

Listado actualizado de fincas disponibles.

Registro de la operación en el historial de auditoría.

**Postcondiciones:**

La finca queda disponible para configurar su infraestructura productiva.

La finca puede asociarse a usuarios, dispositivos de monitoreo y activos biológicos dentro del sistema.

Las fincas inactivas no aparecen como opción en los formularios de los demás módulos.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite registrar nuevas fincas solo a usuarios con el rol Administrador.

El sistema impide registrar dos fincas con el mismo nombre y/o ubicación (global y/o por productor).

El sistema impide registrar una finca sin nombre y/o ubicación.

El sistema impide registrar una finca con tamaño menor o igual a cero.

El sistema permite modificar la información de una finca existente solo a usuarios con el rol Administrador.

El sistema impide eliminar fincas con registros asociados.

Los usuarios con rol Productor solo pueden visualizar las fincas a las que están asignados.

El sistema muestra correctamente el estado de cada finca (Activo / Inactivo).

**Requerimientos no funcionales:**

Seguridad: El sistema debe garantizar el aislamiento de datos entre fincas.

Fiabilidad: La información registrada debe almacenarse de forma consistente.

Usabilidad: La gestión de fincas debe ser clara y sencilla para el Administrador.

Trazabilidad: Todas las acciones deben registrarse en el historial de auditoría.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-20 — Gestión de Infraestructura Productiva

**Código Identificación:** RF-20 -- Versión -- 1.0

**Fuente:** Administrador del sistema / Productor

**Descripción:** El sistema debe permitir gestionar la infraestructura productiva asociada a las fincas registradas, mediante el registro, consulta, modificación y control de estado de áreas productivas. Las áreas productivas corresponden a unidades físicas delimitadas dentro de una finca donde se desarrollan actividades agropecuarias, tales como galpones, corrales, potreros, estanques o invernaderos. Estas áreas representan el nivel operativo dentro de la estructura del sistema, donde se podrán asociar dispositivos IoT, sensores y procesos productivos. La infraestructura productiva se organiza jerárquicamente en tres niveles: Productor, Finca y Área productiva, donde cada área depende directamente de una única finca y no contempla subdivisiones adicionales en esta versión del sistema.                                                                                                                                                                      

La relación jerárquica establece una dependencia directa y obligatoria entre los niveles, donde cada área productiva pertenece exclusivamente a una única finca, y cada finca pertenece a un único productor, conformando la estructura Productor → Finca → Área productiva. Esta organización permite mantener la coherencia en la gestión de los datos y la trazabilidad de los procesos productivos.

**Justificación:** La gestión de la infraestructura productiva permite organizar las actividades agropecuarias dentro de espacios físicos definidos, facilitando la trazabilidad de los procesos productivos y la correcta asignación de dispositivos IoT. Esto garantiza que los datos capturados por sensores puedan asociarse de manera precisa a una ubicación específica dentro de la finca, mejorando la interpretación y análisis de la información.

**Precondiciones:** Debe existir al menos una finca registrada en el sistema (RF-19).

El usuario debe tener una sesión activa en el sistema.

**Restricciones:** Cada área productiva debe estar asociada obligatoriamente a una finca existente mediante el identificador finca_id.

El sistema generará un identificador único para cada área productiva (area_id), el cual permitirá su identificación dentro de todos los módulos del sistema.

El nombre del área productiva debe ser único dentro de la misma finca, evitando duplicidad de áreas dentro de una misma área productiva.

La superficie del área productiva debe ser un valor numérico positivo, representando el tamaño físico del área (Metros cuadrados).

El tipo de área productiva debe corresponder a un registro activo del catálogo de tipos de área gestionado en el módulo de Configuración (M09). No se permiten valores fuera del catálogo vigente.

No se permite eliminar áreas productivas que tengan registros asociados (como dispositivos IoT o procesos productivos); únicamente podrán marcarse como inactivas.

Solo el Administrador del sistema puede registrar, modificar o desactivar áreas productivas.

Los usuarios con rol Productor solo pueden consultar las áreas de la finca a la que están asociados. | Especificacion de relacion de area productiva

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-19 — Registro y gestión de datos de la finca.

**Actores:** Administrador del sistema, Productor (consulta)

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| finca_id | integer | Identificador de la finca a la que pertenece el área productiva. |
| tipo_area | varchar(20) | FK al catálogo de tipos de área productiva gestionado en M09. El catálogo incluye por defecto: galpón, corral, potrero, estanque, invernadero, pero el Administrador puede agregar nuevos tipos o desactivar los existentes desde el módulo de Configuración y Personalización. |
| nombre_infraestructura | varchar(50) | Nombre del área productiva. Debe ser único dentro de la finca. |
| superficie | numeric(10,2) | Superficie del área productiva. Debe ser un valor positivo. |
| descripcion_infraestructura | varchar(100) | Descripción opcional del área. |
| activo | boolean | Estado del área (true: activa / false: inactiva). |

**Proceso:**

El Administrador accede al módulo de configuración del sistema.

El sistema muestra la finca seleccionada.

El Administrador accede a la sección de infraestructura productiva.

El Administrador selecciona la opción de registrar nueva área productiva.

El Administrador ingresa los datos requeridos del área.

El sistema valida que el nombre no esté duplicado dentro de la misma finca.

El sistema valida que la superficie sea un valor positivo.

El sistema guarda la información del área productiva.

El Administrador puede modificar o desactivar áreas existentes.

El sistema registra las acciones en el historial de auditoría.

**Flujo alterno:**

Nombre de área productiva duplicado en la misma finca:

El sistema detecta que el nombre_infraestructura ya existe para el finca_id proporcionado (validación case-insensitive).

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de nombre: Ya existe un área denominada '[NOMBRE_INGRESADO]' en esta finca. El nombre de la infraestructura debe ser único por unidad productiva."

Superficie inválida (Cero o Negativa):

El Administrador ingresa un valor $\le 0$ en el campo superficie.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de dimensión: La superficie del área productiva debe ser un valor numérico positivo. El valor [VALOR_INGRESADO] no es aceptable para el cálculo de densidad."

Finca de referencia no encontrada o inactiva:

El finca_id enviado no existe o corresponde a una finca marcada como activo: false.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Error de jerarquía: No se puede registrar la infraestructura porque la finca seleccionada no existe o está desactivada en el sistema."

Desactivación bloqueada por dependencias operativas:

El Administrador intenta marcar como activo: false un área que tiene sensores IoT vinculados (RF-49) o activos biológicos (animales/lotes) actualmente alojados en ella.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Operación denegada: El área '[NOMBRE_AREA]' tiene [N] dispositivos y/o [M] activos biológicos asociados. Debe desvincular o trasladar los recursos antes de desactivar la infraestructura."

Acceso no autorizado (Rol Productor intentando editar):

Un usuario con rol 'Productor' intenta realizar una petición POST, PUT o DELETE sobre el catálogo de infraestructura.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Privilegios insuficientes: Los productores solo tienen permiso de lectura sobre la infraestructura. La gestión física es responsabilidad exclusiva del Administrador."

Tipo de área no reconocido:

El valor enviado en tipo_area no coincide con las opciones permitidas (galpón, corral, potrero, estanque, invernadero).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Dato inválido: El tipo de área '[VALOR_ENVIADO]' no corresponde a ningún tipo activo en el catálogo de infraestructura productiva. Consulte al Administrador para verificar o ampliar el catálogo desde el módulo de Configuración."

Conflicto de edición concurrente (Control Optimista):

Dos administradores intentan modificar la descripción o superficie del mismo galpón simultáneamente.

El sistema detecta que la versión del registro ha cambiado y responde con:

HTTP 412: Precondition Failed

Mensaje: "Conflicto de concurrencia: La información del área ha sido actualizada por otro usuario. Por favor, refresque la vista antes de aplicar sus cambios." | Confirmacion de ampliacion de catalogo en caso de error

**Salida:**

Área productiva registrada o actualizada.

Listado actualizado de áreas productivas.

Registro de la operación en el historial de auditoría.

**Postcondiciones:**

Las áreas productivas quedan disponibles para la asociación de dispositivos IoT y otros elementos del sistema.

Las áreas inactivas no estarán disponibles en otros módulos operativos.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite registrar áreas productivas asociadas a una finca.

El sistema impide registrar áreas con nombres duplicados dentro de la misma finca.

El sistema valida que la superficie sea un valor positivo.

El sistema permite modificar y desactivar áreas productivas.

El sistema impide eliminar áreas con registros asociados.

El sistema restringe la visualización según el rol del usuario.

**Requerimientos no funcionales:**

Seguridad: El sistema debe garantizar el aislamiento de datos entre fincas.
 
 Fiabilidad: La información de infraestructura debe mantenerse consistente en el sistema.
 
 Usabilidad: La gestión de áreas productivas debe ser clara y fácil de administrar.
 
 Trazabilidad: Todas las acciones deben registrarse en el historial de auditoría.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-21 — Registro de dispositivos IoT

**Código Identificación:** RF-21 -- Versión -- 1.0

**Fuente:** Administrador del sistema / Ingeniero de campo

**Descripción:** El sistema debe permitir a usuarios autorizados registrar dispositivos IoT utilizados para la captura de datos ambientales, asociándolos a un área productiva específica dentro de una finca. Cada dispositivo debe contar con un identificador único generado por el sistema, así como un identificador físico (serial) que permite su reconocimiento en el entorno real. El registro del dispositivo permite su gestión dentro del sistema, incluyendo su posterior configuración, calibración y asociación con sensores para procesos de monitoreo ambiental.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              Cada dispositivo IoT registrado en el sistema debe contar con dos identificadores:

Identificador interno (id_dispositivo):

Generado automáticamente por el sistema.

Es único dentro de la base de datos.

Se utiliza para la gestión interna del dispositivo.

Identificador físico (serial):

Corresponde al número de serie del dispositivo en el mundo real.

Es ingresado por el usuario al momento del registro.

Debe ser único dentro del sistema.

Permite vincular el registro lógico con el dispositivo físico.

Esta diferenciación evita ambigüedades y errores en la identificación de dispositivos.

**Justificación:** El registro de dispositivos IoT permite mantener un control organizado de los equipos utilizados para la captura de datos dentro de las fincas. Esto facilita su identificación, ubicación dentro de un área productiva específica y su integración con los procesos de monitoreo ambiental, garantizando la trazabilidad de la información recolectada.

**Precondiciones:** El usuario debe tener una sesión activa en el sistema.

El usuario debe tener rol Administrador o Ingeniero de campo.

Debe existir al menos una finca registrada (RF-19).

Debe existir al menos un área productiva registrada (RF-20).

**Restricciones:** Cada dispositivo debe tener un identificador interno único generado por el sistema.

El serial del dispositivo no puede repetirse dentro del sistema.

El dispositivo debe estar asociado obligatoriamente a un área productiva válida.

Solo usuarios autorizados pueden registrar dispositivos.

No se permite eliminar dispositivos con datos históricos asociados; únicamente pueden marcarse como inactivos.

El dispositivo IoT se asocia directamente a un área productiva, la cual ya pertenece a una finca.
Por lo tanto, la relación queda definida como:

Dispositivo IoT → Área productiva → Finca

No es necesario asociar el dispositivo directamente a la finca, ya que esta relación se obtiene a través del área.

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-19 – Registro y gestión de datos de la finca, RF-20 – Gestión de infraestructura productiva

**Actores:** Administrador del sistema, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| serial | varchar(50) | Identificador físico del dispositivo IoT. Debe ser único y corresponde al número de serie del equipo. |
| descripcion | varchar(100) | Descripción del dispositivo (tipo, modelo o referencia). |
| area_id | integer | Identificador del área productiva donde se instala el dispositivo. Define indirectamente la finca a la que pertenece. |
| activo | boolean | Estado del dispositivo dentro del sistema (true: activo / false: inactivo). |

**Proceso:**

El usuario accede al módulo de configuración del sistema.

El usuario selecciona la opción de registro de dispositivos IoT.

El sistema muestra el listado de dispositivos registrados.

El usuario selecciona la opción de registrar un nuevo dispositivo.

El sistema solicita los datos del dispositivo (serial, descripción, área).

El sistema valida que el serial no se encuentre previamente registrado.

El sistema valida que el área productiva exista.

El sistema asocia el dispositivo al área productiva seleccionada.

El sistema genera el identificador interno del dispositivo.

El sistema guarda la información del dispositivo.

El sistema registra la operación en el historial de auditoría.

**Flujo alterno:**

Serial físico duplicado:

El usuario intenta registrar un dispositivo con un serial que ya existe en la base de datos global.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de hardware: El número de serie '[SERIAL_INGRESADO]' ya se encuentra vinculado al dispositivo [ID_INTERNO]. Cada equipo físico debe tener un registro único."

Área productiva no encontrada o inactiva:

El area_id proporcionado no corresponde a ninguna infraestructura registrada o el área se encuentra en estado activo: false (RF-20).

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Error de ubicación: No se puede registrar el dispositivo porque el área productiva seleccionada no existe o está desactivada. Verifique la infraestructura de la finca."

Intento de eliminación física (Restricción de integridad):

El usuario intenta ejecutar un método DELETE sobre un dispositivo que ya tiene registros de telemetría o alertas asociadas.

El sistema responde con:

HTTP 405: Method Not Allowed

Mensaje: "Operación denegada: El dispositivo [SERIAL] tiene datos históricos vinculados y no puede ser eliminado. Utilice la opción de desactivación lógica (activo: false) para retirarlo de la operación."

Acceso no autorizado (Privilegios insuficientes):

Un usuario con rol 'Productor', 'Veterinario' o 'Contador' intenta realizar el registro de un nuevo dispositivo.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: El aprovisionamiento de hardware es una función exclusiva del Administrador o del Ingeniero de Campo."

Error de formato en el serial o descripción:

El campo serial llega vacío o la descripcion supera los 100 caracteres permitidos.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de validación: El campo [NOMBRE_CAMPO] no cumple con el formato requerido o excede la longitud permitida. Verifique la entrada '[VALOR_INGRESADO]'."

Conflicto de sincronización offline (Serial tomado):

Un Ingeniero de Campo registra un dispositivo localmente sin conexión. Al sincronizar, el sistema detecta que ese serial fue registrado por otro técnico en el servidor central durante el tiempo de desconexión.

El sistema marca el registro con error de conflicto en la cola de sincronización y responde con:

Notificación UI: "Fallo de sincronización: El dispositivo con serial '[SERIAL]' ya fue dado de alta en el servidor. Por favor, valide el inventario físico."

Fallo en el registro de auditoría:

El sistema guarda el dispositivo pero falla al intentar escribir en el log de auditoría inmutable (RF-10).

El sistema realiza un rollback de la transacción y responde con:

HTTP 500: Internal Server Error

Mensaje: "Error de seguridad: No se pudo garantizar la trazabilidad del registro. El dispositivo no ha sido guardado; intente de nuevo en unos minutos."

**Salida:**

Dispositivo IoT registrado en el sistema.

Dispositivo disponible para configuración, calibración y asociación con sensores.

Registro de la operación en el historial de auditoría.

**Postcondiciones:**

El dispositivo queda asociado a un área productiva específica.

El dispositivo puede ser utilizado en procesos de monitoreo ambiental.

El dispositivo queda disponible para configuración y calibración.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite registrar dispositivos IoT con un serial único.

El sistema genera un identificador interno para cada dispositivo.

El sistema valida la existencia del área productiva antes de registrar el dispositivo.

El sistema asocia correctamente el dispositivo a un área productiva.

El sistema impide registrar dispositivos con serial duplicado.

El sistema permite consultar los dispositivos registrados.

El sistema confirma el registro exitoso del dispositivo.

**Requerimientos no funcionales:**

Seguridad: Solo usuarios autorizados pueden registrar dispositivos.
 
 Disponibilidad: El listado de dispositivos debe poder consultarse en todo momento.
 
 Fiabilidad: La información registrada debe mantenerse consistente.
 
 Usabilidad: El proceso de registro debe ser claro para el personal técnico.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-22 — Asociación de sensores a estructuras productivas

**Código Identificación:** RF-22 -- Versión -- 1.1

**Fuente:** Administrador del sistema / Ingeniero de campo

**Descripción:** El sistema debe permitir a usuarios autorizados (Administrador e Ingeniero de campo) asociar sensores pertenecientes a dispositivos IoT previamente registrados a áreas productivas específicas dentro de una finca.

Cada sensor pertenece a un único dispositivo IoT y podrá ser vinculado a una sola área productiva activa a la vez. Esta asociación permitirá que los datos capturados por el sensor queden contextualizados con la ubicación física donde se realiza el monitoreo.

La relación entre entidades se define de la siguiente manera:

Un dispositivo IoT puede tener múltiples sensores asociados (uno a muchos).

Un sensor pertenece a un único dispositivo IoT.

Un sensor solo puede estar asociado a una única área productiva activa a la vez (uno a uno).

Un área productiva puede tener múltiples sensores asociados (uno a muchos).

Un área productiva puede tener múltiples sensores del mismo tipo, siempre que correspondan a sensores distintos.

El sistema deberá gestionar la asociación inicial y la reasignación de sensores, garantizando la integridad de la relación sensor–estructura productiva y la trazabilidad de los datos generados.

Efecto de la reasignación sobre las asociaciones sensor–activo (RF-49, versión 1.1): cuando un sensor se reasigna a otra área productiva, sus asociaciones sensor→activo biológico vigentes cuya premisa es espacial —las de tipo **AMBIENTAL** y **POBLACIONAL**, que se justifican porque el sensor comparte la infraestructura con el activo o el lote— dejan de tener sustento y el sistema las marca como **SUPERADA**, con su registro de auditoría, dentro de la misma transacción de la reasignación. Las asociaciones de tipo **DIRECTA** (biométricas, vinculadas al individuo instrumentado y no al lugar) no se ven afectadas y permanecen activas. El sistema **no recrea automáticamente** ninguna asociación en la nueva área: la re-asociación es una acción explícita y deliberada del usuario a través de RF-49, con sus propias validaciones y permisos, y queda **fuera del alcance** de la reasignación de área por diseño (la nueva área puede tener cero, uno o varios activos, sin un destino inequívoco para una recreación automática).

**Justificación:** La asociación de sensores a áreas productivas permite organizar la información recolectada por los dispositivos IoT dentro del contexto físico donde se generan los datos.
 
Esto facilita el monitoreo de condiciones ambientales en cada área productiva, permitiendo identificar con precisión qué sensores están capturando información en cada área, lo cual es fundamental para la gestión sanitaria, el control productivo y el análisis de datos del sistema.

Además, la correcta definición de la relación entre sensores y estructuras productivas permite mantener la integridad de los datos y asegurar la trazabilidad de la información generada por los dispositivos IoT.

**Precondiciones:** El usuario debe tener una sesión activa en el sistema.

El usuario debe tener rol Administrador o Ingeniero de campo.

Debe existir al menos una finca registrada (RF-19).

Debe existir al menos un área productiva registrada y activa (RF-20).

Debe existir al menos un dispositivo IoT registrado (RF-21).

El dispositivo debe tener sensores previamente definidos en el sistema.

**Restricciones:** Solo usuarios con rol Administrador o Ingeniero de campo pueden realizar asociaciones.

Un sensor solo puede estar asociado a una única área productiva activa a la vez.

No se permite asociar sensores a áreas productivas inactivas.

No se permite registrar asociaciones duplicadas entre el mismo sensor y la misma área productiva.

Un sensor debe pertenecer obligatoriamente a un dispositivo IoT existente.

La asociación debe registrarse mediante los identificadores: dispositivo, sensor y área productiva.

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-21 Registro de dispositivos IoT, RF-20 Gestión de Infraestructura Productiva

**Actores:** Administrador del sistema, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| dispositivo_iot_id | integer | Identificador del dispositivo IoT al que pertenece el sensor. Corresponde al campo id de la tabla dispositivos_edge. |
| sensor_id | integer | Identificador único del sensor que se desea asociar. Corresponde al campo id de la tabla sensores. |
| area_id | integer | Identificador del área productiva donde se instala el sensor. Corresponde al campo id de la tabla lotes. |
| punto_instalacion | varchar(100) | Descripción específica del lugar físico dentro del área donde se instala el sensor (ej: esquina norte, cerca al bebedero) |

**Proceso:**

1. El usuario accede al módulo de gestión de dispositivos IoT.

2. El sistema muestra el listado de dispositivos IoT registrados.

3. El usuario selecciona un dispositivo IoT.

4. El sistema muestra los sensores disponibles asociados al dispositivo.

5. El usuario selecciona el sensor que desea asociar.

6. El sistema muestra el listado de áreas productivas activas disponibles.

7. El usuario selecciona el área productiva destino.

8. El usuario ingresa la descripción del punto de instalación del sensor.

9. El sistema realiza las siguientes validaciones:

- Verifica la existencia del dispositivo IoT.
- Verifica la existencia del sensor seleccionado.
- Verifica la existencia del área productiva.
- Verifica que el área productiva se encuentre activa.
- Verifica si el sensor ya tiene una asociación activa.
- Verifica que no exista una asociación duplicada entre el sensor y el área productiva.

**Flujo alterno:**

Dispositivo IoT no existente:

El sistema no encuentra el dispositivo_iot_id en la tabla de dispositivos registrados.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error de referencia: El dispositivo IoT seleccionado con ID [ID_DISPOSITIVO] no existe o no ha sido dado de alta en el sistema."

Sensor no existente o no vinculado al dispositivo:

El sensor_id no existe o, existiendo, no pertenece al dispositivo_iot_id especificado (intento de asociación cruzada inválida).

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Inconsistencia de hardware: El sensor [ID_SENSOR] no pertenece al dispositivo [ID_DISPOSITIVO]. Verifique la configuración técnica del equipo antes de asociarlo."

Área productiva inexistente o inactiva:

El area_id no se encuentra en los registros o su estado es activo: false (RF-20).

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Ubicación inválida: El área productiva seleccionada no existe o se encuentra desactivada. No se pueden asociar sensores a infraestructuras fuera de operación."

Sensor ya asociado a otra área (Conflicto de reasignación):

El sistema detecta que el sensor ya tiene una relación activa con otra área en la tabla de asociaciones.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de asignación: El sensor [ID_SENSOR] ya está monitoreando el área '[NOMBRE_AREA_ACTUAL]'. ¿Desea reasignarlo? Esta acción finalizará la asociación anterior automáticamente."

Asociación duplicada (Redundancia):

El usuario intenta crear exactamente la misma relación (mismo sensor, misma área, mismo dispositivo) que ya está vigente.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Registro redundante: El sensor ya se encuentra asociado y activo en el punto de instalación '[PUNTO_ACTUAL]' de esta misma área."

Acceso no autorizado (Privilegios insuficientes):

Un usuario con rol 'Productor', 'Veterinario' o 'Contador' intenta realizar o modificar una asociación.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: Solo el Administrador o el Ingeniero de Campo tienen permisos para vincular sensores a la infraestructura física."

Fallo en el registro de auditoría obligatoria:

Se guarda la asociación, pero falla la escritura en el historial de auditoría (RF-10).

El sistema realiza un rollback de la transacción y responde con:

HTTP 500: Internal Server Error

Mensaje: "Fallo de seguridad: No se pudo registrar la trazabilidad de la asociación. La operación ha sido revertida; por favor, intente de nuevo en unos minutos."

Error de formato en punto de instalación:

El campo punto_instalacion llega vacío o supera los 100 caracteres permitidos.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de descripción: El punto de instalación es obligatorio y no debe exceder los 100 caracteres. Verifique la entrada '[VALOR_INGRESADO]'."

**Salida:**

Sensor asociado a una estructura productiva específica.

Registro actualizado de asociaciones sensor–estructura.

Confirmación de la operación.

Registro en el historial de auditoría.

**Postcondiciones:**

El sensor queda vinculado a una única área productiva activa.

Los datos capturados por el sensor se asocian al área productiva correspondiente.

La relación sensor–estructura queda almacenada para consulta futura.

Tras una reasignación de área, ninguna asociación sensor→activo de tipo AMBIENTAL o POBLACIONAL del sensor queda ACTIVA sobre la premisa espacial anterior: todas quedan SUPERADA con auditoría. Las de tipo DIRECTA permanecen activas.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema valida los roles autorizados antes de permitir la asociación.

El sistema valida la existencia del dispositivo, sensor y área productiva.

El sistema impide asociar sensores a áreas inexistentes o inactivas.

El sistema permite seleccionar sensores de dispositivos registrados.

El sistema impide asociaciones duplicadas del mismo sensor.

El sistema permite la reasignación de sensores previamente asociados.

Al reasignar un sensor de área, el sistema marca como SUPERADA —en la misma transacción y con auditoría— las asociaciones sensor→activo de tipo AMBIENTAL y POBLACIONAL vigentes del sensor, y deja intactas las de tipo DIRECTA. El sistema no recrea asociaciones en la nueva área de forma automática.

El sistema garantiza que un sensor solo tenga una asociación activa.

El sistema registra correctamente la relación sensor–estructura.

El sistema registra la operación en el historial de auditoría.

El sistema muestra confirmación al usuario.

Las asociaciones pueden consultarse posteriormente.

**Requerimientos no funcionales:**

Seguridad: Solo usuarios autorizados pueden realizar asociaciones entre sensores y áreas productivas.
 
Disponibilidad: Las asociaciones deben poder consultarse en cualquier momento.
 
Fiabilidad: La relación sensor–estructura debe mantenerse consistente y sin duplicidades.
 
Usabilidad: El proceso de asociación debe ser claro y comprensible para el personal técnico.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-23 — Configuración remota de dispositivos IoT

**Código Identificación:** RF-23 -- Versión -- 1.0

**Fuente:** Administrador del sistema / Ingeniero de campo

**Descripción:** El sistema debe permitir realizar la configuración operativa remota de los dispositivos IoT registrados en el sistema mediante la interfaz de la plataforma.

Esta funcionalidad permitirá modificar ciertos parámetros de funcionamiento del dispositivo, tales como la frecuencia de captura de datos, el intervalo de transmisión de información y el estado operativo del dispositivo.

La configuración podrá aplicarse en tiempo real o de manera diferida, dependiendo de la disponibilidad del dispositivo IoT y del mecanismo de comunicación implementado.

El sistema enviará la configuración al dispositivo IoT mediante el protocolo MQTT sobre la red LoRaWAN, utilizando mensajes en formato JSON.

Cuando el dispositivo se encuentre desconectado, el sistema deberá almacenar la configuración como pendiente de aplicación, la cual será enviada automáticamente cuando el dispositivo recupere la conectividad.

La configuración se realizará desde la interfaz del sistema sin que el personal técnico deba desplazarse físicamente al lugar donde se encuentra instalado el dispositivo.

**Justificación:** Los dispositivos IoT pueden encontrarse instalados en zonas de difícil acceso dentro de la finca o en áreas de producción donde el acceso constante del personal técnico resulta complejo.

La posibilidad de realizar ajustes operativos de forma remota permite reducir los tiempos de intervención técnica, mejorar la eficiencia en la gestión del monitoreo ambiental y facilitar la administración de los dispositivos desplegados en campo.

**Precondiciones:** Debe existir al menos un dispositivo IoT registrado en el sistema (RF-21).

El dispositivo debe estar asociado a un área productiva dentro de la finca (RF-20).

El usuario debe tener sesión activa en el sistema.

**Restricciones:** Solo se podrán modificar los parámetros de configuración definidos por el sistema.

Cada cambio de configuración debe quedar registrado en el historial del dispositivo, incluyendo:

valor anterior

valor nuevo

usuario que realiza el cambio

fecha y hora

identificador del dispositivo

Solo los usuarios con rol Administrador o Ingeniero de campo pueden modificar la configuración de los dispositivos.

Los parámetros de configuración deben cumplir reglas de validación, incluyendo:

valores enteros positivos para frecuencia de captura e intervalo de transmisión

rangos permitidos definidos por el sistema

Los valores de configuración deben cumplir rangos definidos por el sistema, los cuales serán configurables según el tipo de dispositivo IoT registrado.

La disponibilidad de parámetros de configuración dependerá del tipo de dispositivo IoT asociado, conforme a su definición en el sistema.

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-20 — Gestión de infraestructura productiva, RF-21 — Registro de dispositivos IoT, RF-22 — Asociación de sensores a estructuras productivas

**Actores:** Administrador del sistema, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| dispositivo_iot_id | integer | Identificador único del dispositivo IoT cuya configuración se desea modificar. Corresponde al campo id de la tabla dispositivos_edge. |
| frecuencia_captura | integer | Frecuencia de captura de datos del dispositivo expresada en minutos. Debe ser un número entero positivo. |
| intervalo_transmision | integer | Intervalo de transmisión de información del dispositivo expresado en minutos. Debe ser un número entero positivo. |
| estado_dispositivo | boolean | Estado operativo del dispositivo IoT tras la actualización de configuración (true: Activo / false: Inactivo). |

**Proceso:**

El usuario accede al módulo de gestión de dispositivos IoT.

El sistema muestra el listado de dispositivos registrados.

El usuario selecciona el dispositivo que desea configurar.

El sistema valida la existencia del dispositivo y su estado.

El sistema verifica los permisos del usuario.

El sistema muestra los parámetros de configuración disponibles según el tipo de dispositivo.

El usuario selecciona el parámetro que desea modificar.

El usuario ingresa el nuevo valor de configuración.

El sistema valida:

tipo de dato
rangos permitidos
reglas de negocio

Si el dispositivo está disponible:

el sistema envía la configuración al dispositivo mediante MQTT sobre LoRaWAN en formato JSON

el sistema espera confirmación del dispositivo (acknowledgment)

Si el dispositivo no está disponible:

el sistema almacena la configuración en estado PENDIENTE

el sistema programa el envío automático cuando el dispositivo se reconecte

El sistema registra el cambio en el historial de configuraciones con:

valor anterior
valor nuevo
usuario
fecha y hora
dispositivo

El sistema confirma la actualización al usuario.

**Flujo alterno:**

Dispositivo IoT inexistente:



El sistema no localiza el dispositivo_iot_id en la tabla de dispositivos registrados.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error de destino: El dispositivo con ID [ID_DISPOSITIVO] no existe. La orden de configuración ha sido abortada."

Parámetros fuera de rango técnico:



El usuario ingresa una frecuencia de captura o intervalo de transmisión que excede los límites definidos para ese modelo de hardware (ej: frecuencia de 1 segundo en un nodo de bajo consumo).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Valor inválido: El parámetro [NOMBRE_PARAMETRO] debe estar entre [MIN] y [MAX] minutos para este tipo de dispositivo. Valor recibido: [VALOR_INGRESADO]."

Inconsistencia lógica de tiempos:



El usuario intenta configurar un intervalo_transmision menor a la frecuencia_captura (ej: intentar enviar datos cada 5 minutos cuando el sensor solo mide cada 10).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Conflicto lógico: El intervalo de transmisión no puede ser menor a la frecuencia de captura de datos. Ajuste los valores para asegurar la coherencia del flujo."

Dispositivo fuera de línea (Estado Diferido):



El sistema intenta enviar el mensaje MQTT pero el broker reporta que el dispositivo no tiene sesión activa o el gateway LoRaWAN está inaccesible.

El sistema cambia el estado de la solicitud a PENDIENTE y responde con:

HTTP 202: Accepted

Mensaje: "Dispositivo offline. La configuración ha sido almacenada y se enviará automáticamente en la próxima ventana de conexión (Heartbeat) del dispositivo."

Timeout de confirmación (ACK):



El mensaje JSON es enviado exitosamente al broker, pero transcurren 30 segundos sin recibir el mensaje de confirmación (Acknowledgment) desde el hardware.

El sistema marca el comando como 'No Confirmado' y responde con:

HTTP 504: Gateway Timeout

Mensaje: "Sin respuesta del hardware. El comando fue enviado pero el dispositivo no confirmó la recepción dentro de los 30 segundos. La configuración se reintentará en el próximo ciclo."

Acceso no autorizado (Privilegios):



Un usuario con rol 'Veterinario' o 'Productor' intenta acceder al panel de configuración técnica.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: No tiene permisos de Ingeniero de Campo para modificar parámetros operativos del hardware."

Conflicto de comandos concurrentes:



Un administrador intenta enviar una configuración mientras existe otra en estado PENDIENTE para el mismo dispositivo.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Operación en curso: Ya existe una configuración pendiente de aplicación para el dispositivo [SERIAL]. Espere a que se aplique o cancele la anterior antes de enviar una nueva."

Fallo en el registro del historial (Auditoría):



Se procesa el cambio pero falla la escritura en el historial de configuraciones (RF-10).

El sistema realiza un rollback de la instrucción (no envía el MQTT) y responde con:

HTTP 500: Internal Server Error

Mensaje: "Error de trazabilidad: No se pudo registrar el cambio en el historial. Por seguridad, la orden de configuración no ha sido emitida."

**Salida:**

Configuración operativa actualizada del dispositivo IoT.

Registro del cambio en el historial de configuración del dispositivo.

Confirmación de la operación realizada.

**Postcondiciones:**

El dispositivo queda registrado en el sistema con los nuevos parámetros configurados.

El historial de configuración del dispositivo queda almacenado.

La configuración queda aplicada o pendiente de aplicación dependiendo del estado del dispositivo.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite modificar los parámetros configurables de un dispositivo IoT.

El sistema valida la existencia del dispositivo antes de aplicar cambios.

El sistema valida los permisos del usuario según su rol.

El sistema valida correctamente los valores ingresados (tipo, rango y reglas de negocio).

El sistema registra los cambios en el historial con:

valor anterior
valor nuevo
usuario
fecha
dispositivo

El sistema maneja correctamente los siguientes escenarios:

intento de configuración de un dispositivo inexistente
configuración con valores inválidos
dispositivo inactivo
dispositivo desconectado

El sistema guarda la configuración como PENDIENTE cuando el dispositivo está desconectado.

El sistema envía automáticamente la configuración cuando el dispositivo recupera la conexión.

El sistema maneja fallos de comunicación sin pérdida de información.

El sistema gestiona correctamente escenarios de timeout (30 segundos).

El sistema aplica la configuración en tiempo real cuando el dispositivo está disponible.

El sistema envía la configuración mediante MQTT sobre LoRaWAN en formato JSON.

El sistema confirma la operación al usuario.

**Requerimientos no funcionales:**

Seguridad
Solo usuarios autorizados pueden modificar la configuración de los dispositivos.

Disponibilidad
El módulo de configuración debe estar disponible cuando el sistema esté operativo.

Fiabilidad
Los cambios de configuración deben almacenarse correctamente y mantenerse consistentes.

Usabilidad
La interfaz debe facilitar la configuración remota de los dispositivos.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-24 — Calibración de dispositivos IoT

**Código Identificación:** RF-24 -- Versión -- 1.0

**Fuente:** Administrador del sistema / Ingeniero de campo

**Descripción:** El sistema debe permitir al Ingeniero de campo registrar parámetros de calibración asociados a dispositivos IoT previamente registrados y vinculados a una estructura productiva.

La calibración se define como un ajuste lógico aplicado a los valores de referencia utilizados por el sistema en el procesamiento de datos capturados, sin modificar directamente el hardware del dispositivo.

La calibración deberá registrarse a nivel de sensor asociado al dispositivo IoT, permitiendo almacenar valores de referencia y observaciones, con el fin de mejorar la precisión de las mediciones futuras.

**Justificación:** Los sensores pueden presentar variaciones en sus mediciones debido a factores ambientales o al uso continuo. La calibración permite garantizar que los datos capturados reflejen de manera adecuada las condiciones reales del entorno monitoreado mediante ajustes aplicados en el procesamiento de datos.

**Precondiciones:** El dispositivo IoT debe encontrarse registrado en el sistema (RF-21).

El dispositivo debe estar asociado a una estructura productiva (RF-22).

Debe existir al menos un sensor asociado al dispositivo.

El usuario debe tener sesión activa y permisos para gestionar dispositivos.

**Restricciones:** La calibración se aplica únicamente a sensores asociados a dispositivos IoT, no al dispositivo completo.

Solo se podrán calibrar sensores pertenecientes a dispositivos activos.

Cada calibración debe quedar registrada en el sistema con trazabilidad completa.

No se permite registrar calibraciones con valores inválidos (nulos, no numéricos o fuera de rango definido por el sistema).

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-21 — Registro de dispositivos IoT, RF-22 — Asociación de sensores a estructuras productivas

**Actores:** Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| dispositivo_iot_id | integer | Identificador del dispositivo IoT. |
| sensor_id | integer | Identificador del sensor asociado al dispositivo. |
| area_id | integer | Identificador del área productiva donde está instalado el sensor. |
| valor_referencia | numeric(10,4) | Valor de referencia utilizado para el ajuste lógico de las mediciones. |
| observaciones | text | Observaciones registradas durante la calibración. |
| fecha_calibracion | timestamp | Fecha y hora en que se realiza la calibración. |
| usuario_id | integer | Usuario que realiza la calibración. |

**Proceso:**

El Ingeniero de campo accede al módulo de gestión de dispositivos IoT.

El sistema solicita:

Dispositivo IoT

Sensor asociado

Área productiva

El sistema valida:

Existencia del dispositivo

Existencia del sensor asociado

Asociación válida con el área productiva

Estado activo del dispositivo

El usuario ingresa:

Valor de referencia

Observaciones

El sistema valida:

Tipo numérico válido

Rango permitido (según configuración del sistema)

El sistema registra la calibración, incluyendo:

Usuario

Fecha y hora

Sensor

Dispositivo

Valor registrado

El sistema confirma la operación al usuario.

**Flujo alterno:**

Dispositivo o Sensor no encontrado:

El sistema no localiza el dispositivo_iot_id o el sensor_id en los registros maestros.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error de referencia: El sensor o dispositivo especificado no existe. No se puede registrar una calibración sobre un hardware inexistente."

Inconsistencia de asociación (Área incorrecta):

El usuario intenta registrar una calibración para un sensor en el area_id A, pero el sistema detecta que el sensor está legalmente asociado al area_id B (RF-22).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Conflicto de ubicación: El sensor [ID_SENSOR] no está asociado al área [ID_AREA_SOLICITADO]. Verifique la ubicación física y lógica del equipo antes de calibrar."

Dispositivo inactivo:

El dispositivo_iot_id se encuentra en estado activo: false. Según las restricciones, no se pueden calibrar equipos fuera de operación.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Operación rechazada: El dispositivo [SERIAL] está inactivo. Debe activar el dispositivo antes de proceder con el registro de nuevos parámetros de calibración."

Valor de referencia fuera de rango técnico:

El valor_referencia ingresado es absurdamente alto o bajo para la variable (ej: un offset de temperatura de 500°C o un pH de -5).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Valor fuera de límites: El ajuste de [VALOR_REFERENCIA] excede los rangos de seguridad para la variable [TIPO_VARIABLE]. Verifique el estándar de calibración utilizado."

Acceso no autorizado (Privilegios):

Un usuario con rol 'Productor' o 'Contador' intenta acceder al módulo de calibración técnica.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: La calibración de sensores es una función crítica restringida exclusivamente al Ingeniero de Campo o al Administrador."

Fallo en el registro de auditoría:

El sistema procesa el ajuste, pero falla al intentar escribir en el historial de auditoría inmutable (RF-10).

El sistema realiza un rollback de la calibración y responde con:

HTTP 500: Internal Server Error

Mensaje: "Error de integridad: No se pudo garantizar la trazabilidad de la calibración. El ajuste no ha sido aplicado; por favor, intente de nuevo."

Datos no numéricos o incompletos:

El campo valor_referencia llega con caracteres no numéricos o vacío.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de formato: El valor de referencia debe ser un número decimal válido. Verifique la entrada '[VALOR_INGRESADO]'."

**Salida:**

Registro de calibración asociado al sensor del dispositivo IoT.

Confirmación de la operación.

**Postcondiciones:**

El sistema mantiene un historial de calibraciones por sensor.

Los valores de calibración se utilizan para el procesamiento de datos futuros (no alteran datos históricos).

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite registrar calibraciones para sensores asociados a dispositivos existentes.

El sistema valida que el dispositivo, sensor y área productiva existan y estén correctamente relacionados.

El sistema impide registrar calibraciones con valores no numéricos o inválidos.

El sistema impide registrar calibraciones si el dispositivo está inactivo.

El sistema almacena cada calibración con:

Dispositivo

Sensor

Usuario

Fecha y hora

Valor de referencia

Observaciones

El sistema permite consultar el historial de calibraciones por sensor.

El sistema no modifica datos históricos previamente almacenados.

**Requerimientos no funcionales:**

Seguridad: Solo usuarios autorizados pueden registrar calibraciones.

Usabilidad: El proceso debe ser claro para el personal técnico.

Disponibilidad: El módulo debe estar disponible en todo momento.

Fiabilidad: Las calibraciones deben almacenarse de forma consistente.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-25 — Adaptación de interfaz operativa

**Código Identificación:** RF-25 -- Versión -- 1.0

**Fuente:** Administrador del sistema

**Descripción:** El sistema debe adaptar automáticamente la interfaz operativa y la visualización de la información en función del rol del usuario, la finca activa y el contexto productivo configurado en el sistema.

La adaptación de la interfaz se realizará de forma automática al inicio de sesión y durante la sesión activa del usuario, mediante la carga dinámica de módulos, paneles e indicadores permitidos según sus permisos.

La adaptación incluirá:

Visualización de módulos habilitados según el rol y permisos del usuario

Selección de la finca activa asociada al usuario

Visualización de indicadores según las especies productivas configuradas en la finca

Organización dinámica de paneles operativos

El sistema deberá garantizar que la información mostrada sea consistente con los permisos definidos y el contexto productivo, evitando la visualización de módulos no autorizados.

**Justificación:** Los diferentes actores del sistema desempeñan funciones específicas dentro del proceso productivo y requieren acceder a información distinta para la toma de decisiones.
 
 La adaptación automática de la interfaz permite:
 
 reducir la sobrecarga de información presentada al usuario
 
 mejorar la claridad de los indicadores operativos
 
 facilitar la navegación dentro del sistema
 
 garantizar que cada usuario acceda únicamente a los módulos relevantes para su rol.
 
 Además, al considerar el contexto productivo de la finca y las especies monitoreadas, el sistema puede mostrar indicadores específicos del tipo de producción, mejorando la interpretación de la información generada por los sensores y módulos analíticos.

**Precondiciones:** El usuario debe estar autenticado en el sistema (RF-02).

El usuario debe tener un rol asignado (RF-03).

Debe existir al menos una finca registrada (RF-19).

Debe existir al menos una especie productiva registrada (RF-15).

**Restricciones:** La interfaz debe respetar estrictamente los permisos definidos por el sistema RBAC.

Ningún usuario podrá visualizar módulos o información no autorizada.

La adaptación no modifica la configuración visual personalizada del usuario.

La información crítica no podrá ocultarse si es necesaria para la operación del usuario.

La adaptación debe ejecutarse únicamente sobre información disponible y válida en el sistema.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios, RF-03 — Gestión de roles, RF-15 — Catálogo de especies productivas, RF-19 — Registro y gestión de datos de la finca

**Actores:** Administrador del sistema, Ingeniero de campo, Productor

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_usuario | integer | Identificador del usuario autenticado. Corresponde al campo id de la tabla usuarios. Permite recuperar el rol y los permisos asociados. |
| rol_id | integer | Identificador del rol asignado al usuario. Corresponde al campo id_roles de la tabla usuarios. |
| id_finca | integer | Identificador de la finca activa asociada al usuario. Corresponde al campo id de la tabla granjas. |
| especie_id | integer | Identificador de la especie productiva configurada en la finca. Corresponde al campo id de la tabla especies. |

**Proceso:**

El usuario inicia sesión en el sistema.

El sistema:

Identifica el usuario autenticado

Obtiene el rol y permisos asociados

Identifica la finca activa

El sistema consulta:

Especies productivas asociadas a la finca

Módulos habilitados según permisos

El sistema valida:

Permisos del usuario

Existencia de datos asociados (finca, especies)

El sistema construye dinámicamente la interfaz:

Carga módulos permitidos

Filtra paneles e indicadores

Organiza la visualización según contexto

El sistema presenta la interfaz adaptada al usuario.

Durante la sesión:

La interfaz se mantiene consistente con el contexto

Se actualiza si cambia la finca activa o permisos

**Flujo alterno:**

Usuario sin finca asociada:

El sistema autentica al usuario, pero detecta que no tiene ninguna id_finca vinculada en su perfil.

El sistema responde con:

HTTP 200: OK (Vista de Bienvenida)

Mensaje (UI): "Bienvenido al sistema. Actualmente no tiene una unidad productiva asignada. Por favor, contacte al administrador para vincular su cuenta a una finca."

Acción: El sistema oculta todos los paneles operativos y muestra únicamente el módulo de soporte o perfil.

Finca sin especies productivas configuradas:

El usuario accede a una finca válida, pero el sistema detecta que no se han registrado especies (RF-15) ni infraestructura (RF-20).

El sistema responde con:

HTTP 204: No Content

Mensaje (UI): "Finca sin configuración. Para visualizar los indicadores de monitoreo, primero debe configurar las especies y áreas productivas en el módulo de Configuración."

Cambio de permisos en sesión activa:

Mientras el usuario navega, un Administrador modifica su rol_id o revoca permisos específicos.

En la siguiente petición, el sistema detecta la inconsistencia entre el token y la base de datos.

El sistema responde con:

HTTP 403: Forbidden

Mensaje (UI): "Sus permisos han sido actualizados. La interfaz se recargará automáticamente para reflejar los nuevos accesos."

Acción: El sistema fuerza un refresco dinámico de los módulos cargados.

Intento de acceso a módulo no autorizado (URL Bypass):

El usuario intenta acceder a un módulo (ej. Valoración Financiera) escribiendo la ruta directamente, a pesar de que su rol no tiene permiso.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado. No tiene los privilegios necesarios para visualizar este módulo."

Acción: El sistema redirige al usuario al "Dashboard" principal permitido.

Fallo en la carga de contexto (Timeout de base de datos):

La construcción dinámica de la interfaz (consulta de roles + fincas + especies) supera los 2 segundos debido a latencia en el servidor.

El sistema responde con:

HTTP 504: Gateway Timeout

Mensaje (UI): "Error al cargar el contexto operativo. Estamos experimentando demoras; por favor, intente recargar la página en unos segundos."

Inconsistencia de especie-indicador:

El sistema intenta cargar un panel de "pH de Agua", pero la finca activa solo tiene configurada la especie "Avícola" (donde no se monitorea pH en estanques, por ejemplo).

El sistema responde con:

Lógica Interna: El sistema omite el indicador sin generar error crítico.

Mensaje (Log): "Advertencia: El indicador [TIPO_VARIABLE] no es compatible con la configuración productiva de la finca [ID_FINCA]."

Error de ID de finca inválido (Manipulación de parámetros):

El frontend solicita datos para una id_finca que no pertenece al usuario autenticado.

El sistema responde con:

HTTP 401: Unauthorized

Mensaje: "Error de seguridad: La unidad productiva solicitada no está vinculada a sus credenciales. El incidente ha sido reportado."

**Salida:**

Interfaz operativa adaptada al rol y contexto del usuario

Visualización de módulos autorizados

Paneles e indicadores filtrados según finca y especies

**Postcondiciones:**

El usuario solo visualiza información autorizada por medio de los roles que tenga asignados.

La interfaz permanece adaptada durante la sesión.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema adapta automáticamente la interfaz al iniciar sesión.

El sistema muestra únicamente los módulos permitidos según el rol.

El sistema impide visualizar módulos no autorizados.

El sistema carga correctamente la finca activa del usuario.

El sistema muestra indicadores según las especies configuradas.

El sistema mantiene la coherencia de la interfaz durante la sesión.

El sistema actualiza la interfaz si cambia el contexto (rol/finca).

El sistema no altera configuraciones visuales personalizadas.

El tiempo de carga de la interfaz es menor a 2 segundos.

**Requerimientos no funcionales:**

Usabilidad: La interfaz debe ser clara y facilitar la interpretación de datos.

Disponibilidad: La interfaz debe cargarse correctamente al iniciar sesión.

Fiabilidad: La información debe corresponder al rol y contexto del usuario.

Rendimiento: Tiempo de carga ≤ 2 segundos.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-26 — Personalización de identidad visual del sistema

**Código Identificación:** RF-26 -- Versión -- 1.0

**Fuente:** Administrador del sistema

**Descripción:** El sistema debe permitir al administrador configurar y personalizar la identidad visual de la plataforma, de manera que la interfaz del sistema pueda adaptarse a la imagen institucional de la finca, organización o empresa que utilice la plataforma.
 
Solo el usuario con rol Administrador del sistema podrá realizar modificaciones a la identidad visual de la plataforma.
 
Esta funcionalidad permitirá modificar exclusivamente los siguientes elementos visuales del sistema:
 
logotipo institucional de la organización o finca (formatos admitidos: PNG, JPEG, SVG; tamaño máximo: 2 MB)
 
color primario de la interfaz: color principal aplicado a barras de navegación, botones de acción primaria y encabezados de sección
 
color secundario de la interfaz: color de apoyo aplicado a botones de acción secundaria, bordes activos y elementos de énfasis visual
 
nombre visible de la organización dentro de la plataforma
 
El alcance de personalización se limita a los cuatro elementos indicados. Elementos como favicon, tipografía del sistema y paletas de color extendidas quedan fuera del alcance de esta versión.
 
La personalización de la identidad visual permitirá que la plataforma adopte una apariencia coherente con la marca del usuario administrador, facilitando su integración dentro de los entornos operativos de cada organización.
 
Antes de persistir los cambios, el sistema deberá presentar al administrador una vista previa en tiempo real de la identidad visual configurada, permitiendo verificar el resultado antes de confirmar el guardado.
 
Los cambios realizados deberán aplicarse de forma consistente en los distintos componentes de la interfaz del sistema, tales como:
 
barra de navegación
 
pantalla de inicio
 
encabezados del sistema
 
paneles principales
 
Esta funcionalidad no modifica la estructura funcional del sistema, únicamente la apariencia visual del mismo.

**Justificación:** La personalización de la identidad visual permite que las organizaciones que utilicen la plataforma puedan adaptar la apariencia del sistema a su imagen institucional, fortaleciendo la identificación de los usuarios con la herramienta.
 
 Esto es especialmente importante en sistemas utilizados por múltiples organizaciones o fincas, ya que permite mantener una coherencia visual con la marca de cada entidad.
 
 Además, la personalización visual contribuye a mejorar la experiencia de uso del sistema, facilitando su adopción dentro de los procesos operativos de las unidades productivas.

**Precondiciones:** El usuario debe encontrarse autenticado en el sistema (RF-02).
 
 El usuario debe tener permisos de administrador del sistema.
 
 Debe existir al menos una finca u organización registrada en el sistema (RF-19).

**Restricciones:** Solo los usuarios con rol Administrador podrán modificar la identidad visual del sistema.
 
Los elementos configurables son exclusivamente: logotipo institucional, color primario, color secundario y nombre visible de la organización. No se permite modificar otros elementos de la interfaz.
 
El sistema debe validar el formato de los archivos de imagen cargados. Los formatos permitidos son: PNG, JPEG y SVG. Si el archivo cargado no cumple con los formatos admitidos, el sistema rechazará la operación y mostrará un mensaje de error descriptivo, conservando la configuración visual vigente sin alteraciones.
 
El tamaño del archivo de imagen no debe exceder 2 MB. Si se supera este límite, el sistema rechazará la carga con un mensaje de error que indique el tamaño máximo permitido.
 
Los colores primario y secundario deben especificarse en formato hexadecimal válido de seis dígitos (ej. #3A7BD5). Si el valor ingresado no cumple este formato, el sistema rechazará la operación e informará el error al usuario.
 
Si cualquier validación falla, la operación de guardado se cancela en su totalidad; no se aplicarán cambios parciales sobre la identidad visual activa.
 
La personalización visual no debe afectar el funcionamiento operativo del sistema.
 
Los cambios aplicados deben mantenerse consistentes en todas las vistas de la plataforma.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios, RF-03 — Gestión de roles, RF-19 — Registro y gestión de datos de la finca

**Actores:** Administrador del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| logo_path | character(255) | Ruta del servidor donde se almacena el archivo de imagen. |
| primary_color | character(7) | Código hexadecimal del color principal (ej. #FFFFFF). |
| secondary_color | character(7) | Código hexadecimal del color secundario. |
| org_display_name | character(50) | Nombre institucional que se mostrará en los encabezados. |

**Proceso:**

1. El administrador accede al módulo de Configuración y personalización del sistema.
 
2. El sistema muestra las opciones disponibles para personalizar la identidad visual, incluyendo los valores actualmente configurados.
 
3. El administrador carga o modifica los elementos visuales que desea configurar (logotipo, color primario, color secundario, nombre de la organización).
 
4. El sistema valida los formatos y tamaños de los archivos cargados, así como el formato de los valores de color.
 
5. Si alguna validación falla, el sistema muestra un mensaje de error descriptivo y no avanza al paso siguiente. La configuración vigente permanece sin cambios.
 
6. Si todas las validaciones son exitosas, el sistema genera y presenta una vista previa en tiempo real de la identidad visual configurada, aplicando los cambios de forma temporal en la interfaz.
 
7. El administrador revisa la vista previa y confirma o descarta los cambios.
 
8. Si el administrador confirma, el sistema persiste la configuración visual definida.
 
9. El sistema aplica los cambios de forma consistente en todos los componentes de la interfaz.
 
10. El sistema registra la modificación en el historial de auditoría, incluyendo usuario, fecha, hora y valores anteriores y nuevos de cada elemento modificado.

**Flujo alterno:**

Formato de imagen no compatible:

El administrador intenta subir un archivo que no es PNG, JPEG o SVG (ej. un archivo .gif, .pdf o .webp).

El sistema responde con:

HTTP 415: Unsupported Media Type

Mensaje: "Archivo no admitido: El logotipo debe estar en formato PNG, JPEG o SVG. El archivo [NOMBRE_ARCHIVO] ha sido rechazado."

Código de color hexadecimal inválido:

El usuario ingresa un valor que no cumple el patrón hexadecimal (ej. "#ZZZ123", "rojo" o un código de solo 3 dígitos si el sistema exige 6).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Formato de color inválido: Los colores deben expresarse en formato hexadecimal de 6 dígitos (ej. #3A7BD5). Verifique el valor ingresado en [CAMPO_COLOR]."

Nombre de organización demasiado extenso:

El valor de org_display_name supera los 50 caracteres, lo que podría romper la estructura de la barra de navegación (header).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Texto demasiado largo: El nombre de la organización no puede exceder los 50 caracteres para garantizar la correcta visualización en todos los dispositivos."

Fallo en la persistencia del archivo (Storage Error):

El sistema valida la imagen, pero ocurre un error al intentar escribir el archivo en el servidor o en el servicio de almacenamiento en la nube (S3/Cloud Storage).

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Error de almacenamiento: No se pudo guardar el logotipo debido a un fallo en el servidor de archivos. La configuración anterior no ha sido modificada."

Acceso denegado (Privilegios insuficientes):

Un usuario con rol 'Ingeniero de campo' o 'Productor' intenta enviar una petición PATCH o POST al endpoint de identidad visual.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: Solo el Administrador del sistema tiene permisos para modificar la identidad visual institucional."

Cancelación en Vista Previa:

El administrador visualiza los cambios en tiempo real pero decide no confirmar (clic en "Descartar").

El sistema limpia los estados temporales de la interfaz y restaura los valores de primary_color, secondary_color y logo_path almacenados en la base de datos sin realizar ninguna petición de actualización.

**Salida:**

Identidad visual del sistema actualizada.
 
 Interfaz adaptada a la imagen institucional configurada.
 
 Confirmación de guardado de la configuración.

**Postcondiciones:**

El sistema muestra la identidad visual configurada en las distintas pantallas de la plataforma.
 
 Los usuarios visualizarán la identidad visual actualizada en sus sesiones activas o al iniciar sesión nuevamente.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:
 
El administrador puede cargar un logotipo institucional en formato PNG, JPEG o SVG con tamaño máximo de 2 MB.
 
El administrador puede configurar de forma independiente el color primario y el color secundario de la interfaz mediante valores hexadecimales válidos.
 
El color primario se aplica correctamente sobre barras de navegación, botones de acción primaria y encabezados de sección.
 
El color secundario se aplica correctamente sobre botones de acción secundaria, bordes activos y elementos de énfasis visual.
 
Antes de confirmar los cambios, el sistema presenta al usuario una vista previa en tiempo real de la identidad visual configurada.
 
Si se carga un archivo en formato no admitido o que excede el tamaño máximo, el sistema rechaza la operación con un mensaje de error descriptivo y conserva la configuración visual vigente.
 
Si se ingresa un valor de color en formato inválido, el sistema rechaza la operación con un mensaje de error y no aplica ningún cambio parcial.
 
Solo el usuario con rol Administrador puede acceder y modificar la identidad visual.
 
La interfaz mantiene consistencia visual en los distintos módulos del sistema.
 
Los cambios no afectan el funcionamiento operativo del sistema.

**Requerimientos no funcionales:**

Usabilidad
 La configuración de la identidad visual debe ser sencilla e intuitiva para el administrador.
 
 Fiabilidad
 El sistema debe aplicar correctamente los cambios visuales configurados.
 
 Seguridad
 Solo usuarios autorizados podrán modificar la identidad visual del sistema.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-27 — Configuración visual del sistema

**Código Identificación:** RF-27 -- Versión -- 1.0

**Fuente:** Administrador del sistema / Usuarios del sistema

**Descripción:** El sistema debe permitir configurar el tema visual de la interfaz de usuario, permitiendo seleccionar entre diferentes estilos de visualización que modifiquen la apariencia general del sistema sin alterar su funcionamiento.
 
 Los temas visuales permiten adaptar la presentación de la interfaz para mejorar la legibilidad, comodidad visual y experiencia de uso, especialmente en diferentes condiciones de iluminación o preferencias de los usuarios.
 
 El sistema deberá permitir seleccionar entre diferentes temas visuales, tales como:
 
 Tema claro (Light mode)
 
 Tema oscuro (Dark mode)
 
 Tema automático según configuración del dispositivo
 
 La configuración del tema visual podrá ser aplicada a nivel de:
 
 usuario individual, permitiendo que cada usuario seleccione su preferencia de visualización, la cual tiene prioridad sobre la configuración predeterminada global
 
 configuración predeterminada del sistema, definida por el administrador y aplicada a los usuarios que no hayan definido una preferencia individual
 
 Si un usuario no ha definido preferencia individual, el sistema aplica el tema global del administrador. Si tampoco existe tema global configurado, el sistema aplica el tema claro como valor por defecto.
 
 Los temas visuales deberán aplicarse de forma consistente en todos los componentes de la interfaz del sistema, incluyendo:
 
 barra de navegación
 
 paneles de control
 
 tablas de datos
 
 formularios
 
 dashboards de monitoreo
 
 La configuración del tema visual es independiente de la identidad visual del sistema definida en RF-26, ya que únicamente modifica el estilo de visualización de la interfaz.

**Justificación:** La configuración de temas visuales permite mejorar la experiencia de uso del sistema, adaptando la interfaz a las preferencias de los usuarios y a las condiciones de uso del entorno.
 
 El uso de temas visuales como el modo oscuro puede reducir la fatiga visual durante el uso prolongado del sistema, especialmente en entornos de monitoreo donde los usuarios interactúan continuamente con paneles de datos.
 
 Además, esta funcionalidad permite mantener la coherencia visual del sistema mientras se preserva la identidad institucional configurada por el administrador.

**Precondiciones:** El usuario debe encontrarse autenticado en el sistema (RF-02).
 
 Debe existir una configuración visual del sistema definida (RF-26).

**Restricciones:** La configuración del tema visual no debe alterar la estructura ni el funcionamiento del sistema.
 
 La preferencia individual del usuario tiene prioridad sobre el tema global configurado por el administrador. Si el usuario no tiene preferencia configurada, se aplica el tema global. Si no existe tema global, se aplica el tema claro como valor por defecto.
 
 La preferencia de tema del usuario se almacena en base de datos, no en la sesión del navegador, de modo que persiste entre sesiones.
 
 Los temas visuales deben garantizar legibilidad y accesibilidad, con una relación de contraste mínima de 4.5:1 entre texto y fondo, conforme al estándar WCAG 2.1 nivel AA.
 
 Los cambios aplicados deben ser compatibles con todos los módulos del sistema.
 
 La identidad visual institucional definida por el administrador no debe verse comprometida por el tema visual seleccionado.

**Prioridad:** [ ] Alta/Must [ ] Media/Should [X] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios, RF-26 — Personalización de identidad visual del sistema

**Actores:** Administrador del sistema, Usuario del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| theme_mode | integer | Identificador del tema: 1 (Claro), 2 (Oscuro), 3 (Sistema). |
| user_id | integer | ID del usuario que aplica la preferencia (FK a usuarios). |

**Proceso:**

El usuario accede al sistema e inicia sesión.
 
 El usuario accede a la sección de configuración de visualización del sistema.
 
 El sistema muestra las opciones de temas visuales disponibles.
 
 El usuario selecciona el tema visual deseado.
 
 El sistema guarda la preferencia en base de datos asociada al perfil del usuario.
 
 El sistema aplica el tema visual seleccionado en la interfaz.
 
 En sesiones posteriores, el sistema carga la preferencia individual del usuario; si no existe, aplica el tema global; si tampoco existe tema global configurado, aplica el tema claro como valor por defecto.

**Flujo alterno:**

Valor de tema inválido:

El sistema recibe un theme_mode fuera del rango permitido (distinto a 1, 2 o 3).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de configuración: El identificador de tema [VALOR_RECIBIDO] no es válido. Los valores permitidos son 1 (Claro), 2 (Oscuro) o 3 (Automático)."

Fallo de persistencia en Base de Datos:

El usuario intenta guardar su preferencia, pero ocurre un error de conexión con el servidor de base de datos.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Error al guardar preferencia: No se pudo persistir su elección de tema visual en el perfil. El cambio se aplicará temporalmente en esta sesión, pero no se mantendrá al reiniciar."

Privilegios insuficientes (Configuración Global):

Un usuario con rol 'Productor' o 'Veterinario' intenta modificar el tema predeterminado a nivel global para todos los usuarios.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: Solo el Administrador del sistema puede definir el tema visual predeterminado de la plataforma."

Incompatibilidad de contraste con Identidad Visual (RF-26):

El sistema detecta que al aplicar el Modo Oscuro, el color primario definido por la institución (RF-26) no cumple con el ratio de contraste 4.5:1 sobre el fondo oscuro.

El sistema responde con:

Advertencia (UI): "Aviso de accesibilidad: El color institucional configurado tiene bajo contraste en el modo seleccionado. Se aplicará una variante aclarada/oscurecida automáticamente para garantizar la legibilidad."

Error en modo "Automático" (Dispositivo no compatible):

El usuario selecciona el tema 3 (Sincronización con el sistema), pero su navegador o sistema operativo no expone la propiedad prefers-color-scheme.

El sistema responde con:

Lógica de Fallback: El sistema aplica el Tema Claro por defecto y muestra un mensaje informativo: "Su dispositivo no informa una preferencia de tema; se ha aplicado el modo claro por defecto."

Conflicto de actualización de perfil:

El usuario intenta cambiar el tema mientras su perfil está siendo editado por un Administrador (RF-05).

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de datos: No se pudo actualizar la preferencia visual porque su perfil está siendo modificado en este momento. Intente de nuevo en unos segundos."

**Salida:**

Tema visual aplicado en la interfaz del sistema.
 
 Preferencia de visualización almacenada en base de datos para el usuario.

**Postcondiciones:**

La interfaz del sistema se visualizará según el tema configurado.
 
 La preferencia del usuario se aplicará automáticamente en sesiones posteriores.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:
 
 El sistema permite seleccionar entre distintos temas visuales.
 
 El sistema aplica correctamente el tema visual seleccionado.
 
 Un usuario con preferencia individual configurada mantiene su tema aunque el administrador modifique el tema global.
 
 Un usuario sin preferencia individual visualiza el tema global activo del administrador.
 
 Si no existe tema global configurado, el sistema aplica el tema claro como valor por defecto.
 
 La preferencia de tema visual persiste correctamente entre sesiones de usuario.
 
 Los elementos de la interfaz mantienen legibilidad y coherencia visual.

**Requerimientos no funcionales:**

Usabilidad
 El cambio de tema visual debe aplicarse de manera rápida y sin interrumpir el uso del sistema.
 
 Accesibilidad
 Los temas visuales deben garantizar una correcta visibilidad de los elementos de la interfaz, cumpliendo con el estándar WCAG 2.1 nivel AA.
 
 Fiabilidad
 La configuración visual seleccionada debe mantenerse consistente durante el uso del sistema.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-28 — Personalización del dashboard

**Código Identificación:** RF-28 -- Versión -- 1.0

**Fuente:** Administrador del sistema / Ingeniero de campo / Productor

**Descripción:** El sistema debe permitir a los usuarios personalizar la disposición y los elementos visualizados en el panel principal de monitoreo (dashboard), con el fin de adaptar la visualización de la información a sus necesidades operativas.
 
La personalización del dashboard permitirá seleccionar qué indicadores, sensores, gráficos y paneles informativos se muestran en la interfaz principal del sistema.
 
El usuario podrá:
 
seleccionar los indicadores que desea visualizar
 
elegir los sensores o variables ambientales que desea monitorear
 
organizar la disposición de los paneles dentro del dashboard mediante la asignación de posiciones en una grilla fija de 4 columnas × 3 filas (máximo 12 posiciones disponibles)
 
ocultar o mostrar módulos informativos según su preferencia
 
El número máximo de widgets activos simultáneamente en el dashboard es de 12. Si el usuario intenta agregar un widget adicional al alcanzar este límite, el sistema informará que se ha alcanzado el máximo permitido.
 
Si un widget no tiene datos disponibles, el sistema lo mostrará con el mensaje 'Sin datos disponibles', sin ocultarlo ni generar un error en los demás widgets. El widget permanecerá visible y conservará su posición en la grilla.
 
El usuario podrá restaurar el dashboard a la configuración predeterminada de su rol mediante la opción 'Restaurar configuración predeterminada'.
 
La personalización deberá mantenerse asociada al perfil del usuario, permitiendo que cada usuario tenga un dashboard adaptado a su función dentro del sistema.
 
Los cambios realizados en la configuración del dashboard se aplican de forma inmediata en la sesión activa, sin necesidad de recargar la interfaz.
 
La personalización del dashboard es responsiva: la configuración del usuario se adapta automáticamente a diferentes resoluciones de pantalla (escritorio ≥1024px, tableta 768–1023px, móvil <768px), reordenando los widgets de forma proporcional sin perder la configuración del usuario.
 
Los elementos configurables dentro del dashboard podrán incluir:
 
indicadores ambientales (temperatura, humedad, pH, etc.)
 
estado de los dispositivos IoT
 
alertas ambientales
 
gráficos históricos de monitoreo
 
indicadores productivos asociados a las especies monitoreadas
 
Esta funcionalidad permitirá mejorar la interpretación de la información operativa, facilitando el acceso rápido a los datos más relevantes para cada usuario.

**Justificación:** Los diferentes actores del sistema requieren visualizar información distinta según su rol dentro del proceso productivo.
 
 Por ejemplo:
 
 el productor puede requerir observar el estado general del ambiente y alertas críticas
 
 el ingeniero de campo puede necesitar analizar variables ambientales específicas
 
 el administrador puede requerir visualizar el estado de la infraestructura y los dispositivos del sistema
 
 La personalización del dashboard permite adaptar la visualización de los datos a las necesidades de cada usuario, mejorando la eficiencia operativa, la toma de decisiones y la experiencia de uso del sistema.
 
 Además, esta funcionalidad facilita el acceso rápido a los indicadores más relevantes del sistema de monitoreo.

**Precondiciones:** El usuario debe encontrarse autenticado en el sistema (RF-02).
 
 Debe existir al menos una finca registrada en el sistema (RF-19).
 
 Deben existir dispositivos o sensores registrados en el sistema (RF-21).
 
 Deben existir variables ambientales configuradas en el sistema (RF-17).

**Restricciones:** La personalización del dashboard debe respetar los permisos definidos por el sistema de roles.
 
Los usuarios solo podrán visualizar los indicadores correspondientes a los módulos para los cuales tienen permisos.
 
La grilla de posicionamiento se compone de 4 columnas y 3 filas, permitiendo hasta 12 posiciones disponibles para widgets. El número máximo de widgets activos simultáneamente en el dashboard es de 12.
 
El mecanismo de organización de los paneles es mediante la asignación de posiciones en la grilla predefinida de 4×3. Cada widget ocupa una posición definida por su fila, columna y extensión horizontal (span de 1 o 2 columnas).
 
Si un widget no tiene datos disponibles, el sistema lo muestra con el mensaje 'Sin datos disponibles'; no se oculta ni genera error en los demás widgets.
 
Si el usuario intenta guardar una configuración inválida (posición ya ocupada, widget no disponible para su rol, tipo de widget inexistente, o superación del límite máximo de widgets), el sistema rechazará la operación, informará el motivo del error y no persistirá ningún cambio parcial.
 
Los cambios realizados en la configuración del dashboard se aplican de forma inmediata en la sesión activa, sin requerir recarga de la interfaz.
 
La personalización del dashboard es responsiva y se adapta automáticamente a las resoluciones de escritorio (≥1024px), tableta (768–1023px) y móvil (<768px).
 
La configuración del dashboard se almacena en base de datos y se mantiene asociada al perfil del usuario entre sesiones.
 
Los cambios realizados en el dashboard no deben afectar el funcionamiento de los módulos del sistema.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios, RF-03 — Gestión de roles, RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental, RF-19 — Registro y gestión de datos de la finca, RF-21 — Registro de dispositivos IoT

**Actores:** Administrador del sistema / Ingeniero de campo / Productor

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| layout_config | jsonb | Estructura de posicionamiento y visibilidad de los widgets. Campos: id_widget (integer), posicion_fila (integer, 1–3), posicion_columna (integer, 1–4), span_columnas (integer, 1 o 2), visible (boolean), orden (integer). |
| active_widgets | text[] | Arreglo de identificadores de los sensores/indicadores visibles. |

**Proceso:**

1. El usuario accede al sistema e inicia sesión.
 
2. El usuario accede al panel principal del sistema.
 
3. El usuario selecciona la opción de personalización del dashboard.
 
4. El sistema muestra los elementos disponibles para ser configurados y la grilla predefinida de 4×3 con las posiciones actuales de los widgets.
 
5. El usuario selecciona los indicadores y paneles que desea visualizar y asigna una posición en la grilla a cada uno.
 
6. Si el usuario intenta asignar dos widgets a la misma posición, agregar un widget no permitido para su rol, o superar el límite de 12 widgets, el sistema muestra un mensaje de error y no aplica el cambio.
 
7. El sistema aplica los cambios de forma inmediata en la sesión activa, sin requerir recarga de la interfaz.
 
8. El sistema guarda la configuración personalizada del usuario en base de datos.
 
9. Para restaurar, el usuario selecciona 'Restaurar configuración predeterminada' y el sistema carga la configuración por defecto del rol del usuario.

**Flujo alterno:**

Solapamiento de posiciones (Conflicto de grilla):

El usuario intenta asignar un widget a una coordenada (fila, columna) que ya está ocupada, o intenta colocar un widget de ancho doble (span_columnas: 2) en una posición donde la segunda columna ya está en uso.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de posición: La ubicación en la fila [X] y columna [Y] ya está ocupada por otro elemento o se encuentra dentro del rango de expansión de un widget adyacente."

Superación del límite de widgets activos:

El usuario intenta marcar como visible: true un widget adicional cuando ya cuenta con 12 elementos activos en su layout_config.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Límite de widgets alcanzado: El dashboard permite un máximo de 12 elementos activos simultáneamente. Por favor, desactive un widget antes de agregar uno nuevo."

Error de desbordamiento horizontal (Span inválido):

El usuario intenta posicionar un widget con span_columnas: 2 en la columna 4 de la grilla, lo que causaría que el elemento se "desborde" fuera de los límites de la pantalla.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de dimensiones: Un widget con extensión de 2 columnas no puede ubicarse en la última columna (columna 4) de la grilla."

Widget no autorizado para el rol del usuario:

El usuario intenta agregar a su dashboard un id_widget que pertenece a un módulo para el cual su rol no tiene permisos (ej. un Productor intentando ver un panel de configuración técnica de nodos LoRaWAN).

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: El indicador o panel solicitado no está disponible para su nivel de permisos o rol asignado."

Conflicto de actualización de configuración (Concurrencia):

El usuario intenta guardar su personalización mientras el Administrador está realizando cambios críticos en su perfil (ej. cambio de finca asignada o de rol) que invalidan el contexto actual.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de datos: No se pudo actualizar la personalización del dashboard porque su configuración de perfil ha sido modificada recientemente. Por favor, refresque la interfaz."

Fallo en "Restaurar configuración predeterminada":

El usuario solicita restaurar los valores de fábrica, pero el sistema no encuentra un layout_config base definido para el rol del usuario en la base de datos.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Fallo de restauración: No se encontró una configuración predeterminada para el rol [ROL_USUARIO]. Se mantendrá su configuración actual; por favor, contacte a soporte."

Manejo visual de Widget sin datos operativos:

El sistema intenta renderizar un widget de sensor (RF-21) que no ha reportado datos en el rango de tiempo actual o que ha sido desconectado.

El sistema responde con:

Lógica de Fallback: El widget mantiene su posición en la grilla pero renderiza un estado vacío con un ícono de advertencia y el mensaje: "Sin datos disponibles para el sensor o periodo seleccionado."

**Salida:**

Dashboard personalizado según las preferencias del usuario.
 
 Visualización de indicadores y paneles configurados.

**Postcondiciones:**

El usuario visualizará el dashboard configurado en futuras sesiones.
 
 La configuración personalizada se mantendrá asociada al perfil del usuario.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:
 
El sistema permite seleccionar qué indicadores se muestran en el dashboard.
 
El usuario puede modificar la disposición de los paneles mediante la grilla predefinida de 4 columnas × 3 filas.
 
El sistema impide agregar más de 12 widgets activos simultáneamente en el dashboard e informa al usuario cuando se alcanza el límite.
 
Un widget sin datos disponibles muestra el mensaje 'Sin datos disponibles' sin generar error en los demás widgets del dashboard.
 
El sistema rechaza una configuración con dos widgets asignados a la misma posición de la grilla, informando el motivo del conflicto.
 
Los cambios realizados se aplican de forma inmediata en la sesión activa, sin requerir recarga de la interfaz.
 
La configuración del dashboard se adapta automáticamente a pantallas de escritorio, tableta y móvil.
 
Los cambios realizados se guardan correctamente en base de datos para el usuario.
 
El sistema aplica automáticamente la configuración personalizada en sesiones posteriores.
 
La opción 'Restaurar configuración predeterminada' carga correctamente la configuración por defecto del rol del usuario.
 
Los usuarios solo pueden visualizar información correspondiente a sus permisos.

**Requerimientos no funcionales:**

Usabilidad
 La personalización del dashboard debe ser intuitiva y fácil de configurar.
 
 Disponibilidad
 El dashboard debe cargarse correctamente con la configuración definida por el usuario.
 
 Fiabilidad
 La configuración personalizada debe mantenerse consistente entre sesiones del usuario.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-29 — Configuración de idioma

**Código Identificación:** RF-29 -- Versión -- 1.0

**Fuente:** Administrador del sistema / Usuarios del sistema

**Descripción:** El sistema debe permitir configurar el idioma de visualización de la interfaz, permitiendo a los usuarios seleccionar el idioma en el que desean interactuar con la plataforma.
 
 La configuración de idioma deberá aplicarse a los distintos elementos de la interfaz del sistema, incluyendo:
 
 menús de navegación
 
 etiquetas de formularios
 
 mensajes del sistema
 
 paneles informativos
 
 mensajes de error y confirmación
 
 títulos de módulos y dashboards
 
 Los idiomas disponibles en el sistema son español e inglés. El idioma predeterminado es el español.
 
 El cambio de idioma se aplica de forma inmediata, sin necesidad de recargar la sesión activa.
 
 La selección del idioma no afectará los datos ingresados por los usuarios (nombres de fincas, observaciones, descripciones), los cuales permanecerán en el idioma en que fueron registrados.
 
 La preferencia de idioma podrá configurarse a nivel de:
 
 usuario individual, permitiendo que cada usuario seleccione su idioma preferido
 
 configuración predeterminada del sistema, definida por el administrador.
 
 La selección del idioma no afectará la lógica funcional del sistema ni la estructura de los datos almacenados, limitándose únicamente a la traducción de los elementos de la interfaz de usuario.

**Justificación:** La configuración de idioma permite mejorar la accesibilidad y usabilidad del sistema, facilitando su utilización por usuarios que hablan distintos idiomas.
 
 Esta funcionalidad es especialmente relevante en plataformas que pueden ser utilizadas por diferentes organizaciones o usuarios con distintos contextos lingüísticos.
 
 Además, la internacionalización del sistema permite facilitar su escalabilidad y adopción en diferentes regiones, mejorando la experiencia de uso y la comprensión de la información presentada en la interfaz.

**Precondiciones:** El usuario debe encontrarse autenticado en el sistema (RF-02).
 
 El sistema debe tener configurado al menos un idioma disponible para su selección.

**Restricciones:** La configuración del idioma solo afectará la interfaz del sistema, no los datos almacenados.
 
Los idiomas disponibles son español e inglés. No se pueden agregar nuevos idiomas sin intervención del equipo de desarrollo.
 
Si un elemento de la interfaz no tiene traducción disponible en el idioma seleccionado, el sistema lo mostrará en español como idioma de respaldo (fallback).
 
Los datos ingresados por usuarios (nombres, observaciones, descripciones) no se ven afectados por el cambio de idioma de la interfaz.
 
Los textos del sistema deberán mantener coherencia y consistencia en todos los módulos. La implementación del soporte multiidioma debe realizarse mediante un framework de internacionalización estándar (i18n), garantizando que las cadenas de texto se gestionen de forma centralizada y verificable entre todos los módulos.
 
El sistema debe estar diseñado de forma que la incorporación de futuros idiomas no requiera cambios estructurales en el código base, limitándose a la adición de nuevos archivos de traducción.
 
El sistema debe garantizar que los elementos de la interfaz se adapten correctamente a la longitud de los textos en los distintos idiomas, evitando truncamientos, desbordamientos o desalineaciones visuales.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios, RF-03 — Gestión de roles

**Actores:** Administrador del sistema / Usuarios del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| locale_code | character(5) | Código de idioma y región (ej. 'es-CO', 'en-US'). |
| is_default | boolean | Define si es el idioma predeterminado del sistema. |

**Proceso:**

El usuario accede al sistema e inicia sesión.
 
 El usuario accede a la sección de configuración de preferencias del sistema.
 
 El sistema muestra los idiomas disponibles (español e inglés).
 
 El usuario selecciona el idioma de preferencia.
 
 El sistema aplica el idioma de forma inmediata sin recargar la sesión activa.
 
 El sistema guarda la configuración del idioma para el usuario.
 
 Los elementos sin traducción disponible se muestran en español.

**Flujo alterno:**

Código de idioma no soportado:

El sistema recibe un locale_code que no está en el catálogo permitido (ej. 'fr-FR' o 'it-IT').

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Idioma no disponible: El código de cultura [LOCALE_CODE] no está soportado actualmente. Los idiomas disponibles son Español (es-CO) e Inglés (en-US)."

Fallo en la persistencia de la preferencia:

El usuario selecciona un idioma válido, pero ocurre un error al intentar guardar esta preferencia en su perfil en la base de datos.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Error de persistencia: No se pudo guardar su preferencia de idioma. El cambio se aplicará temporalmente en esta sesión, pero se perderá al cerrar el navegador."

Ausencia de traducción (Fallback al Español):

El usuario selecciona 'Inglés', pero el sistema navega a un módulo nuevo donde algunas etiquetas aún no han sido traducidas por el equipo de desarrollo.

El sistema responde con:

Lógica de Fallback: El framework de i18n detecta la ausencia de la clave en en-US.json y renderiza automáticamente el texto contenido en es-CO.json.

Comportamiento visual: No se muestra error al usuario, pero se registra una advertencia en los logs de desarrollo para completar la traducción.

Privilegios insuficientes (Configuración Global):

Un usuario con rol 'Productor' o 'Ingeniero de campo' intenta modificar el is_default: true para cambiar el idioma predeterminado de toda la plataforma.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: Solo el Administrador del sistema puede definir el idioma predeterminado global de la plataforma."

Conflicto de actualización de perfil:

El usuario intenta cambiar su idioma mientras un Administrador está modificando otros datos de su cuenta (RF-05).

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de datos: No se pudo actualizar el idioma porque su perfil está siendo modificado en este momento. Intente de nuevo en unos segundos."

Desbordamiento visual por longitud de texto (UI Error):

Al cambiar a un idioma cuyas palabras son significativamente más largas (típico en algunas traducciones técnicas), el sistema detecta que un botón o etiqueta se desborda de su contenedor.

El sistema responde con:

Lógica de Adaptación: El sistema debe aplicar propiedades CSS como text-overflow: ellipsis o contenedores flexibles (Flexbox/Grid) para evitar que la interfaz se rompa, manteniendo la integridad visual aunque el texto se acorte visualmente.

**Salida:**

Interfaz del sistema mostrada en el idioma seleccionado.
 
 Preferencia de idioma almacenada para el usuario.

**Postcondiciones:**

El sistema mostrará la interfaz en el idioma configurado en futuras sesiones del usuario.
 
 El idioma configurado se aplicará en todos los módulos del sistema.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:
 
 El sistema permite seleccionar un idioma entre los disponibles (español e inglés).
 
 Los textos del sistema se muestran correctamente en el idioma seleccionado.
 
 El cambio de idioma se aplica de forma inmediata sin recargar la sesión activa.
 
 Los elementos sin traducción disponible se muestran en español (fallback).
 
 La preferencia de idioma se guarda correctamente para el usuario.
 
 Los datos ingresados por el usuario no cambian al modificar el idioma de la interfaz.
 
 El idioma configurado se aplica automáticamente en futuras sesiones.

**Requerimientos no funcionales:**

Usabilidad
La selección del idioma debe ser sencilla e intuitiva.
 
Accesibilidad
Los elementos de la interfaz deben adaptarse correctamente al idioma seleccionado, garantizando que variaciones en la longitud de los textos traducidos no generen problemas de presentación visual (truncamientos, desbordamientos o desalineaciones). Deben realizarse pruebas de interfaz específicas para verificar este comportamiento.
 
Fiabilidad
La configuración del idioma debe mantenerse consistente durante el uso del sistema.
 
Mantenibilidad
El sistema de internacionalización debe estar diseñado para soportar la incorporación escalable de nuevos idiomas, sin requerir modificaciones estructurales en la arquitectura de la interfaz. Todas las traducciones deben ser verificadas mediante pruebas de consistencia entre idiomas antes de su despliegue en producción.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-30 — Plantillas de configuración

**Código Identificación:** RF-30 -- Versión -- 1.1

**Fuente:** Administrador del sistema / Ingeniero de campo

**Descripción:** El sistema debe permitir gestionar plantillas de configuración que contengan conjuntos predefinidos de parámetros reutilizables del sistema de monitoreo pecuario.
 
 Una plantilla agrupa parámetros de las siguientes categorías exclusivamente:
 
 parámetros productivos por especie (etapas del ciclo y patologías)
 
 umbrales de monitoreo ambiental y niveles de alerta
 
 variables ambientales monitoreadas
 
 Una plantilla no puede incluir configuraciones de dispositivos IoT, infraestructura física, dashboard ni identidad visual, ya que estas dependen del contexto específico de cada unidad productiva.
 
 La gestión de plantillas comprende dos operaciones atómicas definidas en requerimientos independientes:
 
 RF-31 — Creación de plantilla: registro y almacenamiento de una nueva plantilla.
 
 RF-32 — Aplicación de plantilla: validación y aplicación de una plantilla existente sobre una configuración destino.

 La recomendación asistida de plantillas (RF-108) es una operación de solo lectura que ordena y explica las plantillas técnicamente aplicables a un destino; **no crea, no modifica ni aplica** ninguna plantilla — la creación es exclusiva de RF-31 y la aplicación de RF-32. Esta precisión de alcance delimita el papel de cada uno de los cuatro requerimientos relacionados (RF-30, RF-31, RF-32 y RF-108) para evitar confusión entre "recomendar" y "aplicar".

**Justificación:** Las plantillas de configuración permiten estandarizar la parametrización del sistema y reducir el tiempo de implementación en nuevas fincas o especies. Al separar la creación de la aplicación como operaciones atómicas, se facilita la verificación independiente de cada operación y se reduce el riesgo de implementación, en cumplimiento del atributo de Mantenibilidad de ISO/IEC 25010:2023.

**Precondiciones:** El usuario debe encontrarse autenticado en el sistema (RF-02).
 
 Debe existir al menos una especie registrada en el sistema (RF-13).

**Restricciones:** Solo los usuarios con permisos de Administrador o Ingeniero de campo podrán gestionar plantillas de configuración.
 
El alcance de una plantilla se limita a parámetros productivos por especie y umbrales de monitoreo ambiental. No incluye configuraciones de dispositivos, infraestructura, dashboard ni identidad visual.
 
Cada plantilla almacena un número de versión entero incremental. Una plantilla guardada no puede modificarse; cualquier actualización genera una nueva versión.
 
El nombre de la plantilla debe ser único en el sistema.
 
El campo params_snapshot debe ajustarse al esquema JSON predefinido del sistema (JSON Schema). El incumplimiento del esquema resulta en rechazo de la operación con mensaje descriptivo de los parámetros inválidos.
 
Cuando una plantilla fue creada bajo una versión anterior del esquema JSON y el esquema vigente ha evolucionado de forma incompatible, el sistema verificará la compatibilidad estructural antes de permitir su aplicación mediante RF-32. En caso de incompatibilidad irrecuperable, la operación de aplicación será cancelada e informada al usuario con detalle de los parámetros incompatibles.
 
Las operaciones de creación y aplicación están definidas en RF-31 y RF-32 respectivamente.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-02 — Autenticación de usuarios, RF-15 — Gestión del catálogo de especies, RF-16 — Configuración de parámetros productivos por especie, RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental

**Actores:** Administrador del sistema / Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| template_name | character(50) | Nombre descriptivo de la plantilla. |
| specie_id | integer | ID de la especie a la que aplica la plantilla (FK a especies). |
| params_snapshot | jsonb | Copia de los parámetros productivos y umbrales a reutilizar. |

**Proceso:**

El usuario accede al módulo de Configuración y personalización del sistema.
 
 El usuario selecciona la opción de gestión de plantillas de configuración.
 
 El sistema muestra el listado de plantillas existentes con su nombre, especie asociada y número de versión.
 
 El usuario selecciona la operación que desea realizar: crear una nueva plantilla (RF-31) o aplicar una plantilla existente (RF-32).
 
 El sistema dirige al usuario al flujo correspondiente según la operación seleccionada.

**Flujo alterno:**

Nombre de plantilla duplicado:

El sistema detecta que el template_name ya existe en el registro global de plantillas.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Nombre no disponible: Ya existe una plantilla denominada '[NOMBRE_INGRESADO]'. Por favor, asigne un nombre único o genere una nueva versión de la plantilla existente."

Violación del esquema JSON (Schema Validation):

El objeto enviado en params_snapshot no cumple con la estructura requerida (ej. faltan campos obligatorios de umbrales de temperatura o las etapas del ciclo tienen formatos de fecha inválidos).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de estructura: El contenido de la plantilla no cumple con el esquema técnico del sistema. Detalles: [LISTA_DE_CAMPOS_INVALIDOS]."

Intento de inclusión de parámetros fuera de alcance (Scope Creep):

El usuario intenta registrar una plantilla que contiene claves de configuración de dispositivos IoT, infraestructura o dashboards (violando la restricción de diseño).

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Alcance no permitido: Las plantillas solo pueden contener parámetros productivos y umbrales ambientales. Se han detectado configuraciones de [CATEGORIA_INVALIDA] que deben ser removidas."

Incompatibilidad de versión de esquema (Legacy Template):

El usuario intenta acceder a una plantilla cuya estructura JSON pertenece a una versión antigua del sistema que ya no es compatible con las reglas de validación vigentes.

El sistema responde con:

HTTP 412: Precondition Failed

Mensaje: "Incompatibilidad estructural: La plantilla '[NOMBRE]' (Versión [V]) fue creada bajo un esquema técnico anterior y no puede procesarse. Es necesario recrear la plantilla con el formato actual."

Referencia de especie inexistente o inactiva:

El specie_id asociado a la plantilla no corresponde a ninguna especie activa en el catálogo (RF-15).

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Especie no válida: No se puede gestionar la plantilla porque la especie asociada (ID: [ID]) no existe o ha sido desactivada."

Intento de modificación de plantilla existente (Inmutabilidad):

El usuario intenta sobrescribir una plantilla ya guardada en lugar de generar una nueva versión (violando la restricción de inmutabilidad).

El sistema responde con:

HTTP 405: Method Not Allowed

Mensaje: "Operación no permitida: Las plantillas son inmutables. Para realizar cambios, debe generar una nueva versión (Versión [N+1]) del registro."

Privilegios insuficientes para gestión técnica:

Un usuario con rol 'Productor' o 'Veterinario' intenta registrar o versionar una plantilla.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: La gestión de plantillas de configuración es una función restringida exclusivamente al Administrador o al Ingeniero de campo."

**Salida:**

Listado de plantillas disponibles en el sistema con nombre, especie y versión.
 
 Acceso a los flujos de creación (RF-31) y aplicación (RF-32).

**Postcondiciones:**

Las plantillas registradas quedan disponibles para su reutilización según los permisos del usuario.
 
 Las operaciones realizadas quedan registradas en el historial de auditoría.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:
 
 El sistema muestra el listado de plantillas con nombre, especie asociada y versión.
 
 El sistema permite acceder a los flujos de creación y aplicación desde el mismo módulo.
 
 El sistema impide registrar dos plantillas con el mismo nombre.
 
 Solo los usuarios con rol autorizado acceden al módulo de plantillas.
 
 Una plantilla guardada no puede modificarse; una actualización genera nueva versión.

**Requerimientos no funcionales:**

Usabilidad
El acceso a las operaciones de plantilla debe ser sencillo e intuitivo.
 
Mantenibilidad
La separación en sub-requisitos atómicos facilita la verificación y el mantenimiento independiente de cada operación.
El esquema JSON del campo params_snapshot deberá gestionarse mediante control de versiones de esquema (schema versioning), de modo que los cambios estructurales en la definición de parámetros no invaliden plantillas previamente registradas sin notificación explícita al usuario. Cualquier actualización del esquema debe documentarse con el número de versión correspondiente.
 
Disponibilidad
Las plantillas deben estar disponibles para los usuarios autorizados en todo momento.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-31 — Creación de plantilla de configuración

**Código Identificación:** RF-31 -- Versión -- 1.0

**Fuente:** Administrador del sistema / Ingeniero de campo

**Descripción:** El sistema debe permitir al Administrador o Ingeniero de campo crear y guardar una nueva plantilla de configuración a partir de los parámetros seleccionados, asignándole un nombre único y asociándola a una especie del catálogo.
 
 El proceso es el siguiente:
 
 1. El usuario accede al módulo de Plantillas y selecciona 'Nueva plantilla'.
 2. El usuario ingresa el nombre de la plantilla.
 3. El usuario selecciona la especie del catálogo a la que aplica la plantilla.
 4. El usuario selecciona los parámetros que desea incluir en la plantilla (umbrales ambientales y/o parámetros productivos de la especie seleccionada).
 5. El sistema valida que el nombre sea único en el sistema.
 6. El sistema guarda la plantilla con los parámetros seleccionados y le asigna el número de versión inicial (1).
 7. La plantilla queda disponible en el listado del módulo.

**Justificación:** Permitir la creación de plantillas estandariza la parametrización del sistema y reduce el tiempo de configuración en nuevas unidades productivas. Al ser una operación atómica independiente, se puede verificar, probar y mantener sin afectar la lógica de aplicación definida en RF-32, en cumplimiento del atributo de Mantenibilidad de ISO/IEC 25010:2023.

**Precondiciones:** El usuario debe tener sesión activa con rol de Administrador o Ingeniero de campo.
 
 Debe existir al menos una especie activa en el catálogo (RF-13).
 
 Deben existir configuraciones de parámetros disponibles para la especie seleccionada (RF-14 y/o RF-15).

**Restricciones:** El nombre de la plantilla debe ser único en el sistema; el sistema rechaza nombres duplicados.
 
La plantilla debe estar asociada a al menos una especie del catálogo.
 
Una plantilla creada no puede modificarse directamente; cualquier actualización genera una nueva versión con número incremental.
 
La plantilla solo puede incluir parámetros productivos por especie y umbrales de monitoreo ambiental; no puede incluir configuraciones de dispositivos, infraestructura, dashboard ni identidad visual.
 
El campo params_snapshot generado deberá cumplir con el esquema JSON predefinido del sistema (JSON Schema). El sistema validará la estructura del snapshot antes de persistirlo; si la validación estructural falla, la operación de creación será rechazada con un mensaje de error que identifique los parámetros inválidos. No se almacenará ningún registro parcial.
 
Solo Administrador e Ingeniero de campo pueden crear plantillas.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-30 — Plantillas de configuración, RF-15 — Gestión del catálogo de especies, RF-16 — Configuración de parámetros productivos por especie, RF-17 — Configuración de Umbrales de Monitoreo y Niveles de Alerta Ambiental, RF-02 — Autenticación de usuarios, RF-04 — Gestión de permisos

**Actores:** Administrador del sistema, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| template_name | character(50) | Nombre único descriptivo de la plantilla. |
| specie_id | integer | ID de la especie asociada a la plantilla (FK a especies). |
| params_snapshot | jsonb | Conjunto de parámetros productivos y/o umbrales seleccionados para la plantilla. |

**Proceso:**

1. El usuario accede a Configuración → Plantillas y selecciona 'Nueva plantilla'.
 
2. El usuario ingresa el nombre de la plantilla.
 
3. El usuario selecciona la especie del catálogo a la que aplica.
 
4. El sistema muestra los parámetros disponibles de la especie seleccionada (umbrales ambientales y parámetros productivos).
 
5. El usuario selecciona los parámetros que desea incluir en la plantilla.
 
6. El sistema valida que el nombre sea único y que se haya seleccionado al menos un parámetro.
 
7. El sistema valida la estructura del params_snapshot contra el esquema JSON predefinido. Si la validación estructural falla, el sistema rechaza la operación con un mensaje descriptivo indicando los parámetros inválidos y no avanza al paso siguiente.
 
8. El sistema guarda la plantilla con número de versión = 1 y la muestra en el listado del módulo. Si la persistencia falla por error de base de datos o violación de integridad, el sistema descartará la operación completa y notificará al usuario mediante un mensaje de error. No se registrará ningún cambio parcial ni entrada en el historial de auditoría.
 
9. El sistema registra la acción en el historial de auditoría (nombre, especie, versión, usuario, fecha).

**Flujo alterno:**

Nombre de plantilla duplicado:

El sistema detecta que el template_name ya existe en el registro global de plantillas.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Nombre no disponible: Ya existe una plantilla denominada '[NOMBRE_INGRESADO]'. Por favor, asigne un nombre único para esta nueva configuración."

Creación sin parámetros seleccionados:

El usuario intenta guardar la plantilla sin haber marcado al menos un umbral ambiental o un parámetro productivo.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Plantilla vacía: Debe seleccionar al menos un parámetro (etapa, patología o umbral) para poder generar una plantilla válida."

Fallo de validación de esquema (JSON Schema):

El sistema genera el params_snapshot, pero al validarlo contra el esquema maestro, detecta campos faltantes, tipos de datos erróneos o estructuras mal formadas.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de integridad estructural: Los parámetros seleccionados no cumplen con el formato técnico requerido. Detalles: [LISTA_DE_ERRORES_DE_ESQUEMA]. La operación ha sido abortada."

Especie de referencia inactiva o no encontrada:

El specie_id seleccionado no existe o fue desactivado durante el proceso de creación de la plantilla (RF-15).

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Error de referencia: La especie asociada no está disponible o ha sido desactivada. No se puede crear una plantilla para una especie no operativa."

Intento de sobrescritura (Violación de inmutabilidad):

El usuario intenta realizar una petición de creación (POST) sobre una combinación de template_name y version que ya existe (aunque el sistema debería autogestionar la versión, esto protege la API).

El sistema responde con:

HTTP 405: Method Not Allowed

Mensaje: "Acceso denegado: Las versiones de las plantillas son inmutables. Si desea actualizar '[NOMBRE]', el sistema generará automáticamente la versión [V+1]."

Fallo crítico de persistencia (Atomicidad):

Ocurre un error inesperado en la base de datos durante el guardado. El sistema ejecuta un rollback para asegurar que no queden registros huérfanos.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Error de sistema: No se pudo completar el registro de la plantilla por un fallo en el servidor. No se han guardado cambios ni registros de auditoría. Por favor, intente de nuevo."

Acceso no autorizado:

Un usuario con rol 'Productor' o 'Veterinario' intenta forzar la creación de una plantilla vía API.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Privilegios insuficientes: Su rol no permite la creación de plantillas de configuración técnica."

**Salida:**

Plantilla registrada en el sistema con nombre único, especie asociada y versión 1.
 
 Plantilla disponible en el listado del módulo para ser aplicada (RF-32).
 
 Acción registrada en el historial de auditoría.

**Postcondiciones:**

La plantilla creada queda disponible para ser aplicada a otras especies o fincas mediante RF-32.
 
 La plantilla no puede modificarse directamente; una actualización genera una nueva versión.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:
 
El sistema rechaza la creación de una plantilla con un nombre ya existente.
 
El sistema rechaza guardar una plantilla sin parámetros seleccionados.
 
El sistema rechaza el almacenamiento de una plantilla cuyo params_snapshot no cumpla con el esquema JSON predefinido, indicando los parámetros inválidos en el mensaje de error.
 
Ante un fallo de persistencia, el sistema no registra ningún cambio parcial ni entrada en el historial de auditoría.
 
La plantilla creada aparece en el listado del módulo con nombre, especie y versión 1.
 
La plantilla creada está disponible como opción en el módulo de aplicación (RF-32).
 
El historial de auditoría registra nombre, especie, versión, usuario y fecha de creación.
 
Un intento de modificar una plantilla existente genera una nueva versión, no sobreescribe la original.

**Requerimientos no funcionales:**

Usabilidad
El formulario de creación debe ser claro e indicar qué parámetros están disponibles según la especie seleccionada.
 
Fiabilidad
La plantilla guardada debe preservar exactamente los parámetros seleccionados en el momento de su creación.
Ante fallos en la operación de persistencia, el sistema garantiza atomicidad completa: no se almacenará ningún registro parcial ni inconsistente. El usuario recibirá notificación explícita del fallo con indicación del motivo.
 
Seguridad
Solo los roles autorizados pueden crear plantillas.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-32 — Aplicación de plantilla de configuración

**Código Identificación:** RF-32 -- Versión -- 1.1

**Fuente:** Administrador del sistema / Ingeniero de campo

**Descripción:** El sistema debe permitir al Administrador o Ingeniero de campo seleccionar una plantilla existente y aplicarla sobre una configuración destino, previa validación de consistencia de los datos y confirmación explícita del usuario. Al aplicarse, los parámetros de la plantilla reemplazan en su totalidad los parámetros correspondientes en la configuración destino.
 
 El proceso es el siguiente:
 
 1. El usuario accede al módulo de Plantillas y selecciona una plantilla del listado.
 2. El usuario selecciona la configuración destino (especie o finca) sobre la que se aplicará la plantilla.
 3. El sistema valida la consistencia de los parámetros de la plantilla: verifica que los parámetros referenciados existan en el sistema y tengan formatos válidos.
 4. Si la validación falla, el sistema informa al usuario los parámetros con inconsistencias y cancela la operación.
 5. Si la validación es exitosa, el sistema muestra un resumen de los parámetros que serán reemplazados en la configuración destino.
 6. El sistema solicita confirmación explícita al usuario antes de proceder.
 7. Tras la confirmación, el sistema aplica la plantilla reemplazando en su totalidad los parámetros correspondientes en la configuración destino.
 8. El sistema registra la operación en el historial de auditoría.
 9. El sistema deja, además del evento de auditoría, un **registro estructurado y consultable del intento de aplicación** (ver Restricciones), que es la fuente que RF-108 usa para calcular "aplicaciones exitosas recientes" sin recorrer todo el historial de auditoría.

**Justificación:** Separar la aplicación como operación atómica independiente de la creación permite verificar y probar de forma aislada el comportamiento del sistema al reemplazar configuraciones existentes. La validación previa y la confirmación explícita protegen la integridad de los datos de configuración activa, reduciendo el riesgo de aplicar parámetros inconsistentes sobre unidades productivas en operación. Satisface el atributo de Fiabilidad de ISO/IEC 25010:2023.

**Precondiciones:** El usuario debe tener sesión activa con rol de Administrador o Ingeniero de campo.
 
 Debe existir al menos una plantilla registrada en el sistema (RF-31).
 
 Debe existir una configuración destino válida (especie o finca activa) sobre la que aplicar la plantilla.

**Restricciones:** La aplicación de una plantilla reemplaza en su totalidad los parámetros cubiertos por ella en la configuración destino; no se realiza fusión parcial.
 
La operación no puede ejecutarse sin confirmación explícita del usuario.
 
Si la validación de consistencia falla, la operación se cancela completamente; no se aplican cambios parciales.
 
Antes de aplicar la plantilla, el sistema verificará la compatibilidad de versión del esquema JSON del params_snapshot con la versión de esquema vigente. Si existe incompatibilidad estructural irrecuperable, la operación será cancelada e informada al usuario con detalle de los parámetros incompatibles.
 
En caso de fallo durante la aplicación de la plantilla (error de base de datos, timeout u otro error no controlado), el sistema ejecutará un rollback completo y automático, restaurando la configuración destino al estado previo a la operación. No se almacenará ningún cambio parcial. El usuario recibirá un mensaje de error que describa la causa del fallo.
 
La aplicación de una plantilla no elimina configuraciones existentes que no estén cubiertas por la plantilla.
 
El sistema registra qué plantilla se aplicó, en qué configuración destino, con qué número de versión, por qué usuario y en qué fecha. El registro de auditoría incluirá el estado anterior (before) y el estado posterior (after) de los parámetros modificados.
 
El sistema debe dejar, para **cada intento de aplicación** (no solo los exitosos), un **registro estructurado y consultable** —independiente del evento de auditoría, que es narrativo before/after— con al menos: plantilla y su versión, especie, configuración destino, usuario, fecha, **resultado** (`SUCCESS` / `REJECTED` / `ROLLED_BACK`), motivo en caso de rechazo o rollback, parámetros afectados y referencia al evento de auditoría correspondiente. Este registro es una **dependencia dura de RF-108**: sin él, "aplicaciones exitosas recientes" y "errores/rollback recientes" (criterios de ordenamiento de RF-108) no son consultables de forma eficiente. La comparación de parámetros debe apoyarse en **identificadores estables** (códigos tipo `ambiental.temperatura`), no en las etiquetas visibles, para que un cambio de nombre no rompa la trazabilidad histórica.
 
Solo Administrador e Ingeniero de campo pueden aplicar plantillas.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-30 — Plantillas de configuración, RF-31 — Creación de plantilla de configuración, RF-15 — Gestión del catálogo de especies, RF-02 — Autenticación de usuarios, RF-04 — Gestión de permisos

**Actores:** Administrador del sistema, Ingeniero de campo

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| template_id | integer | ID de la plantilla seleccionada para aplicar (FK a plantillas). |
| target_config | jsonb | Identificador de la configuración destino (especie o finca activa). |
| user_confirm | boolean | Confirmación explícita del usuario para proceder con la aplicación. |

**Proceso:**

1. El usuario accede a Configuración → Plantillas y selecciona una plantilla del listado.
 
2. El usuario selecciona la configuración destino (especie o finca) sobre la que se aplicará.
 
3. El sistema verifica la compatibilidad de versión del esquema JSON del params_snapshot con la versión de esquema vigente. Si existe incompatibilidad, informa al usuario y cancela la operación.
 
4. El sistema valida la consistencia de los parámetros de la plantilla: verifica que los parámetros referenciados existan en el sistema y tengan formatos válidos.
 
5. Si la validación falla, el sistema muestra los parámetros con inconsistencias y cancela la operación sin aplicar cambios.
 
6. Si la validación es exitosa, el sistema muestra un resumen de los parámetros que serán reemplazados en la configuración destino, indicando los valores actuales (before) y los nuevos valores (after) de cada parámetro.
 
7. El sistema solicita confirmación explícita al usuario ('¿Confirma la aplicación?').
 
8. Tras la confirmación, el sistema reemplaza en su totalidad los parámetros correspondientes en la configuración destino con los de la plantilla. Si durante la aplicación ocurre un fallo, el sistema ejecuta un rollback completo y automático, restaurando la configuración destino al estado previo. El usuario recibe notificación del error con descripción de la causa.
 
9. El sistema registra en el historial de auditoría: plantilla aplicada, versión, configuración destino, usuario, fecha, y el estado anterior (before) y posterior (after) de cada parámetro modificado.

**Flujo alterno:**

Incompatibilidad de esquema (Versión Legacy):

El sistema detecta que el params_snapshot de la plantilla fue creado con una versión del esquema JSON que ya no es compatible con las reglas de validación actuales (ej. faltan campos obligatorios nuevos).

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Error de compatibilidad: La plantilla '[NOMBRE]' (v[X]) utiliza una estructura de datos antigua e incompatible con la versión actual del sistema. Debe actualizar la plantilla antes de aplicarla."

Fallo de consistencia (Referencias huérfanas):

La plantilla hace referencia a elementos que ya no existen o están inactivos en el sistema (ej. una patología que fue eliminada del catálogo maestro).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Inconsistencia detectada: La plantilla contiene parámetros que ya no son válidos en el sistema (Detalle: [LISTA_DE_PARAMETROS]). La operación ha sido cancelada."

Configuración destino no encontrada o inactiva:

El target_config (especie o finca) seleccionado para recibir la plantilla no existe o ha sido desactivado durante el proceso.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Destino no válido: La finca o especie seleccionada no existe o se encuentra inactiva. Verifique el estado del destino antes de aplicar la configuración."

Cancelación por el usuario (Abortar en resumen):

El usuario visualiza el resumen "Antes vs. Después" y decide no proceder haciendo clic en 'Cancelar'.

El sistema responde con:

Lógica de UI: Se cierra el resumen, se limpian los datos temporales y se regresa al listado de plantillas sin realizar ninguna petición al servidor. No se genera registro en auditoría.

Fallo crítico durante la aplicación (Rollback automático):

Ocurre un error de red, un timeout o una excepción de base de datos mientras se escriben los nuevos parámetros.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Fallo crítico de aplicación: Ocurrió un error inesperado durante la escritura de datos. Se ha ejecutado un Rollback automático y la configuración original ha sido restaurada íntegramente. Intente nuevamente."

Conflicto de modificación concurrente:

Otro administrador modificó la configuración destino mientras el usuario actual revisaba el resumen de cambios.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de concurrencia: Los parámetros de la finca/especie han cambiado recientemente. Por favor, recargue el resumen para visualizar los valores actuales antes de confirmar."

Acceso no autorizado:

Un usuario con un rol diferente a Administrador o Ingeniero de campo intenta disparar la aplicación de la plantilla mediante la API.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Privilegios insuficientes: No tiene autorización para sobrescribir configuraciones operativas activas."

**Salida:**

Configuración destino actualizada con los parámetros de la plantilla seleccionada.
 
 Resumen de los parámetros reemplazados visible para el usuario.
 
 Mensaje de confirmación de aplicación exitosa o de error con detalle de inconsistencias.
 
 Registro en el historial de auditoría.

**Postcondiciones:**

La configuración destino refleja los parámetros de la plantilla aplicada.
 
 Los parámetros de la configuración destino no cubiertos por la plantilla permanecen sin cambios.
 
 El historial de auditoría contiene el registro completo de la operación.
 
 Existe un registro estructurado del intento de aplicación —con resultado `SUCCESS`, `REJECTED` o `ROLLED_BACK`— consultable por plantilla, especie y destino, que alimenta la recomendación de RF-108.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:
 
El sistema muestra el resumen de los parámetros que serán reemplazados antes de solicitar confirmación, indicando valores actuales y nuevos.
 
El sistema no aplica la plantilla sin confirmación explícita del usuario.
 
Si la validación de consistencia falla, el sistema informa los parámetros con error y no aplica ningún cambio.
 
Si existe incompatibilidad de versión del esquema JSON, el sistema cancela la operación e informa al usuario con detalle de los parámetros incompatibles.
 
Ante un fallo durante la aplicación, el sistema ejecuta un rollback completo y automático; la configuración destino permanece en su estado previo sin cambios parciales.
 
Tras la aplicación exitosa, los parámetros de la configuración destino coinciden exactamente con los de la plantilla aplicada.
 
Los parámetros de la configuración destino no cubiertos por la plantilla no son modificados.
 
El historial de auditoría registra plantilla, versión, configuración destino, usuario, fecha y el estado anterior (before) y posterior (after) de cada parámetro modificado.
 
Cada intento de aplicación —exitoso, rechazado o revertido— deja un registro estructurado y consultable con su resultado (`SUCCESS`/`REJECTED`/`ROLLED_BACK`), motivo, plantilla, versión, especie, destino, usuario y fecha, utilizable por RF-108 para ordenar las recomendaciones.
 
Solo los usuarios con rol autorizado pueden aplicar plantillas.

**Requerimientos no funcionales:**

Fiabilidad
Si la validación falla, no se aplica ningún cambio parcial; la operación es atómica (todo o nada).
Ante fallos durante la aplicación, el sistema ejecuta un rollback completo y automático, garantizando que la configuración destino no quede en estado inconsistente. El rollback debe completarse antes de notificar al usuario el resultado de la operación.
 
Usabilidad
El resumen previo a la confirmación debe ser claro e indicar exactamente qué parámetros serán reemplazados, con sus valores actuales (before) y nuevos (after).
 
Seguridad
Solo los roles autorizados pueden aplicar plantillas sobre configuraciones activas.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---
