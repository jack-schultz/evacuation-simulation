export type SpaceType = 'room' | 'corridor' | 'stairs';

export interface Space {
  id: string;
  name: string;
  type: SpaceType;
  /** Closed polygon ring in metres (closing duplicate omitted). */
  vertices: [number, number][];
  capacity_density_per_m2?: number | null;
  /** Paired stairs space id for teleport pathing; only used when type is stairs. */
  linked_stair_id?: string | null;
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
  spawn_x?: number | null;
  spawn_y?: number | null;
  walking_speed_mps: number;
  destination_exit_id?: string | null;
  behaviour?: Record<string, string | number | boolean>;
}

export interface RadialEmergency {
  enabled: boolean;
  x: number;
  y: number;
  radius_m: number;
  spread_speed_mps?: number;
  intensity: number;
}

export type FloodEmergency = RadialEmergency;
export type FireEmergency = RadialEmergency;

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
  spaces: Space[];
  doors: Door[];
  exits: Exit[];
  occupant_groups: OccupantGroup[];
  flood?: FloodEmergency | null;
  fire?: FireEmergency | null;
  obstacle_map?: PixelObstacleMap | null;
}
