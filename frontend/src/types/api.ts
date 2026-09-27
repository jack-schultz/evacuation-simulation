import type { BuildingLayout } from './layout';

export interface BuildingSummary {
  id: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface BuildingResponse {
  id: string;
  name: string;
  layout: BuildingLayout;
  created_at: string;
  updated_at: string;
}

export interface FloorPlanImageSummary {
  id: string;
  filename: string;
  created_at: string;
}

export interface SimulationParameters {
  timestep_s: number;
  max_time_s: number;
  door_flow_per_s: number;
  stairs_flow_per_s: number;
  exit_flow_per_s: number;
  corridor_density_per_m2: number;
  occupant_radius_m: number;
  frame_interval_s: number;
  hazard_clearance_m?: number;
  hazard_soft_clearance_m?: number;
}

export interface OccupantFrameState {
  id: string;
  x: number;
  y: number;
  status: 'active' | 'waiting' | 'evacuated' | 'trapped' | 'climbing';
  deceased?: boolean;
  group_id: string;
  floor_id?: string;
  route_index?: number;
  climb_progress?: number | null;
  /** Remaining debug polyline: local skirt hops then openings. */
  path_preview?: [number, number][];
}

export interface SmokeFloorState {
  floor_id: string;
  radius_m: number;
  x: number;
  y: number;
  intensity: number;
}

export interface FloodRoomState {
  space_id: string;
  radius_m: number;
  x: number;
  y: number;
  intensity: number;
}

export interface SmokeRoomState {
  space_id: string;
  radius_m: number;
  x: number;
  y: number;
  intensity: number;
}

export interface SimulationFrame {
  flood_radius_m?: number | null;
  flood_rooms?: FloodRoomState[];
  fire_radius_m?: number | null;
  fire_floors?: SmokeFloorState[];
  smoke_floors?: SmokeFloorState[];
  smoke_rooms?: SmokeRoomState[];
  t: number;
  occupants: OccupantFrameState[];
}

export interface CongestionHotspot {
  element_id: string;
  element_type: 'door' | 'corridor' | 'stairs' | 'exit';
  total_wait_s: number;
  peak_queue: number;
}

export interface OccupantResult {
  id: string;
  group_id: string;
  evacuated: boolean;
  deceased?: boolean;
  distance_m: number;
  travel_time_s: number;
  wait_time_s: number;
  total_time_s: number;
  route_node_ids: string[];
  route_points: [number, number][];
  /** Floor id for each route_points entry (same length). */
  route_floors?: string[];
  /** Index into route_node_ids for each route_points entry. */
  route_point_indexes?: number[];
}

export interface SimulationResults {
  total_occupants: number;
  evacuated_count: number;
  remaining_count: number;
  death_count?: number;
  total_evacuation_time_s: number | null;
  average_evacuation_time_s: number | null;
  max_evacuation_time_s: number | null;
  average_distance_m: number | null;
  average_wait_time_s: number | null;
  congestion_hotspots: CongestionHotspot[];
  occupants: OccupantResult[];
  assumptions_note: string;
}

export interface SimulationRunResponse {
  id: string;
  building_id: string;
  status: string;
  parameters: SimulationParameters;
  results: SimulationResults | null;
  frames: SimulationFrame[];
  error_message: string | null;
}
