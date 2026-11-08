# TC-M06-G82

No se usó SQL local. Las lecturas salieron de la API de TEST.

- TC-M06-35: BLOQUEADO. Registrar un alimento o medicamento válido crea el costo, puede generar asiento o factura y audita COSTO_REGISTRADO en el período compartido. No hay un activo aislado ni autorización para esa escritura.
- TC-M06-36: APROBADO. 0 y -100 respondieron 400 VAL_ENTRADA. La cantidad de costos, la auditoría y el valor en libros quedaron iguales.
- TC-M06-38: APROBADO. Un alimento declarado como inversión y con confirmación de capitalización respondió 422 RECLASIFICACION_NO_PERMITIDA. No se creó el costo y el valor en libros del activo 951 no cambió.

El mantenimiento queda en política GASTO. La suma al valor contable solo ocurre con política CAPITALIZAR, reservada a una inversión confirmada sobre un activo valorado por costo.
