# RF-24 v2.0 — Mensajes de validación de calibración

Incidencia: `INC-M09-69-G75-v2.0`. Grupo: `TC-M09-G75-v2.0`.
Casos: `TC-M09-144-v2.0` y `TC-M09-145-v2.0`.
Base de trabajo: `origin/dev`, commit `5541ea36`.
Rama: `fix/rf24-g75-mensajes-calibracion`.

## Desvío y causa raíz

El rechazo funcional era correcto. En `RegistrarCalibracionUseCase._validar`,
el mensaje de rango omitía `Valor fuera de límites:` y añadía el rango permitido.
El mensaje de formato omitía `Error de formato:` y la entrada rechazada.
El handler HTTP reutiliza este mensaje tanto en `message` como en `fields`.

Los textos esperados se contrastaron con el flujo alterno de RF-24 v2.0
del documento `Requerimientos_3.md` proporcionado por el usuario.
La evidencia Newman compartida es el reporte textual de la incidencia:
no se dispone de los archivos originales enumerados para repetir ese RUN_ID.

## Corrección

- Rango: incorporar el prefijo contractual, conservar valor y categoría del sensor,
  y retirar el fragmento `(permitido ...)`.
- Formato: incorporar el prefijo y `Verifique la entrada '<valor>'.`.
  Representar el `null` de JSON como `null`, conservando `''` y `'abc'`.
- Conservar condiciones de validación, HTTP 400, códigos, campos, rango inclusivo,
  conversión Decimal, auditoría de rechazos y transacciones existentes.
- No modificar DTO, router, autorización, alcance por finca, repositorios,
  `modo_calibracion`, persistencia ni esquema. No requiere migración.

## Pruebas HTTP de la incidencia

`tests/configuration/test_rf24_g75_mensajes_calibracion.py` usa router, DTO,
caso de uso y handlers reales. Los repositorios, la sesión, la autorización y
el alcance se sustituyen por dobles en memoria; no acredita integración con
PostgreSQL ni autenticación real en TEST.

| Escenario | Resultado comprobado |
| --- | --- |
| LOW: `-0.0001` | 400, `VALOR_FUERA_DE_RANGO`, mensaje exacto |
| HIGH: `45.0001` | 400, `VALOR_FUERA_DE_RANGO`, mensaje exacto |
| EMPTY: `""` | 400, `VALOR_CALIBRACION_INVALIDO`, entrada `''` |
| NULL: `null` | 400, `VALOR_CALIBRACION_INVALIDO`, entrada `'null'` |
| ABC: `"abc"` | 400, `VALOR_CALIBRACION_INVALIDO`, entrada `'abc'` |
| Mínimo: `0.0000` | 201, registro y auditoría de creación en memoria |
| Máximo: `45.0000` | 201, registro y auditoría de creación en memoria |
| Offset fuera de rango | 400, mismo código y campo `offset`, sin calibración |
| Fallo de auditoría del rechazo | Conserva 400 y mensaje contractual; rollback |

En cada variante inválida se comprueba que no se llama a guardar calibración,
el historial simulado con IDs 10–14 permanece idéntico, el rango permanece
intacto y el evento de rechazo conserva código y motivo. Los históricos
simulados no son los registros del entorno TEST.

Antes de corregir el código, las nueve pruebas HTTP dieron **6 fallidas y
3 aprobadas**: los cinco mensajes reportados por QA y el mismo mensaje de
formato en la prueba adicional de fallo de auditoría.

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration/test_rf24_g75_mensajes_calibracion.py -q --tb=short
```

Después de corregir el código, este comando dio **20 aprobadas**:

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration/test_rf24_g75_mensajes_calibracion.py tests/test_registrar_calibracion_use_case.py tests/test_rango_calibracion.py -q --tb=short
```

La regresión existente cubre además auditoría obligatoria, rollback ante fallo,
auditoría de rechazos, 403, modo de calibración y acceso por finca.

## Regresión ampliada

