const PAGE_SIZE = 20;
export { PAGE_SIZE };

/** Navigation is visual only; the persisted result never changes. */
export function replayIndex(index: number, step: number, total: number): number {
  return Math.max(0, Math.min(Math.max(0, total - 1), index + step));
}

export function pageOffset(index: number, size = PAGE_SIZE): number {
  return Math.floor(Math.max(0, index) / size) * size;
}
