import type {
  BuildingLayout,
  BuildingResponse,
  BuildingSummary,
  FloorPlanImageSummary,
  SimulationParameters,
  SimulationRunResponse,
} from '../types/building';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  listBuildings: () => request<BuildingSummary[]>('/api/buildings'),
  getBuilding: (id: string) => request<BuildingResponse>(`/api/buildings/${id}`),
  createBuilding: (layout: BuildingLayout) =>
    request<BuildingResponse>('/api/buildings', {
      method: 'POST',
      body: JSON.stringify({ layout }),
    }),
  updateBuilding: (id: string, layout: BuildingLayout) =>
    request<BuildingResponse>(`/api/buildings/${id}`, {
      method: 'PUT',
      body: JSON.stringify({ layout }),
    }),
  uploadFloorPlan: async (buildingId: string, file: File) => {
    const res = await fetch(`${API_BASE}/api/buildings/${buildingId}/floor-plans`, {
      method: 'POST',
      headers: { 'Content-Type': 'image/png', 'X-Filename': encodeURIComponent(file.name) },
      body: file,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = await res.json();
        detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? body);
      } catch { /* ignore */ }
      throw new Error(detail);
    }
    return res.json() as Promise<{ stored: boolean; id: string; filename: string }>;
  },
  listFloorPlans: (buildingId: string) =>
    request<FloorPlanImageSummary[]>(`/api/buildings/${buildingId}/floor-plans`),
  getFloorPlan: async (buildingId: string, imageId: string) => {
    const res = await fetch(`${API_BASE}/api/buildings/${buildingId}/floor-plans/${imageId}`);
    if (!res.ok) {
      if (res.status === 404) return null;
      throw new Error(res.statusText || 'Could not load floor plan');
    }
    return URL.createObjectURL(await res.blob());
  },
  deleteBuilding: (id: string) =>
    request<void>(`/api/buildings/${id}`, { method: 'DELETE' }),
  createSimulation: (buildingId: string, parameters?: Partial<SimulationParameters>) =>
    request<{ id: string; status: string }>('/api/simulations', {
      method: 'POST',
      body: JSON.stringify({ building_id: buildingId, parameters: parameters ?? null }),
    }),
  runSimulation: (id: string) =>
    request<SimulationRunResponse>(`/api/simulations/${id}/run`, { method: 'POST' }),
  resetSimulation: (id: string) =>
    request<{ id: string; status: string }>(`/api/simulations/${id}/reset`, { method: 'POST' }),
};
