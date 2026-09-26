"""Spatial door aperture / collision behaviour."""

import unittest

from app.domain.building import BuildingLayout, SimulationParameters, Wall
from app.simulation.collision import (
    Aabb,
    aperture_slots,
    build_collision_solids,
    dist,
    inset_aabb,
    resolve_overlaps,
    resolve_space_containment,
    resolve_wall_collisions,
    solid_wall_rects,
    space_boundary_rects,
)
from app.simulation.engine import SimulationEngine
from app.simulation.graph import NavigationGraphBuilder
from app.simulation.movement import SimulatedOccupant, SpatialMovementModel


def packed_room(door_width: float, count: int = 12, walls: list | None = None) -> BuildingLayout:
    data = {
        "width": 20,
        "height": 20,
        "spaces": [
            {
                "id": "room",
                "name": "Room",
                "type": "room",
                "x": 0,
                "y": 0,
                "width": 10,
                "height": 10,
            }
        ],
        "exits": [
            {
                "id": "out",
                "x": 10,
                "y": 5,
                "width": door_width,
                "connected_space_id": "room",
            }
        ],
        "occupant_groups": [
            {
                "id": "g",
                "name": "Crowd",
                "count": count,
                "space_id": "room",
                "walking_speed_mps": 1.4,
            }
        ],
        "walls": walls or [],
    }
    return BuildingLayout.model_validate(data)


def two_room_layout(count: int = 10) -> BuildingLayout:
    """Office above corridor, door on shared edge — mirrors typical seed adjacency."""
    return BuildingLayout.model_validate(
        {
            "width": 30,
            "height": 30,
            "spaces": [
                {
                    "id": "office",
                    "name": "Office",
                    "type": "room",
                    "x": 5,
                    "y": 5,
                    "width": 20,
                    "height": 10,
                },
                {
                    "id": "corridor",
                    "name": "Corridor",
                    "type": "corridor",
                    "x": 9,
                    "y": 15,
                    "width": 6,
                    "height": 7,
                },
            ],
            "doors": [
                {
                    "id": "d1",
                    "x": 13,
                    "y": 15,
                    "width": 0.9,
                    "connects": ["office", "corridor"],
                }
            ],
            "exits": [
                {
                    "id": "out",
                    "x": 12,
                    "y": 22,
                    "width": 1.2,
                    "connected_space_id": "corridor",
                }
            ],
            "occupant_groups": [
                {
                    "id": "g",
                    "name": "Crowd",
                    "count": count,
                    "space_id": "office",
                    "walking_speed_mps": 1.4,
                }
            ],
        }
    )


class ApertureHelpersTests(unittest.TestCase):
    def test_aperture_slots_scales_with_width(self):
        self.assertEqual(aperture_slots(0.9, 0.25), 1)
        self.assertEqual(aperture_slots(1.2, 0.25), 2)
        self.assertEqual(aperture_slots(2.0, 0.25), 4)

    def test_resolve_overlaps_separates_coincident_bodies(self):
        a = SimulatedOccupant(
            id="a", group_id="g", speed_mps=1.0, route=["n"], x=0.0, y=0.0
        )
        b = SimulatedOccupant(
            id="b", group_id="g", speed_mps=1.0, route=["n"], x=0.0, y=0.0
        )
        resolve_overlaps([a, b], radius_m=0.25, iterations=6)
        self.assertGreaterEqual(dist(a.x, a.y, b.x, b.y), 0.5 - 1e-6)


