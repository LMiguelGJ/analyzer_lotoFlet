<!-- SEED: established before implementation (yolo mode, no decision page; assigned by concept-seed key d55eb430, index 6 of the grounded list). Re-run /impeccable document in scan mode once the first screens exist to carbonize exact tokens and components. -->
---
name: Laboratorio Quiniela 80
description: La libreta del apostador, ahora con una estrategia que se corre sola sobre el historial.
---

# Design System: Laboratorio Quiniela 80

## Overview

**Creative North Star: "La libreta del apostador"**

Una libreta de hojas cuadriculadas donde alguien apunta números a mano: cada corrida es una página rayada, cada sesión una fila apoyada en la cuadrícula y el resultado se subraya con marcador. El mundo viene de la cultura de la banca: quien juega a la quiniela lleva su libreta, tacha, suma y vuelve a probar. Aquí la libreta hace las cuentas por él, sin dejar de parecer una libreta.

Reemplaza por completo el diseño anterior (una adaptación oscura y plana de BossFarmer), que el usuario rechazó. No se hereda su paleta, su tipografía de rótulos ni su lenguaje de placas.

La luz es de escritorio: papel claro de día o bajo una lámpara. La interfaz es de **operación** (Operate): la tarea es correr, leer y repetir, y la expresión nunca tapa una cifra.

**Key Characteristics:**
- Papel blanco azulado con cuadrícula de 24 px; las filas, los campos y las tablas se apoyan en las líneas.
- Tinta azul-negra para las cifras; lápiz rojo para pérdidas y correcciones; marcador amarillo solo detrás de la cifra clave de cada pantalla.
- Esquinas vivas, sin sombras ni desenfoques: el relieve lo da la línea y el papel.
- Sin gráficos, sin iconos decorativos, sin ilustraciones. La cuadrícula y los números son la imagen.
- Cada número lleva signo y unidad; el color nunca es el único portador de significado.

## Colors

Estrategia **restringida**: neutros de papel y tinta más un acento de lápiz rojo y un marcador amarillo de uso mínimo. Los valores exactos se fijan al implementar `[to be resolved during implementation]`, dentro de estas reglas:

### Neutral
- **Papel cuadriculado**: blanco con un matiz azul-verdoso muy leve, no crema. Fondo de página y de las hojas.
- **Línea de cuadrícula**: azul-cian pálido; sirve de textura y de regla de filas. No es borde de control.
- **Tinta**: azul-negro de bolígrafo; texto y cifras. Contraste de texto AA como mínimo, AAA para cifras clave.
- **Tinta suave**: gris azulado para rótulos y ayudas, con contraste AA sobre el papel.

### Accent
- **Lápiz rojo**: pérdidas, quiebras, errores y la línea de margen. Siempre acompañado de signo o palabra.
- **Marcador amarillo**: un único uso por pantalla, detrás de la cifra clave (neto total). Texto en tinta encima.

### Named Rules
**The One Highlighter Rule.** El marcador amarillo aparece una sola vez por pantalla. Su escasez es lo que marca "esto es lo que importa".
**The Sign Always Rule.** Toda cifra monetaria lleva signo (+ o −) y unidad (RD$); el rojo acompaña, nunca sustituye.
**The Not Cream Rule.** El papel no es crema ni sepia: es blanco frío de libreta escolar. Nada de serif display con terracota.

## Typography

**Display / Body / Label:** familias ya instaladas en local (Archivo y Archivo Narrow); sin red. La elección final de pesos y de cifras tabulares se resuelve al implementar `[to be resolved during implementation]`.

**Character:** letra de imprenta clara para rotular y cifras de ancho fijo para sumar. Ninguna fuente manuscrita: la mano se sugiere con la cuadrícula y el color, no con una tipografía de disfraz.

### Hierarchy
- **Cifra clave** (grande, tabular): el neto total, sobre marcador.
- **Título de página** y **título de sección**: sobrios; el tamaño y el peso hacen la jerarquía.
- **Cuerpo**: legible, línea de hasta 65 caracteres en texto corrido.
- **Rótulo**: pequeño, en mayúsculas o versalitas, con interletraje moderado, para los términos de cada fila.

### Named Rules
**The Tabular Rule.** Toda columna de cifras usa números tabulares alineados a la derecha; dos filas nunca desalinean sus dígitos.

## Layout

Una cuadrícula base de **24 px**. La altura de cada fila, el interlineado y los espacios son múltiplos de 24 px, y las filas de tablas descansan sobre las líneas. Los objetivos táctiles miden al menos 2 celdas (48 px). Una línea de margen roja vertical a la izquierda en escritorio; en móvil el margen se pliega y la hoja ocupa el ancho.

Dos secciones de navegación (Corridas, Ajustes) en una barra superior de texto en escritorio y una barra inferior en móvil. Contenido en una sola columna de lectura; el resultado ordena resumen → sesiones → apuestas de arriba abajo.

## Elevation & Depth

Plano. Sin sombras ni desenfoques. Una hoja se distingue del fondo por su línea fina y por un tono de papel ligeramente distinto; el foco se marca con un contorno grueso de tinta.

### Named Rules
**The Flat Sheet Rule.** Nada flota. Un diálogo es una hoja con borde que cubre el fondo atenuado, no una tarjeta con sombra.

## Shapes

Esquinas vivas (0 px) en todo. Bordes de 1 px para hojas y de 2 px de tinta para los límites de controles, de modo que cada control tenga un contraste de borde de al menos 3:1 contra su fondo. Las líneas de la cuadrícula no cuentan como borde de control.

## Components

Se definirán al implementar la primera pantalla. Invariantes: los campos son celdas rotuladas sobre la cuadrícula (rótulo arriba, valor abajo); el botón principal es un bloque de tinta con texto de papel; los estados de carga, vacío y error son hojas con su rótulo, no pantallas aparte.

## Do's and Don'ts

### Do:
- **Do** apoyar filas, campos y tablas en la cuadrícula de 24 px.
- **Do** mostrar signo y unidad en cada cifra y alinear columnas con números tabulares.
- **Do** decir con palabras cuando el detalle está truncado, incompleto o no almacenado.
- **Do** mantener la advertencia "describe el historial, no promete resultados futuros" visible en el formulario y en el resultado.
- **Do** respetar `prefers-reduced-motion`; el movimiento es mínimo y opcional.

### Don't:
- **Don't** volver al diseño oscuro y plano de BossFarmer ni a su lenguaje de placas y rótulos.
- **Don't** usar crema, serif de exhibición ni terracota, ni neón sobre negro, ni los gradientes de las apps de fintech.
- **Don't** imitar la libreta con espirales, bordes rasgados, sombras de papel o tipografías manuscritas.
- **Don't** usar gráficos, iconos decorativos ni ilustraciones; la cuadrícula y las cifras bastan.
- **Don't** usar el marcador amarillo más de una vez por pantalla ni el rojo como único indicador.
