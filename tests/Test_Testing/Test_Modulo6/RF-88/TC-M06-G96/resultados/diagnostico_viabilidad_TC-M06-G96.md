# Diagnóstico de viabilidad funcional — TC-M06-G96 (RF-88)

Revisión de código en `laura` (`e5d6934d`) y lecturas sobre `sgpmp_test` y la API `https://api.inmero.co/api-sgpmp-test`. No se ejecutó POST, PUT, PATCH ni DELETE. No se cerró ningún período. No se marcó APROBADO ni RECHAZADO.

La fórmula que el caso pide es `MAX(0, costo − depreciación acumulada − deterioro acumulado)`. Ningún DTO la recibe con esos tres montos. `valor_por_costo(costo_adquisicion, vida_util_meses, meses, deterioro_acumulado)` calcula la depreciación como `min(costo, costo × meses / vida útil)`. El deterioro entra como argumento; la depreciación no.

## A. Matriz de viabilidad

| Escenario | ¿Se puede ejecutar funcionalmente hoy? | Endpoint o flujo necesario | Qué falta |
|---|---|---|---|
| TC-M06-05 | No | Reconocimiento por costo, un cierre que deje la depreciación en 2.000.000 y `POST /finanzas/activos/{id}/deterioros` con impacto 1.000.000. Verificación en `GET /finanzas/activos/{id}`. | Tablas de configuración, matriz, líneas y comprobantes. Activo aislado con costo 10.000.000, sin precio de mercado, vida útil 10 meses y 2 meses transcurridos. Token. El cierre no puede usar un NIT que ya tenga otros activos reconocidos. |
| TC-M06-06 | No | El mismo reconocimiento y un cierre con vida útil ya cumplida. No hace falta deterioro. | Las mismas tablas y el mismo aislamiento. Vida útil 1 mes y al menos un mes transcurrido, para que la depreciación quede topada en el costo. |
| TC-M06-07 | No, ni después de crear las tablas | Cierre con 7 meses de 10 de vida útil y luego deterioro de 5.000.000. | Todo lo de TC-M06-05, más una alerta que el código no genera. El piso en cero sí está en el caso de uso y en el trigger. |

Clasificación de la sección E: TC-M06-05 y TC-M06-06 son **viables con ajustes**. TC-M06-07 está **bloqueado** en el resultado completo, porque la alerta no existe.

## B. Flujo que el código permite, y qué respondería cada paso

Este orden es el único que puede acercarse a los montos. No está ejecutado.

1. `GET /finanzas/configuracion`  
   Permiso `configuracion_contable` lectura. Hoy, sin token, respondió 401 `TOKEN_REQUERIDO` el 2026-11-08T02:06:43Z. Con token, `config.obtener()` lee `modulo6.configuraciones_contables` id 1 y el mismo GET cuenta líneas en `lineas_asiento_nic41`. Esas tablas no están. No hay respuesta de negocio que verificar.

2. `PUT /finanzas/configuracion`  
   Cuerpo: `tipo_cierre` (`MENSUAL`, `TRIMESTRAL` o `ANUAL`), `pct_umbral_desviacion_precio` y `dias_alerta_vencimiento_precio` (7, 15 o 30). Actualiza la configuración de todo el módulo. El campo de alertas es el vencimiento de precios, no el valor en libros. No se debe llamar sobre la configuración compartida.

3. `PUT /finanzas/configuracion/especies/{id_especie}`  
   Cuerpo: `clasificacion` (`PRODUCCION` o `CONSUMO`), `categoria_precio` y `vida_util_meses` de 1 a 1200. La vida útil es de la especie, no del activo. El cierre posterior la aplica a todos los activos de esa especie valorados por costo. Para 10.000.000 exactos: vida 10 y 2 meses (depreciación 2.000.000), vida 1 y 1 mes o más (depreciación 10.000.000), o vida 10 y 7 meses (depreciación 7.000.000).