Se instalaron en `.venv` los paquetes que faltaban para esta ejecución mediante
`uv pip install --python .venv/Scripts/python.exe defusedxml==0.7.1`.
Esta dependencia y versión ya estaban declaradas en `requirements.txt`; ese
archivo no cambió. Antes de instalarla, la recolección se interrumpió con tres
errores de importación de pruebas de RF-26.

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration tests/configuration tests/test_registrar_calibracion_use_case.py tests/test_rango_calibracion.py --ignore=tests/configuration/test_rf36_densidad_maxima_especie.py --ignore=tests/configuration/test_tc_m02_g12_rango_metricas.py --ignore=tests/configuration/test_tc_m02_g12_metrica_nombre_legacy.py -m 'not integration' -q --tb=short
```

Resultado: **392 aprobadas, 1 fallida y 7 errores de preparación**.
Se excluyeron los tres archivos de M02 indicados en el comando; no se ejecutó
la suite de integración. La prueba fallida fue
`test_rf26_identidad_visual_accesibilidad.py::test_la_aplicacion_sirve_el_directorio_de_logotipos`:
importar `main.py` requiere `fcntl`, no disponible en Windows.

Los siete errores provenían de los permisos del directorio temporal habitual
de pytest. Se repitieron únicamente esos siete casos, con un directorio nuevo
dentro de `.pytest_cache` y `--basetemp`, sin modificar el directorio anterior:

```powershell
.\.venv\Scripts\python.exe -m pytest --confcutdir=tests/configuration --basetemp $taskTempPath tests/configuration/test_rf26_almacen_logos.py::test_fallo_de_escritura_se_traduce_a_error_de_almacenamiento tests/configuration/test_rf26_almacen_logos.py::test_svg_valido_se_acepta tests/configuration/test_rf26_almacen_logos.py::test_svg_con_doctype_estandar_se_acepta tests/configuration/test_rf26_almacen_logos.py::test_logo_valido_escribe_y_devuelve_ruta_publica tests/configuration/test_rf26_almacen_logos.py::test_imagen_mas_grande_que_el_maximo_se_redimensiona tests/configuration/test_rf26_identidad_visual_accesibilidad.py::test_el_logo_se_guarda_bajo_la_ruta_publica_montada tests/configuration/test_rf26_identidad_visual_accesibilidad.py::test_el_logotipo_subido_se_descarga_por_su_ruta -q --tb=short
```

Resultado de la repetición: **7 aprobadas**. En conjunto se verificaron
**399 casos distintos** de este conjunto ampliado. Sigue pendiente la prueba
que requiere Linux; no se afirma que toda la suite del proyecto haya pasado.

## Diagnóstico de DEV y límites de verificación

Consulta del 7 de octubre de 2026 con `member_dev`, sobre `sgpmp_dev`,
con `transaction_read_only=on` y rollback al finalizar:

- `modulo9.sensores`: 0 registros visibles.
- `modulo9.calibraciones`: 0 registros visibles.
- `modulo9.rangos_calibracion`: la cuenta no tiene permiso SELECT.
- `modulo9.auditorias_calibraciones`: la cuenta no tiene permiso SELECT.

No se crearon fixtures, usuarios, permisos ni calibraciones en DEV. No se
aplicaron migraciones ni se guardaron credenciales en archivos. No se puede equiparar este
estado con TEST ni afirmar que se verificó allí el rango o los históricos.

La ejecución ordinaria de pytest en Windows se bloquea al importar `fcntl`
desde el `conftest` global de M02. Las pruebas de M09 se ejecutan con
`--confcutdir=tests/configuration`, sin cambiar ni simular esa dependencia.
El motor Docker local no estaba iniciado para ejecutar la suite global en Linux.

QA debe repetir los siete requests en TEST después del despliegue y verificar
mensajes, ambos límites válidos, ausencia de calibraciones inválidas e
integridad de sus históricos. El resultado oficial del grupo sigue pendiente.
