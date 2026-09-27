import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { SimulationFrame, SimulationResults } from '../types/building';
import { frameIndexAt, interpolateFrame } from './interpolateFrame';

export type PlaybackState = 'idle' | 'playing' | 'paused' | 'finished';

export function useSimulationPlayback() {
  const [frames, setFrames] = useState<SimulationFrame[]>([]);
  const [results, setResults] = useState<SimulationResults | null>(null);
  const [simTime, setSimTime] = useState(0);
  const [status, setStatus] = useState<PlaybackState>('idle');
  const [speed, setSpeed] = useState(1);
  const [streaming, setStreaming] = useState(false);

  const rafRef = useRef<number | null>(null);
  const lastWallRef = useRef<number | null>(null);
  const simTimeRef = useRef(0);
  const framesRef = useRef(frames);
  const speedRef = useRef(speed);
  const statusRef = useRef(status);
  const streamingRef = useRef(streaming);

  useEffect(() => {
    framesRef.current = frames;
  }, [frames]);

  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);

  useEffect(() => {
    statusRef.current = status;
  }, [status]);

  useEffect(() => {
    streamingRef.current = streaming;
  }, [streaming]);

  const clearRaf = () => {
    if (rafRef.current != null) {
      window.cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    lastWallRef.current = null;
  };

  const load = useCallback((nextFrames: SimulationFrame[], nextResults: SimulationResults | null) => {
    clearRaf();
    streamingRef.current = false;
    setStreaming(false);
    framesRef.current = nextFrames;
    setFrames(nextFrames);
    setResults(nextResults);
    const t = nextFrames[0]?.t ?? 0;
    simTimeRef.current = t;
    setSimTime(t);
    setStatus(nextFrames.length ? 'paused' : 'idle');
  }, []);

  const startStream = useCallback(() => {
    clearRaf();
    framesRef.current = [];
    setFrames([]);
    setResults(null);
    simTimeRef.current = 0;
    setSimTime(0);
    streamingRef.current = true;
    setStreaming(true);
    setStatus('playing');
  }, []);

  const appendFrame = useCallback((frame: SimulationFrame) => {
    const nextFrames = [...framesRef.current, frame];
    framesRef.current = nextFrames;
    setFrames(nextFrames);
  }, []);

  const finishStream = useCallback((nextResults: SimulationResults | null) => {
    setResults(nextResults);
    streamingRef.current = false;
    setStreaming(false);
    if (!framesRef.current.length) setStatus('idle');
  }, []);

  const reset = useCallback(() => {
    clearRaf();
    streamingRef.current = false;
    setStreaming(false);
    framesRef.current = [];
    setFrames([]);
    setResults(null);
    simTimeRef.current = 0;
    setSimTime(0);
    setStatus('idle');
  }, []);

  const play = useCallback(() => {
    const list = framesRef.current;
    if (!list.length) return;
    const endT = list[list.length - 1].t;
    if (simTimeRef.current >= endT && !streamingRef.current) {
      setStatus('finished');
      return;
    }
    setStatus('playing');
  }, []);

  const pause = useCallback(() => {
    setStatus((s) => (s === 'playing' ? 'paused' : s));
  }, []);

  const seekFrameIndex = useCallback((index: number) => {
    const list = framesRef.current;
    if (!list.length) return;
    const clamped = Math.max(0, Math.min(index, list.length - 1));
    const t = list[clamped].t;
    simTimeRef.current = t;
    setSimTime(t);
    const endT = list[list.length - 1].t;
    if (t >= endT) {
      setStatus('finished');
    } else if (statusRef.current === 'finished') {
      setStatus('paused');
    }
  }, []);

  useEffect(() => {
    clearRaf();
    if (status !== 'playing' || frames.length === 0) return;

    const endT = frames[frames.length - 1].t;
    lastWallRef.current = performance.now();

    const tick = (now: number) => {
      const last = lastWallRef.current ?? now;
      lastWallRef.current = now;
      const dtWall = Math.max(0, (now - last) / 1000);
      const next = Math.min(endT, simTimeRef.current + dtWall * speedRef.current);
      simTimeRef.current = next;
      setSimTime(next);
      if (next >= endT && !streamingRef.current) {
        setStatus('finished');
        clearRaf();
        return;
      }
      rafRef.current = window.requestAnimationFrame(tick);
    };

    rafRef.current = window.requestAnimationFrame(tick);
    return clearRaf;
  }, [status, frames, streaming]);

  const currentFrame = useMemo(
    () => interpolateFrame(frames, simTime),
    [frames, simTime],
  );

  const frameIndex = useMemo(
    () => frameIndexAt(frames, simTime),
    [frames, simTime],
  );

  return {
    frames,
    results,
    frameIndex,
    currentFrame,
    simTime,
    status,
    streaming,
    speed,
    setSpeed,
    load,
    startStream,
    appendFrame,
    finishStream,
    reset,
    play,
    pause,
    setFrameIndex: seekFrameIndex,
  };
}
