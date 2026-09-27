import type { PlaybackState } from '../simulation/useSimulationPlayback';
import type { SimulationResults } from '../types/building';

interface Props {
  simTime: number;
  status: PlaybackState;
  speed: number;
  onSpeedChange: (speed: number) => void;
  onRun: () => void;
  onPause: () => void;
  onPlay: () => void;
  onReset: () => void;
  running: boolean;
  simulating: boolean;
  results: SimulationResults | null;
  /** Live count from the current playback frame; falls back to final results. */
  evacuatedCount?: number | null;
  showPaths: boolean;
  onShowPathsChange: (show: boolean) => void;
  error?: string | null;
}

export function SimulationControls({
  simTime,
  status,
  speed,
  onSpeedChange,
  onRun,
  onPause,
  onPlay,
  onReset,
  running,
  simulating,
  results,
  evacuatedCount,
  showPaths,
  onShowPathsChange,
  error,
}: Props) {
  const evacuated =
    evacuatedCount != null
      ? evacuatedCount
      : results?.evacuated_count;
  return (
    <div className="controls-bar">
      <div className="controls-left">
        <button type="button" onClick={onRun} disabled={running}>
          {running ? 'Loading...' : simulating ? 'Restart' : 'Run'}
        </button>
        {status === 'playing' ? (
          <button type="button" onClick={onPause}>
            Pause
          </button>
        ) : (
          <button type="button" onClick={onPlay} disabled={!results}>
            Play
          </button>
        )}
        <button type="button" onClick={onReset}>
          Reset
        </button>
        <label className="speed">
          Speed
          <input
            type="range"
            min={0.25}
            max={4}
            step={0.25}
            value={speed}
            onChange={(e) => onSpeedChange(Number(e.target.value))}
          />
          <span>{speed.toFixed(2)}x</span>
        </label>
        <label className="path-toggle">
          <input
            type="checkbox"
            checked={showPaths}
            disabled={!results}
            onChange={(e) => onShowPathsChange(e.target.checked)}
          />
          Show paths
        </label>
      </div>
      <div className="controls-right">
        <span>Simulation time: {simTime.toFixed(1)}s</span>
        {results && (
          <>
            <span>
              Evacuated: {evacuated ?? 0} / {results.total_occupants}
            </span>
            <span>
              Est. total:{' '}
              {results.total_evacuation_time_s != null
                ? `${results.total_evacuation_time_s.toFixed(1)}s`
                : '—'}
            </span>
          </>
        )}
        {error && <span className="error-text">{error}</span>}
      </div>
    </div>
  );
}
