/* Paleta validada (skill de dataviz): orden categórico fijo, seguro para daltonismo en pares
   adyacentes. Nunca reasignar por candidato/canal al filtrar. Mismos valores que usaba el tablero
   anterior, para que las gráficas conserven su significado. */
export const BLUE = "#2a78d6", ORANGE = "#eb6834", AQUA = "#1baf7a", YELLOW = "#eda100",
  MAGENTA = "#e87ba4", GREEN = "#008300", VIOLET = "#4a3aa7", RED = "#e34948";
export const GOOD = "#0ca30c", CRITICAL = "#d03b3b", NEUTRAL_TONE = "#b7b6ad";
export const INK = "#14140f", INK_SOFT = "#52514e", MUTED = "#84837c", GRID = "#e7e6e0";
export const CARLOS_GRAY = "#c7cbd6"; // candidatos que no son Carlos, en las gráficas que solo lo resaltan a él
export const COLORS = [BLUE, RED, AQUA, YELLOW, MAGENTA, VIOLET, ORANGE, GREEN, MUTED]; // hasta 9 candidatos
export const SRC_COLOR = { Prensa: BLUE, YouTube: ORANGE, Reddit: AQUA, "Redes (búsqueda)": YELLOW, Instagram: MAGENTA, Facebook: GREEN, X: VIOLET };
// Rueda de emociones del cliente: ira=rojo, miedo=gris, asco=verde azulado, tristeza=violeta, felicidad=naranja, sorpresa=amarillo.
export const EMOTION_COLOR = { ira: CRITICAL, miedo: NEUTRAL_TONE, asco: AQUA, tristeza: VIOLET, felicidad: ORANGE, sorpresa: YELLOW, "sin emoción marcada": MUTED };
export const PERIOD_FILL = ["#eef3fb", "#f7f3ea", "#eef3fb", "#f7f3ea", "#eef7f1"];
