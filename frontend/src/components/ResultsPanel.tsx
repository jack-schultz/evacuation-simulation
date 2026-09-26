import type { SimulationResults } from '../types/building';

interface Props {
  results: SimulationResults | null;
  /** Live count from the current playback frame. */
  evacuatedCount?: number | null;
}

function fmt(v: number | null | undefined, suffix = ''): string {
  if (v == null) return '—';
  return `${v.toFixed(1)}${suffix}`;
}

export function ResultsPanel({ results, evacuatedCount }: Props) {
  if (!results) {
    return (
      <div className="results-bar">
        <span className="hint">Run a simulation to see evacuation statistics.</span>
      </div>
    );
  }

  const evacuated = evacuatedCount ?? results.evacuated_count;
  const remaining = Math.max(0, results.total_occupants - evacuated);

  return (
    <div className="results-bar">
      <div className="stat">
        <strong>Total time</strong>
        <span>{fmt(results.total_evacuation_time_s, 's')}</span>
      </div>
      <div className="stat">
        <strong>Evacuated</strong>
        <span>
          {evacuated} / {results.total_occupants}
        </span>
      </div>
      <div className="stat">
        <strong>Remaining</strong>
        <span>{remaining}</span>
      </div>
      <div className="stat">
        <strong>Avg time</strong>
        <span>{fmt(results.average_evacuation_time_s, 's')}</span>
      </div>
      <div className="stat">
        <strong>Max time</strong>
        <span>{fmt(results.max_evacuation_time_s, 's')}</span>
      </div>
      <div className="stat">
        <strong>Avg wait</strong>
        <span>{fmt(results.average_wait_time_s, 's')}</span>
      </div>
      <div className="stat wide">
        <strong>Congestion</strong>
        <span>
          {results.congestion_hotspots.length
            ? results.congestion_hotspots
                .slice(0, 3)
                .map((h) => `${h.element_id} (peak ${h.peak_queue})`)
                .join(', ')
            : 'None detected'}
        </span>
      </div>
    </div>
  );
}
