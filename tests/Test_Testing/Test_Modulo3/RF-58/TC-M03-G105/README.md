# TC-M03-G105 — RF-58 / CU04 (usabilidad)

Caso original: **TC-M03-205**. Un usuario Productor interpreta el estado de una variable en **≤ 5 s**, sin requerir información técnica del sensor.

La matriz lo define como **prueba manual controlada**: sesión moderada con cronómetro y usuarios reales o representativos del perfil Productor. La interpretación humana no se automatiza, así que no hay Newman ni Cypress, y el ejecutor no se conecta al API. El ejecutor **asiste a la sesión y evalúa su registro**.

## Modos

| Modo | Uso |
| --- | --- |
| Captura cronometrada | `--ejecutar` sin `--registro`. Por cada ensayo, el moderador pulsa Enter al mostrar la variable y otra vez cuando el participante responde; después anota el estado indicado y si necesitó información técnica. |
| Registro en papel | `--ejecutar --registro <archivo.json>`, a partir de `plantilla_registro_g105.json` completada durante la sesión. |

En ambos casos se exigen la autorización (`QA_AUTORIZADO=SI`, TEST, referencia de Desarrollo) y la aceptación del efecto de login: los participantes inician sesión en la vista de TEST.

## Evaluación

- **`[PRE]`** (las declara el moderador; si faltan, el resultado es BLOQUEADO):
  - el panel presenta variables en VERDE, AMARILLO, ROJO y GRIS;
  - hay al menos una alerta activa visible;
  - los participantes tienen perfil Productor y no tienen conocimiento técnico;
  - el registro no contiene datos personales (solo códigos `Pxx`);
  - los ensayos están completos y hay al menos un ensayo por estado.
- **`[ASSERT]` UI-205-01, por ensayo:** el estado identificado coincide con el presentado, el tiempo es ≤ 5 s y no se requirió información técnica. Se exige al menos un ensayo superado por estado y ninguno fallido.
- Un fallo con las precondiciones cumplidas propone **RECHAZADO**. Si un estado no estaba en el panel, se invalidan solo sus ensayos.

## Dependencias y decisiones

- **Preparación del panel.** La sesión necesita un panel visible para el Productor con los cuatro estados y una alerta activa, durante el tiempo de la sesión.
  - Los datos del sandbox no sirven: viven en una transacción de corta inactividad y un navegador manual no envía las cabeceras del RUN. Hace falta un **conjunto de datos QA persistente**, cuya creación no está autorizada. **REQUIERE DECISIÓN QA.**
  - GRIS depende de la transición de **RF-60**.
  - Las políticas RLS de `modulo9.sensores` solo permiten lectura a Administrador e Ingeniero. Si el panel del Productor no muestra sensores, la sesión no puede ejecutarse. Eso se evalúa en TC-M03-188 (G97); aquí no se atribuye.
- **REQUIERE DECISIÓN QA:** número mínimo de participantes y ensayos, y si el criterio se exige en todos los ensayos (lo implementado) o en un porcentaje.

## Uso

```
node ejecutar_tc_m03_g105.mjs --validar-local
node --test validar_local_g105.mjs
node ejecutar_tc_m03_g105.mjs --ejecutar --ambiente TEST --autorizacion "<referencia>" --tipo evaluacion --aceptar-efectos notificacion-login [--registro <archivo.json>]
```

V1 se guarda en `RESULTADOS/<RUN_ID>/` y V2 y siguientes en `EvaluacionVN/RESULTADOS/<RUN_ID>/`, con informe Markdown y `evidencia.json` (que incluye el registro de la sesión).