class WallCollisionHelpersTests(unittest.TestCase):
    def test_resolve_wall_collisions_pushes_body_outside(self):
        wall = Aabb(x=0.0, y=0.0, width=2.0, height=1.0)
        occ = SimulatedOccupant(
            id="a", group_id="g", speed_mps=1.0, route=["n"], x=1.0, y=0.5
        )
        resolve_wall_collisions([occ], [wall], radius_m=0.25)
        self.assertFalse(wall.contains_point(occ.x, occ.y))
        if wall.x <= occ.x <= wall.right:
            self.assertTrue(
                occ.y <= wall.y - 0.25 + 1e-9 or occ.y >= wall.bottom + 0.25 - 1e-9
            )
        if wall.y <= occ.y <= wall.bottom:
            self.assertTrue(
                occ.x <= wall.x - 0.25 + 1e-9 or occ.x >= wall.right + 0.25 - 1e-9
            )

    def test_solid_wall_rects_carves_exit_gap(self):
        walls = [Wall(id="w", x=9.7, y=0.0, width=0.6, height=10.0)]
        layout = packed_room(door_width=0.9, count=1, walls=[w.model_dump() for w in walls])
        solids = solid_wall_rects(layout.walls, layout.doors, layout.exits)
        for s in solids:
            self.assertFalse(
                s.contains_point(10.0, 5.0),
                f"exit center still blocked by {s}",
            )
        self.assertGreaterEqual(len(solids), 2)

    def test_space_boundaries_block_except_at_openings(self):
        layout = packed_room(door_width=0.9, count=1)
        solids = space_boundary_rects(layout.spaces, layout.doors, layout.exits)
        self.assertGreater(len(solids), 0)
        # Exit center on the right edge must be clear
        for s in solids:
            self.assertFalse(s.contains_point(10.0, 5.0), f"blocked by {s}")
        # Midpoint of bottom edge (no opening) must remain solid
        bottom_edge_y = 10.0
        hit = any(s.contains_point(5.0, bottom_edge_y) for s in solids)
        self.assertTrue(hit, "bottom edge without door should be solid")

    def test_build_collision_solids_includes_boundaries_without_walls(self):
        layout = packed_room(door_width=0.9, count=1)
        solids = build_collision_solids(
            layout.walls, layout.spaces, layout.doors, layout.exits
        )
        self.assertGreater(len(solids), 0)


class DoorJamTests(unittest.TestCase):
    def test_narrow_exit_serializes_passage_with_waiting(self):
        radius = 0.25
        output = SimulationEngine().run(
            packed_room(door_width=0.9, count=10),
            SimulationParameters(
                max_time_s=120,
                occupant_radius_m=radius,
                frame_interval_s=0.25,
                timestep_s=0.25,
            ),
        )
        self.assertEqual(output.results.evacuated_count, 10)
        self.assertGreater(output.results.average_wait_time_s or 0, 0)

        exit_x, exit_y = 10.0, 5.0
        throat = max(radius * 2.5, 0.6)
        max_in_throat = 0
        for frame in output.frames:
            in_throat = 0
            for o in frame.occupants:
                if o.status == "evacuated":
                    continue
                if dist(o.x, o.y, exit_x, exit_y) <= throat:
                    in_throat += 1
            max_in_throat = max(max_in_throat, in_throat)
        self.assertLessEqual(max_in_throat, aperture_slots(0.9, radius))

    def test_wide_exit_evacuates_faster_than_narrow(self):
        params = SimulationParameters(
            max_time_s=180,
            occupant_radius_m=0.25,
            frame_interval_s=0.5,
        )
        narrow = SimulationEngine().run(packed_room(0.9, count=12), params).results
        wide = SimulationEngine().run(packed_room(2.0, count=12), params).results
        self.assertEqual(narrow.evacuated_count, 12)
        self.assertEqual(wide.evacuated_count, 12)
        self.assertLess(
            wide.total_evacuation_time_s or 0,
            narrow.total_evacuation_time_s or 0,
        )

    def test_bodies_do_not_stack_on_identical_points_mid_sim(self):
        radius = 0.25
        output = SimulationEngine().run(
            packed_room(door_width=0.9, count=8),
            SimulationParameters(max_time_s=60, occupant_radius_m=radius),
        )
        min_sep = 2 * radius - 0.05
        for frame in output.frames:
            active = [o for o in frame.occupants if o.status != "evacuated"]
            for i in range(len(active)):
                for j in range(i + 1, len(active)):
                    d = dist(active[i].x, active[i].y, active[j].x, active[j].y)
                    self.assertGreaterEqual(
                        d,
                        min_sep,
                        f"overlap at t={frame.t}: {active[i].id} and {active[j].id}",
                    )

    def test_wall_across_exit_still_evacuates(self):
        walls = [
            {
                "id": "barrier",
                "name": "Barrier",
                "x": 9.7,
                "y": 0.0,
                "width": 0.6,
                "height": 10.0,
            }
        ]
        output = SimulationEngine().run(
            packed_room(door_width=0.9, count=6, walls=walls),
            SimulationParameters(max_time_s=120, occupant_radius_m=0.25),
        )
        self.assertEqual(output.results.evacuated_count, 6)

    def test_space_edge_keeps_queue_on_office_side_of_door(self):
        """Shared space edge forces approach from the office; sealed edge stays blocked."""
        layout = two_room_layout(count=12)
        solids = build_collision_solids(
            layout.walls, layout.spaces, layout.doors, layout.exits
        )
        # Sealed point on shared edge (west of door) must be solid
        self.assertTrue(
            any(s.contains_point(10.0, 15.0) for s in solids),
            "shared edge away from door should be solid",
        )
        # Door center must not be covered
        self.assertFalse(any(s.contains_point(13.0, 15.0) for s in solids))

        radius = 0.25
        output = SimulationEngine().run(
            layout,
            SimulationParameters(
                max_time_s=180,
                occupant_radius_m=radius,
                frame_interval_s=0.25,
            ),
        )
        self.assertEqual(output.results.evacuated_count, 12)

        door_x, door_y = 13.0, 15.0
        # While jammed near the door, waiting bodies should sit on the office side
        # (y <= door), not wrapped into a ring on the corridor side of the sealed edge.
        saw_jam = False
        for frame in output.frames:
            near = [
                o
                for o in frame.occupants
                if o.status != "evacuated"
                and dist(o.x, o.y, door_x, door_y) < 2.0
            ]
            if len(near) < 4:
                continue
            saw_jam = True
            office_side = sum(1 for o in near if o.y <= door_y + 0.05)
            self.assertGreaterEqual(
                office_side,
                len(near) // 2,
                f"expected queue mostly on office side at t={frame.t}",
            )
        self.assertTrue(saw_jam, "expected a multi-person jam near the door")


