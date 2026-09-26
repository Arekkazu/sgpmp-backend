# Especificación de Requerimientos — Módulo 1

_Convertido de `Especificacion de requerimiento (1).xlsx`, hoja "Modulo 1". Original en `backups/1-analisis/`._

## RF-01 — Registro de usuarios

**Código Identificación:** RF-01 -- Versión -- 1.0

**Fuente:** Stakeholders del sistema

**Descripción:** El sistema debe permitir la creación de nuevas cuentas de usuario dentro de la plataforma de gestión pecuaria, con el fin de habilitar el acceso controlado a las funcionalidades del sistema según el rol asignado.

El proceso de registro se compone de dos etapas principales:

1. Creación de la cuenta de usuario, donde se registran los datos básicos de identificación y credenciales de acceso.

2. Activación de la cuenta, mediante la validación de un token de verificación enviado al correo electrónico del usuario, con el fin de confirmar la autenticidad de la dirección registrada.

Durante el proceso de registro, el sistema debe garantizar que la información del usuario sea única, válida y segura, aplicando políticas de validación de datos y almacenamiento seguro de credenciales.
Formulario de Registro: El usuario ingresa directamente sus datos básicos: Identificación, Tipo de identificación (CC, CE, Pasaporte), Nombres, Apellidos, Fecha de nacimiento (DD, MM, AAAA), Género (Masculino (M), Femenino (F), No Binario (X), Trans (T) ), Correo electrónico, Contraseña y Confirmar contraseña. Las credenciales deben almacenarse mediante un mecanismo de hash criptográfico seguro (Bcrypt).

Activación por Token: El sistema genera un estado "pendiente de confirmación" y envía un token único con validez de 24 horas al correo registrado para confirmar la identidad y activar la cuenta.

El rol del usuario será asignado automáticamente por el sistema con un valor por defecto (ej. PRODUCTOR), y no podrá ser definido por el usuario durante el proceso de registro. |  

**Justificación:** La funcionalidad de registro de usuarios es necesaria para permitir que los diferentes actores del sistema puedan acceder a la plataforma y gestionar sus unidades productivas dentro del sistema de monitoreo agropecuario.

Este mecanismo garantiza que cada usuario disponga de una identidad digital única, permitiendo controlar el acceso a las funcionalidades del sistema mediante roles y permisos definidos en el modelo de control de acceso.

Además, la verificación del correo electrónico y el almacenamiento seguro de contraseñas contribuyen a fortalecer la seguridad y trazabilidad de las acciones realizadas dentro del sistema, permitiendo mantener un registro confiable de las operaciones realizadas por cada usuario.

**Precondiciones:** El sistema debe encontrarse disponible y operativo.

Debe existir al menos un rol de usuario definido en el sistema.

El servicio de correo electrónico utilizado para el envío de tokens de activación debe estar configurado y disponible.

**Restricciones:** No se pueden registrar usuarios con correos electrónicos ya existentes en el sistema.

No se pueden registrar usuarios con números de identificación previamente registrados.

El token de activación tendrá una validez de 24 horas desde su generación.

El usuario no podrá asignarse roles durante el proceso de registro.
La asignación de roles es responsabilidad exclusiva del sistema o de un Administrador en procesos posteriores.

