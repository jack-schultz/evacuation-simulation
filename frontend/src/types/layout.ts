export type SpaceType = 'room' | 'corridor' | 'stairs';

export const DEFAULT_FLOOR_ID = 'floor-0';

export interface Floor {
  id: string;
  name: string;
  elevation_m: number;
  order: number;
}

export interface Space {
  id: string;
  name: string;
  type: SpaceType;
  /** Closed polygon ring in metres (closing duplicate omitted). */
  vertices: [number, number][];
  capacity_density_per_m2?: number | null;
  /** Paired stairs space id for vertical pathing; only used when type is stairs. */
  linked_stair_id?: string | null;
  floor_id?: string;
}

export interface Door {
  id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  connects: [string, string];
  flow_rate_per_s?: number | null;
  floor_id?: string;
}

export interface Exit {
  id: string;
  name: string;
  x: number;
  y: number;
  width: number;
  connected_space_id: string;
  flow_rate_per_s?: number | null;
  floor_id?: string;
}

export interface OccupantGroup {
  id: string;
  name: string;
  count: number;
  space_id: string;
  spawn_x?: number | null;
  spawn_y?: number | null;
  walking_speed_mps: number;
  destination_exit_id?: string | null;
  behaviour?: Record<string, string | number | boolean>;
  floor_id?: string;
}

export interface RadialEmergency {
  enabled: boolean;
  x: number;
  y: number;
  radius_m: number;
  spread_speed_mps?: number;
  intensity: number;
  floor_id?: string;
}

export type FloodEmergency = RadialEmergency;

export interface FireEmergency extends RadialEmergency {
  emit_smoke?: boolean;
}

export interface SmokeEmergency extends RadialEmergency {
  visibility_m?: number;
  stair_spread_delay_s?: number;
  stair_spread_intensity_factor?: number;
}

export interface PixelObstacleMap {
  width: number;
  height: number;
  /** Row-major strings where 1 is blocked and 0 is walkable. */
  rows: string[];
}

export interface BuildingLayout {
  name: string;
  width: number;
  height: number;
  meters_per_cell: number;
  floors?: Floor[];
  spaces: Space[];
  doors: Door[];
  exits: Exit[];
  occupant_groups: OccupantGroup[];
  flood?: FloodEmergency | null;
  fire?: FireEmergency | null;
  smoke?: SmokeEmergency | null;
  obstacle_map?: PixelObstacleMap | null;
}
