# INFORME DE INCIDENCIA TÉCNICA
## G37 — Módulo 3: Validación de rendimiento del clasificador Edge

**Fecha:** 21 de octubre de 2026  
**Proyecto:** SGPMP — Backend  
**Grupo de pruebas:** TC-M03-G37  
**Casos relacionados:** TC-M03-082 y TC-M03-102  
**Requisitos relacionados:** RF-55 y RF-55.1  
**Estado:** BLOQUEADO — requisito no validado  
**Prioridad sugerida:** Por determinar con el equipo de desarrollo según la criticidad del requisito.

### 1. Objetivo del reporte

Documentar las causas por las cuales no fue posible validar el grupo G37 del Módulo 3, identificar los componentes y las definiciones que faltan y solicitar al equipo de desarrollo las acciones necesarias para permitir la ejecución de las pruebas.

### 2. Descripción del problema

Durante la revisión y ejecución controlada de G37 se encontró que el entorno disponible no cuenta con un motor de clasificación ni con un simulador Edge identificable en el código de `src/` o `tests/`.

El grupo G37 busca verificar el rendimiento del procesamiento en Edge. Sin embargo, el backend disponible recibe eventos que ya contienen el resultado de la clasificación mediante el campo `clasificacion_rf55` del DTO `RecibirEventoEdgeDTO`.

Por esta razón, el backend recibe una clasificación previamente calculada, pero no se dispone del componente que permita medir directamente cuánto tarda el clasificador Edge en producirla.

En consecuencia, no fue posible verificar los criterios de aceptación de rendimiento definidos para G37.

### 3. Escenarios afectados

| Caso de prueba | Comportamiento esperado | Situación encontrada |
|---|---|---|
| TC-M03-082 | La latencia de clasificación Edge debe ser menor o igual a 500 ms. | No está disponible el clasificador ni el simulador Edge requerido para medir la latencia. |
| TC-M03-102 | El sistema debe soportar una ráfaga de eventos sin bloquearse, conforme a CA-12. | No se pudo validar el comportamiento del nodo Edge bajo carga. Además, la matriz no cuantifica la ráfaga necesaria para ejecutar el escenario de forma reproducible. |

### 4. Ejecución realizada

Se actualizó la información del remoto y se revisó `origin/test`. No se encontraron commits nuevos durante los dos días anteriores a la revisión. No se cambió de rama ni se incorporaron cambios que pudieran poner en riesgo el trabajo local existente.

Se realizó una única ejecución del script de G37:

`python -m pytest tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G37/test_tc_m03_g37.py --noconftest -p no:cacheprovider -vv`

**Resultado:** 2 pruebas omitidas (`skipped`) en 0,08 segundos.

La ejecución no realizó solicitudes HTTP, operaciones de base de datos ni pruebas contra el backend desplegado. Por tanto, el resultado no representa una medición de rendimiento ni una validación funcional del sistema.

**Clasificación correcta:** BLOQUEADO. No hay evidencia suficiente para declarar un defecto confirmado del backend.

### 5. Causa identificada y aspectos pendientes

**Causa principal del bloqueo**

No está disponible el componente de ejecución requerido para medir la clasificación en Edge. El requisito de rendimiento corresponde al nodo o simulador Edge, no únicamente al backend Dev.

**Aspectos adicionales pendientes**

- No se encontró un motor o simulador Edge disponible en el código inspeccionado.
- RF-55 está documentado como una funcionalidad de AIOT fuera del alcance de implementación Dev revisado.
- La matriz no especifica la cantidad de eventos, la tasa de llegada, la duración ni los criterios cuantitativos de la ráfaga del TC-M03-102.
- No se dispone de evidencia de ejecución real que permita comprobar la latencia de 500 ms ni el comportamiento bajo carga.

Estos hallazgos describen las limitaciones observadas durante la revisión. No demuestran por sí solos que la implementación completa del proyecto carezca de esos componentes en otros repositorios, dispositivos o entornos.

### 6. Solicitudes al equipo de desarrollo

Se solicita al equipo de desarrollo:

1. **Confirmar la ubicación y disponibilidad del clasificador Edge.** Determinar si ya existe en otro repositorio, dispositivo, servicio o entorno de AIOT.
2. **Proporcionar un entorno de prueba ejecutable.** Si el componente ya existe, facilitar el acceso al nodo o simulador Edge y las instrucciones necesarias para ejecutar G37.
3. **Implementar o habilitar un simulador Edge**, si el componente aún no está disponible, que permita procesar entradas de prueba y medir la latencia real de clasificación sin sustituir el comportamiento que se busca validar por un resultado previamente calculado.
4. **Definir el escenario de ráfaga del TC-M03-102.** Especificar cantidad de eventos, tasa de llegada, duración, concurrencia, comportamiento esperado y criterio objetivo para determinar si existe bloqueo.
5. **Definir las evidencias de aceptación.** Acordar cómo se medirá la latencia, qué punto marca el inicio y el final de la medición y cómo se comprobará que la carga no bloquea el procesamiento.
6. **Coordinar con QA una nueva validación controlada** una vez disponible el componente y definidos los criterios faltantes.

### 7. Criterios para cerrar la incidencia

La incidencia podrá considerarse resuelta cuando:

- El nodo o simulador Edge requerido esté disponible y pueda ejecutarse en un entorno autorizado.
- TC-M03-082 permita medir la latencia de clasificación y contrastarla con el límite de 500 ms.
- TC-M03-102 tenga parámetros de carga definidos y pueda ejecutarse de manera reproducible.
- Existan evidencias verificables de ambos escenarios.
- QA ejecute los casos y registre sus resultados, sin declarar aprobado ningún requisito que no haya sido comprobado.

La disponibilidad del componente no implica automáticamente que los casos estén aprobados; únicamente permite realizar la validación pendiente.

### 8. Evidencias asociadas

Se generaron los siguientes archivos durante la revisión:

- `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G37/Resultados/INFORME_TC-M03-G37_2026-10-21.md`
- `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G37/Resultados/TC-M03-G37-pytest.txt`
- `tests/Test_Testing/Test_Modulo3/RF-55/TC-M03-G37/Resultados/TC-M03-G37-pytest.xml`

La ejecución se realizó una sola vez. No se ejecutaron G38 ni pruebas del Módulo 4. No se realizó commit ni push.

### 9. Conclusión

El grupo G37 permanece bloqueado porque no se dispone del componente necesario para validar el rendimiento del clasificador Edge y porque el escenario de ráfaga requiere parámetros cuantitativos adicionales.

No se confirmó un defecto funcional del backend. La acción solicitada a desarrollo es confirmar la disponibilidad del componente Edge, habilitar el entorno necesario y completar las definiciones que permitan ejecutar y evaluar los dos casos de prueba.

**Estado final: BLOQUEADO — pendiente de disponibilidad del componente Edge, definición del escenario de carga y posterior validación por QA.**
