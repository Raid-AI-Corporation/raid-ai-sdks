import type { PagedResult } from "../types.js";

/**
 * Normalize a `?skip=&take=` list response into `{ items, totalCount }`.
 *
 * The platform returns `PagedResult<T>` (`{ items, totalCount }`), but some list
 * endpoints/deployments return a bare array. This accepts either.
 */
export function normalizePaged<T>(raw: unknown): PagedResult<T> {
  if (Array.isArray(raw)) {
    return { items: raw as T[], totalCount: raw.length };
  }
  if (raw && typeof raw === "object") {
    const obj = raw as { items?: unknown; totalCount?: unknown; data?: unknown };
    const items = (Array.isArray(obj.items) ? obj.items : Array.isArray(obj.data) ? obj.data : []) as T[];
    const totalCount = typeof obj.totalCount === "number" ? obj.totalCount : items.length;
    return { items, totalCount };
  }
  return { items: [], totalCount: 0 };
}
