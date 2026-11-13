# INC-M05-350-G05 e INC-M05-351-G05 · RF-74 — Interrupción manual del batch ICA

La evidencia de TC-M05-015d mostró que el corte detenía el procesamiento, pero guardaba el motivo libre en el campo de causa y omitía el aviso de interrupción. El caso de uso copiaba el motivo como causa. El worker solo activaba el aviso de cierre cuando detectaba la ventana excedida.

La interrupción manual guarda `MANUAL`, el operador y la hora de corte. El texto opcional se guarda en `motivo_interrupcion` y se devuelve en el resultado y el panel. La revisión `f108174bc001` parte de `603631775892` y recupera el motivo de las corridas históricas cuya interrupción registró un operador y una causa distinta de `MANUAL`. Los cortes automáticos mantienen sus causas de catálogo.

El caso de uso confirma el corte y envía `BATCH_ICA_INTERRUMPIDO` a las cuentas activas de Administrador y Productor. La sesión de servicio existente permite emitir el evento y la notificación para cada destinatario, de modo que la bandeja pueda leerlos con RLS activa. El aviso contiene el identificador de la corrida y su causa. El motivo queda en el panel autorizado. La migración anterior retiró al Productor el acceso administrativo al batch y el aviso se resuelve por rol.

La interrupción y la finalización bloquean la misma fila para serializar sus transiciones. La finalización conserva el corte que ya se confirmó y actualiza las métricas. El worker sigue encolando los activos que aún no ha iniciado. Una solicitud repetida recibe `422 BATCH_NO_EN_EJECUCION`.

El envío conserva el comportamiento de mejor esfuerzo de M05. Una falla posterior al commit queda en el log del adaptador. La bandeja no tiene reintento durable en este flujo.

## Validación

- 16 pruebas focalizadas con dobles aprobaron. Cubren el corte, las métricas finales, la preservación de pendientes por el worker, el aviso posterior al commit, el corte por ventana y la recuperación de corridas huérfanas.
- 2 pruebas de integración aprobaron en PostgreSQL 18. Se verificaron corte y panel HTTP, respuestas 404/409/422, restricción del Productor en el batch, aviso en ambas bandejas con JWT y RLS, ausencia de duplicados, y conservación de causas y motivos históricos al migrar.
- La integración creó una corrida controlada y verificó el corte por HTTP. La reacción del worker se comprobó aparte con dobles. Queda pendiente repetir TC-M05-015d con una corrida activa en TEST tras desplegar la migración.

Referencia [issue #1081](https://github.com/Arekkazu/sgpmp-backend/issues/1081).
