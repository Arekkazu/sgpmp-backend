# Diagn├│stico de viabilidad funcional ÔÇö TC-M06-G96 (RF-88)

Revisi├│n de c├│digo en `laura` (`e5d6934d`) y lecturas sobre `sgpmp_test` y la API `https://api.inmero.co/api-sgpmp-test`. No se ejecut├│ POST, PUT, PATCH ni DELETE. No se cerr├│ ning├║n per├¡odo. No se marc├│ APROBADO ni RECHAZADO.

La f├│rmula que el caso pide es `MAX(0, costo ÔêÆ depreciaci├│n acumulada ÔêÆ deterioro acumulado)`. Ning├║n DTO la recibe con esos tres montos. `valor_por_costo(costo_adquisicion, vida_util_meses, meses, deterioro_acumulado)` calcula la depreciaci├│n como `min(costo, costo ├ù meses / vida ├║til)`. El deterioro entra como argumento; la depreciaci├│n no.

## A. Matriz de viabilidad

| Escenario | ┬┐Se puede ejecutar funcionalmente hoy? | Endpoint o flujo necesario | Qu├® falta |
|---|---|---|---|
| TC-M06-05 | No | Reconocimiento por costo, un cierre que deje la depreciaci├│n en 2.000.000 y `POST /finanzas/activos/{id}/deterioros` con impacto 1.000.000. Verificaci├│n en `GET /finanzas/activos/{id}`. | Tablas de configuraci├│n, matriz, l├¡neas y comprobantes. Activo aislado con costo 10.000.000, sin precio de mercado, vida ├║til 10 meses y 2 meses transcurridos. Token. El cierre no puede usar un NIT que ya tenga otros activos reconocidos. |
| TC-M06-06 | No | El mismo reconocimiento y un cierre con vida ├║til ya cumplida. No hace falta deterioro. | Las mismas tablas y el mismo aislamiento. Vida ├║til 1 mes y al menos un mes transcurrido, para que la depreciaci├│n quede topada en el costo. |
| TC-M06-07 | No, ni despu├®s de crear las tablas | Cierre con 7 meses de 10 de vida ├║til y luego deterioro de 5.000.000. | Todo lo de TC-M06-05, m├ís una alerta que el c├│digo no genera. El piso en cero s├¡ est├í en el caso de uso y en el trigger. |

Clasificaci├│n de la secci├│n E: TC-M06-05 y TC-M06-06 son **viables con ajustes**. TC-M06-07 est├í **bloqueado** en el resultado completo, porque la alerta no existe.

## B. Flujo que el c├│digo permite, y qu├® responder├¡a cada paso

Este orden es el ├║nico que puede acercarse a los montos. No est├í ejecutado.

1. `GET /finanzas/configuracion`  
   Permiso `configuracion_contable` lectura. Hoy, sin token, respondi├│ 401 `TOKEN_REQUERIDO` el 2026-11-08T02:06:43Z. Con token, `config.obtener()` lee `modulo6.configuraciones_contables` id 1 y el mismo GET cuenta l├¡neas en `lineas_asiento_nic41`. Esas tablas no est├ín. No hay respuesta de negocio que verificar.

2. `PUT /finanzas/configuracion`  
   Cuerpo: `tipo_cierre` (`MENSUAL`, `TRIMESTRAL` o `ANUAL`), `pct_umbral_desviacion_precio` y `dias_alerta_vencimiento_precio` (7, 15 o 30). Actualiza la configuraci├│n de todo el m├│dulo. El campo de alertas es el vencimiento de precios, no el valor en libros. No se debe llamar sobre la configuraci├│n compartida.

3. `PUT /finanzas/configuracion/especies/{id_especie}`  
   Cuerpo: `clasificacion` (`PRODUCCION` o `CONSUMO`), `categoria_precio` y `vida_util_meses` de 1 a 1200. La vida ├║til es de la especie, no del activo. El cierre posterior la aplica a todos los activos de esa especie valorados por costo. Para 10.000.000 exactos: vida 10 y 2 meses (depreciaci├│n 2.000.000), vida 1 y 1 mes o m├ís (depreciaci├│n 10.000.000), o vida 10 y 7 meses (depreciaci├│n 7.000.000).

