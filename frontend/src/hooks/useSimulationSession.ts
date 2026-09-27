import { useCallback, useMemo, useRef, useState } from 'react';
import { api } from '../services/api';
import { normalizeHazards } from '../layout/hazards';
import { useSimulationPlayback } from '../simulation/useSimulationPlayback';
import type { BuildingLayout } from '../types/building';

export function useSimulationSession({
  setBusy,
  setError,
}: {
  setBusy: (busy: boolean) => void;
  setError: (error: string | null) => void;
}) {
  const [simId, setSimId] = useState<string | null>(null);
  const [playbackBuildingId, setPlaybackBuildingId] = useState<string | null>(null);
  const [occupantRadiusM, setOccupantRadiusM] = useState(0.25);
  const streamController = useRef<AbortController | null>(null);
  const runVersion = useRef(0);
  const playback = useSimulationPlayback();
  const simulating =
    playback.status === 'playing' || playback.status === 'paused' || playback.status === 'finished';

  const congestedIds = useMemo(() => {
    const ids = new Set<string>();
    playback.results?.congestion_hotspots.forEach((h) => ids.add(h.element_id));
    return ids;
  }, [playback.results]);

  const resetSession = useCallback(() => {
    runVersion.current += 1;
    streamController.current?.abort();
    streamController.current = null;
    setBusy(false);
    playback.reset();
    setSimId(null);
    setPlaybackBuildingId(null);
    setOccupantRadiusM(0.25);
  }, [playback, setBusy]);

  const onRun = async ({
    buildingId,
    setBuildingId,
    layout,
    setLayout,
    dirty,
    setDirty,
    refreshList,
  }: {
    buildingId: string | null;
    setBuildingId: (id: string | null) => void;
    layout: BuildingLayout;
    setLayout: (layout: BuildingLayout) => void;
    dirty: boolean;
    setDirty: (dirty: boolean) => void;
    refreshList: () => Promise<unknown>;
  }) => {
    const currentRun = ++runVersion.current;
    streamController.current?.abort();
    const controller = new AbortController();
    streamController.current = controller;
    let streamStarted = false;
    setBusy(true);
    setError(null);
    try {
      let id = buildingId;
      if (!id || dirty) {
        if (id) {
          const b = await api.updateBuilding(id, layout);
          if (currentRun !== runVersion.current) return;
          id = b.id;
          setLayout(normalizeHazards(b.layout));
        } else {
          const b = await api.createBuilding(layout);
          if (currentRun !== runVersion.current) return;
          id = b.id;
          setBuildingId(b.id);
          setLayout(normalizeHazards(b.layout));
        }
        setDirty(false);
        await refreshList();
        if (currentRun !== runVersion.current) return;
      }

      const created = await api.createSimulation(id, {
        timestep_s: 0.25,
        max_time_s: 600,
        frame_interval_s: 0.5,
        occupant_radius_m: 0.25,
      });
      if (currentRun !== runVersion.current) return;
      setSimId(created.id);
      setPlaybackBuildingId(id);
      playback.startStream();
      streamStarted = true;
      await api.streamSimulation(
        created.id,
        playback.appendFrame,
        playback.finishStream,
        controller.signal,
      );
    } catch (e) {
      if (currentRun === runVersion.current && !(e instanceof DOMException && e.name === 'AbortError')) {
        setError(e instanceof Error ? e.message : String(e));
        if (streamStarted) playback.finishStream(null);
      }
    } finally {
      if (currentRun === runVersion.current) {
        if (streamController.current === controller) streamController.current = null;
        setBusy(false);
      }
    }
  };

  const onReset = async () => {
    runVersion.current += 1;
    streamController.current?.abort();
    streamController.current = null;
    setBusy(false);
    playback.reset();
    setOccupantRadiusM(0.25);
    setPlaybackBuildingId(null);
    if (simId) {
      try {
        await api.resetSimulation(simId);
      } catch {
        /* ignore */
      }
    }
    setSimId(null);
    setError(null);
  };

  return {
    playback,
    playbackBuildingId,
    simulating,
    streaming: playback.streaming,
    congestedIds,
    occupantRadiusM,
    resetSession,
    onRun,
    onReset,
  };
}
