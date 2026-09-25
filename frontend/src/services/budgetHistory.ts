// Session-scoped list of budget plans computed in this browser session.
// Same pattern as recent retrieval searches: real plans the user generated,
// cleared on tab close — no fabricated history.
export interface SavedPlanRef {
  request_id: string;
  at: string;
  query_label: string;
  budget_ceiling: number;
  status: string;
}

const KEY = 'budget_saved_plans';
const MAX_ENTRIES = 20;

export function savePlanRef(entry: SavedPlanRef) {
  try {
    const list = readPlanRefs().filter((e) => e.request_id !== entry.request_id);
    list.unshift(entry);
    sessionStorage.setItem(KEY, JSON.stringify(list.slice(0, MAX_ENTRIES)));
  } catch {
    /* storage unavailable */
  }
}

export function readPlanRefs(): SavedPlanRef[] {
  try {
    const raw = sessionStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as SavedPlanRef[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function cachePlan(requestId: string, plan: unknown) {
  try {
    sessionStorage.setItem(`plan:${requestId}`, JSON.stringify(plan));
  } catch {
    /* storage unavailable */
  }
}

export function readCachedPlan<T>(requestId: string): T | null {
  try {
    const raw = sessionStorage.getItem(`plan:${requestId}`);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}
