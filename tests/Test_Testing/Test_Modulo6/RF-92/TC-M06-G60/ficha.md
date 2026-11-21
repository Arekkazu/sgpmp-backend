# TC-M06-G60 — RF-92

Fuente: `RF-92_TC_Individuales_y_Agrupados.xlsx`, hoja TC Agrupados, TCG-02 (TC-92-008 a TC-92-011). Adaptado a la API real `/finanzas` de `origin/test`; las diferencias con la matriz están en `anotaciones/Testing/Modulo6/analisis_RF91_RF92.md`.

**Estado de la ejecución:** NO EJECUTADO en TEST.

**Grupo:** Separación de ganancia o pérdida por transformación biológica y por variación de precio (CA-2, Párr. 40a): ambas partidas con los valores exactos de RF-86, con el signo conservado en pérdidas, separadas aun cuando se compensen entre sí, y con su suma coincidiendo con la variación total del período.

### TC-92-008 — Verificar que el informe discrimina la ganancia por transformación biológica de la variación por precio con los valores exactos de RF-86
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí (sobre el informe existente).
- **Pasos:** «TC-92-008..011 Separacion transformacion biologica / precio (APROBADO)»; «TC-92-008..011 Separacion transformacion biologica / precio (BORRADOR)».

### TC-92-009 — Verificar la discriminación cuando el período arroja pérdida neta
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Alta · **Ejecutable:** Sí, si el período tiene pérdida neta.
- **Pasos:** «TC-92-008..011 Separacion transformacion biologica / precio (APROBADO)»; «TC-92-008..011 Separacion transformacion biologica / precio (BORRADOR)».
- **Esperado (matriz):** que el signo se conserve en ambas partidas.

### TC-92-010 — Período con transformación positiva compensada por variación de precio negativa
- **Tipo:** Funcional / regla de negocio · **Prioridad:** Crítica · **Ejecutable:** Sí, si el período tiene partidas compensadas.
- **Pasos:** «TC-92-008..011 Separacion transformacion biologica / precio (APROBADO)»; «TC-92-008..011 Separacion transformacion biologica / precio (BORRADOR)».
- **Esperado (matriz):** que ambas partidas se revelen por separado aunque el neto sea cercano a cero.

### TC-92-011 — Verificar que la suma de las dos partidas coincide con la variación total del período registrada en RF-86
- **Tipo:** Funcional / cálculo · **Prioridad:** Alta · **Ejecutable:** Sí (contra la conciliación del informe; la comparación con RF-86 directo no está en el API).
- **Pasos:** «TC-92-008..011 Separacion transformacion biologica / precio (APROBADO)»; «TC-92-008..011 Separacion transformacion biologica / precio (BORRADOR)».

## Ejecución automatizada
- Colección: `tc_m06_g60.postman_collection.json`
- Reporte: `resultados/resultado_TC-M06-G60.html`
- Aserciones: pendiente (sin ejecutar en TEST)
- Roles: Contador.
- Sin escritura en TEST.
- Las peticiones cuya precondición no existe en TEST se omiten y el log de Newman muestra `PRECONDICION NO DISPONIBLE`.
