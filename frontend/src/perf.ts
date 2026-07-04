type PerfDetail = Record<string, unknown>;

const SAMPLE_WINDOW = 40;
const SAMPLE_LOG_EVERY = 20;

const samples = new Map<string, number[]>();
const counters = new Map<string, number>();

export function markPerf(): number | null {
  return isPerfEnabled() ? performance.now() : null;
}

export function measurePerf(name: string, startMs: number | null, detail?: PerfDetail): number | null {
  if (startMs == null || !isPerfEnabled()) return null;
  const durationMs = performance.now() - startMs;
  reportPerfSample(name, durationMs, detail);
  return durationMs;
}

export function reportPerfSample(name: string, durationMs: number, detail?: PerfDetail) {
  if (!isPerfEnabled()) return;
  const nextSamples = samples.get(name) ?? [];
  nextSamples.push(durationMs);
  if (nextSamples.length > SAMPLE_WINDOW) nextSamples.shift();
  samples.set(name, nextSamples);

  const count = (counters.get(name) ?? 0) + 1;
  counters.set(name, count);
  if (count % SAMPLE_LOG_EVERY !== 0) return;

  const sorted = [...nextSamples].sort((left, right) => left - right);
  console.debug('[hype:perf]', name, {
    count,
    lastMs: round(durationMs),
    p50Ms: round(percentile(sorted, 0.5)),
    p95Ms: round(percentile(sorted, 0.95)),
    ...detail,
  });
}

function isPerfEnabled() {
  if (import.meta.env.DEV) return true;
  try {
    return window.localStorage.getItem('hype:perf') === '1'
      || new URLSearchParams(window.location.search).get('perf') === '1';
  } catch {
    return false;
  }
}

function percentile(sorted: number[], ratio: number) {
  if (sorted.length === 0) return 0;
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil(sorted.length * ratio) - 1));
  return sorted[index];
}

function round(value: number) {
  return Math.round(value * 10) / 10;
}
