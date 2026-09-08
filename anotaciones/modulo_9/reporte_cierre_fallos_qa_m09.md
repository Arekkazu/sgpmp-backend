# Cierre técnico de reportes QA del Módulo 9

## Alcance

Este documento relaciona los reportes `TC-M09-G001` a `TC-M09-G126` recibidos
para RF-15, RF-17, RF-20, RF-21, RF-22, RF-24, RF-25, RF-26, RF-27, RF-30,
RF-31 y RF-32 con el estado verificable de la rama `fix/reportes-m09`.

La revisión se hizo contra:

- El código local del backend.
- Las pruebas de regresión presentes en `tests/`.
- Las pruebas externas en `sgpmp-backend-test/tests/Test_Testing/Test_Modulo9`.
- Las anotaciones de `anotaciones/modulo_9/`.
- `CLAUDE.md`, `CONTRIBUTING.md` y `anotaciones/convencion_nomenclatura_bd.md`.

No se modificó el broker MQTT porque ninguno de los fallos reportados requiere
cambiar el contrato MQTT ni el procesamiento del broker. Los cambios de
configuración MQTT permanecen responsabilidad de RF-23 y de la infraestructura
de despliegue.

## Diagnóstico por grupo

### RF-15: especies

El fallo `500 ERROR_INTERNO` de creación y edición estaba asociado al trigger
huérfano de auditoría de especies, que exigía `app.usuario_id` aunque la
aplicación ya registra la auditoría mediante su repositorio. La corrección
Alembic `a1c3f6e0b2d4_rf15_eliminar_trigger_auditoria_especies_huerfano.py`
elimina ese trigger.

La regresión local
`tests/integration/test_rf15_especies_registro.py` cubre:

- creación válida con respuesta `201`;
- auditoría `CREATE`;
- edición válida con respuesta `200`.

Resultado local: `57 passed` en las regresiones de RF-15/RF-30/RF-32
ejecutables sin una base externa. La prueba de RF-15 se omite cuando la base
no tiene el esquema `modulo9`, por lo que TEST debe confirmar que la migración
está aplicada antes de repetir Newman.

### RF-17: umbrales ambientales

El modelo representa el enum PostgreSQL como `String`, de acuerdo con la
convención del repositorio. SQLAlchemy podía agrupar los tres niveles con
`insertmanyvalues` y producir `DatatypeMismatch`. El motor se crea con
`use_insertmanyvalues=False` en `src/shared/database.py`.

La regresión correspondiente verifica el registro de los tres niveles. No se
debe reemplazar esta solución por `Enum` de SQLAlchemy, porque intentaría
administrar un tipo enum que ya existe en PostgreSQL.

### RF-20: infraestructuras

La creación y edición consultan el catálogo administrable `modulo9.tipos_area`
mediante comparación case-insensitive. La migración
`2dbb6d44046f_rf20_catalogo_tipos_area.py` crea el catálogo y migra la
referencia de las infraestructuras.

Los payloads reportados (`tipo_area=galpon`, `tipo_area=estanque`,
`superficie` decimal) son compatibles con el DTO y el repositorio actuales.
Los `undefined` y `NaN` observados en Newman son efectos del `500` anterior,
no campos de respuesta válidos.

Antes de repetir los casos `TC-M09-G048` a `TC-M09-G050` en TEST se debe
verificar:

1. Que `alembic upgrade head` haya aplicado el catálogo `tipos_area`.
2. Que existan tipos activos con los nombres usados por la colección.
3. Que el contenedor esté ejecutando la rama que contiene el repositorio de
   tipos de área.

### RF-21: dispositivos IoT

Las dos expectativas OWASP reportadas están cubiertas por código y regresiones:

- `SerialDispositivo` usa una allow-list para impedir sintaxis de inyección.
- `RegistrarDispositivoIotDTO` rechaza caracteres peligrosos en la descripción.
- El endpoint aplica límite de diez registros por usuario en sesenta segundos.

Las pruebas locales:

- `tests/configuration/test_inc_m09_21_g125_01_sanitizacion_dispositivo_iot.py`
- `tests/shared/test_inc_m09_21_g125_02_rate_limit.py`

Resultado: `9 passed` junto con la regresión de aislamiento de RF-22.

El limitador es local al proceso. Un despliegue con múltiples workers debe
usar un almacén compartido antes de afirmar que el límite es global; esta
limitación no explica un `201` local, pero sí debe considerarse en producción.

### RF-22: asociaciones de sensores

