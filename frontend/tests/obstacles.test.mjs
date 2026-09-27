import assert from 'node:assert/strict';
import { test } from 'node:test';
import { deleteFloor, duplicateFloor } from '../src/layout/floors.ts';
import { filterLayoutByFloor } from '../src/layout/emptyLayout.ts';
import { deleteRefs, extractSelection, pastePayload, translateSelection } from '../src/layout/clipboard.ts';
import { contentMinSize } from '../src/components/BuildingCanvas/buildingBounds.ts';

const layout = {
  name: 'Obstacles', width: 30, height: 20, meters_per_cell: 1,
  floors: [{ id: 'floor-0', name: 'Ground', order: 0, elevation_m: 0 }],
  spaces: [], doors: [], exits: [], occupant_groups: [],
  obstacles: [{ id: 'box', name: 'Box', x: 3, y: 4, width: 5, height: 2, floor_id: 'floor-0' }],
};
const selection = [{ kind: 'obstacle', id: 'box' }];

test('obstacle clipboard and delete preserve the source layout', () => {
  const payload = extractSelection(layout, selection);
  const pasted = pastePayload(layout, payload, { x: 1, y: 2 }, 'floor-0');
  assert.equal(pasted.layout.obstacles.length, 2);
  const copy = pasted.layout.obstacles[1];
  assert.notEqual(copy.id, 'box');
  assert.deepEqual([copy.x, copy.y, copy.width, copy.height], [4, 6, 5, 2]);
  assert.equal(copy.floor_id, 'floor-0');
  assert.equal(deleteRefs(pasted.layout, pasted.selection).obstacles.length, 1);
  assert.equal(layout.obstacles.length, 1);
});

test('paste onto another floor reassigns floor_id', () => {
  const multiFloor = {
    ...layout,
    floors: [
      ...layout.floors,
      { id: 'floor-1', name: 'Level 1', order: 1, elevation_m: 3.2 },
    ],
    spaces: [
      {
        id: 'room',
        name: 'Room',
        type: 'room',
        floor_id: 'floor-0',
        vertices: [[0, 0], [4, 0], [4, 4], [0, 4]],
      },
    ],
  };
  const payload = extractSelection(multiFloor, [
    { kind: 'space', id: 'room' },
    { kind: 'obstacle', id: 'box' },
  ]);
  const pasted = pastePayload(multiFloor, payload, { x: 1, y: 1 }, 'floor-1');
  const spaceCopy = pasted.layout.spaces.find((s) => s.id !== 'room');
  const obstacleCopy = pasted.layout.obstacles.find((o) => o.id !== 'box');
  assert.equal(spaceCopy.floor_id, 'floor-1');
  assert.equal(obstacleCopy.floor_id, 'floor-1');
  assert.equal(filterLayoutByFloor(pasted.layout, 'floor-1').spaces.length, 1);
  assert.equal(filterLayoutByFloor(pasted.layout, 'floor-1').obstacles.length, 1);
});

test('moving obstacles stays inside the building and preserves rectangular dimensions', () => {
  const moved = translateSelection(layout, selection, 100, -100).obstacles[0];
  assert.deepEqual([moved.x, moved.y, moved.width, moved.height], [25, 0, 5, 2]);
  assert.deepEqual(contentMinSize(layout), { width: 8, height: 6 });
});

test('floor duplication, filtering and deletion include obstacles', () => {
  const duplicated = duplicateFloor(layout, 'floor-0');
  assert.equal(duplicated.layout.obstacles.length, 2);
  const upper = filterLayoutByFloor(duplicated.layout, duplicated.newFloorId);
  assert.equal(upper.obstacles.length, 1);
  assert.equal(upper.obstacles[0].floor_id, duplicated.newFloorId);
  assert.notEqual(upper.obstacles[0].id, 'box');
  assert.deepEqual(deleteFloor(duplicated.layout, duplicated.newFloorId).obstacles, layout.obstacles);
});