4. `PUT /finanzas/configuracion/costos-venta/{id_especie}` y `POST /finanzas/configuracion/matriz`  
   Los costos de venta alimentan el valor razonable. La matriz asigna cuentas de un hecho (`DEPRECIACION_ACTIVO_COSTO` y `DETERIORO_ACTIVO_COSTO`, sentido `UNICO`) a d├®bito y cr├®dito distintos. Sin esas filas, el cierre deja l├¡neas `PENDIENTE_CUENTA` y luego rechaza con `CIERRE_BLOQUEADO`.

5. Activo aislado, fuera de estos endpoints.  
   `POST /finanzas/reconocimientos/{id}` no recibe el costo. Lo toma de `costo_adquisicion` del activo biol├│gico. Para el caso tiene que ser exactamente 10.000.000, origen compra o donaci├│n, sin precio de mercado vigente en la fecha de ingreso ni hoy, con NIT propio y sin otros activos reconocidos de ese NIT. La fecha de ingreso define los meses: `meses_transcurridos` cuenta meses de calendario entre esa fecha y el fin del per├¡odo, limitado a hoy.

6. `GET /finanzas/reconocimientos/propuestas/{id_activo_biologico}`  
   Solo lectura. Una propuesta confirmable por costo trae `indicador_valoracion = VALORACION_POR_COSTO` y `valor_inicial` igual al costo. Si hay precio hoy, el c├│digo bloquea con `PRECIO_NO_VIGENTE_EN_FECHA` y no pasa a costo. Si falta vida ├║til, bloquea con `VIDA_UTIL_NO_CONFIGURADA`.

7. `POST /finanzas/reconocimientos/{id_activo_biologico}`  
   Cuerpo opcional: `clasificacion`, `costos_manuales`, `justificacion`. En compra por costo no arma hechos contables. Guarda depreciaci├│n 0, deterioro 0 y valor en libros igual al costo. La respuesta trae `indicador_valoracion`, `valor_inicial` y `lineas`. No demuestra 7.000.000, 0 ni el piso del resultado negativo.

8. `GET /finanzas/periodos` y `GET /finanzas/periodos/{id}/prevalidacion`  
   La prevalidaci├│n recorre todos los activos reconocidos del mismo NIT. Bloquea si hay un per├¡odo anterior abierto, l├¡neas sin cuenta, costos sin clasificar o entregas de suministros pendientes. Los activos a valor razonable sin precio exigen `autorizar_exclusiones` o `incluir_activos_sin_precio`.

9. `POST /finanzas/periodos/{id}/cierre`  
   Cuerpo: `autorizar_exclusiones`, `incluir_activos_sin_precio`. No recibe depreciaci├│n. Antes de depreciar procesa hasta 2000 eventos pendientes de M02. Pasa el per├¡odo a `EN_CIERRE`, deprecia cada activo a costo de ese NIT y reval├║a los que est├ín a valor razonable. Genera l├¡neas, comprobantes, cierra el per├¡odo, abre el siguiente y notifica a los usuarios con rol Contador el evento `CIERRE_PERIODO_CONTABLE`. `_depreciar` solo actualiza si el delta del per├¡odo es mayor que cero y deja en auditor├¡a `DEPRECIACION_REGISTRADA`, con `totalmente_depreciado` dentro del payload. Eso es auditor├¡a del cierre, no la alerta de TC-M06-07.

10. `GET /finanzas/activos/{id_activo_biologico}/eventos-sanitarios` y `POST /finanzas/activos/{id}/deterioros`  
    El POST exige `id_evento_sanitario` del mismo activo, `impacto_economico_cop` mayor que cero y `justificacion` de al menos 30 caracteres. No recibe depreciaci├│n ni el valor en libros deseado. Suma el impacto completo al deterioro acumulado, recalcula `MAX(0, costo ÔêÆ depreciaci├│n ÔêÆ deterioro)` y contabiliza solo `min(impacto, valor en libros anterior)`. La respuesta es `id_deterioro_activo`, `valor_contable` y, si el valor qued├│ en cero, un texto `aviso`. Para TC-M06-05 el impacto es 1.000.000 y el valor esperado es 7.000.000, sin `aviso`. Para TC-M06-07 el impacto es 5.000.000 despu├®s de tener depreciaci├│n 7.000.000; el valor esperado es 0 y aparece `aviso`. TC-M06-06 no usa este POST.

