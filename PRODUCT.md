# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Una sola persona que usa la app en su propia computadora. Analiza el historial de Quiniela 80 (una lotería dominicana) y quiere saber si una estrategia de selección de números habría sido rentable. Trabaja repitiendo pruebas: cambia un parámetro, corre otra vez y compara lo que ve. (Confirmado en la entrevista de especificación; el contexto de uso exacto es inferido del brief.)

## Product Purpose

Definir laboratorios con reglas fijas, ejecutarlos sobre la referencia histórica congelada y leer sus resultados guardados por sesiones. El éxito es reproducir una configuración y entender sin ambigüedad cuánto ganó o perdió en el pasado. La sección histórica de Corridas conserva sus rutas y su motor; no se confunden sus contratos con los de laboratorios.

## Positioning

Resultados históricos con configuración y procedencia fijadas por corrida. Las huellas identifican la reproducción; no son una promesa de ganancia ni una probabilidad futura. Los estilos de apuesta dependen del laboratorio, no de una regla global.

## Operating Context

- Servidor local en 127.0.0.1 que sirve el frontend compilado; sin cuentas ni acceso remoto.
- Historial incluido: 105.426 sorteos, del 2025-03-05 al 2026-09-25, con 5 números por sorteo (00–99). Los rankings (13 sistemas, entre ellos transición y fríos) existen solo para los sorteos que cubre el archivo congelado.
- Dinero en RD$ enteros. Las reglas (posiciones, premios, apuesta mínima) se fijan en cada corrida y no se guardan de forma global.
- Se puede importar un historial actualizado en formato canónico JSON, sin vista previa.

## Capabilities and Constraints

- Laboratorios: definiciones guardadas con nombre, sistema de selección, cobertura de 1 a 50, estilo (`bold`, `ladder`, `flat`), capital, meta, cinco premios y ventana histórica. Paridad requiere cobertura 50. Cambiar las reglas exige otra definición.
- Ejecución: cada acción guarda una corrida nueva sobre la fuente congelada. Una respuesta incierta bloquea otro envío hasta completar una consulta nueva de corridas; no hay reintento automático.
- Resultado propio: neto, ROI histórico, apostado, pagado, media de cerradas y contadores de cierre; páginas de resúmenes de sesión, sin detalle por apuesta. Las ocho métricas originales se conservan; ROI es presentación derivada y no se persiste.
- Procedencia: sorteos evaluados, huecos entre extremos elegibles y un desplegable con ventana y huellas completas. Sin gráficos, comparación de corridas ni nuevas predicciones.
- Navegación: Laboratorios y Ajustes. Corridas anteriores mantiene acceso directo y sus capacidades históricas de detalle, sin aparecer en el menú principal.
- Fuera de alcance: apuestas reales, predicción de sorteos, probabilidades futuras, Monte Carlo, exportación, generar rankings nuevos.
- Código U2/U4/U5 entregado con comprobaciones focalizadas, tipos y compilación observados; aceptación manual e independiente pendiente. U1 sigue sin aceptación completa. U3 (migración 20/caché) no está implementado.
- Dirección visual fijada: libreta cuadriculada fría, tinta, Archivo/Archivo Narrow y controles cuadrados; no es un rediseño. Guía de revisión: [QA manual](docs/quiniela-ui-manual-qa.md).

## Brand Commitments

Nombre visible: **Quiniela**. Interfaz en español rioplatense con voseo, como el resto de la app. No hay logotipo ni identidad previa vinculante.

## Evidence on Hand

- `chance_express_history.json` (SHA-256 `d1c0e9ec…9711`) y `repo_ref/reports/chance_rank_v1/predictions/pos1.npz` (SHA-256 `b405041f…4d94d`), verificados al arrancar.
- Catorce escenarios de referencia con resultado conocido en `docs/resumen_resultados_quiniela.md`.
- No hay testimonios, clientes, precios ni métricas de uso, y no deben inventarse.

## Product Principles

1. **Describir el pasado, nunca prometer el futuro.** Todo resultado se presenta como lo ocurrido en el historial; la advertencia no se esconde.
2. **Una sola tarea, a la vista.** La app existe para correr, leer y repetir; cada elemento que no sirve a eso sobra.
3. **El número manda.** Las cifras (neto, retorno, saldo, sorteo) se leen primero, con signo y unidad, y nunca se adornan.
4. **Nada de falsa precisión.** Si el detalle está truncado, incompleto o no almacenado, se dice con claridad.
5. **Reproducir sin ambigüedad.** Reutilizar reglas fijas requiere una acción explícita de ejecución. Cambiar las reglas crea otro laboratorio; la incertidumbre nunca se resuelve reenviando automáticamente.

## Accessibility & Inclusion

Cumplir WCAG AA: contraste de texto y de los límites de los controles (3:1 como mínimo), operación completa por teclado, foco visible, respeto de `prefers-reduced-motion` y ningún dato transmitido solo por color. Objetivos táctiles de al menos 44 px. (Estándar elegido por el equipo, no un requisito del usuario.)