4. `PUT /finanzas/configuracion/costos-venta/{id_especie}` y `POST /finanzas/configuracion/matriz`  
   Los costos de venta alimentan el valor razonable. La matriz asigna cuentas de un hecho (`DEPRECIACION_ACTIVO_COSTO` y `DETERIORO_ACTIVO_COSTO`, sentido `UNICO`) a débito y crédito distintos. Sin esas filas, el cierre deja líneas `PENDIENTE_CUENTA` y luego rechaza con `CIERRE_BLOQUEADO`.

5. Activo aislado, fuera de estos endpoints.  
   `POST /finanzas/reconocimientos/{id}` no recibe el costo. Lo toma de `costo_adquisicion` del activo biológico. Para el caso tiene que ser exactamente 10.000.000, origen compra o donación, sin precio de mercado vigente en la fecha de ingreso ni hoy, con NIT propio y sin otros activos reconocidos de ese NIT. La fecha de ingreso define los meses: `meses_transcurridos` cuenta meses de calendario entre esa fecha y el fin del período, limitado a hoy.

6. `GET /finanzas/reconocimientos/propuestas/{id_activo_biologico}`  
   Solo lectura. Una propuesta confirmable por costo trae `indicador_valoracion = VALORACION_POR_COSTO` y `valor_inicial` igual al costo. Si hay precio hoy, el código bloquea con `PRECIO_NO_VIGENTE_EN_FECHA` y no pasa a costo. Si falta vida útil, bloquea con `VIDA_UTIL_NO_CONFIGURADA`.

7. `POST /finanzas/reconocimientos/{id_activo_biologico}`  
   Cuerpo opcional: `clasificacion`, `costos_manuales`, `justificacion`. En compra por costo no arma hechos contables. Guarda depreciación 0, deterioro 0 y valor en libros igual al costo. La respuesta trae `indicador_valoracion`, `valor_inicial` y `lineas`. No demuestra 7.000.000, 0 ni el piso del resultado negativo.

8. `GET /finanzas/periodos` y `GET /finanzas/periodos/{id}/prevalidacion`  
   La prevalidación recorre todos los activos reconocidos del mismo NIT. Bloquea si hay un período anterior abierto, líneas sin cuenta, costos sin clasificar o entregas de suministros pendientes. Los activos a valor razonable sin precio exigen `autorizar_exclusiones` o `incluir_activos_sin_precio`.

9. `POST /finanzas/periodos/{id}/cierre`  
   Cuerpo: `autorizar_exclusiones`, `incluir_activos_sin_precio`. No recibe depreciación. Antes de depreciar procesa hasta 2000 eventos pendientes de M02. Pasa el período a `EN_CIERRE`, deprecia cada activo a costo de ese NIT y revalúa los que están a valor razonable. Genera líneas, comprobantes, cierra el período, abre el siguiente y notifica a los usuarios con rol Contador el evento `CIERRE_PERIODO_CONTABLE`. `_depreciar` solo actualiza si el delta del período es mayor que cero y deja en auditoría `DEPRECIACION_REGISTRADA`, con `totalmente_depreciado` dentro del payload. Eso es auditoría del cierre, no la alerta de TC-M06-07.

10. `GET /finanzas/activos/{id_activo_biologico}/eventos-sanitarios` y `POST /finanzas/activos/{id}/deterioros`  
    El POST exige `id_evento_sanitario` del mismo activo, `impacto_economico_cop` mayor que cero y `justificacion` de al menos 30 caracteres. No recibe depreciación ni el valor en libros deseado. Suma el impacto completo al deterioro acumulado, recalcula `MAX(0, costo − depreciación − deterioro)` y contabiliza solo `min(impacto, valor en libros anterior)`. La respuesta es `id_deterioro_activo`, `valor_contable` y, si el valor quedó en cero, un texto `aviso`. Para TC-M06-05 el impacto es 1.000.000 y el valor esperado es 7.000.000, sin `aviso`. Para TC-M06-07 el impacto es 5.000.000 después de tener depreciación 7.000.000; el valor esperado es 0 y aparece `aviso`. TC-M06-06 no usa este POST.

