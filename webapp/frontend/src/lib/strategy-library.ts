import type { ConfigurationSummary, ProfileBatchStrategy } from "../api/types";

export type ClassicLibraryEntry = {
  kind: "classic"; nativeId: string; revision: null; value: ConfigurationSummary;
};
export type ProfileLibraryEntry = {
  kind: "profile-definition"; nativeId: string; revision: number; value: ProfileBatchStrategy;
};
export type StrategyLibraryEntry = ClassicLibraryEntry | ProfileLibraryEntry;

export function classicLibraryEntry(value: ConfigurationSummary): ClassicLibraryEntry {
  return { kind: "classic", nativeId: value.id, revision: null, value };
}
export function profileLibraryEntry(value: ProfileBatchStrategy): ProfileLibraryEntry {
  return { kind: "profile-definition", nativeId: value.id, revision: value.revision, value };
}
export function libraryEntryKey(entry: StrategyLibraryEntry): string {
  return JSON.stringify([entry.kind, entry.nativeId, entry.revision]);
}

/** Search only the independently loaded pages; no global ordering or total is implied. */
export function filterLibraryEntries<T extends StrategyLibraryEntry>(entries: T[], search: string): T[] {
  const term = search.trim().toLocaleLowerCase();
  return entries.filter((entry) => `${entry.value.name} ${entry.nativeId}`.toLocaleLowerCase().includes(term));
}

/** The latest-detail endpoint must never silently substitute another revision. */
export function matchesProfileRevision(expected: ProfileBatchStrategy, actual: ProfileBatchStrategy): boolean {
  return expected.id === actual.id && expected.revision === actual.revision && expected.definition_sha256 === actual.definition_sha256;
}
