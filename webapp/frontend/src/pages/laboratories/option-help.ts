import { STAKE_STYLES, SYSTEMS } from "./form-model";

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
