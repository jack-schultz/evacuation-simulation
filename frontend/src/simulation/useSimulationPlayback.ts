import { useCallback, useEffect, useRef, useState } from 'react';
import type { SimulationFrame, SimulationResults } from '../types/building';

export type PlaybackState = 'idle' | 'playing' | 'paused' | 'finished';

export function useSimulationPlayback() {
  const [frames, setFrames] = useState<SimulationFrame[]>([]);
  const [results, setResults] = useState<SimulationResults | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [status, setStatus] = useState<PlaybackState>('idle');
  const [speed, setSpeed] = useState(1);
  const timerRef = useRef<number | null>(null);

  const clearTimer = () => {
    if (timerRef.current != null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  const load = useCallback((nextFrames: SimulationFrame[], nextResults: SimulationResults | null) => {
    clearTimer();
    setFrames(nextFrames);
    setResults(nextResults);
    setFrameIndex(0);
    setStatus(nextFrames.length ? 'paused' : 'idle');
  }, []);

  const reset = useCallback(() => {
    clearTimer();
    setFrames([]);
    setResults(null);
    setFrameIndex(0);
    setStatus('idle');
  }, []);

  const play = useCallback(() => {
    if (!frames.length) return;
    setStatus('playing');
  }, [frames.length]);

  const pause = useCallback(() => {
    setStatus((s) => (s === 'playing' ? 'paused' : s));
  }, []);

  useEffect(() => {
    clearTimer();
    if (status !== 'playing' || frames.length === 0) return;

    const intervalMs = Math.max(50, 500 / speed);
    timerRef.current = window.setInterval(() => {
      setFrameIndex((i) => {
        if (i >= frames.length - 1) {
          setStatus('finished');
          return i;
        }
        return i + 1;
      });
    }, intervalMs);

    return clearTimer;
  }, [status, speed, frames.length]);

  const currentFrame = frames[frameIndex] ?? null;
  const simTime = currentFrame?.t ?? 0;

  return {
    frames,
    results,
    frameIndex,
    currentFrame,
    simTime,
    status,
    speed,
    setSpeed,
    load,
    reset,
    play,
    pause,
    setFrameIndex,
  };
}
