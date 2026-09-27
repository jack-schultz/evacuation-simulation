import type {
  BuildingLayout,
  FireEmergency,
  FloodEmergency,
} from '../types/building';

function asHazardList<T extends { id?: string }>(
  plural: unknown,
  singular: unknown,
  fallbackId: string,
): T[] {
  const fromPlural = Array.isArray(plural)
    ? plural
    : plural && typeof plural === 'object'
      ? [plural]
      : null;
  const fromSingular =
    singular && typeof singular === 'object' && !Array.isArray(singular)
      ? [singular]
      : Array.isArray(singular)
        ? singular
        : [];
  const raw = (fromPlural ?? fromSingular) as T[];
  return raw.map((item, index) => ({
    ...item,
    id: item.id || (index === 0 ? fallbackId : `${fallbackId}-${index}`),
  }));
}

/** Normalize legacy flood/fire singletons into floods/fires arrays with ids. */
export function normalizeHazards(layout: BuildingLayout): BuildingLayout {
  const floods = asHazardList<FloodEmergency>(layout.floods, layout.flood, 'flood');
  const fires = asHazardList<FireEmergency>(layout.fires, layout.fire, 'fire');
  const { flood: _flood, fire: _fire, ...rest } = layout;
  return { ...rest, floods, fires };
}

export function layoutFloods(layout: BuildingLayout): FloodEmergency[] {
  return normalizeHazards(layout).floods ?? [];
}

export function layoutFires(layout: BuildingLayout): FireEmergency[] {
  return normalizeHazards(layout).fires ?? [];
}
