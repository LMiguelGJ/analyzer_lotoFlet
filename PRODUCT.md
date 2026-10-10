# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Una sola persona que usa la app en su propia computadora. Analiza el historial de Quiniela 80 (una lotería dominicana) y quiere saber si una estrategia de selección de números habría sido rentable. Trabaja repitiendo pruebas: cambia un parámetro, corre otra vez y compara lo que ve. (Confirmado en la entrevista de especificación; el contexto de uso exacto es inferido del brief.)

## Product Purpose

Correr **una** estrategia sobre el historial, en **sesiones consecutivas**, y medir su rentabilidad. Cada sesión arranca con el capital inicial y termina por meta, por quiebra o por un límite opcional de sorteos; la siguiente arranca en el sorteo siguiente, hasta agotar la ventana. El éxito es poder lanzar muchas corridas sobre el mismo historial, repetir con cambios y leer sin ambigüedad cuánto ganó o perdió la estrategia en total.

## Positioning

Resultados reproducibles sobre un historial congelado y verificado por huella, con reglas del juego fijadas en cada corrida y apuestas siempre al mínimo. Ninguna otra herramienta de lotería para el público general trata la estrategia como algo que se **mide en el pasado** sin prometer nada hacia adelante.

## Operating Context

- Servidor local en 127.0.0.1 que sirve el frontend compilado; sin cuentas ni acceso remoto.
- Historial incluido: 105.426 sorteos, del 2025-03-05 al 2026-09-25, con 5 números por sorteo (00–99). Los rankings (13 sistemas, entre ellos transición y fríos) existen solo para los sorteos que cubre el archivo congelado.
- Dinero en RD$ enteros. Las reglas (posiciones, premios, apuesta mínima) se fijan en cada corrida y no se guardan de forma global.
- Se puede importar un historial actualizado en formato canónico JSON, sin vista previa.

## Capabilities and Constraints

- Estrategia: mezcla de rankings con porcentajes que suman 100, o paridad; cobertura de 1 a 50 números. Apuesta siempre la mínima por número.
- Condiciones: capital, meta de saldo y duración máxima opcional medida en sorteos.
- Ventana: todo el historial por defecto, con inicio y fin opcionales.
- Resultado: neto total, retorno sobre lo apostado, sesiones por motivo de cierre (meta, quiebra, límite, incompleta), lista de sesiones y detalle de apuestas. El detalle puede estar completo, parcial o no almacenado. Sin gráficos, sin reproducción, sin comparación entre corridas, sin biblioteca de estrategias.
- Navegación: dos secciones, Corridas y Ajustes.
- Fuera de alcance: apuestas reales, predicción de sorteos, probabilidades futuras, Monte Carlo, exportación, generar rankings nuevos.
- **Sin decidir:** la dirección visual. El usuario rechazó el diseño anterior (una adaptación oscura de BossFarmer) sin precisar por qué.

## Brand Commitments

Nombre: **Laboratorio Quiniela 80**. Interfaz en español rioplatense con voseo, como el resto de la app. No hay logotipo ni identidad previa vinculante.

## Evidence on Hand

- `chance_express_history.json` (SHA-256 `d1c0e9ec…9711`) y `repo_ref/reports/chance_rank_v1/predictions/pos1.npz` (SHA-256 `b405041f…4d94d`), verificados al arrancar.
- Catorce escenarios de referencia con resultado conocido en `docs/resumen_resultados_quiniela.md`.
- No hay testimonios, clientes, precios ni métricas de uso, y no deben inventarse.

## Product Principles

1. **Describir el pasado, nunca prometer el futuro.** Todo resultado se presenta como lo ocurrido en el historial; la advertencia no se esconde.
2. **Una sola tarea, a la vista.** La app existe para correr, leer y repetir; cada elemento que no sirve a eso sobra.
3. **El número manda.** Las cifras (neto, retorno, saldo, sorteo) se leen primero, con signo y unidad, y nunca se adornan.
4. **Nada de falsa precisión.** Si el detalle está truncado, incompleto o no almacenado, se dice con claridad.
5. **Repetir es barato.** Volver a correr con un cambio debe costar un clic, no un formulario nuevo.

## Accessibility & Inclusion

Cumplir WCAG AA: contraste de texto y de los límites de los controles (3:1 como mínimo), operación completa por teclado, foco visible, respeto de `prefers-reduced-motion` y ningún dato transmitido solo por color. Objetivos táctiles de al menos 44 px. (Estándar elegido por el equipo, no un requisito del usuario.)
