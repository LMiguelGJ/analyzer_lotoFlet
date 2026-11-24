import { CHANCE_LIST_ID, STAKE_STYLES, SYSTEMS } from "./form-model";

export type HelpKind = "system" | "stake_style";
export interface OptionExplanation { what: string; effect: string; example: string }

// Semantics: repo_ref/chance_rank/{models,walkforward,protocol}.py;
// stakes: laboratorio/engine/reference_labs.py; parity: domain/selection.py.
const systems: Record<(typeof SYSTEMS)[number]["value"], OptionExplanation> = {
  transition: {
    what: "Ordena los números según lo que ocurrió después del número anterior en el historial, en la misma posición.",
    effect: "Cambia qué números se seleccionan según esas transiciones históricas; no cambia cuánto apostás por número.",
    example: "Con cobertura 5, selecciona los cinco primeros del ranking de transición preparado para ese sorteo.",
  },
  cold: {
    what: "Ordena los números por el tiempo sin aparecer en la posición analizada.",
    effect: "Prioriza los que llevan más tiempo ausentes. Eso no significa que tengan más probabilidad de salir después.",
    example: "Con cobertura 5, selecciona los cinco primeros del ranking de antigüedad.",
  },
  select_interpretable: {
    what: "Usa el modelo interpretable con mejor promedio de aciertos en la validación interna de cada bloque histórico.",
    effect: "El modelo usado puede cambiar entre bloques. No elige usando el resultado del sorteo que va a evaluar.",
    example: "Si Fríos gana la validación de un bloque, usa su ranking en ese bloque; la cobertura define cuántos números toma.",
  },
  mix: {
    what: "Combina frecuencia histórica, frecuencia reciente y tiempo sin aparecer mediante pesos definidos en el ranking preparado.",
    effect: "Selecciona por la combinación de esas señales, en lugar de seguir una sola. Este formulario no cambia sus pesos.",
    example: "Con cobertura 5, toma los cinco primeros del ranking combinado de Mezclas.",
  },
  ensemble: {
    what: "Combina cinco rankings: frecuencia histórica, frecuencia reciente, antigüedad, transición y contexto horario.",
    effect: "El ranking preparado combina sus posiciones o votos, según el método configurado; no implica una garantía de aciertos.",
    example: "Con cobertura 5, toma los cinco primeros del ranking combinado de Ensemble.",
  },
  parity: {
    what: "Una votación de modelos que usa solo el historial previo elige pares o impares para cada sorteo.",
    effect: "Selecciona el conjunto completo elegido, no unos pocos números de un ranking. Requiere cobertura 50.",
    example: "Si la votación elige pares, selecciona los 50 números pares; el estilo determina cuánto apostar por cada uno.",
  },
};

/** Help the Quiniela Leidsa list uses for its own systems; it wins over the archived Chance copy. */
const listSystems: Record<string, OptionExplanation & { label: string }> = {
  cold: {
    label: "Fríos",
    what: "Ordena los números por los sorteos que llevan sin salir en la primera posición.",
    effect: "Prioriza los más ausentes. Parece que «ya tocan», pero cada sorteo es independiente: es una hipótesis de patrón, no una garantía.",
    example: "Con cobertura 5, selecciona los cinco números con más sorteos seguidos sin salir primero.",
  },
  freq_hist: {
    label: "Frecuencia histórica",
    what: "Ordena los números por cuántas veces salieron en esa posición en todo el historial previo.",
    effect: "Prioriza los más frecuentes del pasado. Que hayan salido más veces no significa que salgan antes en el futuro.",
    example: "Con cobertura 5, selecciona los cinco números que más veces salieron en esa posición hasta el sorteo anterior.",
  },
  freq_recent: {
    label: "Frecuencia reciente",
    what: "Ordena los números por cuántas veces salieron en esa posición en los sorteos más recientes.",
    effect: "Da más peso a lo que pasó hace poco que a lo que pasó hace años.",
    example: "Con cobertura 5, selecciona los cinco números más frecuentes de la ventana reciente.",
  },
  decay: {
    label: "Decaimiento",
    what: "Cuenta cada aparición pasada con un peso que baja a medida que el sorteo queda atrás.",
    effect: "Es un punto medio entre la frecuencia histórica y la reciente: lo viejo cuenta, pero menos.",
    example: "Con cobertura 5, selecciona los cinco números con mayor puntaje ponderado por antigüedad.",
  },
  transition: {
    label: "Transición",
    what: "Ordena los números por la secuencia de la primera posición: cuántas veces salió cada número justo después del último número que salió primero.",
    effect: "Supone que algunas continuaciones se repiten más que otras. Es una hipótesis de patrón, no una garantía, y no cambia cuánto apostás por número.",
    example: "Con cobertura 5, selecciona los cinco números que más veces siguieron al último primer número del historial.",
  },
  overdue: {
    label: "Ciclo vencido",
    what: "Ordena los números comparando los sorteos que llevan sin salir primero con la espera habitual de cada número en el historial previo.",
    effect: "Destaca los que ya superaron su espera típica. Es una hipótesis de patrón: no significa que el próximo sorteo los vaya a sacar.",
    example: "Con cobertura 5, selecciona los cinco números que llevan más veces su espera promedio sin salir primero.",
  },
  digits: {
    label: "Terminaciones y decenas",
    what: "Mira la unidad y la decena de la primera posición en los sorteos recientes y ordena los números según cuánto se repiten esas terminaciones.",
    effect: "Prefiere números cuyas unidades y decenas fueron comunes hace poco. Es una hipótesis de patrón, no una garantía de aciertos.",
    example: "Con cobertura 5, selecciona los cinco números cuyas terminaciones y decenas son las más frecuentes de la ventana reciente.",
  },
  ensemble: {
    label: "Ensamble",
    what: "Combina los siete rankings de la lista (Fríos, Frecuencia histórica, Frecuencia reciente, Decaimiento, Transición, Ciclo vencido y Terminaciones y decenas) promediando la posición de cada número.",
    effect: "Un número sube si varios rankings lo ponen arriba. Es una hipótesis de patrón: combinar señales no garantiza aciertos.",
    example: "Con cobertura 5, selecciona los cinco números con mejor posición promedio entre los siete rankings.",
  },
};

