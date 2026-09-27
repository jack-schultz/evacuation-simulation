import assert from 'node:assert/strict';
import { test } from 'node:test';
import { findOverlappingSpaceIds } from '../src/components/BuildingCanvas/geometryHelpers.ts';
import { polygonsOverlap } from '../src/utils.ts';

test('edge-adjacent rectangles do not overlap', () => {
  const a = [[0, 0], [10, 0], [10, 10], [0, 10]];
  const b = [[10, 0], [20, 0], [20, 10], [10, 10]];
  assert.equal(polygonsOverlap(a, b), false);
});

test('partially overlapping rectangles are detected', () => {
  const a = [[0, 0], [10, 0], [10, 10], [0, 10]];
  const b = [[5, 5], [15, 5], [15, 15], [5, 15]];
  assert.equal(polygonsOverlap(a, b), true);
});

test('contained rectangle overlaps its host', () => {
  const outer = [[0, 0], [20, 0], [20, 20], [0, 20]];
  const inner = [[5, 5], [10, 5], [10, 10], [5, 10]];
  assert.equal(polygonsOverlap(outer, inner), true);
});

test('findOverlappingSpaceIds ignores stairs and other floors', () => {
  const layout = {
    name: 'Overlap',
    width: 40,
    height: 20,
    meters_per_cell: 1,
    floors: [
      { id: 'floor-0', name: 'Ground', order: 0, elevation_m: 0 },
      { id: 'floor-1', name: 'Level 1', order: 1, elevation_m: 3 },
    ],
    spaces: [
      {
        id: 'a',
        name: 'A',
        type: 'room',
        floor_id: 'floor-0',
        vertices: [[0, 0], [10, 0], [10, 10], [0, 10]],
      },
      {
        id: 'b',
        name: 'B',
        type: 'room',
        floor_id: 'floor-0',
        vertices: [[5, 5], [15, 5], [15, 15], [5, 15]],
      },
      {
        id: 'stairs',
        name: 'Stairs',
        type: 'stairs',
        floor_id: 'floor-0',
        vertices: [[1, 1], [3, 1], [3, 3], [1, 3]],
      },
      {
        id: 'upper',
        name: 'Upper',
        type: 'room',
        floor_id: 'floor-1',
        vertices: [[0, 0], [10, 0], [10, 10], [0, 10]],
      },
    ],
    doors: [],
    exits: [],
    occupant_groups: [],
  };
  const overlapping = findOverlappingSpaceIds(layout);
  assert.deepEqual([...overlapping].sort(), ['a', 'b']);
});