11. `GET /finanzas/activos/{id}`  
    Devuelve `valoracion_costo` con costo, vida útil, depreciación, deterioro y valor en libros, más las líneas del activo. Esa lectura consulta `lineas_asiento_nic41`. Mientras la tabla no exista, el historial no puede confirmar la persistencia.

12. `GET /finanzas/auditoria?id_activo_biologico={id}&tipo_evento=DETERIORO_REGISTRADO`  
    Permiso `auditoria_financiera` lectura. Filtros reales: `tipo_evento`, período, activo, severidad, fechas, página y formato `LEGIBLE` o `TECNICO`. Sirve para ver el evento que el deterioro siempre escribe. No demuestra la alerta del caso.

Estos endpoints no forman parte del cálculo:

- `GET /finanzas/activos/{id}/simulacion` calcula valor razonable menos costos de venta y no lo guarda.
- `POST /finanzas/activos/{id}/valor-razonable` abandona el modelo de costo.
- `POST /finanzas/costos`, si capitaliza, suma el monto al costo y al valor en libros. No fija la depreciación acumulada.
- `GET` de mediciones, cálculos y variaciones muestran valor razonable del período, no la fórmula por costo.

## C. Bloqueos

Comprobado de nuevo en `sgpmp_test`, solo con SELECT:

| Objeto | Estado | Consecuencia |
|---|---|---|
| `modulo6.configuraciones_contables` | Ausente | Reconocimiento, deterioro y cierre se detienen en `config.obtener()`. |
| `modulo6.parametros_contables_especies` | Ausente | No hay vida útil. Sin ella el reconocimiento por costo responde `VIDA_UTIL_NO_CONFIGURADA`. |
| `modulo6.asignaciones_cuentas_contables` | Ausente | La depreciación y el deterioro no resuelven cuentas. |
| `modulo6.lineas_asiento_nic41` | Ausente | No se puede asentar la depreciación ni el deterioro, ni leer el historial completo. |
| `modulo6.comprobantes_nic41` | Ausente | El cierre no guarda el comprobante. |
| `modulo6.valoraciones_por_costos` | Presente, 0 filas con costo 10.000.000 | El trigger `tgr_m06_12_valor_contable_no_negativo` y `chk_valcosto_valor_contable_no_negativo` impiden guardar un valor negativo. No se insertó ninguna fila de prueba. |
| `modulo6.periodos_contables` y `ejecuciones_cierre_periodo` | Presentes | Hay 8 períodos. Cerrar uno existente afecta los activos ya reconocidos de su NIT. Hay 15 reconocimientos. |
| Token Bearer | No disponible en esta revisión | Los GET de negocio respondieron 401. |

El cierre no es una operación de un activo. `listar_reconocidos` trae todos los confirmados del mismo `numero_id_tributaria` que sigan en estado valorable. Deprecia los de costo y remide los de valor razonable. También procesa eventos M02 pendientes de forma global, cambia el estado del período y avisa a todos los contadores. Usar un período o un NIT ya poblado no es una prueba aislada.

`member_qa` puede insertar en las tablas que ya existen. No se hizo. Crear las cinco tablas ausentes es cambio de esquema y queda fuera de esta etapa.

## D. Validación de la alerta

No hay una alerta cuando el deterioro deja el valor en libros en cero.

- `valor_por_costo` devuelve el valor ya limitado a cero y el booleano `totalmente_depreciado`. No llama al notificador.
- El trigger, si la resta es negativa, asigna `valor_contable_por_costo = 0` y termina. No inserta aviso ni hace `RAISE` por ese motivo. El `RAISE` ocurre si el resultado no es negativo y el valor enviado no coincide, con tolerancia 0,01.
- `RegistrarDeterioroUseCase` pone en la respuesta HTTP: «El activo {identificador} llegó a valor contable cero por depreciación y deterioro. Evalúe registrar su baja o revisar la vida útil de la especie.» Ese texto no se inserta en `modulo1.notificaciones` ni en `auditorias_financieras`.
- El evento `DETERIORO_REGISTRADO`, severidad `WARNING`, se escribe en todo deterioro, también cuando el valor sigue positivo. Su payload trae el impacto y el valor contable resultante. Consultarlo en `GET /finanzas/auditoria` no distingue el caso del piso.
- `DEPRECIACION_REGISTRADA` incluye `totalmente_depreciado` solo si ese cierre calculó depreciación nueva.
- `a_contadores` se usa para `ALERTA_FINANCIERA_NIC41` en precios y para `CIERRE_PERIODO_CONTABLE` al cerrar. `registrar_deterioro` no lo llama. `dias_alerta_vencimiento_precio` no tiene relación con el valor en libros.

