// Client-side "recent searches" for Agent 2. This is NOT server history —
// Agent 2 does not persist searches. These entries are real searches the
// user ran in THIS browser tab session (sessionStorage), cleared on tab close.
import type { RetrievalStatus } from '../types/agent2';

const KEY = 'agent2_recent_searches';
const MAX_ENTRIES = 20;

export interface RecentSearch {
  at: string; // ISO timestamp
  category: string;
  query_text: string | null;
  status: RetrievalStatus;
  results: number;
  // Full RetrievalResponse exactly as returned by Agent 2 (real, live data).
  response?: unknown;
}

export function recordRecentSearch(entry: RecentSearch) {
  try {
    const list = readRecentSearches();
    list.unshift(entry);
    sessionStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX_ENTRIES)));
  } catch {
    /* storage unavailable — history display is best-effort */
  }
}

export function readRecentSearches(): RecentSearch[] {
  try {
    const raw = sessionStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as RecentSearch[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}