La contraseña debe cumplir con las siguientes políticas de seguridad definidas por el sistema:
- Mínimo 8 caracteres
- Al menos una letra mayúscula
- Al menos un número
- Al menos un carácter especial (@, #, $, etc.)

Las contraseñas deben almacenarse utilizando un algoritmo de hash criptográfico seguro (ej. bcrypt)

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** Ninguna

**Actores:** Usuario del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| tipo_identificacion | varchar(10) | Tipo de documento de identificación del usuario (CC, CE, Pasaporte). |
| numero_identificacion | varchar(20) | Número único de identificación del usuario dentro del sistema. |
| nombres | varchar(80) | Nombres del usuario que se registra en la plataforma. |
| apellidos | varchar(80) | Apellidos del usuario que se registra en la plataforma. |
| fecha_nacimiento | date | Fecha de nacimiento del usuario. |
| genero | char(1) | Género del usuario (M: Masculino, F: Femenino, X: No binario, T: Trans). |
| correo_electronico | varchar(100) | Dirección de correo electrónico utilizada para autenticación y verificación de cuenta. |
| contraseña | varchar(60) | Contraseña definida por el usuario para acceder al sistema. Debe almacenarse mediante hash criptográfico seguro (bcrypt). |
| telefono | varchar(20) | Número de contacto del usuario registrado en el sistema. |
| direccion | varchar(150) | Dirección de residencia del usuario registrada en el sistema. |

**Proceso:**

El usuario accede a la opción de registro.

El sistema presenta el formulario de registro.

El usuario ingresa los datos requeridos.

El sistema valida:
  - unicidad del correo electrónico
  - unicidad del número de identificación
  - cumplimiento de políticas de contraseña

Si el correo o ID ya existen, el sistema detendrá el proceso e informará: "El usuario ya se encuentra registrado".

Si las validaciones son correctas:
  - se crea la cuenta en estado PENDIENTE_ACTIVACION
  - el sistema asigna automáticamente el rol por defecto
  - se genera un token de activación

El sistema envía el correo de activación.
Si el servicio SMTP falla, el sistema debe reintentar el envío hasta 3 veces de forma asíncrona y notificar al usuario: "Registro exitoso, envío de correo en proceso".

El usuario accede al enlace o ingresa el token.
Si el usuario activa el token después de 24 horas, el sistema mostrará el error "Token expirado" y habilitará la opción "Re-enviar token de activación".

El sistema valida:
  - existencia del token
  - vigencia (no expirado)

Si es válido:
  - cambia estado a ACTIVO

Si no es válido:
  - rechaza la activación

El rol no forma parte de las entradas del usuario y es asignado automáticamente por el sistema.

En caso de error, el sistema responde con:
- HTTP 400: datos inválidos o incompletos
- HTTP 409: usuario ya registrado (correo o identificación)
- HTTP 500: error en servicio de correo
- Mensaje descriptivo del error |                                           

**Flujo alterno:**

Número de identificación ya registrado:

El sistema detecta que el numero_identificacion ingresado ya existe en la base de datos de usuarios.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "El número de identificación [ID_INGRESADO] ya se encuentra vinculado a una cuenta. Si ha olvidado sus credenciales, utilice la opción de recuperación de contraseña."

Correo electrónico duplicado:

El sistema detecta que el correo_electronico ya está asociado a otro usuario activo o pendiente de activación.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "La dirección de correo [CORREO_INGRESADO] ya está en uso. Por favor, utilice una dirección diferente o inicie sesión si ya tiene una cuenta."

Incumplimiento de política de contraseñas:

La contraseña ingresada no cumple con uno o más de los 4 criterios de seguridad (longitud, mayúscula, número, carácter especial).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Contraseña no válida. La clave debe tener al menos 8 caracteres e incluir obligatoriamente: una letra mayúscula, un número y un carácter especial (ej. @, #, $, %)."

Token de activación expirado:

El usuario intenta activar su cuenta mediante un token cuyo timestamp de creación es superior a las 24 horas permitidas.

El sistema responde con:

HTTP 410: Gone

Mensaje: "El token de activación ha expirado. Fue generado el [DD/MM/AAAA] a las [HH:mm:ss] y perdió validez el [DD/MM/AAAA] a las [HH:mm:ss]. Use la opción 'Re-enviar token' para recibir uno nuevo."

Token de activación inválido o inexistente:

El usuario ingresa un token que no coincide con ningún registro en la base de datos o que ya fue marcado como 'Utilizado'.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Token de activación inválido. El enlace es incorrecto o la cuenta ya ha sido activada anteriormente."

Fallo en la validación de seguridad (CAPTCHA):

El usuario no completa o falla la validación del reCAPTCHA integrado en el formulario.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Validación de seguridad fallida. Por favor, confirme que no es un robot e intente enviar el formulario nuevamente."

Fallo crítico en el servicio de correo (SMTP):

El sistema no logra conectar con el servidor de correos tras 3 intentos para enviar el token de activación.

El sistema responde con:

HTTP 503: Service Unavailable

Mensaje: "Registro exitoso, pero el servicio de notificaciones no está disponible. Su token se enviará automáticamente en los próximos 10 minutos. No es necesario registrarse de nuevo."

Usuario menor de edad:

El cálculo basado en la fecha_nacimiento indica que el usuario tiene menos de 18 años.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Registro denegado. Debe ser mayor de 18 años para registrarse como responsable de una unidad productiva en el sistema."

Error de formato en datos de entrada:

Se ingresan caracteres alfabéticos en el número de identificación o el formato de correo no es válido (falta @ o dominio).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de formato: El campo [NOMBRE_CAMPO] contiene caracteres no permitidos o un formato inválido. Por favor, verifique su información."

**Salida:**

Registro de usuario creado en la base de datos del sistema.

Envío de correo electrónico de verificación al usuario registrado.

Activación de la cuenta una vez validado el token de verificación.

Mensaje de confirmación indicando que el usuario puede iniciar sesión en la plataforma. |  

**Postcondiciones:**

El usuario queda habilitado para acceder al sistema mediante el proceso de autenticación.

El sistema registra el evento de creación y activación del usuario dentro del historial de auditoría.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema valida que el correo no esté duplicado.

El sistema valida que el número de identificación no exista.

El sistema valida que la contraseña cumpla con las políticas definidas y rechaza cualquier registro cuya contraseña no cumpla los 4 requisitos de complejidad.

El sistema genera un token único con validez de 24 horas.

El sistema envía correctamente el correo de activación.

El usuario no puede autenticarse sin activar la cuenta.

El sistema permite regenerar el token si este expira.

**Requerimientos no funcionales:**

Seguridad:
- Implementar CAPTCHA (Google reCAPTCHA v2 o v3)

Fiabilidad:
- El sistema debe garantizar consistencia en el registro de usuarios

Disponibilidad:
- El sistema debe permitir el registro en todo momento

Usabilidad:
- El formulario debe ser claro e intuitivo

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-02 — Autenticación de Usuarios

**Código Identificación:** RF-02 -- Versión -- 1.0

**Fuente:** Stakeholders del sistema

**Descripción:** El sistema debe permitir a los usuarios autenticarse en la plataforma mediante el uso de credenciales (correo electrónico y contraseña) previamente registradas.

El sistema validará la identidad del usuario verificando la correspondencia entre las credenciales ingresadas y la información almacenada, así como el estado de la cuenta.

Una vez autenticado, el sistema generará un token de acceso (JWT) que permitirá al usuario interactuar con las funcionalidades del sistema según su rol y permisos asignados.

El sistema garantizará que únicamente usuarios con cuentas activas y que no se encuentren bloqueadas temporalmente por intentos fallidos de autenticación ni deshabilitadas por políticas de seguridad del sistema.

**Justificación:** La autenticación de usuarios es necesaria para asegurar que el acceso al sistema sea realizado únicamente por usuarios autorizados. Este proceso permite validar la identidad digital de cada actor que interactúa con la plataforma, garantizando que las operaciones realizadas dentro del sistema puedan ser asociadas a un usuario específico.

Además, el mecanismo de autenticación contribuye a la protección de la información gestionada por el sistema, evitando accesos no autorizados y permitiendo mantener un control adecuado sobre las actividades realizadas dentro de la plataforma.

**Precondiciones:** El usuario debe estar previamente registrado en el sistema.

La cuenta del usuario debe encontrarse activa.

El sistema debe encontrarse disponible y operativo.

**Restricciones:** El sistema debe generar un token de autenticación JWT único por sesión.

El token tendrá una vigencia máxima de 8 horas desde su generación.

El sistema implementará un tiempo de inactividad máximo de 30 minutos, tras el cual la sesión será invalidada.

El sistema implementará un mecanismo de invalidación de tokens mediante revocación activa utilizando una lista negra (blacklist), permitiendo invalidar tokens en casos de cierre de sesión o inicio de sesión en otro dispositivo.

Adicionalmente, los tokens expirarán automáticamente al cumplir su tiempo de vigencia (8 horas).

Un usuario solo podrá tener una sesión activa simultáneamente.

Si el usuario inicia sesión en otro dispositivo, se invalidará la sesión anterior.

El sistema permitirá un máximo de 5 intentos fallidos consecutivos de autenticación.

Al superar el límite de intentos fallidos, la cuenta será bloqueada temporalmente durante 15 minutos.

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-01 Registro de usuarios, RF-07 Gestión de contraseñas

**Actores:** Usuario del sistema (Productor, Veterinario, Contador, Ingeniero de Campo, Administrador).

**Proceso:**

El usuario accede al formulario de inicio de sesión.

El sistema solicita las credenciales de acceso.

El usuario ingresa correo electrónico y contraseña.

El sistema valida la existencia del usuario.

El sistema verifica que la cuenta esté activa.

El sistema valida la contraseña ingresada.

Flujo exitoso:

El sistema genera un token JWT.

El sistema verifica si existe una sesión activa previa.

Si existe, invalida la sesión anterior.

El sistema registra la nueva sesión.

El sistema concede acceso según el rol.

El sistema registra el evento de autenticación.

**Flujo alterno:**

Credenciales inválidas (Usuario o contraseña incorrectos):

El sistema no encuentra coincidencia entre el correo electrónico y el hash de la contraseña almacenada.

El sistema incrementa el contador de intentos fallidos para el usuario y registra el evento en el log de auditoría.

El sistema responde con:

HTTP 401: Unauthorized

Mensaje: "Credenciales incorrectas. Intento [N] de 5. Tras el quinto intento fallido, su cuenta será bloqueada por 15 minutos por seguridad." (Donde N es el número actual de intentos).

Cuenta bloqueada por exceso de intentos fallidos:

El contador de intentos fallidos alcanza el límite de 5 registros consecutivos.

El sistema marca la cuenta como bloqueada y calcula la hora exacta de liberación (Hora actual + 15 minutos).

El sistema responde con:

HTTP 423: Locked

Mensaje: "Cuenta bloqueada por seguridad debido a múltiples intentos fallidos. Podrá intentar acceder nuevamente a las [HH:mm:ss] (dentro de 15 minutos exactos)."

Cuenta en estado 'Pendiente de Activación':

El usuario ingresa credenciales válidas, pero no ha completado el proceso de verificación por token (RF-01).

El sistema deniega la generación del token JWT.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado. Su cuenta no ha sido activada. Por favor, haga clic en el enlace enviado a su correo [CORREO_ELECTRONICO] o utilice la opción 'Re-enviar token de activación'."

Cuenta deshabilitada por políticas del sistema:

El estado del usuario en la base de datos es 'INACTIVO' o 'SUSPENDIDO' por acción de un administrador.

El sistema bloquea el flujo de autenticación inmediatamente.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso restringido. Su cuenta ha sido desactivada por políticas de seguridad o administración. Por favor, contacte al soporte técnico para más información."

Conflicto de sesión única (Cierre de sesión previa):

Un usuario con una sesión activa inicia sesión desde un nuevo dispositivo o navegador.

El sistema invalida el token JWT anterior incluyéndolo en la blacklist y procede con la nueva autenticación.

El sistema responde con:

HTTP 200: OK

Mensaje: "Sesión iniciada exitosamente. Se ha cerrado automáticamente la sesión activa en otros dispositivos por políticas de seguridad de sesión única."

Fallo en el formato de entrada de datos:

El campo de correo electrónico no cumple con la expresión regular de validación (falta @, dominio o caracteres inválidos).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error en la solicitud. El formato del correo electrónico ingresado no es válido. Por favor, verifíquelo e intente de nuevo."

Indisponibilidad del servicio de identidad:

El motor de base de datos o el servicio de validación de tokens no responde tras 3 intentos internos.

El sistema responde con:

HTTP 503: Service Unavailable

Mensaje: "El servicio de autenticación no está disponible en este momento. Estamos trabajando para restaurarlo. Por favor, intente iniciar sesión nuevamente después de las [HH:mm:ss]."

**Postcondiciones:**

El sistema mantiene una única sesión activa por usuario.

El usuario puede acceder a las funcionalidades según su rol.

La sesión permanecerá activa hasta que ocurra alguno de los siguientes eventos:
- el usuario cierre sesión manualmente
- el token expire (8 horas)
- se alcance el tiempo de inactividad (30 minutos)

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite acceso con credenciales válidas.

El sistema rechaza credenciales incorrectas.

El sistema impide acceso a cuentas inactivas.

El sistema bloquea la cuenta tras 5 intentos fallidos.

El sistema desbloquea la cuenta después de 15 minutos.

El sistema genera un token JWT válido por 8 horas.

El sistema invalida tokens expirados.

El sistema mantiene una única sesión activa por usuario.

El sistema invalida la sesión tras 30 minutos de inactividad.

El sistema registra todos los intentos de autenticación.

El sistema responde con códigos HTTP adecuados en cada escenario (200, 401, 423).

El sistema muestra mensajes claros y consistentes ante errores de autenticación.

El sistema invalida el token al iniciar sesión en otro dispositivo.

**Requerimientos no funcionales:**

Seguridad:

Uso de tokens JWT con expiración definida

Protección contra ataques de fuerza bruta

Uso obligatorio de HTTPS

Disponibilidad:

El servicio de autenticación debe estar disponible el 99% del tiempo

Usabilidad:

Formulario claro con mensajes de error inmediatos

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-03 — Gestión de roles

**Código Identificación:** RF-03

**Fuente:** Stakeholders del sistema

**Descripción:** El sistema debe permitir la gestión de roles mediante la creación, modificación, consulta y eliminación de roles dentro de la plataforma.

Cada rol representa un conjunto de permisos que determinan el acceso a las funcionalidades del sistema, siguiendo el modelo de control de acceso basado en roles (RBAC - Role-Based Access Control).

El sistema permitirá asociar uno o más permisos a cada rol, definiendo así las capacidades funcionales disponibles para los usuarios que posean dicho rol.

Se limita a la definición de la estructura de roles y no incluye la asignación de estos a usuarios específicos.

El sistema deberá garantizar que los cambios en los permisos asociados a un rol se reflejen dinámicamente en los usuarios que posean dicho rol, incluyendo aquellos con sesiones activas.

Asimismo, los permisos asociados a un rol solo serán aplicables a usuarios que se encuentren en estado activo dentro del sistema, según lo definido en el requerimiento RF-06.

El sistema implementará validación de permisos en tiempo de ejecución, verificando en cada solicitud que el usuario autenticado posee los permisos necesarios para acceder a los recursos solicitados.

El modelo de roles definido no contempla jerarquías ni herencia entre roles, operando bajo un esquema plano de asignación de permisos.

**Restricciones:** El nombre del rol debe ser único y descriptivo dentro del sistema.

Todo rol debe tener al menos un permiso asociado.

Se prohíbe la eliminación de roles que tengan usuarios vinculados para preservar la integridad del control de acceso.

El rol Administrador es un rol protegido e inmutable, por ende, no puede ser eliminado.

La asociación entre roles y permisos debe ser obligatoria al momento de crear o modificar un rol.

Los permisos asociados a un rol solo serán efectivos para usuarios en estado activo.

El sistema deberá validar en cada solicitud que el usuario posee los permisos requeridos para acceder al recurso solicitado.

Los cambios en roles y permisos deben reflejarse inmediatamente en las sesiones activas del sistema.

**Prioridad:** [ X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-01 Registro de usuarios, RF-04 Gestión de permisos

**Actores:** Administrador del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| nombre_rol | varchar(100) | Nombre único que identifica el rol dentro del sistema (por ejemplo: Administrador, Productor, Veterinario, Ingeniero de Campo). |
| descripcion_rol | varchar(255) | Descripción funcional del rol y de las responsabilidades asociadas dentro del sistema. |
| lista_permisos | jsonb | Conjunto de identificadores de permisos o submódulos seleccionados desde el catálogo del sistema que serán asociados al rol. |

**Proceso:**

El administrador accede al módulo de gestión de roles.

El sistema muestra la lista de roles existentes.

El administrador puede realizar las siguientes operaciones:

Crear rol

El administrador ingresa nombre y descripción del rol.

Selecciona uno o más permisos desde el catálogo.

El sistema valida:

unicidad del nombre

existencia de al menos un permiso

El sistema registra el rol con sus permisos asociados.

Modificar rol

El administrador selecciona un rol existente.

Modifica nombre, descripción o permisos.

El sistema valida las restricciones.

El sistema actualiza la información del rol.

Eliminar rol

El administrador selecciona un rol.

El sistema valida:

que no esté asignado a usuarios

que no sea el rol Administrador

El sistema elimina el rol.

Consultar rol

El administrador visualiza la información del rol y sus permisos asociados.

El sistema propagará los cambios realizados en roles y permisos a los usuarios que posean dicho rol.

Si existen sesiones activas, el sistema actualizará dinámicamente los permisos en las sesiones activas sin requerir cierre de sesión.

En cada solicitud al sistema, se validará que el usuario autenticado tenga los permisos necesarios para acceder al recurso solicitado.

**Flujo alterno:**

Nombre de rol duplicado:

El administrador intenta crear o renombrar un rol con un nombre que ya existe en el catálogo.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de identidad: El nombre de rol '[NOMBRE_ROL]' ya se encuentra registrado. Por favor, utilice una denominación única y descriptiva."

Rol sin permisos asociados:

Se intenta guardar un rol nuevo o modificado con una lista_permisos vacía o nula.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Operación rechazada: Todo rol debe poseer al menos un permiso asociado para ser funcional. Seleccione al menos una capacidad del catálogo."

Intento de eliminación de rol con usuarios vinculados:

El administrador solicita eliminar un rol que actualmente está asignado a uno o más usuarios en la base de datos.

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "No se puede eliminar el rol: Existen [N] usuarios vinculados a '[NOMBRE_ROL]'. Para proceder, debe reasignar a estos usuarios a un rol diferente."

Intento de modificación o eliminación de rol protegido:

Se intenta eliminar o alterar el nombre del rol 'Administrador' (ID reservado).

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acción denegada: El rol 'Administrador' es un objeto protegido por el sistema. No se permite su eliminación ni el cambio de su identificador base."

Fallo en la sincronización de sesiones activas:

Tras una modificación exitosa en la base de datos, el servicio de mensajería (Websockets/Redis) falla al intentar actualizar los permisos en las sesiones de usuarios conectados.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Cambio registrado, pero falló la propagación en tiempo real. Los usuarios con sesión activa verán los cambios reflejados tras su próximo inicio de sesión o actualización manual (F5)."

Acceso no autorizado a la gestión de roles:

Un usuario con un token válido pero sin el permiso específico de 'GESTION_ROLES' intenta acceder al endpoint.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Privilegios insuficientes: Su rol actual no tiene autorización para realizar cambios en la matriz de permisos del sistema."

Error en la integridad de la lista de permisos:

Se envían identificadores de permisos en el JSON que no existen en el catálogo maestro de funcionalidades.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Datos inconsistentes: Uno o más permisos enviados ([ID_PERMISO]) no son válidos o han sido depreciados del sistema."

**Salida:**

Creación de un nuevo rol dentro del sistema.

Actualización de la información de un rol existente.

Eliminación de roles que no se encuentren asociados a usuarios activos.

Visualización de la lista de roles disponibles en el sistema.

**Postcondiciones:**

Los roles definidos pueden ser utilizados posteriormente para asignar permisos y controlar el acceso a las funcionalidades del sistema.

El sistema registra las acciones administrativas relacionadas con la gestión de roles en el historial de auditoría. Los usuarios solo podrán utilizar los roles asignados dentro del periodo de vigencia establecido.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite crear roles con nombre único.

El sistema exige al menos un permiso por rol.

El sistema permite modificar roles existentes.

El sistema permite consultar roles y sus permisos.

El sistema impide eliminar roles asignados a usuarios.

El sistema impide eliminar el rol Administrador.

El sistema asocia correctamente permisos a cada rol.

El sistema registra todas las operaciones en auditoría.

El sistema actualiza los permisos de usuarios con sesiones activas cuando se modifican los roles.

El sistema aplica los permisos de un rol únicamente a usuarios en estado activo.

El sistema valida en cada solicitud que el usuario tenga permisos para acceder al recurso solicitado.

El sistema no implementa jerarquías entre roles y opera bajo un modelo plano de permisos.

**Requerimientos no funcionales:**

Seguridad:

Acceso restringido únicamente a administradores

Validación de integridad en asignación de permisos

Usabilidad:

Interfaz clara para selección de permisos (checkbox/listado)

Disponibilidad:

El módulo debe estar disponible en todo momento para gestión administrativa

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-04 — Gestión de permisos

**Código Identificación:** RF-04 -- Versión -- 1.0

**Fuente:** Stakeholders del sistema

**Descripción:** El sistema debe permitir la gestión de permisos asociados a los roles, definiendo el acceso a las funcionalidades mediante la asignación de acciones sobre recursos del sistema, siguiendo el modelo RBAC (Role-Based Access Control).

Un permiso se define como la combinación de:

Rol + Recurso + Acción

Donde:

Recurso: módulo o entidad del sistema (Usuarios, Animales, Inventario, Producción, etc.)

Acción: operación permitida sobre el recurso

Las acciones disponibles serán:

Crear (C)

Leer (R)

Actualizar (U)

Eliminar (D)

Ejecutar (E) → para procesos especiales

Los procesos especiales corresponden a funcionalidades críticas del sistema:

Cierre de ciclo productivo

Ajustes de inventario

Generación de reportes

Exportación de datos

Estos procesos deberán estar definidos en un catálogo de funcionalidades del sistema.

Los permisos asignados a un rol serán utilizados por el sistema para validar el acceso a los recursos durante la ejecución del sistema.
La validación de permisos se realizará en cada solicitud HTTP al backend, verificando que el usuario autenticado posea, a través de su rol, autorización para ejecutar la acción solicitada sobre el recurso correspondiente.

Los cambios en permisos asociados a un rol se aplicarán dinámicamente a los usuarios que posean dicho rol, incluyendo aquellos con sesiones activas, sin requerir cierre de sesión.

**Justificación:** La gestión de permisos es necesaria para garantizar que los usuarios del sistema solo puedan acceder a las funcionalidades que corresponden a sus responsabilidades dentro de la plataforma.

Este mecanismo permite establecer un control de acceso estructurado, facilitando la administración de privilegios dentro del sistema y evitando accesos no autorizados a información o funcionalidades sensibles.

Además, el uso de permisos asociados a roles permite adaptar el sistema a diferentes perfiles de usuario, manteniendo una estructura de acceso flexible y segura.

**Precondiciones:** Deben existir roles previamente definidos (RF-03).

Debe existir un catálogo de recursos (módulos o entidades del sistema).

El usuario debe tener privilegios administrativos.

El sistema debe estar operativo.

**Restricciones:** Los permisos solo pueden asignarse a roles existentes.

Un permiso no puede repetirse bajo la misma combinación:

(rol + recurso + acción)

Todo rol debe tener al menos un permiso asociado, conforme a lo establecido en el requerimiento RF-03 Gestión de roles.

Los permisos asociados a un rol solo serán efectivos para usuarios que se encuentren en estado activo dentro del sistema.

La validación de permisos se realizará en cada solicitud HTTP al backend, verificando que el rol del usuario tenga autorización para ejecutar la acción solicitada sobre el recurso correspondiente.

Los cambios realizados en permisos deben reflejarse inmediatamente en las sesiones activas del sistema, aplicándose en la siguiente solicitud realizada por el usuario.

**Prioridad:** [X ] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-03 Gestión de roles, RF-02 Autenticacion de usuarios, RF-01 Registro de usuarios

**Actores:** Administrador del Sistema.

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_rol | integer | Identificador del rol al cual se le asignarán permisos. |
| id_recurso | integer | Identificador del módulo o entidad del sistema. |
| accion | varchar(10) | Tipo de acción permitida: C, R, U, D, E. |
| estado_permiso | boolean | Indica si el permiso se asigna (true) o se retira (false). |

**Proceso:**

El administrador accede al módulo de gestión de permisos.

El sistema muestra los roles disponibles.

El administrador selecciona un rol.

El sistema muestra el catálogo de recursos y acciones disponibles.

El administrador asigna o retira permisos (recurso + acción).

Validaciones:
El sistema valida:

existencia del rol

existencia del recurso

validez de la acción

no duplicidad del permiso (rol + recurso + acción)

Posteriormente:

El sistema guarda la configuración de permisos.

El sistema registra la operación en auditoría.

Durante la ejecución del sistema:

En cada solicitud HTTP realizada al backend, el sistema valida que el usuario autenticado posea el permiso necesario para ejecutar la acción solicitada sobre el recurso correspondiente.


**Flujo alterno:**

Rol no encontrado:

El administrador intenta asignar un permiso a un id_rol que no existe en la base de datos.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error: El rol solicitado con ID [ID_ROL] no existe. La operación de asignación ha sido cancelada."

Recurso no válido o inexistente:

El identificador del módulo o entidad (id_recurso) no corresponde a ninguno de los elementos definidos en el catálogo del sistema.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de catálogo: El recurso [ID_RECURSO] no es un módulo válido. Verifique el catálogo de funcionalidades disponibles."

Permiso duplicado (Redundancia):

El administrador intenta crear una combinación de (Rol + Recurso + Acción) que ya se encuentra activa en el sistema.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Conflicto de redundancia: El rol [NOMBRE_ROL] ya cuenta con el permiso de [ACCION] sobre el recurso [NOMBRE_RECURSO]. No se admiten registros duplicados."

Acción no permitida para el recurso:

Se intenta asignar una acción de tipo 'E' (Ejecutar) a un recurso que no es un proceso especial o una acción CRUD a un recurso que no las soporta.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Acción inválida: El recurso [NOMBRE_RECURSO] no admite la operación '[ACCION]'. Solo se permiten acciones de ejecución en procesos especiales del catálogo."

Violación de integridad (Rol huérfano):

El administrador intenta retirar un permiso (estado_permiso: false), pero este es el único permiso que le queda al rol (incumpliendo el RF-03).

El sistema responde con:

HTTP 422: Unprocessable Entity

Mensaje: "Error de integridad: No se puede retirar el permiso. Todo rol debe mantener al menos una capacidad activa. El rol [NOMBRE_ROL] no puede quedar sin permisos asociados."

Usuario sin privilegios administrativos:

Un usuario con un token válido intenta acceder al servicio de gestión de permisos sin poseer el rol de Administrador.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: Se requieren privilegios de Administrador para modificar la matriz de seguridad. Este intento ha sido registrado en el log de auditoría."

Fallo en la sincronización en tiempo real:

El sistema actualiza la base de datos pero falla al intentar invalidar el caché de permisos o enviar la notificación vía WebSocket a las sesiones activas.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Actualización parcial: Los permisos se guardaron en la base de datos, pero falló la propagación a las sesiones activas. Los cambios se aplicarán automáticamente en el próximo inicio de sesión de los usuarios."

Fallo de persistencia transaccional:

Ocurre un error inesperado en el motor de base de datos durante la escritura del permiso o del registro de auditoría.

El sistema realiza un rollback de la operación y responde con:

HTTP 500: Internal Server Error

Mensaje: "Fallo crítico: No se pudieron guardar los cambios debido a un error de persistencia. La integridad del sistema no ha sido afectada. Intente de nuevo en unos minutos."

**Salida:**

Actualización de los permisos asociados a un rol del sistema.

Visualización de los permisos asignados a cada rol.

Registro de las modificaciones realizadas en el historial de auditoría.

**Postcondiciones:**

Los permisos quedan asociados al rol correspondiente.

Los usuarios heredan los permisos a través de sus roles.

Los cambios se aplican en la validación de acceso del sistema (backend).

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite asignar permisos a un rol existente.

El sistema permite retirar permisos de un rol.

El sistema impide duplicar permisos con la misma combinación (rol + recurso + acción).

El sistema valida los permisos del usuario en cada solicitud HTTP al backend.

El sistema impide acceder a un recurso si el rol no tiene permiso de lectura.

El sistema bloquea la creación si el rol no tiene permiso de creación.

El sistema bloquea la actualización si el rol no tiene permiso de actualización.

El sistema bloquea la eliminación si el rol no tiene permiso de eliminación.

El sistema permite ejecutar procesos especiales solo si el rol tiene permiso de ejecución.

El sistema aplica los cambios de permisos a usuarios con sesiones activas sin requerir cierre de sesión.

El sistema registra todas las modificaciones en auditoría.

**Requerimientos no funcionales:**

Seguridad:

Validación de permisos en cada solicitud al backend

Uso de HTTPS para transmisión de datos

Rendimiento:

Validación de permisos en menos de 200 ms

Disponibilidad:

El sistema de control de acceso debe estar disponible permanentemente

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-05 — Edición de datos de usuario

**Código Identificación:** RF-05 -- Versión -- 1.0

**Fuente:** Stakeholders del sistema

**Descripción:** El sistema debe permitir la actualización de la información de los usuarios registrados en la plataforma.

La edición de datos podrá ser realizada por:

El usuario autenticado: quien podrá modificar únicamente su propia información personal.

El administrador del sistema: quien podrá modificar la información de cualquier usuario registrado, incluyendo datos críticos del sistema.

Los datos editables se clasifican en:

Datos personales

nombres

apellidos

Datos de contacto

correo_electronico

telefono

Datos críticos (solo administrador)

estado_usuario (Activo, Inactivo, Pendiente)

rol_usuario

El sistema debe validar la integridad de los datos ingresados, verificar los permisos del actor que realiza la modificación y registrar todas las operaciones en el sistema de auditoría.

Cuando se modifique el correo electrónico de un usuario, el sistema deberá iniciar un proceso de verificación mediante el envío de un nuevo token de validación al correo actualizado.

**Justificación:** La edición de datos de usuario es necesaria para permitir la actualización de la información asociada a las cuentas registradas en el sistema. Dado que los datos personales o de contacto pueden cambiar con el tiempo, esta funcionalidad garantiza que la información almacenada en el sistema se mantenga actualizada y consistente.

Además, la posibilidad de actualizar estos datos contribuye a mejorar la comunicación entre los usuarios y el sistema, así como la correcta identificación de los actores que interactúan con la plataforma.

**Precondiciones:** El usuario debe estar registrado (RF-01).

El usuario debe estar autenticado (RF-02).

Para edición de terceros: 
- debe existir por lo menos un usuario registrado en el sistema
- el actor que va a ejecutar la operacion debe tener el rol administrador.

**Restricciones:** Un usuario solo puede modificar su propia información personal y de contacto.

El correo electrónico debe ser único dentro del sistema.

Los campos estado_usuario y rol_usuario solo pueden ser modificados por administradores.

El identificador del usuario (id_usuario) no puede ser modificado.

Los nombres y apellidos deben permitir letras del alfabeto (A–Z, a–z), espacios y caracteres propios del idioma español, tales como vocales acentuadas (á, é, í, ó, ú) y la letra ñ. No se permiten números ni caracteres especiales (simbolos) distintos a los mencionados.

Un administrador no puede modificar su propio rol ni cambiar su estado dentro del sistema para evitar pérdida de privilegios administrativos.

Cuando se modifique el correo electrónico, el sistema deberá enviar un nuevo token de verificación al correo actualizado y cambiar temporalmente el estado del usuario a Pendiente hasta que la verificación sea completada.

El sistema debe aplicar control de concurrencia optimista para evitar conflictos de edición simultánea.

Si un registro fue modificado por otro actor durante el proceso de edición, el sistema debe rechazar la actualización y solicitar recargar la información.

**Prioridad:** [ ] Alta/Must [ X] Media/Should [ ] Baja/Could

**Dependencia:** RF-01 Registro de usuarios, RF-02 Autenticación de usuarios, RF-03 Gestión de roles

**Actores:** Usuario del sistema / Administrador

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_usuario | integer | Identificador del usuario a modificar. |
| nombres | varchar(80) | Nombres del usuario (solo letras, espacios y caracteres especiales válidos, obligatorio). |
| apellidos | varchar(80) | Apellidos del usuario (solo letras, espacios y caracteres especiales válidos, obligatorio). |
| correo_electronico | varchar(100) | Correo válido, formato email, único. |
| telefono | varchar(20) | Número telefónico, opcional, formato numérico. |
| estado_usuario | varchar(20) | Estado del usuario: Activo, Inactivo, Pendiente (solo admin). |
| rol_usuario | integer | Identificador del rol asignado (solo admin). |

**Proceso:**

1. El usuario o administrador accede al módulo de perfil o gestión de usuarios.

2. El sistema identifica el tipo de actor autenticado.

3. El sistema carga la información del usuario a editar:

- Si el actor es usuario normal (sin rol Administrastivo), el sistema carga únicamente su propio perfil.
- Si el actor es administrador, el sistema carga el perfil del usuario seleccionado previamente para modificar.

4. El sistema muestra los campos editables.

Usuario (sin rol Administrador) puede editar:

- nombres
- apellidos
- correo_electronico
- telefono

Administrador puede editar:

- nombres
- apellidos
- correo_electronico
- telefono
- estado_usuario
- rol_usuario

5. El actor modifica los campos permitidos.

6. El actor confirma la actualización de los datos.

7. El sistema ejecuta las validaciones:

- formato de nombres y apellidos
- formato del correo electrónico
- formato del teléfono
- unicidad del correo electrónico
- permisos del actor para modificar el usuario
- validez del rol asignado (solo administrador)


**Flujo alterno:**

Correo electrónico ya registrado:

El sistema detecta que el nuevo correo_electronico ingresado ya pertenece a otro usuario en la base de datos.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Actualización denegada. La dirección [CORREO_INGRESADO] ya se encuentra vinculada a otra cuenta. El correo debe ser único."

Conflicto de concurrencia (Control Optimista):

El sistema detecta que los datos del usuario fueron modificados por otro actor (ej. un administrador) mientras el usuario actual tenía el formulario abierto.

El sistema responde con:

HTTP 412: Precondition Failed

Mensaje: "Conflicto de edición. Los datos del usuario han sido actualizados recientemente por otro proceso. Por favor, recargue la página para obtener la información más reciente antes de editar."

Intento de escalada de privilegios (Seguridad):

Un usuario sin rol de Administrador intenta enviar en la petición valores para rol_usuario o estado_usuario.

El sistema ignora esos campos o rechaza la petición.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso restringido. No tiene permisos para modificar campos críticos (Rol/Estado). Esta acción ha sido reportada al sistema de auditoría."

Restricción de autogestión administrativa:

Un Administrador intenta cambiarse a sí mismo el estado_usuario a 'Inactivo' o degradar su rol_usuario a uno no administrativo.

El sistema bloquea la acción para evitar que el sistema quede sin administradores activos.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Operación no permitida. Por seguridad, un administrador no puede desactivar su propia cuenta ni remover sus privilegios administrativos."

Formato de nombres o apellidos inválido:

El sistema detecta números, símbolos o caracteres especiales no permitidos en los campos de texto.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de formato. Los nombres y apellidos solo deben contener letras, espacios y caracteres del idioma español (á, ñ, etc.). Verifique el campo [NOMBRE_CAMPO]."

Error en el envío de verificación por cambio de correo:

El sistema actualiza el correo pero el servicio SMTP falla al enviar el token de validación obligatorio.

El sistema responde con:

HTTP 503: Service Unavailable

Mensaje: "Correo actualizado y cuenta puesta en espera. Sin embargo, no se pudo enviar el mensaje de verificación. Por favor, use la opción 'Re-enviar token' desde la pantalla de inicio."

Identificador de usuario no encontrado:

Se intenta editar un id_usuario que no existe (posible manipulación de URL o petición API).

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Usuario no encontrado. El registro que intenta modificar no existe en el sistema."

Formato de teléfono inválido:

El campo telefono contiene caracteres alfabéticos o no cumple con la longitud mínima/máxima.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Número telefónico inválido. Asegúrese de ingresar solo dígitos numéricos (mínimo 7, máximo 15)."

**Salida:**

Actualización exitosa de los datos del usuario.

Visualización de la información actualizada en el perfil del usuario.

Registro de la modificación realizada dentro del historial de auditoría del sistema.

**Postcondiciones:**

La información del usuario queda actualizada en la base de datos si todas las validaciones se cumplen.

Si el correo electrónico fue modificado, el sistema:

- cambia el estado del usuario a Pendiente
- genera un token de verificación de correo
- envía el token al nuevo correo electrónico registrado
- invalida la sesión activa del usuario modificado

El sistema registra la modificación realizada en el historial de auditoría, incluyendo:

- identificador del usuario modificado
- actor que realizó la modificación
- fecha y hora de la operación
- campos modificados

Si el estado_usuario fue modificado por un administrador:

- el nuevo estado se aplica en la siguiente solicitud al sistema
- si el estado cambia a Inactivo, las sesiones activas del usuario quedan invalidadas.

Si el rol_usuario fue modificado por un administrador:

- el nuevo rol queda asociado al usuario en la base de datos
- los nuevos permisos se aplican en la siguiente solicitud al sistema.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite al usuario editar su propia información personal y de contacto.

El sistema impide que un usuario edite información de otros usuarios.

El sistema permite al administrador editar la información de cualquier usuario.

El sistema valida el formato de todos los campos antes de guardar cambios.

El sistema impide registrar correos duplicados.

El sistema restringe la modificación de datos críticos (estado_usuario y rol_usuario) solo a administradores.

El sistema envía un nuevo token de verificación cuando se modifica el correo electrónico.

El sistema cambia el estado del usuario a Pendiente después de modificar el correo.

El sistema registra la operación en el sistema de auditoría.

El sistema actualiza la información correctamente.

El sistema refleja los cambios de la actualizacion de datos en un tiempo menor o igual a 2 segundos.

En caso de que la operación falle por errores de validación o conflictos de concurrencia, no se realizan modificaciones en la base de datos.

**Requerimientos no funcionales:**

Seguridad:

Validación de permisos en backend

Protección contra modificación no autorizada

Usabilidad:

Validaciones en tiempo real en el formulario

Rendimiento:

Actualización en menos de 2 segundos

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-06 — Gestión de cuentas de usuario

**Código Identificación:** RF-06 -- Versión -- 1.0

**Fuente:** Stakeholders del sistema

**Justificación:** La gestión de cuentas permite controlar el acceso de los usuarios al sistema mediante estados claramente definidos, asegurando que solo los usuarios autorizados puedan autenticarse y manteniendo la trazabilidad de las acciones realizadas.

**Precondiciones:** Deben existir usuarios registrados (RF-01)

El actor debe ser administrador

El sistema debe estar operativo

**Restricciones:** No se permite eliminación física de usuarios.

La eliminación es lógica (estado = ELIMINADO).

Solo administradores pueden gestionar cuentas.

No se puede asignar un estado diferente a los definidos.

**Prioridad:** [X ] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-01 Registro de usuarios, RF-02 Autenticación de usuarios, RF-03 Gestión de roles

**Actores:** Administrador del Sistema.

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_usuario | integer | Identificador único del usuario cuya cuenta será gestionada por el administrador del sistema. |
| accion_cuenta | enum | Acción administrativa que el administrador desea aplicar sobre la cuenta del usuario. |
| motivo_accion | varchar(255) | Descripción opcional del motivo por el cual se realiza la acción administrativa sobre la cuenta del usuario.  |

**Proceso:**

El administrador accede al módulo de gestión de usuarios

El sistema muestra la lista de usuarios

El administrador selecciona un usuario

El administrador selecciona una acción

Validaciones:

El sistema valida:

existencia del usuario

validez de la acción

transición permitida

El sistema actualiza el estado de la cuenta

Integración con autenticación

Solo usuarios en estado ACTIVO pueden autenticarse.

Si el estado cambia a:

INACTIVO

BLOQUEADO

ELIMINADO

entonces:

Si el estado del usuario cambia a INACTIVO, BLOQUEADO o ELIMINADO, el sistema invalidará todos los tokens JWT activos del usuario.

La invalidación de sesiones debe aplicarse de forma inmediata y en un tiempo máximo de 5 segundos.

Cuando una sesión es invalidada por cambio de estado, el sistema debe mostrar al usuario el siguiente mensaje en la interfaz:

"Su sesión ha sido finalizada debido a un cambio en el estado de su cuenta."

**Flujo alterno:**

Transición de estado no permitida:

El administrador intenta realizar una transición que rompe las reglas del modelo de estados (ej. intentar pasar de ELIMINADO a ACTIVO).

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Transición de estado inválida. Una cuenta en estado 'ELIMINADO' tiene carácter irreversible para preservar la integridad histórica. No se permite el cambio a [ESTADO_DESTINO]."

Intento de eliminar o desactivar al último administrador:

El sistema detecta que la acción se aplica sobre el único usuario con rol 'Administrador' que tiene estado 'ACTIVO'.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Operación denegada por seguridad. El usuario [ID_USUARIO] es el único administrador activo del sistema. Debe designar y activar un nuevo administrador antes de proceder con la desactivación o eliminación."

Usuario no encontrado:

El id_usuario proporcionado en la solicitud no coincide con ningún registro en la base de datos.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error de referencia. El usuario con ID [ID_USUARIO] no existe en los registros actuales del sistema."

Acceso no autorizado (Privilegios insuficientes):

Un usuario sin el permiso de 'GESTIÓN_CUENTAS' intenta consumir el endpoint de cambio de estado.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado. Se requieren privilegios administrativos para gestionar estados de cuenta. Este intento de acceso ha sido registrado en el log de auditoría."

Acción inconsistente con el estado actual:

Se intenta aplicar la acción 'Desbloquear' sobre un usuario que ya se encuentra en estado 'ACTIVO' o 'INACTIVO'.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Inconsistencia de estado. La acción 'Desbloquear' solo es aplicable a cuentas en estado 'BLOQUEADO'. El usuario actual ya se encuentra [ESTADO_ACTUAL]."

Fallo en la invalidación de sesiones (JWT Blacklist):

El estado se actualiza en la base de datos, pero el servicio de caché (Redis/Blacklist) falla al intentar invalidar los tokens activos del usuario.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Cambio de estado persistido, pero falló la invalidación inmediata de sesiones. Se recomienda contactar a soporte técnico para asegurar el cierre forzado de las conexiones activas del usuario [ID_USUARIO]."

Ausencia de motivo en acción crítica:

El administrador intenta 'Eliminar' o 'Desactivar' una cuenta pero deja el campo motivo_accion vacío.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Campo obligatorio faltante. Para las acciones de Desactivación o Eliminación, es obligatorio registrar una justificación en el campo 'motivo_accion' para fines de auditoría."

**Salida:**

Actualización del estado de la cuenta.

Confirmación de la operación.

Registro en el historial de auditoría (RF-08).

**Postcondiciones:**

El estado del usuario queda actualizado.

Solo usuarios en estado ACTIVO pueden acceder al sistema.

Las sesiones se invalidan según corresponda.

Se registra la acción en auditoría.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite activar cuentas de usuario.

El sistema permite desactivar cuentas de usuario.

El sistema permite bloquear cuentas de usuario.

El sistema permite eliminar lógicamente cuentas de usuario.

El sistema impide la autenticación de usuarios en estado:

INACTIVO

BLOQUEADO

PENDIENTE

ELIMINADO

El sistema invalida sesiones activas al cambiar el estado a INACTIVO, BLOQUEADO o ELIMINADO.

El sistema muestra al usuario un mensaje sobre la invalidacion de la sesion por cambio de estado.

El sistema impide transiciones de estado no definidas.

El sistema registra todas las acciones en el historial de auditoría.

**Requerimientos no funcionales:**

Seguridad:

Invalidación inmediata de sesiones
Control de acceso en backend

Integridad:

Eliminación lógica obligatoria

Rendimiento:

Actualización de estado < 1 segundo

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-07 — Cambio de contraseña | Título Requerimiento

**Código Identificación:** RF-07 -- Versión -- 1.0 -- Código Identificación

**Fuente:** Stakeholders del sistema | Fuente

**Descripción:** El sistema debe permitir al usuario autenticado cambiar su contraseña actual mediante la validación de sus credenciales y el cumplimiento de las políticas de seguridad definidas, garantizando la protección de su cuenta y la integridad del acceso al sistema. | Descripción

**Justificación:** El cambio de contraseña permite a los usuarios mantener la seguridad de sus credenciales, especialmente en casos de sospecha de compromiso, cumplimiento de políticas de seguridad o actualización periódica. Esta funcionalidad garantiza que solo el usuario legítimo pueda modificar su contraseña mediante la verificación de su identidad. | Justificación

**Precondiciones:** El usuario debe estar registrado en el sistema

El usuario debe haber iniciado sesión (RF-02)

La cuenta del usuario debe estar en estado ACTIVO

El sistema debe estar operativo | Precondiciones

**Restricciones:** La contraseña no debe almacenarse en texto plano

Se debe utilizar hashing seguro (BCrypt, Argon2 o PBKDF2)

No se permite reutilizar la contraseña actual

Se debe validar la identidad mediante contraseña actual

El cambio solo puede ser realizado por el usuario autenticado (no por terceros)

Se bloquea temporalmente la operación tras 5 intentos fallidos consecutivos. | Restricciones

**Prioridad:** [X ] Alta/Must [ ] Media/Should [ ] Baja/Could | Prioridad

**Dependencia:** RF-02 Autenticación de usuarios | Dependencia

**Actores:** Usuario autenticado | Actores

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_usuario | integer | Identificador del usuario que solicita el cambio de contraseña dentro del sistema. |
| contraseña_actual | varchar(60) | Contraseña actual del usuario utilizada para verificar su identidad antes de permitir el cambio de credenciales. |
| nueva_contraseña | varchar(60) | Nueva contraseña definida por el usuario que reemplazará la contraseña actual en el sistema. |
| confirmar_nueva_contraseña | varchar(60) | Campo utilizado para confirmar que la nueva contraseña ingresada coincide con la contraseña definida por el usuario. |

**Proceso:**

El usuario accede a la opción “Cambiar contraseña” dentro de su perfil

El sistema solicita la contraseña actual y la nueva contraseña

El usuario ingresa los datos requeridos

Validaciones:

El sistema valida:

Que la contraseña actual sea correcta

Que la nueva contraseña cumpla las políticas

Que la confirmación coincida

Si las validaciones son exitosas:

Se genera el hash de la nueva contraseña

Se actualiza en la base de datos

El sistema ejecuta:

Invalidación de todas las sesiones activas

Revocación de tokens de autenticación

El sistema registra la operación en el historial de auditoría | Proceso

**Flujo alterno:**

Contraseña actual incorrecta:

El sistema detecta que el hash de la contraseña_actual no coincide con el almacenado en la base de datos.

El sistema incrementa el contador de intentos fallidos de cambio de clave para ese usuario.

El sistema responde con:

HTTP 401: Unauthorized

Mensaje: "Verificación de identidad fallida. La contraseña actual es incorrecta. Intento [N] de 5. Al alcanzar el límite, la opción de cambio se bloqueará por 30 minutos."

Nueva contraseña no cumple las políticas de seguridad:

La nueva_contraseña no cumple con los criterios de complejidad (8 caracteres, mayúscula, número y carácter especial).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "La nueva contraseña no cumple con los requisitos de seguridad. Debe incluir al menos 8 caracteres, una mayúscula, un número y un símbolo (ej. @, #, $)."

Confirmación de contraseña no coincide:

El contenido de nueva_contraseña y confirmar_nueva_contraseña es diferente.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de confirmación. Las contraseñas ingresadas no coinciden. Por favor, verifique e intente de nuevo."

Intento de reutilización de contraseña actual:

El sistema genera el hash de la nueva_contraseña y detecta que es idéntico al hash de la contraseña_actual.

El sistema responde con:

HTTP 409: Conflict

Mensaje: "Seguridad de credenciales: No se permite reutilizar la contraseña actual. Por favor, defina una clave completamente nueva."

Bloqueo por exceso de intentos fallidos:

El usuario alcanza el límite de 5 intentos fallidos de verificación de contraseña actual.

El sistema bloquea la funcionalidad de cambio para ese id_usuario durante 30 minutos.

El sistema responde con:

HTTP 423: Locked

Mensaje: "Funcionalidad bloqueada temporalmente por múltiples intentos fallidos. Podrá intentar cambiar su contraseña nuevamente a las [HH:mm:ss] (dentro de 30 minutos)."

Error de integridad en la sesión (ID Mismatch):

El id_usuario enviado en la petición no coincide con el sub (subject) del token JWT del usuario autenticado.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acción no autorizada. Un usuario no puede modificar la contraseña de otra cuenta. Este incidente ha sido reportado al log de auditoría."

Fallo en la invalidación masiva de sesiones:

El sistema actualiza la contraseña con éxito, pero falla al intentar registrar los tokens previos en la blacklist o al limpiar la tabla de sesiones activas.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Contraseña actualizada, pero ocurrió un error al cerrar las sesiones en otros dispositivos. Se recomienda cerrar sesión manualmente en todos sus equipos para garantizar la seguridad."

Fallo en el proceso de Hashing:

Ocurre un error interno en el servidor al intentar ejecutar el algoritmo de cifrado (Bcrypt/Argon2).

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Error interno de seguridad. No se pudo procesar el cifrado de la nueva credencial. La contraseña anterior sigue vigente; intente de nuevo en unos minutos." | Flujo alterno

**Salida:**

Confirmación de cambio exitoso | Salida

**Postcondiciones:**

La contraseña queda actualizada en el sistema

Todas las sesiones activas del usuario son invalidadas

El usuario debe autenticarse nuevamente

Se registra la acción en auditoría | Postcondiciones

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite cambiar la contraseña con credenciales válidas

El sistema rechaza contraseñas actuales incorrectas

El sistema valida las políticas de seguridad

El sistema impide reutilizar la contraseña anterior

El sistema invalida todas las sesiones activas tras el cambio

El sistema registra la operación en auditoría

El sistema bloquea temporalmente tras múltiples intentos fallidos | Criterios de aceptación

**Requerimientos no funcionales:**

Seguridad:

Uso obligatorio de hashing seguro (BCrypt, Argon2 o PBKDF2)

Uso de salt automático

No almacenamiento reversible

Rendimiento:

El cambio de contraseña debe completarse en menos de 2 segundos

Usabilidad:

Mensajes claros de error y validación

Auditoría:

Registro obligatorio del evento (usuario, fecha, IP, acción) | Requerimientos no funcionales

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado | Estado


---

> **⚠️ Nota de conversión:** el Excel original salta de RF-07 a RF-10 —
> **RF-08 (Recuperación de Contraseña) y RF-09 (Restablecimiento de
> Contraseña) no tienen formulario detallado en este archivo**, aunque sí
> aparecen en `Matriz de Requerimientos F-NF.md` marcados como
> "Completado/Aprobado". No es un error de esta conversión; Análisis debe
> completar sus especificaciones aquí si se necesitan documentadas a este
> nivel de detalle.

## RF-10 — Historial de acceso y auditoria

**Código Identificación:** RF-10 -- Versión -- 1.0

**Fuente:** Stakeholders del sistema

**Descripción:** El sistema debe registrar y mantener un historial de auditoría de todos los eventos de seguridad y operaciones relevantes realizadas por los usuarios dentro de la plataforma, garantizando la trazabilidad, integridad y monitoreo de las acciones. El presente requerimiento define el historial de auditoría para el Módulo 1 – Gestión de Acceso y Usuarios. Los eventos auditables de otros módulos serán definidos en sus respectivos requerimientos de auditoría.
 
 Se consideran eventos auditables los siguientes:
 
 - Inicio de sesión exitoso
 - Intento de inicio de sesión fallido
 - Cierre de sesión
 - Registro de nuevo usuario
 - Cambio de contraseña
 - Recuperación o restablecimiento de contraseña
 - Modificación de datos de usuario
 - Cambio de estado de cuenta (activación, desactivación, bloqueo)
 - Creación, modificación o eliminación de roles
 - Asignación o revocación de permisos
 - Consulta del historial de auditoría
 
 Cada registro de auditoría debe almacenar información detallada que permita identificar de forma inequívoca:
 
 el usuario que realizó la acción
 
 la acción ejecutada
 
 el módulo afectado
 
 la fecha y hora del evento
 
 el resultado de la operación

**Justificación:** Los registros de auditoría son fundamentales para garantizar la trazabilidad de las acciones realizadas por los usuarios dentro del sistema, permitiendo identificar responsabilidades, detectar comportamientos anómalos y mantener la integridad operativa de la plataforma.
 
Este historial constituye un mecanismo de control esencial para el cumplimiento de políticas de seguridad interna, facilitando la detección oportuna de accesos no autorizados, cambios indebidos de configuración y otros eventos de riesgo que puedan comprometer la confiabilidad del sistema de gestión pecuaria.

**Precondiciones:** Deben existir usuarios registrados en el sistema.
 
 El sistema debe encontrarse operativo.
 
 El usuario que accede al historial de auditoría debe contar con privilegios administrativos.

**Restricciones:** Los registros de auditoría son inmutables. No se deben permitir operaciones de UPDATE o DELETE sobre esta tabla, ni siquiera para el rol Administrador.
 
 Solo los usuarios con privilegios administrativos pueden consultar el historial completo de auditoría.
 
 El sistema debe garantizar la integridad de cada registro de auditoría mediante la aplicación obligatoria de un mecanismo de hash criptográfico SHA-256 sobre el contenido del registro al momento de su creación. Este hash debe almacenarse junto al registro y verificarse en cada consulta.

**Prioridad:** [X] Alta/Must [ ] Media/Should [ ] Baja/Could

**Dependencia:** RF-02 Autenticación de usuarios, RF-06 Gestión de cuentas de usuario

**Actores:** Administrador del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_evento | integer | Identificador único |
| id_usuario | integer | Usuario que ejecuta la acción |
| nombre_usuario | varchar(80) | Nombre o email |
| tipo_evento | enum | Tipo de evento |
| modulo | varchar(50) | Módulo afectado |
| descripcion | text | Detalle del evento |
| resultado | enum | EXITOSO / FALLIDO |
| direccion_ip | varchar(45) | IP del usuario |
| user_agent | varchar(255) | Navegador/dispositivo |
| id_sesion | varchar(255) | Identificador de sesión |
| fecha_hora | datetime | Timestamp del evento |

**Proceso:**

El sistema detecta un evento auditable
 
 Se recopilan los datos del evento
 
 Se construye el registro de auditoría
 
 Se almacena en base de datos
 
 Se garantiza integridad del registro
 
 Consulta:
 
 El administrador accede al módulo
 
 Aplica filtros:
 
 usuario
 
 tipo_evento
 
 fecha
 
 El sistema devuelve resultados paginados
 
 Política de retención
 
 Los registros se conservan mínimo 12 meses
 
 Registros antiguos se:
 
 archivan automáticamente
 
 o se trasladan a almacenamiento histórico

**Flujo alterno:**

Fallo de integridad del registro (Hash Mismatch):

Al realizar una consulta, el sistema recalcula el hash SHA-256 del registro y detecta que no coincide con el valor almacenado en el campo hash_integridad.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Alerta de seguridad: Se ha detectado una violación de integridad en el registro de auditoría [ID_EVENTO]. Los datos han sido manipulados o están corruptos. Se ha notificado al oficial de seguridad."

Fallo de persistencia obligatoria (Blocker):

El sistema intenta registrar un evento auditable (ej. un cambio de contraseña), pero la base de datos de auditoría no responde o está bloqueada. Dado que la auditoría es obligatoria, la acción principal debe revertirse (Rollback).

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Fallo crítico de seguridad: No se pudo generar el registro de auditoría obligatorio. La operación [ACCION_SOLICITADA] ha sido cancelada para garantizar la trazabilidad del sistema."

Acceso denegado a la consulta de logs:

Un usuario con un rol diferente a 'Administrador' (ej. Veterinario) intenta acceder al endpoint de consulta de auditoría.

El sistema bloquea el acceso y registra este mismo intento fallido en la auditoría.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado: No posee privilegios de administrador para consultar el historial de auditoría. Este incidente ha sido registrado."

Intento de modificación o eliminación (Inmutabilidad):

Se recibe una petición de tipo PUT, PATCH o DELETE dirigida a la tabla o endpoint de auditoría.

El sistema debe tener bloqueados estos métodos a nivel de API y Base de Datos.

El sistema responde con:

HTTP 405: Method Not Allowed

Mensaje: "Operación no permitida: Los registros de auditoría son inmutables por diseño y no pueden ser modificados ni eliminados bajo ninguna circunstancia."

Filtro de búsqueda inválido:

El administrador ingresa un rango de fechas inconsistente (ej. fecha fin anterior a fecha inicio) o un id_usuario inexistente en los filtros.

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error de consulta: Los parámetros de filtrado son inconsistentes. Verifique el rango de fechas y los identificadores de usuario seleccionados."

Exceso de resultados en consulta (Saturación):

Una consulta sin filtros adecuados intenta devolver más de 10,000 registros simultáneamente.

El sistema fuerza la paginación para proteger el rendimiento.

El sistema responde con:

HTTP 206: Partial Content

Mensaje: "Consulta extensa: Se muestran los primeros 50 resultados. Utilice los parámetros de paginación o filtros adicionales para refinar la búsqueda."

Error en el proceso de archivado automático:

El proceso programado para trasladar registros mayores a 12 meses al almacenamiento histórico falla por falta de espacio o permisos en el almacenamiento de destino.

El sistema dispara una alerta crítica al administrador.

El sistema responde con:

Notificación Interna: "Fallo en política de retención: No se pudo completar el archivado de logs antiguos. Espacio en disco insuficiente en el servidor de respaldo."

**Salida:**

Visualización del historial de accesos y eventos del sistema.
 
 Presentación de los registros de auditoría con la información correspondiente a cada evento.

**Postcondiciones:**

Los registros de auditoría quedan almacenados de forma permanente en el sistema.
 
 El sistema mantiene un historial completo de las acciones relevantes realizadas por los usuarios.

**Criterios de aceptación:**

El sistema cumple si:
 
 Registra TODOS los eventos definidos
 Cada registro contiene TODOS los campos obligatorios
 El sistema registra intentos fallidos
 El sistema almacena IP y sesión
 No permite modificación de registros
 Permite consulta con filtros funcionales
 La paginación funciona correctamente
 Los registros se mantienen según política de retención

**Requerimientos no funcionales:**

Seguridad
 
 Integridad de registros
 
 Acceso restringido
 
 Protección contra manipulación
 
 Rendimiento
 
 Consulta < 3 segundos
 
 Paginación obligatoria
 
 Escalabilidad
 
 Soporte para alto volumen de logs
 
 Auditoría
 
 Registro completo y consistente

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-11 — Visualización de usuarios del sistema

**Código Identificación:** RF-11 -- Versión -- 1.0

**Fuente:** Stakeholders del sistema

**Descripción:** El sistema debe permitir a los administradores visualizar un listado paginado de los usuarios registrados en la plataforma, mostrando información específica de cada cuenta que facilite su identificación, gestión y supervisión.
 
 El listado debe incluir únicamente los siguientes atributos por usuario:
 
 nombre de usuario
 
 correo electrónico
 
 rol asignado
 
 estado de la cuenta

El listado debe implementar un mecanismo de actualización en tiempo real o refresco manual para asegurar la consistencia de los datos. Se debe gestionar el comportamiento visual ante cambios de estado o rol realizados por otros administradores de forma concurrente, garantizando que la información refleje el estado actual de la base de datos sin recargar la página.

**Justificación:** La visualización de usuarios permite a los administradores tener un control general sobre las cuentas registradas en el sistema, facilitando la identificación de usuarios activos, la supervisión de cuentas y el acceso a funciones administrativas relacionadas con la gestión de usuarios.

**Precondiciones:** Deben existir usuarios previamente registrados en el sistema.
 
 El actor debe contar con privilegios administrativos.

**Restricciones:** Solo usuarios con permisos administrativos pueden acceder.
 
 No se deben exponer datos sensibles (contraseñas, hashes, tokens) en ningún escenario de consulta, incluyendo los resultados obtenidos mediante filtros combinados o individuales. Esta restricción aplica tanto en la interfaz de usuario como en las respuestas de la API.
 
 El sistema debe limitar limite_registros a un máximo de 50 registros por página.
 
 El listado debe estar paginado obligatoriamente.
 
 El sistema debe soportar filtros combinados; cuando se apliquen múltiples filtros simultáneamente, el sistema debe tratarlos con operador AND (intersección de resultados). Los filtros de texto (nombre_usuario, correo_electronico) aplican coincidencia parcial (LIKE). Los filtros de tipo enum (estado_cuenta, id_rol) aplican coincidencia exacta.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-01 Registro de usuarios
 RF-04 Gestión de permisos
 RF-06 Gestión de cuentas de usuario

**Actores:** Administrador del sistema, usuarios con permisos administrativos

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| pagina | integer | Número de página (>=1) |
| limite_registros | integer | Máximo de registros por página (máx. 50) |
| nombre_usuario | varchar(80) | Filtro parcial |
| correo_electronico | varchar(100) | Filtro exacto o parcial |
| estado_cuenta | enum | ACTIVO, INACTIVO, BLOQUEADO, PENDIENTE |
| id_rol | integer | Filtro por rol |

**Proceso:**

El administrador accede al módulo.
 
 El sistema consulta los usuarios registrados.
 
 El sistema aplica filtros (si existen) con las siguientes reglas:
 - Cuando se aplican múltiples filtros, se combinan con operador AND.
 - Los filtros de texto (nombre_usuario, correo_electronico) utilizan coincidencia parcial.
 - Los filtros de tipo enum (estado_cuenta, id_rol) utilizan coincidencia exacta.
 - Si ningún filtro produce resultados, el sistema muestra un mensaje de lista vacía.
 
 El sistema ordena los resultados por:
 fecha de registro DESCENDENTE (más recientes primero).
 
 El sistema aplica paginación.
 
 El sistema retorna la lista de usuarios, garantizando que ningún dato sensible sea incluido en la respuesta, independientemente de los filtros aplicados.

El sistema implementa un servicio de refresco que detecta cambios en tiempo real sobre los registros cargados.

Ante un cambio de estado o rol de un usuario en el listado, el sistema actualiza la fila correspondiente o notifica al administrador sobre la desactualización de la vista para evitar conflictos operativos.

**Flujo alterno:**

Búsqueda sin coincidencias:

El administrador aplica filtros combinados (operador AND) que no arrojan resultados en la base de datos.

El sistema responde con:

HTTP 200: OK

Mensaje: "Consulta exitosa. No se encontraron usuarios que coincidan con los criterios aplicados: [LISTA_DE_FILTROS]. La tabla se mostrará vacía."

Parámetros de paginación fuera de rango:

Se solicita una pagina menor a 1 o un limite_registros superior a 50 (violando la restricción de diseño).

El sistema responde con:

HTTP 400: Bad Request

Mensaje: "Error en parámetros de consulta. La página debe ser un número entero mayor o igual a 1 y el límite de registros no puede exceder los 50 por página."

Fallo en el servicio de actualización en tiempo real (WebSockets/SSE):

El túnel de comunicación para el refresco dinámico de datos se interrumpe por latencia o caída del servicio de mensajería.

El sistema muestra un indicador visual en la interfaz y responde con:

HTTP 503: Service Unavailable (en el canal de streaming)

Mensaje (UI): "Conexión en tiempo real perdida. Los cambios realizados por otros administradores no se verán reflejados automáticamente. Por favor, use el botón 'Refrescar' manualmente."

Conflicto de visualización por eliminación lógica concurrente:

El administrador intenta interactuar con un usuario que aparece en su lista, pero que otro administrador acaba de cambiar al estado 'ELIMINADO' en ese mismo instante.

El sistema detecta el cambio de estado mediante la validación de concurrencia.

El sistema responde con:

HTTP 410: Gone

Mensaje: "El registro ya no está disponible. El usuario [NOMBRE_USUARIO] ha sido eliminado o modificado recientemente por otro administrador. El listado se actualizará automáticamente."

Intento de inyección de parámetros inválidos en filtros:

Se envían valores que no corresponden al tipo de dato esperado (ej. un string en id_rol o caracteres especiales prohibidos en correo_electronico).

El sistema sanitiza la entrada y, si es inválida, responde con:

HTTP 400: Bad Request

Mensaje: "Error de filtrado. El valor ingresado para el campo [NOMBRE_CAMPO] no es válido o contiene caracteres no permitidos."

Fallo de seguridad por exposición de datos sensibles (Sanitización):

La capa de servicio detecta que el objeto de respuesta hacia la API contiene campos no autorizados (hashes de contraseñas o tokens de sesión).

El sistema bloquea la salida de datos por seguridad interna.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Fallo de seguridad detectado. La consulta ha sido abortada para proteger la integridad de los datos sensibles. Reporte este incidente al equipo técnico."

Acceso denegado (Falta de privilegios):

Un usuario con un token válido de un rol no administrativo (ej. Veterinario) intenta forzar el acceso al endpoint de listado de usuarios.

El sistema bloquea la solicitud y registra el evento en el log de auditoría (RF-10).

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Acceso denegado. No tiene los permisos necesarios para visualizar el listado global de usuarios."

**Salida:**

Listado de usuarios con estructura:
 
 Campo
 nombre_usuario
 correo_electronico
 rol
 estado_cuenta
 
 metadatos de paginación:
 
 total_registros
 
 total_paginas
 
 pagina_actual

**Criterios de aceptación:**

El sistema cumple si:
 
 Muestra un listado paginado de usuarios.
 Cada registro contiene EXACTAMENTE los campos definidos.
 No expone información sensible en ningún escenario de filtrado.
 Permite filtrar por:
 
 nombre
 
 correo
 
 estado
 
 rol
 
 Permite combinar filtros aplicando operador AND.
 Aplica límite máximo de 50 registros.
 Ordena por fecha de registro descendente.
 Muestra mensaje informativo cuando no hay resultados que coincidan con los filtros aplicados.
 La paginación funciona correctamente.
 Los usuarios con estado BLOQUEADO se incluyen en el listado y su estado se muestra correctamente.
 Al filtrar exclusivamente por estado BLOQUEADO, el sistema retorna únicamente los usuarios en ese estado.

El sistema permite la actualización de datos sin necesidad de recarga completa de página.


El sistema refleja cambios de estado o rol de forma dinámica durante la interacción del administrador.

**Requerimientos no funcionales:**

Rendimiento
 
 Respuesta < 2 segundos con hasta 10,000 usuarios
 
 Seguridad
 
 Acceso restringido por roles
 
 Protección de datos sensibles
 
 Usabilidad
 
 Tabla clara, con paginación visible
 
 Indicador de página actual

La interfaz debe incluir indicadores visuales de actualización de datos.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-12 — Visualizacion de detalles del usuario

**Código Identificación:** RF-12 -- Versión -- 1.0

**Fuente:** Stakeholders del sistema

**Descripción:** El sistema debe permitir a los administradores consultar la información detallada de un usuario específico seleccionado desde el listado de usuarios del sistema, mostrando un conjunto definido de datos personales y administrativos que permitan su identificación y gestión dentro del sistema.
 
 La información mostrada debe incluir únicamente los siguientes campos:
 
 nombre
 
 apellido
 
 correo electrónico
 
 tipo de identificación
 
 número de identificación
 
 fecha de nacimiento
 
 fecha de registro
 
 rol asignado
 
 estado de la cuenta
 
 No se deben incluir datos sensibles como contraseñas, hashes o tokens.

Se implementa una auditoría obligatoria por cada acceso a esta vista al contener datos sensibles. El sistema incluye un monitoreo de seguridad para detectar patrones de consulta inusuales y aplica controles de protección de datos personales adicionales conforme a la normativa vigente.

**Justificación:** La consulta detallada de usuarios facilita la supervisión administrativa y permite acceder de forma estructurada a la información necesaria para la gestión y verificación de usuarios dentro del sistema.

**Precondiciones:** El usuario debe estar previamente registrado en el sistema.
 
 El actor debe contar con privilegios administrativos.

**Restricciones:** No se deben mostrar:
 
 contraseñas
 
 hashes
 
 tokens
 
 El número de identificación debe:
 
 mostrarse enmascarado por defecto, mostrando únicamente los primeros 4 dígitos seguidos de asteriscos (ej: 1075******). Este enmascaramiento aplica tanto en la interfaz de usuario como en las respuestas de la API y servicios backend.
 
 mostrarse completo únicamente si el administrador posee el permiso de acción 'ver_identificacion_completa' sobre el recurso 'usuario', conforme al modelo RBAC definido en RF-04. Este permiso debe ser verificado en el backend en cada solicitud, de forma independiente a las validaciones de interfaz.
 
 El acceso a esta funcionalidad está restringido a usuarios con rol administrativo. La validación de este control de acceso debe realizarse en el backend en cada solicitud recibida.

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-09 Visualización de usuarios del sistema

**Actores:** Administrador/es del sistema

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| id_usuario | integer | Identificador único del usuario seleccionado |

**Proceso:**

El administrador selecciona un usuario.
 
 El sistema recibe id_usuario.
 
 Validaciones (realizadas en el backend en cada solicitud):
 
 el usuario existe
 
 el administrador tiene permisos de acceso

El sistema registra automáticamente en el historial de auditoría (RF-10) la visualización de la ficha, vinculando el ID del consultor, el ID del consultado y la marca de tiempo, cumpliendo con el control de acceso a datos sensibles.
 
 Si las validaciones son correctas:
 
 se obtiene la información del usuario desde la base de datos transaccional confirmada
 
 se aplica enmascaramiento del número de identificación (primeros 4 dígitos visibles, resto reemplazado por asteriscos), tanto en la respuesta de interfaz como en la respuesta de API
 
 si el administrador posee el permiso 'ver_identificacion_completa' (RF-04), se muestra el número completo en lugar del enmascarado

El sistema evalúa la frecuencia y volumen de accesos detallados por parte del usuario actual para detectar patrones de extracción masiva y aplica controles adicionales de protección de datos personales.
 
 El sistema retorna la información.


**Flujo alterno:**

Usuario inexistente:

El administrador intenta acceder a un detalle mediante un id_usuario que ha sido eliminado lógicamente o no existe en la base de datos.

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Consulta fallida: El usuario solicitado no existe o ha sido retirado del sistema."

Acceso denegado (Falta de privilegios administrativos):

Un usuario con un rol inferior intenta forzar la entrada al endpoint de detalles o el administrador actual no tiene el permiso de lectura de perfiles.

El sistema responde con:

HTTP 403: Forbidden

Mensaje: "Privilegios insuficientes: No tiene autorización para consultar la ficha técnica de otros usuarios. El incidente ha sido reportado."

Fallo en el registro de auditoría obligatoria:

El sistema intenta obtener los datos, pero el servicio de auditoría (RF-10) no responde o falla al insertar el registro de acceso. Por seguridad y cumplimiento, el acceso se bloquea si no se puede auditar.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Error de seguridad: No se pudo garantizar la trazabilidad de la consulta. La visualización de datos sensibles ha sido bloqueada preventivamente."

Detección de patrón de consulta inusual (Rate Limiting/Seguridad):

El administrador realiza consultas detalladas de múltiples usuarios en un lapso de tiempo extremadamente corto (posible extracción masiva o scraping).

El sistema responde con:

HTTP 429: Too Many Requests

Mensaje: "Alerta de seguridad: Patrón de consulta inusual detectado. Su acceso a vistas detalladas ha sido restringido temporalmente por protección de datos."

Fallo en la validación del permiso de identificación completa:

El sistema no logra verificar si el administrador tiene el permiso ver_identificacion_completa debido a un fallo en el servicio de permisos (RF-04).

Comportamiento preventivo: El sistema aplica el enmascaramiento por defecto (****) y no muestra el número completo, priorizando la privacidad sobre la visualización.

Mensaje (UI): "Aviso: No se pudo verificar su permiso de visualización completa; los datos se mostrarán enmascarados por seguridad."

**Salida:**

Objeto con estructura:
 
 nombre
 apellido
 correo
 tipo_identificacion
 numero_identificacion (enmascarado)
 fecha_nacimiento
 fecha_registro
 rol
 estado_cuenta

**Postcondiciones:**

El administrador visualiza la información del usuario seleccionado conforme a las restricciones definidas.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:
 
 Permite consultar un usuario mediante id_usuario.
 
 El sistema valida que el usuario exista.
 
 El sistema valida permisos del administrador en el backend en cada solicitud.
 
 Retorna exactamente los campos definidos en la salida.
 
 No incluye contraseñas ni datos sensibles.
 
 Aplica el enmascaramiento del número de identificación por defecto (primeros 4 dígitos visibles, resto con asteriscos), tanto en interfaz como en respuesta de API.
 
 Muestra el número completo solo si el administrador tiene el permiso 'ver_identificacion_completa' (RF-04).

Cada acceso a la vista detallada genera un registro de auditoría inmutable y verificable en el RF-10.

El sistema dispara alertas de seguridad ante patrones de acceso anómalos o repetitivos a perfiles de usuario.
 
 Muestra "Usuario no encontrado" si el usuario no existe.
 
 Muestra "Acceso denegado" si no tiene permisos.
 
 Muestra mensaje de error ante fallos internos.
 
 Los datos retornados son consistentes con la información almacenada en la base de datos transaccional confirmada en el momento de la consulta.

**Requerimientos no funcionales:**

Seguridad
 
 Protección de datos sensibles mediante enmascaramiento.
 Control de acceso basado en roles.

Documentación y aplicación de controles estrictos de protección de datos personales en la visualización.
 
 Rendimiento
 
 Tiempo de respuesta menor a 2 segundos.
 
 Usabilidad
 
 Información clara, estructurada y legible.
 
 Fiabilidad
 
 Los datos deben ser consistentes con la base de datos.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-13 — Visualización de perfil del usuario

**Código Identificación:** RF-13 -- Versión -- 1.0

**Fuente:** Stakeholders del sistema

**Descripción:** El sistema debe permitir a un usuario autenticado visualizar la información asociada a su propio perfil dentro de la plataforma, mostrando un conjunto definido de datos personales y de cuenta que faciliten su consulta y verificación.

La información del perfil debe obtenerse exclusivamente a partir del contexto de autenticación de la sesión activa del usuario, sin permitir el uso de identificadores externos o parámetros de entrada.

La información mostrada debe incluir únicamente los siguientes campos:

nombre

apellido

correo electrónico

tipo de identificación

número de identificación

fecha de nacimiento

fecha de registro

rol asignado

estado de la cuenta

Datos sensibles que NO deben incluirse en ningún escenario:

contraseñas

hashes de contraseña

tokens de autenticación

claves de acceso

información de recuperación de credenciales

**Justificación:** Permite al usuario verificar la exactitud de su información registrada, facilitando la transparencia y reduciendo errores antes de realizar operaciones dentro del sistema.

**Precondiciones:** El usuario debe estar autenticado.

Debe existir una sesión activa válida.

La sesión debe corresponder a un token de autenticación vigente (no expirado) generado por el sistema.

**Restricciones:** El usuario solo puede acceder a su propio perfil.

No se permite consultar información de otros usuarios.

La información debe obtenerse exclusivamente desde el contexto de sesión autenticada (no desde parámetros externos).

Protección de datos:

No se deben mostrar:

contraseñas

hashes

credenciales de autenticación

Enmascaramiento del número de identificación:

Debe mostrarse enmascarado por defecto con el siguiente formato:

Mostrar únicamente los primeros 4 dígitos

El resto de los dígitos deben reemplazarse con asteriscos

Ejemplo: 1075******

Este enmascaramiento aplica tanto en:

interfaz de usuario

respuestas de API

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-02 Autenticación de usuarios

**Actores:** Usuario del sistema

**Proceso:**

El usuario accede a la sección “Mi perfil”.

El sistema obtiene la identidad del usuario desde la sesión activa.

El sistema valida la sesión:

token válido

no expirado

asociado a un usuario existente

El sistema consulta la información del usuario en la base de datos transaccional.

El sistema aplica reglas de protección de datos:

exclusión de datos sensibles

enmascaramiento del número de identificación

El sistema construye la respuesta estructurada.

El sistema retorna la información al usuario.

**Flujo alterno:**

Token de sesión inválido o malformado:

El sistema recibe una solicitud donde el token de autenticación no cumple con el estándar técnico (ej. JWT corrupto o firma digital inválida).

El sistema responde con:

HTTP 401: Unauthorized

Mensaje: "Sesión inválida: Las credenciales de acceso no son reconocidas o han sido manipuladas. Por favor, inicie sesión nuevamente."

Sesión expirada (TTL finalizado):

El token de sesión es auténtico, pero su tiempo de validez ha caducado según la política de seguridad del sistema.

El sistema responde con:

HTTP 401: Unauthorized

Mensaje: "Sesión expirada: Su tiempo de conexión ha finalizado. Inicie sesión para continuar."

Usuario inexistente en persistencia:

El token es válido, pero el identificador del usuario contenido en él no corresponde a ningún registro activo en la base de datos (ej. el usuario fue eliminado mientras mantenía la sesión abierta).

El sistema responde con:

HTTP 404: Not Found

Mensaje: "Error de perfil: No se pudo recuperar la información asociada a su cuenta. El registro no existe o ha sido desactivado."

Intento de consulta mediante parámetros externos (Bypass):

El usuario intenta enviar un id_usuario a través de la URL o el cuerpo de la petición para intentar visualizar un perfil ajeno.

Comportamiento del sistema: El sistema ignora cualquier parámetro de entrada y procesa la solicitud utilizando únicamente el ID extraído del token de sesión. Si hay una discrepancia forzada o el endpoint no permite parámetros, responde con:

HTTP 400: Bad Request

Mensaje: "Solicitud inválida: Este recurso no acepta parámetros externos para la identificación del usuario."

Fallo en el servicio de enmascaramiento:

Ocurre un error lógico al procesar la máscara del número de identificación (ej. el dato almacenado es más corto de 4 dígitos o tiene un formato inesperado).

Comportamiento preventivo: El sistema oculta completamente el campo antes de enviarlo al frontend para evitar la fuga de información parcial.

Mensaje (UI): "Aviso: Información de identificación temporalmente no disponible por reglas de protección."

Fallo de conexión con la base de datos:

El sistema no logra establecer comunicación con el servidor de persistencia para recuperar los datos transaccionales.

El sistema responde con:

HTTP 500: Internal Server Error

Mensaje: "Error interno: No se pudo conectar con el servicio de datos. Intente de nuevo en unos minutos."

**Salida:**

Objeto estructurado con los siguientes campos y tipos de dato:

nombre	string
apellido	string
correo_electronico	string
tipo_identificacion	string
numero_identificacion	string (enmascarado)
fecha_nacimiento	date
fecha_registro	timestamp
rol	string
estado_cuenta    enum (ACTIVO, INACTIVO, BLOQUEADO, PENDIENTE)

**Postcondiciones:**

El usuario visualiza su información de perfil conforme a las restricciones definidas.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema permite acceder al perfil únicamente con una sesión activa válida.

El sistema obtiene la información del usuario desde la sesión, sin parámetros externos.

El sistema valida que el token de autenticación no esté expirado.

El sistema retorna exactamente los campos definidos en la salida.

El sistema no expone datos sensibles bajo ningún escenario.

El sistema aplica correctamente el enmascaramiento del número de identificación:

primeros 4 dígitos visibles

resto enmascarado con asteriscos

El sistema impide el acceso a perfiles de otros usuarios.

Casos negativos (AGREGADOS SEGÚN REEVALUACIÓN)

Si la sesión es inválida → retorna error.

Si la sesión está expirada → retorna error.

Si el usuario no existe → retorna error.

Si ocurre un fallo interno → retorna error controlado.

**Requerimientos no funcionales:**

Seguridad

Control de acceso basado en sesión autenticada.
Protección de datos sensibles mediante enmascaramiento.

Rendimiento

Tiempo de respuesta menor a 2 segundos.

Usabilidad

Información clara, estructurada y legible.

Fiabilidad

Los datos deben ser consistentes con la base de datos transaccional.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---

## RF-14 — Notificar a los usuarios

**Código Identificación:** RF-14 -- Versión -- 1.0

**Fuente:** Stakeholders / Productor pecuario / Veterinario

**Descripción:** El sistema debe generar y enviar notificaciones automáticas a los usuarios cuando ocurran eventos específicos relacionados con la seguridad de la cuenta o la gestión del sistema, con el fin de informar oportunamente sobre acciones relevantes.

Las notificaciones deben enviarse a través de los siguientes canales:

correo electrónico

notificación interna dentro de la plataforma

Los eventos que deben generar notificaciones son:

registro exitoso de usuario

inicio de sesión exitoso

intento de inicio de sesión fallido

cambio de contraseña

solicitud de recuperación de contraseña

restablecimiento de contraseña

actualización de perfil

bloqueo o desactivación de cuenta

Cada notificación debe contener como mínimo la siguiente información:

tipo de evento

mensaje descriptivo

fecha y hora del evento

**Justificación:** El mecanismo de notificaciones permite mantener informados a los usuarios sobre eventos relevantes asociados a su cuenta, contribuyendo a mejorar la comunicación entre el sistema y los usuarios y reforzando la seguridad de la plataforma.

**Precondiciones:** El usuario debe estar registrado en el sistema.

El usuario debe tener un correo electrónico verificado.

Debe existir un evento del sistema que genere notificación.

El sistema debe contar con un servicio de notificaciones configurado.

**Restricciones:** Se debe validar el estado del usuario antes del envío:

Usuarios inactivos no reciben notificaciones

Usuarios bloqueados solo reciben notificaciones de seguridad

No se deben incluir datos sensibles en el contenido

olítica anti-spam obligatoria:

notificación por tipo_evento + usuario + canal cada 5 minutos

No se deben generar reintentos automáticos en caso de fallo
(evita duplicidad y mantiene simplicidad del sistema)

**Prioridad:** [ ] Alta/Must [X] Media/Should [ ] Baja/Could

**Dependencia:** RF-01 Registro de usuarios, RF-02 Autenticación de usuarios, RF-07 Gestión de contraseñas

**Actores:** Sistema (actor principal encargado de generar y enviar las notificaciones)

Usuario (receptor de la notificación)

**Entradas:**

| Variable | Tipo de dato | Descripción |
|---|---|---|
| tipo_evento | enum | Tipo de evento que genera la notificación. Valores permitidos: REGISTRO_USUARIO, LOGIN_EXITOSO, LOGIN_FALLIDO, CAMBIO_CONTRASENA, SOLICITUD_RECUPERACION, RESTABLECIMIENTO_CONTRASENA, ACTUALIZACION_PERFIL, BLOQUEO_CUENTA, DESACTIVACION_CUENTA |
| id_usuario | integer | Identificador del usuario que recibe la notificación. FK → usuarios.id |
| fecha_evento | timestamp | Fecha y hora en que ocurrió el evento en el sistema |
| canal_envio | enum | Canal por el cual se enviará la notificación. Valores: EMAIL, INTERNO |
| estado_usuario | enum | Estado actual del usuario al momento del evento. Valores: ACTIVO, INACTIVO, BLOQUEADO |
| mensaje | varchar(255) | Mensaje descriptivo generado por el sistema (sin datos sensibles) |

**Proceso:**

1. Ocurre un evento dentro del sistema.

2. El sistema valida si el evento es notificable.

3. El sistema identifica el usuario asociado al evento.

4. El sistema valida el estado del usuario:
   - Si el usuario está INACTIVO:
       No se envía notificación por ningún canal.
   - Si el usuario está BLOQUEADO:
       Solo se permite notificación para eventos de seguridad:
           - intento de inicio de sesión fallido
           - bloqueo de cuenta
   - Si el usuario está ACTIVO:
       Continúa el proceso normal.

5. El sistema construye el mensaje de notificación:
   - tipo de evento
   - mensaje descriptivo
   - fecha y hora

6. El sistema valida la política anti-spam:
   - Máximo 1 notificación por tipo_evento + usuario + canal cada 5 minutos
   - Si se excede:
       Se descarta la notificación

7. El sistema registra la notificación con estado inicial:
   - QUEUED

8. El sistema intenta el envío por cada canal configurado:
   - EMAIL
   - INTERNO

9. Manejo de resultado de envío:
   - Si el envío es exitoso:
       estado → SENT
   - Si falla el envío:
       estado → FAILED

10. En caso de fallo:
   - El sistema NO reintenta automáticamente (para evitar duplicidad)
   - El fallo queda registrado para auditoría

11. El sistema almacena la notificación con:
   - usuario
   - evento
   - canal
   - estado
   - fecha/hora

12. El sistema confirma la ejecución del proceso internamente.

**Flujo alterno:**

Descarte por política Anti-Spam:

El sistema detecta que ya se envió una notificación del mismo tipo_evento al mismo id_usuario por el mismo canal_envio en un lapso menor a 5 minutos.

El sistema responde con:

Lógica de Descarte: La notificación no se encola ni se envía.

Registro: Se guarda un log interno de "Notificación omitida por política de frecuencia" para evitar bucles de envío.

Restricción por estado de usuario (Usuario Bloqueado):

Ocurre un evento no crítico (ej. ACTUALIZACION_PERFIL) para un usuario cuyo estado es BLOQUEADO.

El sistema responde con:

Lógica de Bloqueo: El sistema identifica que el evento no pertenece a la categoría de seguridad permitida para usuarios bloqueados.

Resultado: El proceso de notificación se aborta silenciosamente.

Fallo en el proveedor de correo (SMTP/API Error):

El sistema intenta enviar el EMAIL, pero el servicio externo de mensajería devuelve un error (ej. timeout, credenciales expiradas o rechazo del servidor).

El sistema responde con:

Estado: FAILED.

Acción: Se registra el error técnico en el log de auditoría. Cumpliendo la restricción, no se programa ningún reintento.

Usuario sin dirección de correo válida:

El sistema intenta enviar una notificación, pero el campo correo_electronico del usuario está vacío o tiene un formato inválido (error de integridad previo).

El sistema responde con:

Estado: FAILED.

Mensaje de Auditoría: "Error: Destinatario inválido o inexistente".

Fallo en el servicio de notificaciones internas:

El sistema intenta persistir la notificación en la tabla de notificaciones_internas para su visualización en la plataforma, pero la base de datos no está disponible.

El sistema responde con:

Estado: FAILED.

Resultado: La notificación se pierde para garantizar que no se generen procesos huérfanos.

Evento de seguridad en Usuario Inactivo:

Se intenta generar una notificación de LOGIN_FALLIDO para una cuenta que ya está en estado INACTIVO.

El sistema responde con:

Lógica de Privacidad: Para evitar confirmar la existencia de cuentas o procesar datos de usuarios fuera de servicio, el sistema ignora la petición de notificación por completo.

**Salida:**

Envío de notificación al usuario por los canales definidos.

Registro de la notificación con estado (QUEUED, SENT, FAILED).

Visualización de la notificación en la plataforma.

**Postcondiciones:**

El usuario queda informado sobre el evento ocurrido en su cuenta.

El sistema mantiene registro del envío de la notificación.

**Criterios de aceptación:**

El requerimiento se considera cumplido cuando:

El sistema genera notificaciones solo para los eventos definidos

El sistema envía notificaciones por:

correo electrónico
notificación interna

El sistema valida el estado del usuario antes del envío:

No envía a usuarios inactivos
Restringe envío a usuarios bloqueados según reglas

El sistema registra cada notificación con:

tipo de evento
usuario
canal
estado (QUEUED, SENT, FAILED)
fecha y hora

El sistema aplica correctamente la política anti-spam

El sistema no envía notificaciones duplicadas dentro del intervalo definido

El contenido incluye:

tipo de evento
mensaje descriptivo
fecha y hora

El sistema maneja correctamente errores de envío:

Registra estado FAILED
No genera reintentos automáticos

El sistema permite visualizar la notificación en la plataforma

**Requerimientos no funcionales:**

Seguridad

No se deben exponer datos sensibles en las notificaciones.
El envío debe garantizar confidencialidad.

Disponibilidad

El sistema de notificaciones debe estar disponible ≥ 99%.

Rendimiento

El envío de notificaciones debe ejecutarse en menos de 5 segundos.

Escalabilidad

El sistema debe soportar múltiples notificaciones concurrentes.

**Estado:**

[X] Pendiente [ ] Implementado [ ] Verificado


---