11. `GET /finanzas/activos/{id}`  
    Devuelve `valoracion_costo` con costo, vida ├║til, depreciaci├│n, deterioro y valor en libros, m├ís las l├¡neas del activo. Esa lectura consulta `lineas_asiento_nic41`. Mientras la tabla no exista, el historial no puede confirmar la persistencia.

12. `GET /finanzas/auditoria?id_activo_biologico={id}&tipo_evento=DETERIORO_REGISTRADO`  
    Permiso `auditoria_financiera` lectura. Filtros reales: `tipo_evento`, per├¡odo, activo, severidad, fechas, p├ígina y formato `LEGIBLE` o `TECNICO`. Sirve para ver el evento que el deterioro siempre escribe. No demuestra la alerta del caso.

Estos endpoints no forman parte del c├ílculo:

- `GET /finanzas/activos/{id}/simulacion` calcula valor razonable menos costos de venta y no lo guarda.
- `POST /finanzas/activos/{id}/valor-razonable` abandona el modelo de costo.
- `POST /finanzas/costos`, si capitaliza, suma el monto al costo y al valor en libros. No fija la depreciaci├│n acumulada.
- `GET` de mediciones, c├ílculos y variaciones muestran valor razonable del per├¡odo, no la f├│rmula por costo.

## C. Bloqueos

Comprobado de nuevo en `sgpmp_test`, solo con SELECT:

| Objeto | Estado | Consecuencia |
|---|---|---|
| `modulo6.configuraciones_contables` | Ausente | Reconocimiento, deterioro y cierre se detienen en `config.obtener()`. |
| `modulo6.parametros_contables_especies` | Ausente | No hay vida ├║til. Sin ella el reconocimiento por costo responde `VIDA_UTIL_NO_CONFIGURADA`. |
| `modulo6.asignaciones_cuentas_contables` | Ausente | La depreciaci├│n y el deterioro no resuelven cuentas. |
| `modulo6.lineas_asiento_nic41` | Ausente | No se puede asentar la depreciaci├│n ni el deterioro, ni leer el historial completo. |
| `modulo6.comprobantes_nic41` | Ausente | El cierre no guarda el comprobante. |
| `modulo6.valoraciones_por_costos` | Presente, 0 filas con costo 10.000.000 | El trigger `tgr_m06_12_valor_contable_no_negativo` y `chk_valcosto_valor_contable_no_negativo` impiden guardar un valor negativo. No se insert├│ ninguna fila de prueba. |
| `modulo6.periodos_contables` y `ejecuciones_cierre_periodo` | Presentes | Hay 8 per├¡odos. Cerrar uno existente afecta los activos ya reconocidos de su NIT. Hay 15 reconocimientos. |
| Token Bearer | No disponible en esta revisi├│n | Los GET de negocio respondieron 401. |

El cierre no es una operaci├│n de un activo. `listar_reconocidos` trae todos los confirmados del mismo `numero_id_tributaria` que sigan en estado valorable. Deprecia los de costo y remide los de valor razonable. Tambi├®n procesa eventos M02 pendientes de forma global, cambia el estado del per├¡odo y avisa a todos los contadores. Usar un per├¡odo o un NIT ya poblado no es una prueba aislada.

`member_qa` puede insertar en las tablas que ya existen. No se hizo. Crear las cinco tablas ausentes es cambio de esquema y queda fuera de esta etapa.

## D. Validaci├│n de la alerta

No hay una alerta cuando el deterioro deja el valor en libros en cero.

- `valor_por_costo` devuelve el valor ya limitado a cero y el booleano `totalmente_depreciado`. No llama al notificador.
- El trigger, si la resta es negativa, asigna `valor_contable_por_costo = 0` y termina. No inserta aviso ni hace `RAISE` por ese motivo. El `RAISE` ocurre si el resultado no es negativo y el valor enviado no coincide, con tolerancia 0,01.
- `RegistrarDeterioroUseCase` pone en la respuesta HTTP: ┬½El activo {identificador} lleg├│ a valor contable cero por depreciaci├│n y deterioro. Eval├║e registrar su baja o revisar la vida ├║til de la especie.┬╗ Ese texto no se inserta en `modulo1.notificaciones` ni en `auditorias_financieras`.
- El evento `DETERIORO_REGISTRADO`, severidad `WARNING`, se escribe en todo deterioro, tambi├®n cuando el valor sigue positivo. Su payload trae el impacto y el valor contable resultante. Consultarlo en `GET /finanzas/auditoria` no distingue el caso del piso.
- `DEPRECIACION_REGISTRADA` incluye `totalmente_depreciado` solo si ese cierre calcul├│ depreciaci├│n nueva.
- `a_contadores` se usa para `ALERTA_FINANCIERA_NIC41` en precios y para `CIERRE_PERIODO_CONTABLE` al cerrar. `registrar_deterioro` no lo llama. `dias_alerta_vencimiento_precio` no tiene relaci├│n con el valor en libros.