No existe, por tanto, un registro consultable que sea la alerta exigida por TC-M06-07.

## E. Conclusión

| Escenario | Clasificación | Fundamento |
|---|---|---|
| TC-M06-05 | Viable con ajustes | El cierre puede dejar la depreciación en 2.000.000 si la vida útil es 10 y han pasado 2 meses, y el deterioro de 1.000.000 deja el valor en 7.000.000. Hoy no se puede ejecutar: faltan tablas, token y un activo aislado. |
| TC-M06-06 | Viable con ajustes | Con la vida útil cumplida, el cierre topa la depreciación en el costo y el valor queda en 0 sin deterioro. Mismos ajustes de esquema y aislamiento. |
| TC-M06-07 | Bloqueado | El piso en cero se puede preparar con los mismos ajustes, pero ninguna operación genera ni guarda la alerta. Completar las tablas no vuelve ejecutable el resultado completo. |

Ningún escenario es viable con los componentes ya disponibles en TEST.

## F. Próximo paso

Para Desarrollo, antes de intentar TC-M06-07:

- Emitir una alerta distinta de `DETERIORO_REGISTRADO` y del texto `aviso` cuando la resta sea negativa y el valor quede en cero.
- Guardarla donde `GET /finanzas/auditoria` o la bandeja de `modulo1.notificaciones` pueda filtrarla por activo.
- El contrato actual no acepta los tres montos. El flujo indirecto sí puede producirlos si la vida útil y la fecha de ingreso quedan bajo control de la prueba. Un endpoint que reciba costo, depreciación y deterioro solo haría falta si QA no puede disponer de un activo aislado con esa fecha y esa vida útil.

Para el DBA, sin repetir la migración completa sobre objetos que ya existen:

- Crear `configuraciones_contables`, `parametros_contables_especies`, `asignaciones_cuentas_contables`, `lineas_asiento_nic41` y `comprobantes_nic41`.
- Conservar `valoraciones_por_costos`, `deterioros_activos`, `periodos_contables` y `ejecuciones_cierre_periodo`.

Escrituras que no se harán sin autorización, y que no bastan mientras falten las tablas:

1. Una finca, un NIT y un activo nuevos, con costo de adquisición 10.000.000, fecha de ingreso calculada para 2, 1 o 7 meses, y ningún otro activo reconocido en ese NIT.
2. La fila única de `configuraciones_contables` y la vida útil de una especie que no esté en uso por activos ya reconocidos.
3. Dos asignaciones de matriz: `DEPRECIACION_ACTIVO_COSTO` y `DETERIORO_ACTIVO_COSTO`, sentido `UNICO`.
4. `POST /finanzas/reconocimientos/{id}` de ese activo.
5. Un período de ese NIT y un solo `POST /finanzas/periodos/{id}/cierre`.
6. Para TC-M06-05 y TC-M06-07, un evento sanitario de ese activo y `POST /finanzas/activos/{id}/deterioros`.
7. `GET /finanzas/activos/{id}` y `GET /finanzas/auditoria`.

Riesgo si se usa lo ya cargado: el cierre depreciaría o revaluaría los activos de los 15 reconocimientos existentes, cerraría uno de los 8 períodos y notificaría a los contadores. Las dos valoraciones actuales (2.800.000 y 4.500.000) no sirven para estos montos y no deben modificarse.

Hasta esa autorización, y hasta que exista la alerta, TC-M06-05 y TC-M06-06 siguen sin ejecución funcional y TC-M06-07 sigue bloqueado.
