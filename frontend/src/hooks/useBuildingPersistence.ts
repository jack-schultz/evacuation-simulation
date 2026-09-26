import { useCallback, useEffect, useState } from 'react';
import { api } from '../services/api';
import { emptyLayout } from '../layout/emptyLayout';
import type { BuildingLayout, BuildingSummary } from '../types/building';

export function useBuildingPersistence({
  layout,
  setLayout,
  setUndoHistory,
  setSelected,
  dirty,
  setDirty,
  setBusy,
  setError,
  onResetSimulation,
}: {
  layout: BuildingLayout;
  setLayout: (layout: BuildingLayout) => void;
  setUndoHistory: (history: BuildingLayout[]) => void;
  setSelected: (ref: null) => void;
  dirty: boolean;
  setDirty: (dirty: boolean) => void;
  setBusy: (busy: boolean) => void;
  setError: (error: string | null) => void;
  onResetSimulation: () => void;
}) {
  const [buildingId, setBuildingId] = useState<string | null>(null);
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [floorPlanStatus, setFloorPlanStatus] = useState<string | null>(null);
  const [floorPlanUrl, setFloorPlanUrl] = useState<string | null>(null);

  const refreshList = useCallback(async () => {
    const list = await api.listBuildings();
    setBuildings(list);
    return list;
  }, []);

  const loadBuilding = useCallback(async (id: string) => {
    const b = await api.getBuilding(id);
    const imageUrl = await api.getFloorPlan(id);
    setFloorPlanUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return imageUrl;
    });
    setBuildingId(b.id);
    setLayout(b.layout);
    setUndoHistory([]);
    setSelected(null);
    setDirty(false);
    setFloorPlanStatus(null);
    onResetSimulation();
  }, [setLayout, setUndoHistory, setSelected, setDirty, onResetSimulation]);

  useEffect(() => {
    (async () => {
      try {
        const list = await refreshList();
        if (list.length) {
          await loadBuilding(list[0].id);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onSave = async () => {
    setBusy(true);
    setError(null);
    try {
      if (buildingId) {
        const b = await api.updateBuilding(buildingId, layout);
        setLayout(b.layout);
        setBuildingId(b.id);
      } else {
        const b = await api.createBuilding(layout);
        setBuildingId(b.id);
        setLayout(b.layout);
      }
      setDirty(false);
      await refreshList();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onImportFloorPlan = async (file?: File) => {
    if (!file) return;
    setError(null);
    setFloorPlanStatus(null);
    if (!file.name.toLowerCase().endsWith('.png') || (file.type && file.type !== 'image/png')) {
      setError('Choose a PNG file.');
      return;
    }
    setBusy(true);
    try {
      const layoutToSave = layout.obstacle_map ? { ...layout, obstacle_map: null } : layout;
      let id = buildingId;
      if (!id) {
        const building = await api.createBuilding(layoutToSave);
        id = building.id;
        setBuildingId(id);
        setLayout(building.layout);
        setDirty(false);
        await refreshList();
      } else if (dirty || layout.obstacle_map) {
        const building = await api.updateBuilding(id, layoutToSave);
        setLayout(building.layout);
        setDirty(false);
      }
      const result = await api.uploadFloorPlan(id, file);
      const imageUrl = await api.getFloorPlan(id);
      setFloorPlanUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        return imageUrl;
      });
      setFloorPlanStatus(`PNG stored in database and shown as a pale overlay: ${result.filename}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onNew = () => {
    setBuildingId(null);
    if (floorPlanUrl) URL.revokeObjectURL(floorPlanUrl);
    setFloorPlanUrl(null);
    setLayout(emptyLayout());
    setUndoHistory([]);
    setSelected(null);
    setFloorPlanStatus(null);
    setDirty(true);
    onResetSimulation();
  };

  return {
    buildingId,
    setBuildingId,
    buildings,
    floorPlanStatus,
    floorPlanUrl,
    refreshList,
    loadBuilding,
    onSave,
    onImportFloorPlan,
    onNew,
  };
}
