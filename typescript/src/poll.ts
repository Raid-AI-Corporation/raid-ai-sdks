import { RaidTimeoutError } from "./errors.js";

export interface PollOptions {
  /** Milliseconds between polls (default 3_000). */
  intervalMs?: number;
  /** Overall timeout in milliseconds before giving up (default 300_000 = 5 min). */
  timeoutMs?: number;
  /** Optional callback invoked with each intermediate poll result. */
  onPoll?: (value: unknown) => void;
}

const DEFAULT_INTERVAL_MS = 3_000;
const DEFAULT_POLL_TIMEOUT_MS = 300_000;

/**
 * Poll `fetchOnce` until `isDone` returns true or the timeout elapses.
 *
 * Used by the async modalities' `submitAndWait` helpers. Throws `RaidTimeoutError`
 * if the deadline passes before a terminal state is reached.
 */
export async function pollUntil<T>(
  fetchOnce: () => Promise<T>,
  isDone: (value: T) => boolean,
  describeStatus: (value: T) => string,
  options: PollOptions = {},
): Promise<T> {
  const intervalMs = options.intervalMs ?? DEFAULT_INTERVAL_MS;
  const timeoutMs = options.timeoutMs ?? DEFAULT_POLL_TIMEOUT_MS;
  // Monotonic clock — immune to wall-clock/NTP adjustments during a long poll.
  const now = () => performance.now();
  const deadline = now() + timeoutMs;

  let last: T | undefined;
  for (;;) {
    last = await fetchOnce();
    options.onPoll?.(last);
    if (isDone(last)) {
      return last;
    }
    // Give up only once the deadline has actually passed — so the full budget is
    // used and a job that finishes just before the deadline is still caught. The
    // final sleep is clamped so we never overshoot the deadline waiting to poll.
    const remaining = deadline - now();
    if (remaining <= 0) {
      throw new RaidTimeoutError(
        `Timed out after ${timeoutMs}ms waiting for the job to finish`,
        last === undefined ? undefined : describeStatus(last),
      );
    }
    await sleep(Math.min(intervalMs, remaining));
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
