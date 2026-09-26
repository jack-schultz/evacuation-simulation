import type { BuildingLayout } from '../types/building';

export const emptyLayout = (): BuildingLayout => ({
  name: 'New Building',
  width: 48,
  height: 36,
  meters_per_cell: 1,
  spaces: [],
  doors: [],
  exits: [],
  occupant_groups: [],
});
