# TC-M03-G92 — estado de INC-M03-150-G92

El intento V1-2 terminó antes de RF-58: `POST /configuracion/dispositivos-iot/522/sensores` respondió HTTP 500. El registro histórico consignó DELETE del sandbox y verificación de rollback. Este antecedente documental no es una dependencia de la automatización vigente.

La orden ORD-G92-010 informa que la corrección RLS de sensores está desplegada en `origin/test` (08088948 y d3d6ec39, con 9a7fcdac y 6b116a2a para Alembic). Esto elimina el bloqueo de preparación local, pero **no acredita TEST**. El reintento V1-3 deberá comprobar por API pública la creación autorizada y lectura posterior (`RLS-G92-01`) antes de emitir veredictos RF-58.

La cuenta configurada por nombre como `QA_PROD_SIN_FINCA` se usará solo si `/usuarios/me` acredita que no tiene finca 184. `RLS-G92-02` comprueba lectura y creación denegadas; UPDATE queda no concluyente. `RLS-G92-03` queda no concluyente porque las rutas públicas de sensores revisadas no exponen UPDATE ni traslado de dispositivo. Se prohíbe usar SQL o `/test-control/query` como sustituto.

No hubo acceso a TEST ni se creó RUN en esta preparación.
