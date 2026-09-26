export type SpaceType = 'room' | 'corridor' | 'stairs';

export interface Space {
  id: string;
  name: string;
  type: SpaceType;
  x: number;
  y: number;
  width: number;
  height: number;
  capacity_density_per_m2?: number | null;
}

export interface Wall {
  id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Door {
  id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  connects: [string, string];
  flow_rate_per_s?: number | null;
}

export interface Exit {
  id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  connected_space_id: string;
  flow_rate_per_s?: number | null;
}

export interface OccupantGroup {
  id: string;
  name: string;
  count: number;
  space_id: string;
  walking_speed_mps: number;
  destination_exit_id?: string | null;
  behaviour?: Record<string, string | number | boolean>;
}

export interface FloodEmergency {
  enabled: boolean;
  x: number;
  y: number;
  radius_m: number;
  intensity: number;
}

export interface BuildingLayout {
  name: string;
  width: number;
  height: number;
  meters_per_cell: number;
  spaces: Space[];
  walls: Wall[];
  doors: Door[];
  exits: Exit[];
  occupant_groups: OccupantGroup[];
  flood?: FloodEmergency | null;
}

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

export interface SimulationParameters {
  timestep_s: number;
  max_time_s: number;
  door_flow_per_s: number;
  stairs_flow_per_s: number;
  exit_flow_per_s: number;
  corridor_density_per_m2: number;
  frame_interval_s: number;
}

export interface OccupantFrameState {
  id: string;
  x: number;
  y: number;
  status: 'active' | 'waiting' | 'evacuated' | 'trapped';
  group_id: string;
}

export interface SimulationFrame {
  t: number;
  occupants: OccupantFrameState[];
}

export interface CongestionHotspot {
  element_id: string;
  element_type: 'door' | 'corridor' | 'stairs' | 'exit';
  total_wait_s: number;
  peak_queue: number;
}

export interface SimulationResults {
  total_occupants: number;
  evacuated_count: number;
  remaining_count: number;
  total_evacuation_time_s: number | null;
  average_evacuation_time_s: number | null;
  max_evacuation_time_s: number | null;
  average_distance_m: number | null;
  average_wait_time_s: number | null;
  congestion_hotspots: CongestionHotspot[];
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

export type EditorTool =
  | 'select'
  | 'room'
  | 'corridor'
  | 'stairs'
  | 'wall'
  | 'door'
  | 'exit'
  | 'occupants';

export type SelectedRef =
  | { kind: 'space'; id: string }
  | { kind: 'wall'; id: string }
  | { kind: 'door'; id: string }
  | { kind: 'exit'; id: string }
  | { kind: 'occupants'; id: string }
  | null;