const stakes: Record<(typeof STAKE_STYLES)[number]["value"], OptionExplanation> = {
  bold: {
    what: "Calcula cuánto apostar por número para alcanzar la meta con un acierto en el primer premio, sin superar el saldo disponible.",
    effect: "El importe depende de la distancia a la meta, la cobertura y el primer premio. Puede comprometer gran parte del saldo; no garantiza llegar a la meta.",
    example: "Con saldo 2.000, meta 2.800, cobertura 10 y primer premio 80, apuesta 12 unidades por número: 120 en total.",
  },
  ladder: {
    what: "Usa una escalera de diez rondas que calcula la apuesta por número a partir de lo invertido en los tramos anteriores.",
    effect: "Avanza de tramo si no acierta el primer premio y vuelve al primero cuando lo acierta. No duplica automáticamente la apuesta.",
    example: "Con cobertura 10 y primer premio 80, comienza con una unidad por número: 10 en total. Los tramos siguientes se calculan para recuperar lo invertido más 10 unidades al acertar el primer premio.",
  },
  flat: {
    what: "Apuesta una unidad por número en cada sorteo.",
    effect: "El importe no aumenta para recuperar pérdidas ni se ajusta a la meta.",
    example: "Con cobertura de 5 números, apostás 5 unidades por sorteo.",
  },
};

export interface HelpOption extends OptionExplanation { value: string; label: string }

/**
 * Explanations for the systems a list offers; unknown ids are skipped, never invented.
 * Outside Chance Express the list's own copy wins, so Leidsa never shows the archived Chance text.
 */
export function systemHelpOptions(values: readonly string[], listId?: string): HelpOption[] {
  const chance = listId === undefined || listId === CHANCE_LIST_ID;
  return values.flatMap((value): HelpOption[] => {
    const base = chance ? SYSTEMS.find((system) => system.value === value) : undefined;
    if (base) return [{ ...base, ...systems[base.value] }];
    const extra = listSystems[value];
    if (extra) return [{ value, ...extra }];
    const fallback = SYSTEMS.find((system) => system.value === value);
    return fallback ? [{ ...fallback, ...systems[fallback.value] }] : [];
  });
}

/** Bold and ladder examples quote the first prize; only the archived 80 keeps its worked numbers. */
export function stakeHelpOptions(firstPrize: number): HelpOption[] {
  return STAKE_STYLES.map((option) => {
    const base = { ...option, ...stakes[option.value] };
    if (firstPrize === 80 || option.value === "flat") return base;
    return { ...base, example: `Con primer premio ${firstPrize} y cobertura 10, la apuesta por número se recalcula en cada sorteo según el saldo y la meta.` };
  });
}

export const OPTION_HELP = {
  system: {
    label: "Sistema de selección", title: "Sistemas de selección",
    introduction: "El sistema decide qué números seleccionar.",
    options: SYSTEMS.map((option) => ({ ...option, ...systems[option.value] })),
  },
  stake_style: {
    label: "Estilo de apuesta", title: "Estilos de apuesta",
    introduction: "El estilo determina cuánto apostar por número.",
    options: STAKE_STYLES.map((option) => ({ ...option, ...stakes[option.value] })),
  },
};
