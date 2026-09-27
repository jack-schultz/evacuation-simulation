import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  floorIdForRouteNode,
  routeSegmentsForFloor,
} from '../src/components/BuildingCanvas/layers/pathFloorFilter.ts';

const layout = {
  name: 'Multi',
  width: 40,
  height: 40,
  meters_per_cell: 1,
  floors: [
    { id: 'floor-0', name: 'Ground', order: 0, elevation_m: 0 },
    { id: 'floor-1', name: 'Level 1', order: 1, elevation_m: 3.2 },
  ],
  spaces: [
    {
      id: 'room-0',
      name: 'Ground room',
      type: 'room',
      floor_id: 'floor-0',
      vertices: [[0, 0], [10, 0], [10, 10], [0, 10]],
    },
    {
      id: 'stair-0',
      name: 'Stairs G',
      type: 'stairs',
      floor_id: 'floor-0',
      vertices: [[10, 0], [12, 0], [12, 4], [10, 4]],
      linked_stair_id: 'stair-1',
    },
    {
      id: 'stair-1',
      name: 'Stairs 1',
      type: 'stairs',
      floor_id: 'floor-1',
      vertices: [[10, 0], [12, 0], [12, 4], [10, 4]],
      linked_stair_id: 'stair-0',
    },
    {
      id: 'room-1',
      name: 'Upper room',
      type: 'room',
      floor_id: 'floor-1',
      vertices: [[0, 0], [10, 0], [10, 10], [0, 10]],
    },
  ],
  doors: [
    { id: 'door-0', name: 'D0', x: 10, y: 2, width: 1, connects: ['room-0', 'stair-0'], floor_id: 'floor-0' },
    { id: 'door-1', name: 'D1', x: 10, y: 2, width: 1, connects: ['room-1', 'stair-1'], floor_id: 'floor-1' },
  ],
  exits: [
    { id: 'exit-0', name: 'Exit', x: 0, y: 5, width: 1, connected_space_id: 'room-0', floor_id: 'floor-0' },
  ],
  occupant_groups: [
    {
      id: 'group-1',
      name: 'People',
      space_id: 'room-1',
      count: 1,
      walking_speed_mps: 1.2,
      floor_id: 'floor-1',
    },
  ],
};

test('floorIdForRouteNode maps node prefixes to storeys', () => {
  assert.equal(floorIdForRouteNode('space:room-1', layout), 'floor-1');
  assert.equal(floorIdForRouteNode('door:door-0', layout), 'floor-0');
  assert.equal(floorIdForRouteNode('exit:exit-0', layout), 'floor-0');
  assert.equal(floorIdForRouteNode('waypoint:stair-1:0', layout), 'floor-1');
  assert.equal(floorIdForRouteNode('spawn:group-1:0', layout, 'group-1'), 'floor-1');
  assert.equal(floorIdForRouteNode('space:missing', layout), null);
});

test('routeSegmentsForFloor keeps only the active storey and splits at floor changes', () => {
  const points = [
    [1, 1],
    [5, 5],
    [11, 2],
    [11, 2],
    [5, 5],
    [1, 1],
  ];
  const floors = [
    'floor-1',
    'floor-1',
    'floor-1',
    'floor-0',
    'floor-0',
    'floor-0',
  ];

  assert.deepEqual(routeSegmentsForFloor(points, floors, 'floor-1'), [
    [[1, 1], [5, 5], [11, 2]],
  ]);
  assert.deepEqual(routeSegmentsForFloor(points, floors, 'floor-0'), [
    [[11, 2], [5, 5], [1, 1]],
  ]);
  assert.deepEqual(routeSegmentsForFloor(points, floors, 'floor-1', true), [
    [[1, 1], [5, 5], [11, 2]],
    [[11, 2], [5, 5], [1, 1]],
  ]);
});
