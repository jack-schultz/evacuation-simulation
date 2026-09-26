import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../services/api';
import { emptyLayout } from '../layout/emptyLayout';
import type { BuildingLayout, BuildingSummary } from '../types/building';
import type { FloorPlanImageSummary } from '../types/building';

export interface FloorPlanLibraryImage extends FloorPlanImageSummary {
  url: string;
}

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
  setSelected: (selection: Selection) => void;
  dirty: boolean;
  setDirty: (dirty: boolean) => void;
  setBusy: (busy: boolean) => void;
  setError: (error: string | null) => void;
  onResetSimulation: () => void;
}) {
  const [buildingId, setBuildingId] = useState<string | null>(null);
  const [buildings, setBuildings] = useState<BuildingSummary[]>([]);
  const [floorPlanStatus, setFloorPlanStatus] = useState<string | null>(null);
  const [floorPlans, setFloorPlans] = useState<FloorPlanLibraryImage[]>([]);
  const [selectedFloorPlanId, setSelectedFloorPlanId] = useState<string | null>(null);
  const [floorPlanOpacity, setFloorPlanOpacity] = useState(0.2);
  const imageUrls = useRef<string[]>([]);

  const replaceFloorPlans = useCallback((next: FloorPlanLibraryImage[]) => {
    imageUrls.current.forEach((url) => URL.revokeObjectURL(url));
    imageUrls.current = next.map((image) => image.url);
    setFloorPlans(next);
  }, []);

  const loadFloorPlans = useCallback(async (id: string, preferredId?: string) => {
    const summaries = await api.listFloorPlans(id);
    const assets = await Promise.all(summaries.map(async (summary) => ({
      ...summary,
      url: await api.getFloorPlan(id, summary.id) ?? '',
    })));
    const loaded = assets.filter((image) => image.url);
    replaceFloorPlans(loaded);
    setSelectedFloorPlanId(
      loaded.find((image) => image.id === preferredId)?.id ?? loaded[0]?.id ?? null,
    );
  }, [replaceFloorPlans]);

  useEffect(() => () => {
    imageUrls.current.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  const floorPlanUrl = floorPlans.find((image) => image.id === selectedFloorPlanId)?.url ?? null;

  const refreshList = useCallback(async () => {
    const list = await api.listBuildings();
    setBuildings(list);
    return list;
  }, []);

  const loadBuilding = useCallback(async (id: string) => {
    const b = await api.getBuilding(id);
    await loadFloorPlans(id);
    setBuildingId(b.id);
    setLayout(b.layout);
    setUndoHistory([]);
    setSelected([]);
    setDirty(false);
    setFloorPlanStatus(null);
    onResetSimulation();
  }, [setLayout, setUndoHistory, setSelected, setDirty, onResetSimulation, loadFloorPlans]);

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
      await loadFloorPlans(id, result.id);
      setFloorPlanStatus(`PNG added to the library: ${result.filename}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const onNew = () => {
    setBuildingId(null);
    replaceFloorPlans([]);
    setSelectedFloorPlanId(null);
    setLayout(emptyLayout());
    setUndoHistory([]);
    setSelected([]);
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
    floorPlans,
    selectedFloorPlanId,
    setSelectedFloorPlanId,
    floorPlanOpacity,
    setFloorPlanOpacity,
    refreshList,
    loadBuilding,
    onSave,
    onImportFloorPlan,
    onNew,
  };
}
