import assert from 'node:assert/strict';
import { test } from 'node:test';
import { exitSpaceAt, moveExit } from '../src/exitPlacement.ts';

function rect(id, name, x, y, width, height) {
  return {
    id,
    name,
    type: 'room',
    vertices: [
      [x, y],
      [x + width, y],
      [x + width, y + height],
      [x, y + height],
    ],
  };
}

const layout = {
  name: 'Two rooms', width: 30, height: 20, meters_per_cell: 1,
  spaces: [
    rect('a', 'A', 0, 0, 10, 10),
    rect('b', 'B', 10, 0, 10, 10),
  ],
  exits: [{ id: 'exit', name: 'Exit', x: 0, y: 5, width: 1.2, connected_space_id: 'a' }],
  doors: [], occupant_groups: [],
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
    rect('a', 'A', 0, 0, 20, 20),
    rect('b', 'B', 22, 8, 2, 2),
  ] };
  assert.equal(exitSpaceAt(uneven, 20.5, 9), 'a');
});

test('dropping inside a new room takes priority over the previous connection', () => {
  assert.equal(moveExit(layout, 'exit', 12, 5).exits[0].connected_space_id, 'b');
});

test('placing on an exterior wall chooses the adjacent room', () => {
  assert.equal(exitSpaceAt(layout, 0, 5), 'a');
  assert.equal(exitSpaceAt(layout, 20, 5), 'b');
});

test('nearest polygon edge determines the connection outside concave rooms', () => {
  const concave = {
    id: 'concave', name: 'L room', type: 'room',
    vertices: [[0, 0], [12, 0], [12, 2], [2, 2], [2, 12], [0, 12]],
  };
  const nearby = rect('nearby', 'Nearby', 7, 6, 2, 2);
  const building = { ...layout, spaces: [concave, nearby] };
  // This point is in the L room's bounding box but outside its polygon.
  assert.equal(exitSpaceAt(building, 6, 6), 'nearby');
});
