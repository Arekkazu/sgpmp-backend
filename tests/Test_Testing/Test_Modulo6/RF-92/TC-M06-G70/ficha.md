# TC-M06-G70 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-12 (TC-92-073 a TC-92-080, TC-92-081). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Formatos de salida, rendimiento y retención (RNF-92-01 a RNF-92-05): PDF validado contra PDF/A-1 y Excel compatible con la plantilla UPRA con valores idénticos entre ambos; generación del BORRADOR en ≤ 30 segundos y validación de consistencia en ≤ 5 segundos para hasta 1.000 activos; 10 informes simultáneos sin degradación; y disponibilidad de informes APROBADOS y ARCHIVADOS tras simular la retención de 10 años.

### TC-92-073 — Generar el informe en formato PDF_A1 y validarlo contra el estándar PDF/A-1 con un verificador independiente
- **Tipo:** Funcional / cumplimiento · **Prioridad:** Alta · **Ejecutable:** Parcial: se comprueba que es PDF y que declara PDF/A; la validación completa requiere veraPDF.
- **Pasos:** «TC-92-073 PDF del informe APROBADO».

### TC-92-074 — Generar el informe en formato EXCEL_UPRA y verificar su compatibilidad con la plantilla UPRA
- **Tipo:** Funcional / cumplimiento · **Prioridad:** Alta · **Ejecutable:** Parcial: se comprueba el tipo de archivo; la plantilla UPRA se revisa a mano.
- **Pasos:** «TC-92-074 Excel del informe APROBADO».

### TC-92-075 — Comparar los valores de las 9 secciones entre el PDF y el Excel del mismo informe
- **Tipo:** Funcional / cumplimiento · **Prioridad:** Alta · **Ejecutable:** Manual: comparar el PDF y el Excel descargados.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** coincidencia exacta.

### TC-92-076 — Medir la generación del BORRADOR para un período de 1.000 activos
- **Tipo:** Rendimiento · **Prioridad:** Alta · **Ejecutable:** Sí, con escritura, con el volumen que tenga TEST (no 1.000 activos).
- **Pasos:** «TC-92-076 Generacion del BORRADOR en <= 30 s [escritura]».
- **Esperado (matriz):** ≤ 30 segundos.

### TC-92-077 — Medir la validación de consistencia del paso 3 para un período de 1.000 activos
- **Tipo:** Rendimiento · **Prioridad:** Alta · **Ejecutable:** Bloqueado: la validación de consistencia no tiene endpoint propio.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** ≤ 5 segundos.

### TC-92-078 — Generar 10 informes de períodos distintos de forma simultánea
- **Tipo:** Rendimiento · **Prioridad:** Alta · **Ejecutable:** Requiere k6 y visto bueno: 10 informes simultáneos sobre el TEST compartido.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** que no haya degradación.

### TC-92-079 — Consultar un informe APROBADO tras simular el envejecimiento conforme a la retención de 10 años
- **Tipo:** No funcional / retención · **Prioridad:** Alta · **Ejecutable:** Bloqueado: requiere simular 10 años de antigüedad en la base de datos.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** disponibilidad íntegra.

### TC-92-080 — Consultar un informe ARCHIVADO tras el envejecimiento simulado
- **Tipo:** No funcional / retención · **Prioridad:** Alta · **Ejecutable:** Bloqueado: misma razón.
- **Pasos:** sin petición automatizada (ver Ejecutable).
- **Esperado (matriz):** disponibilidad íntegra para consulta del auditor.

### TC-92-081 — Revisar el informe en pantalla y el PDF descargado en busca de terminología interna
- **Tipo:** Negativo / presentación · **Prioridad:** Crítica · **Ejecutable:** Parcial: se revisa el contenido del API; la pantalla se revisa a mano.
- **Pasos:** «TC-92-081 El informe no muestra terminologia interna».
- **Esperado (matriz):** que ningún texto muestre «RF-xx», «M06», «Módulo N», null, undefined, un identificador como «#123» ni un código en mayúsculas como PENDIENTE_CUENTA o ACTIVO_MARCADO_SIN_MERCADO.

## Ejecución automatizada
- Colección: `tc_m06_g12.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G70.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Las peticiones marcadas **[escritura]** crean o cambian datos en TEST: solo corren con `--env-var "permitir_escritura=SI"`. Sin esa variable se omiten.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
