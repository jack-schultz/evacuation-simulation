"""Spatial door aperture / collision behaviour."""

import unittest

from app.domain.building import BuildingLayout, SimulationParameters
from app.simulation.collision import (
    Aabb,
    aperture_slots,
    build_collision_solids,
    dist,
    inset_aabb,
    resolve_overlaps,
    resolve_space_containment,
    resolve_wall_collisions,
    space_boundary_rects,
    update_space_membership_from_position,
)
from app.simulation.engine import SimulationEngine
from app.simulation.graph import NavigationGraphBuilder
from app.simulation.movement import SimulatedOccupant, SpatialMovementModel


def packed_room(door_width: float, count: int = 12) -> BuildingLayout:
    data = {
        "width": 20,
        "height": 20,
        "spaces": [
            {
                "id": "room",
                "name": "Room",
                "type": "room",
                "vertices": [[0, 0], [10, 0], [10, 10], [0, 10]],
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
                    "vertices": [[5, 5], [25, 5], [25, 15], [5, 15]],
                },
                {
                    "id": "corridor",
                    "name": "Corridor",
                    "type": "corridor",
                    "vertices": [[9, 15], [15, 15], [15, 22], [9, 22]],
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

    def test_build_collision_solids_uses_space_boundaries(self):
        layout = packed_room(door_width=0.9, count=1)
        solids = build_collision_solids(layout.spaces, layout.doors, layout.exits)
        self.assertGreater(len(solids), 0)
        self.assertEqual(
            len(solids),
            len(space_boundary_rects(layout.spaces, layout.doors, layout.exits)),
        )


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

    def test_space_edge_keeps_queue_on_office_side_of_door(self):
        """Shared space edge forces approach from the office; sealed edge stays blocked."""
        layout = two_room_layout(count=12)
        solids = build_collision_solids(layout.spaces, layout.doors, layout.exits)
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
        # Anyone west of the gap while still on the shared edge must stay on
        # the office side — they must not wrap through the sealed wall.
        # People who already passed the door and wait in the corridor are fine.
        saw_west = False
        for frame in output.frames:
            west_near = [
                o
                for o in frame.occupants
                if o.status != "evacuated"
                and dist(o.x, o.y, door_x, door_y) < 2.5
                and o.x <= door_x - 0.6
                and abs(o.y - door_y) <= 0.35
            ]
            if not west_near:
                continue
            saw_west = True
            for o in west_near:
                self.assertLessEqual(
                    o.y,
                    door_y + 0.05,
                    f"body west of door gap wrapped to corridor at t={frame.t}",
                )
        self.assertTrue(saw_west, "expected occupants west of the door during egress")

    def test_bodies_do_not_stack_on_identical_points_mid_sim(self):
        radius = 0.25
        output = SimulationEngine().run(
            packed_room(door_width=0.9, count=8),
            SimulationParameters(max_time_s=60, occupant_radius_m=radius),
        )
        min_sep = 2 * radius - 0.1
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

    def test_small_timestep_still_clears_doorway(self):
        """Body-radius inset must not strand the last person on the origin side."""
        # Step length 1.4 * 0.1 = 0.14 < radius 0.25 — previously never crossed.
        output = SimulationEngine().run(
            two_room_layout(count=6),
            SimulationParameters(
                max_time_s=120,
                occupant_radius_m=0.25,
                timestep_s=0.1,
                frame_interval_s=0.5,
            ),
        )
        self.assertEqual(output.results.evacuated_count, 6)
        door_x, door_y = 13.0, 15.0
        last = output.frames[-1]
        stranded = [
            o
            for o in last.occupants
            if o.status != "evacuated" and dist(o.x, o.y, door_x, door_y) < 1.0
        ]
        self.assertEqual(stranded, [])

    def test_wide_exit_evacuates_faster_than_narrow(self):
        params = SimulationParameters(
            max_time_s=180,
            occupant_radius_m=0.25,
            frame_interval_s=0.5,
        )
        # Larger crowd so aperture width dominates travel time noise.
        narrow = SimulationEngine().run(packed_room(0.9, count=24), params).results
        wide = SimulationEngine().run(packed_room(2.0, count=24), params).results
        self.assertEqual(narrow.evacuated_count, 24)
        self.assertEqual(wide.evacuated_count, 24)
        self.assertLess(
            wide.total_evacuation_time_s or 0,
            narrow.total_evacuation_time_s or 0,
        )


class SpaceContainmentTests(unittest.TestCase):
    _defaults = {
        "door_flow_per_s": 1.2,
        "stairs_flow_per_s": 1.0,
        "exit_flow_per_s": 1.5,
        "corridor_density_per_m2": 2.0,
    }

    def test_membership_does_not_flip_back_on_shared_door_edge(self):
        """Shared-edge points belong to both polygons; transit must stay one-way."""
        layout = two_room_layout(count=1)
        graph = NavigationGraphBuilder().build(layout, self._defaults)
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=1.4,
            route=["space:office", "door:d1", "exit:out"],
            route_index=1,
            current_space_id="corridor",
            x=13.0,
            y=15.0,  # exactly on the shared door edge
        )
        update_space_membership_from_position(
            [occ], spaces, doors, graph, admitted={"g:0"}
        )
        self.assertEqual(occ.current_space_id, "corridor")

    def test_forced_through_shared_wall_clamps_back(self):
        layout = two_room_layout(count=1)
        graph = NavigationGraphBuilder().build(layout, self._defaults)
        spaces = {s.id: s for s in layout.spaces}
        radius = 0.25
        # Place body center deep in the corridor without door membership flip
        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=1.4,
            route=["space:office", "door:d1", "exit:out"],
            current_space_id="office",
            x=12.0,
            y=18.0,
        )
        resolve_space_containment([occ], spaces, radius)
        office_inset = inset_aabb(spaces["office"], radius)
        self.assertTrue(
            office_inset.contains_point(occ.x, occ.y),
            f"expected clamp into office inset, got ({occ.x}, {occ.y})",
        )
        self.assertEqual(occ.current_space_id, "office")

    def test_membership_flip_then_single_space_clamp(self):
        layout = two_room_layout(count=1)
        graph = NavigationGraphBuilder().build(layout, self._defaults)
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        radius = 0.25
        office_inset = inset_aabb(spaces["office"], radius)
        corridor_inset = inset_aabb(spaces["corridor"], radius)

        # Admission alone does not allow free-roaming in the destination.
        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=1.4,
            route=["space:office", "door:d1", "exit:out"],
            current_space_id="office",
            x=corridor_inset.x + corridor_inset.width / 2,
            y=corridor_inset.y + corridor_inset.height / 2,
        )
        resolve_space_containment([occ], spaces, radius)
        self.assertTrue(
            office_inset.contains_point(occ.x, occ.y),
            "origin member must clamp to origin without membership flip",
        )
        self.assertEqual(occ.current_space_id, "office")

        # Body in destination while admitted/on door flips membership, then stays.
        occ.route_index = 1
        occ.x = corridor_inset.x + corridor_inset.width / 2
        occ.y = corridor_inset.y + corridor_inset.height / 2
        update_space_membership_from_position(
            [occ], spaces, doors, graph, admitted={"g:0"}
        )
        self.assertEqual(occ.current_space_id, "corridor")
        resolve_space_containment([occ], spaces, radius)
        self.assertTrue(corridor_inset.contains_point(occ.x, occ.y))

        # Corridor member without transit is clamped out of the office
        occ2 = SimulatedOccupant(
            id="g:1",
            group_id="g",
            speed_mps=1.4,
            route=["space:corridor", "exit:out"],
            route_index=0,
            current_space_id="corridor",
            x=10.0,
            y=8.0,
        )
        resolve_space_containment([occ2], spaces, radius)
        self.assertTrue(corridor_inset.contains_point(occ2.x, occ2.y))

    def test_cannot_advance_past_door_until_in_destination(self):
        layout = two_room_layout(count=1)
        graph = NavigationGraphBuilder().build(layout, self._defaults)
        spaces = {s.id: s for s in layout.spaces}
        doors = {d.id: d for d in layout.doors}
        radius = 0.25
        movement = SpatialMovementModel()

        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=1.4,
            route=["space:office", "door:d1", "exit:out"],
            current_space_id="office",
            x=13.0,
            y=14.75,
        )
        # Claim the door while still origin-side
        movement.try_advance_route(
            occ, graph, radius, t=1.0, admitted=True, doors=doors
        )
        self.assertEqual(occ.current_node_id, "door:d1")
        self.assertEqual(occ.current_space_id, "office")

        # Still in office near door — must not advance toward the exit
        occ.x, occ.y = 13.0, 14.8
        movement.try_advance_route(
            occ, graph, radius, t=1.0, admitted=True, doors=doors
        )
        self.assertEqual(occ.current_node_id, "door:d1")
        self.assertEqual(occ.current_space_id, "office")
        self.assertNotEqual(occ.status.value, "evacuated")

        # Enter corridor physically → membership flips → can leave the door
        occ.x, occ.y = 12.0, 18.0
        update_space_membership_from_position(
            [occ], spaces, doors, graph, admitted={"g:0"}
        )
        self.assertEqual(occ.current_space_id, "corridor")
        # Near the exit on the destination side
        occ.x, occ.y = 12.0, 21.7
        movement.try_advance_route(
            occ, graph, radius, t=1.0, admitted=True, doors=doors
        )
        self.assertEqual(occ.status.value, "evacuated")

    def test_large_step_toward_solid_edge_stays_inside(self):
        layout = packed_room(door_width=0.9, count=1)
        spaces = {s.id: s for s in layout.spaces}
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
        resolve_space_containment([occ], spaces, radius)
        inset = inset_aabb(spaces["room"], radius)
        self.assertTrue(inset.contains_point(occ.x, occ.y))
        self.assertLessEqual(occ.y, inset.bottom + 1e-9)

    def test_obstacle_waypoint_nearer_far_room_still_opens_door(self):
        """Lobby obstacle waypoints can sit closer to the stair centroid than lobby.

        Forward space must follow waypoint ownership, not centroid distance —
        otherwise containment clamps bodies back onto the origin side forever.
        """
        from app.domain.building import OccupantStatus
        from app.simulation.containment import _forward_space_for_door

        layout = BuildingLayout.model_validate(
            {
                "width": 30,
                "height": 20,
                "spaces": [
                    {
                        "id": "lobby",
                        "name": "Lobby",
                        "type": "room",
                        "floor_id": "floor-0",
                        "vertices": [[1, 1], [17, 1], [17, 13], [1, 13]],
                    },
                    {
                        "id": "stairs_g",
                        "name": "Stairs",
                        "type": "stairs",
                        "floor_id": "floor-0",
                        "vertices": [[17, 2], [19, 2], [19, 8], [17, 8]],
                    },
                ],
                "doors": [
                    {
                        "id": "door_lobby_stairs",
                        "x": 17,
                        "y": 3,
                        "width": 0.6,
                        "connects": ["lobby", "stairs_g"],
                        "floor_id": "floor-0",
                    }
                ],
                "exits": [
                    {
                        "id": "exit_street",
                        "x": 1,
                        "y": 11,
                        "width": 1.4,
                        "connected_space_id": "lobby",
                        "floor_id": "floor-0",
                    }
                ],
                "obstacles": [
                    {
                        "id": "desk",
                        "x": 14.5,
                        "y": 4.5,
                        "width": 1.0,
                        "height": 1.0,
                        "floor_id": "floor-0",
                    }
                ],
                "occupant_groups": [
                    {
                        "id": "g",
                        "name": "Crowd",
                        "count": 1,
                        "space_id": "stairs_g",
                        "floor_id": "floor-0",
                        "walking_speed_mps": 1.2,
                    }
                ],
            }
        )
        graph = NavigationGraphBuilder().build(layout, self._defaults)
        doors = {d.id: d for d in layout.doors}
        spaces = {s.id: s for s in layout.spaces}
        wp_id = next(
            nid
            for nid, n in graph.nodes.items()
            if n.kind.value == "waypoint" and n.ref_id == "lobby"
        )
        lobby_n = graph.nodes[graph.space_node_ids["lobby"]]
        stairs_n = graph.nodes[graph.space_node_ids["stairs_g"]]
        wp = graph.nodes[wp_id]
        # Sanity: this is the mis-ranking geometry the bug depended on.
        self.assertLess(
            dist(wp.x, wp.y, stairs_n.x, stairs_n.y),
            dist(wp.x, wp.y, lobby_n.x, lobby_n.y),
        )

        occ = SimulatedOccupant(
            id="g:0",
            group_id="g",
            speed_mps=1.2,
            route=["space:stairs_g", "door:door_lobby_stairs", wp_id, "exit:exit_street"],
            route_index=1,
            current_space_id="stairs_g",
            x=16.6,
            y=3.0,
            status=OccupantStatus.ACTIVE,
            floor_id="floor-0",
        )
        self.assertEqual(
            _forward_space_for_door(occ, doors["door_lobby_stairs"], graph),
            "lobby",
        )
        update_space_membership_from_position(
            [occ], spaces, doors, graph, admitted={"g:0"}
        )
        self.assertEqual(occ.current_space_id, "lobby")
        resolve_space_containment(
            [occ], spaces, 0.25, doors=doors, graph=graph, admitted={"g:0"}
        )
        self.assertLess(occ.x, 17.0, "must stay on lobby side, not clamped into stairs")

        output = SimulationEngine().run(
            layout,
            SimulationParameters(max_time_s=120, occupant_radius_m=0.25),
        )
        self.assertEqual(output.results.evacuated_count, 1)


if __name__ == "__main__":
    unittest.main()