class SpaceContainmentTests(unittest.TestCase):
    _defaults = {
        "door_flow_per_s": 1.2,
        "stairs_flow_per_s": 1.0,
        "exit_flow_per_s": 1.5,
        "corridor_density_per_m2": 2.0,
    }

    def test_forced_through_shared_wall_clamps_back(self):
        layout = two_room_layout(count=1)
        graph = NavigationGraphBuilder().build(layout, self._defaults)
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        radius = 0.25
        # Place body center deep in the corridor without door admission
        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=1.4,
            route=["space:office", "door:d1", "space:corridor", "exit:out"],
            current_space_id="office",
            x=12.0,
            y=18.0,
        )
        resolve_space_containment([occ], spaces, doors, graph, radius, admitted=set())
        office_inset = inset_aabb(spaces["office"], radius)
        self.assertTrue(
            office_inset.contains_point(occ.x, occ.y),
            f"expected clamp into office inset, got ({occ.x}, {occ.y})",
        )
        self.assertEqual(occ.current_space_id, "office")

    def test_admitted_door_transit_allows_destination(self):
        layout = two_room_layout(count=1)
        graph = NavigationGraphBuilder().build(layout, self._defaults)
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        radius = 0.25
        corridor_inset = inset_aabb(spaces["corridor"], radius)
        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=1.4,
            route=["space:office", "door:d1", "space:corridor", "exit:out"],
            current_space_id="office",
            x=corridor_inset.x + corridor_inset.width / 2,
            y=corridor_inset.y + corridor_inset.height / 2,
        )
        resolve_space_containment(
            [occ], spaces, doors, graph, radius, admitted={"g:0"}
        )
        self.assertTrue(
            corridor_inset.contains_point(occ.x, occ.y),
            "admitted toward door should allow destination inset",
        )

        # After claiming the door and advancing onto the destination space node
        occ.route_index = 1  # on door
        SpatialMovementModel().try_advance_route(
            occ, graph, radius, t=1.0, admitted=True
        )
        # Force position at corridor centroid and advance again if still on door
        if occ.current_node_id.startswith("door:"):
            dest = graph.nodes["space:corridor"]
            occ.x, occ.y = dest.x, dest.y
            SpatialMovementModel().try_advance_route(
                occ, graph, radius, t=1.0, admitted=True
            )
        self.assertEqual(occ.current_space_id, "corridor")

        # Without admission back to office, clamp stays in corridor
        occ.x, occ.y = 10.0, 8.0  # deep in office
        resolve_space_containment([occ], spaces, doors, graph, radius, admitted=set())
        self.assertTrue(corridor_inset.contains_point(occ.x, occ.y))

    def test_large_step_toward_solid_edge_stays_inside(self):
        layout = packed_room(door_width=0.9, count=1)
        graph = NavigationGraphBuilder().build(layout, self._defaults)
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        radius = 0.25
        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=5.0,
            route=["space:room", "exit:out"],
            current_space_id="room",
            x=5.0,
            y=5.0,
        )
        # Simulate a huge discrete step through the bottom edge
        occ.y = 12.0
        resolve_space_containment([occ], spaces, doors, graph, radius)
        inset = inset_aabb(spaces["room"], radius)
        self.assertTrue(inset.contains_point(occ.x, occ.y))
        self.assertLessEqual(occ.y, inset.bottom + 1e-9)


if __name__ == "__main__":
    unittest.main()
