import { useCallback, useMemo, useState } from 'react';
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
  const [occupantRadiusM, setOccupantRadiusM] = useState(0.25);
  const playback = useSimulationPlayback();
  const simulating =
    playback.status === 'playing' || playback.status === 'paused' || playback.status === 'finished';

  const congestedIds = useMemo(() => {
    const ids = new Set<string>();
    playback.results?.congestion_hotspots.forEach((h) => ids.add(h.element_id));
    return ids;
  }, [playback.results]);

  const resetSession = useCallback(() => {
    playback.reset();
    setSimId(null);
    setOccupantRadiusM(0.25);
  }, [playback]);

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
    setBusy(true);
    setError(null);
    try {
      let id = buildingId;
      if (!id || dirty) {
        if (id) {
          const b = await api.updateBuilding(id, layout);
          id = b.id;
          setLayout(normalizeHazards(b.layout));
        } else {
          const b = await api.createBuilding(layout);
          id = b.id;
          setBuildingId(b.id);
          setLayout(normalizeHazards(b.layout));
        }
        setDirty(false);
        await refreshList();
      }

      const created = await api.createSimulation(id, {
        timestep_s: 0.25,
        max_time_s: 600,
        frame_interval_s: 0.5,
        occupant_radius_m: 0.25,
      });
      setSimId(created.id);
      const run = await api.runSimulation(created.id);
      setOccupantRadiusM(run.parameters?.occupant_radius_m ?? 0.25);
      playback.load(run.frames, run.results);
      playback.play();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onReset = async () => {
    playback.reset();
    setOccupantRadiusM(0.25);
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
    simulating,
    congestedIds,
    occupantRadiusM,
    resetSession,
    onRun,
    onReset,
  };
}