La asociación compara la finca del área destino con la finca del área de
instalación del dispositivo y rechaza cruces con `SENSOR_FINCA_DISTINTA`.
La consulta de historial filtra sensores fuera del alcance del productor y
responde `404` para no confirmar la existencia del objeto.

Las regresiones locales de `TC-M09-G126` pasan. La rama todavía contiene una
constante histórica para identificar el rol Productor en el router; el
permiso del endpoint continúa siendo dinámico mediante `require_permission`.
No se cambia esa política en este cierre porque sustituirla requiere acordar
un mecanismo de alcance por usuario que no dependa de un catálogo de roles
fijo y debe cubrir también RF-19 y RF-20.

### RF-24: calibración

La validación de formato, rango y auditoría está cubierta por las pruebas de
calibración existentes. El reporte de `401` no es reproducible con el cliente
local autenticado y debe revisarse contra las credenciales, expiración del JWT
o configuración de permisos del entorno TEST.

### RF-25, RF-26 y RF-27: acceso y personalización

La rama frontend contiene las pestañas y componentes de personalización,
identidad visual y temas, y sus pruebas unitarias pasan. El backend expone los
endpoints multipart de identidad visual y los endpoints de tema personal y
global.

Los casos que indican que las opciones no existen en la interfaz son
incompatibles con la rama frontend revisada. Esto indica un bundle desplegado
anterior o una sesión sin permiso de lectura del recurso de personalización.
Debe invalidarse la caché del frontend y confirmarse el commit desplegado.

### RF-30 y RF-31: plantillas

La creación, versionado, auditoría y validación del rango físico están
implementados. La auditoría se consulta mediante el endpoint de auditoría de
plantillas. El snapshot usa `schema_version` y conserva su contenido al
aplicar una plantilla.

Las pruebas de RF-30/RF-31 pasan localmente cuando la base de integración
dispone de `modulo9`. Un `409` por nombre duplicado es correcto cuando el
nombre realmente ya existe; las colecciones deben generar nombres únicos por
ejecución.

### RF-32: aplicación de plantillas

La aplicación valida plantilla existente, versión de esquema, especie destino
activa y concurrencia mediante `fecha_actualizacion`. El flujo reemplaza la
configuración dentro de una única transacción y registra la auditoría.

La regresión `test_rf32_aplicar_plantilla_reaplicacion.py` reproduce la
reaplicación con ciclos, métricas y umbrales y evita el choque con filas
desactivadas. La regresión de concurrencia comprueba el `412` cuando el
timestamp no coincide.

Los `500` de `TC-M09-G116`, `G118` y `G119` no se reproducen en la rama con la
migración y la configuración actuales. Si persisten en TEST, se deben capturar
los logs de la excepción y el `alembic_version` de esa base antes de modificar
la lógica.

## Validación ejecutada

Backend:

```text
PYTHONPATH=. pytest -q \
  tests/configuration/test_inc_m09_21_g125_01_sanitizacion_dispositivo_iot.py \
  tests/shared/test_inc_m09_21_g125_02_rate_limit.py \
  tests/configuration/test_inc_m09_22_g126_02_idor_historial_asociaciones.py
9 passed

PYTHONPATH=. pytest -q \
  tests/integration/test_rf15_especies_registro.py \
  tests/integration/test_rf32_aplicar_plantilla_reaplicacion.py \
  tests/integration/test_rf30_auditoria_plantillas.py
57 passed
```

Los casos de integración que requieren el esquema `modulo9` se omiten
automáticamente cuando la base de pruebas no lo tiene.

## Requisitos para revalidar TEST

1. Desplegar el commit de `fix/reportes-m09` del backend.
2. Ejecutar `alembic upgrade head` contra la base TEST.
3. Confirmar el valor de `alembic_version` y la existencia de las migraciones
   RF-15, RF-17, RF-20, RF-22, RF-26, RF-31 y RF-32.
4. Confirmar que el catálogo `tipos_area` tenga registros activos.
5. Invalidar la caché/CDN del frontend y desplegar `fix/reportes-m09`.
6. Repetir Newman y Cypress con credenciales y permisos de TEST vigentes.
7. Si aparece un nuevo `500`, adjuntar timestamp, endpoint, request id y
   traceback del backend; el cuerpo genérico `ERROR_INTERNO` no permite
   determinar una nueva causa raíz.

## Estado de cambios

Este cierre no agrega una migración ni altera contratos funcionales sin una
reproducción local. La evidencia indica que los fallos principales ya tienen
correcciones en la rama y que el siguiente paso necesario es sincronizar el
artefacto desplegado y su base de datos.
