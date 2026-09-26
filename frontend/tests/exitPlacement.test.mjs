import assert from 'node:assert/strict';
import { test } from 'node:test';
import { exitSpaceAt, moveExit } from '../src/exitPlacement.ts';

const layout = {
  name: 'Two rooms', width: 30, height: 20, meters_per_cell: 1,
  spaces: [
    { id: 'a', name: 'A', type: 'room', x: 0, y: 0, width: 10, height: 10 },
    { id: 'b', name: 'B', type: 'room', x: 10, y: 0, width: 10, height: 10 },
  ],
  exits: [{ id: 'exit', name: 'Exit', x: 0, y: 5, width: 1.2, connected_space_id: 'a' }],
  walls: [], doors: [], occupant_groups: [],
};

test('moving an exit updates the serialized coordinates and routing connection together', () => {
  const moved = moveExit(layout, 'exit', 20, 5);
  const payload = JSON.parse(JSON.stringify({ layout: moved }));
  assert.deepEqual(payload.layout.exits[0], {
    ...layout.exits[0], x: 20, y: 5, connected_space_id: 'b',
  });
  // Undo retains the original geometry and connection.
  assert.equal(layout.exits[0].x, 0);
  assert.equal(layout.exits[0].connected_space_id, 'a');
});

test('moving within the same room retains its connection', () => {
  assert.equal(moveExit(layout, 'exit', 5, 0).exits[0].connected_space_id, 'a');
});

test('shared boundaries preserve the current connection regardless of space order', () => {
  assert.equal(exitSpaceAt(layout, 10, 5, 'b'), 'b');
  assert.equal(exitSpaceAt({ ...layout, spaces: [...layout.spaces].reverse() }, 10, 5, 'a'), 'a');
});

test('outside drops choose the nearest rectangle rather than its center', () => {
  const uneven = { ...layout, spaces: [
    { ...layout.spaces[0], width: 20, height: 20 },
    { ...layout.spaces[1], x: 22, y: 8, width: 2, height: 2 },
  ] };
  assert.equal(exitSpaceAt(uneven, 20.5, 9), 'a');
});

test('dropping inside a new room takes priority over the previous connection', () => {
  assert.equal(moveExit(layout, 'exit', 12, 5).exits[0].connected_space_id, 'b');
});