No existe, por tanto, un registro consultable que sea la alerta exigida por TC-M06-07.

## E. Conclusi├│n

| Escenario | Clasificaci├│n | Fundamento |
|---|---|---|
| TC-M06-05 | Viable con ajustes | El cierre puede dejar la depreciaci├│n en 2.000.000 si la vida ├║til es 10 y han pasado 2 meses, y el deterioro de 1.000.000 deja el valor en 7.000.000. Hoy no se puede ejecutar: faltan tablas, token y un activo aislado. |
| TC-M06-06 | Viable con ajustes | Con la vida ├║til cumplida, el cierre topa la depreciaci├│n en el costo y el valor queda en 0 sin deterioro. Mismos ajustes de esquema y aislamiento. |
| TC-M06-07 | Bloqueado | El piso en cero se puede preparar con los mismos ajustes, pero ninguna operaci├│n genera ni guarda la alerta. Completar las tablas no vuelve ejecutable el resultado completo. |

Ning├║n escenario es viable con los componentes ya disponibles en TEST.

## F. Pr├│ximo paso

Para Desarrollo, antes de intentar TC-M06-07:

- Emitir una alerta distinta de `DETERIORO_REGISTRADO` y del texto `aviso` cuando la resta sea negativa y el valor quede en cero.
- Guardarla donde `GET /finanzas/auditoria` o la bandeja de `modulo1.notificaciones` pueda filtrarla por activo.
- El contrato actual no acepta los tres montos. El flujo indirecto s├¡ puede producirlos si la vida ├║til y la fecha de ingreso quedan bajo control de la prueba. Un endpoint que reciba costo, depreciaci├│n y deterioro solo har├¡a falta si QA no puede disponer de un activo aislado con esa fecha y esa vida ├║til.

Para el DBA, sin repetir la migraci├│n completa sobre objetos que ya existen:

- Crear `configuraciones_contables`, `parametros_contables_especies`, `asignaciones_cuentas_contables`, `lineas_asiento_nic41` y `comprobantes_nic41`.
- Conservar `valoraciones_por_costos`, `deterioros_activos`, `periodos_contables` y `ejecuciones_cierre_periodo`.

Escrituras que no se har├ín sin autorizaci├│n, y que no bastan mientras falten las tablas:

1. Una finca, un NIT y un activo nuevos, con costo de adquisici├│n 10.000.000, fecha de ingreso calculada para 2, 1 o 7 meses, y ning├║n otro activo reconocido en ese NIT.
2. La fila ├║nica de `configuraciones_contables` y la vida ├║til de una especie que no est├® en uso por activos ya reconocidos.
3. Dos asignaciones de matriz: `DEPRECIACION_ACTIVO_COSTO` y `DETERIORO_ACTIVO_COSTO`, sentido `UNICO`.
4. `POST /finanzas/reconocimientos/{id}` de ese activo.
5. Un per├¡odo de ese NIT y un solo `POST /finanzas/periodos/{id}/cierre`.
6. Para TC-M06-05 y TC-M06-07, un evento sanitario de ese activo y `POST /finanzas/activos/{id}/deterioros`.
7. `GET /finanzas/activos/{id}` y `GET /finanzas/auditoria`.

Riesgo si se usa lo ya cargado: el cierre depreciar├¡a o revaluar├¡a los activos de los 15 reconocimientos existentes, cerrar├¡a uno de los 8 per├¡odos y notificar├¡a a los contadores. Las dos valoraciones actuales (2.800.000 y 4.500.000) no sirven para estos montos y no deben modificarse.

Hasta esa autorizaci├│n, y hasta que exista la alerta, TC-M06-05 y TC-M06-06 siguen sin ejecuci├│n funcional y TC-M06-07 sigue bloqueado.
