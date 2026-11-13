# INC-M05-357-G02 · RF-74 — Texto del aviso de conversión alimenticia crítica

TC-M05-007b identificó que el aviso de «Urgencia ALTA» interpolaba el ID interno del activo, el valor del enum del período y el CA con punto decimal. Se reprodujo el defecto localmente con el caso de uso real para los tres períodos.

El aviso reutiliza el activo consultado durante el cálculo y su identificador visible. Si falta el identificador, aplica la referencia de Suministros «activo seleccionado» o «lote seleccionado». El texto presenta el período como «en la semana», «en el mes» o «en el ciclo», y el CA con coma decimal y la precisión original.

> Urgencia ALTA: la conversión alimenticia del activo BOV-114-TIL es crítica (CA 8,4444 en el ciclo). Revise dieta, calidad del alimento y estado sanitario.

El aviso se solicita al puerto de notificaciones después de confirmar el cálculo y conserva el ID y el CA original en los metadatos técnicos. La fórmula, el umbral crítico, el evento de alerta del panel y la resolución de responsables siguen sus flujos existentes. El cierre de ciclo conserva su cálculo sin commit propio. La corrección no requiere migración.

## Validación

En la base de código `dfc4a682`, tres casos reprodujeron el defecto y dos controles aprobaron. Con la corrección aplicada, `tests/supplies` registró **156 pruebas aprobadas, 0 fallidas y 0 omitidas**, incluidas las cinco pruebas de esta incidencia. Los casos nuevos ejercitan el cálculo real con dobles de los puertos. Cubren tres períodos, cálculo automático y manual, reintento manual, lote sin identificador, el límite de CA 5 y el cálculo sin commit del cierre.

Queda pendiente repetir TC-M05-007b y consultar las bandejas en TEST tras el despliegue. Esta validación fue local y no ejercitó la entrega con PostgreSQL ni el batch desplegado.

Referencia [issue #1082](https://github.com/Arekkazu/sgpmp-backend/issues/1082).
