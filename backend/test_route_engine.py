import unittest

from route_engine import recommend_route


NOW = "2026-07-21T15:00:00+09:00"


class RouteEngineTest(unittest.TestCase):
    def test_qr_gate_changes_start_location(self):
        e3 = recommend_route("E3-01", 30, "memory", now_value=NOW)
        e4 = recommend_route("E4-01", 30, "memory", now_value=NOW)
        self.assertEqual(e3["gate"]["node"], "E3_WEST")
        self.assertEqual(e4["gate"]["node"], "E4_WEST")
        self.assertNotEqual(e3["route"]["path_nodes"][0], e4["route"]["path_nodes"][0])

    def test_route_uses_exact_requested_time_budget(self):
        result = recommend_route("E4-01", 30, "make", now_value=NOW)
        self.assertEqual(result["route"]["total_minutes"], 30)
        self.assertEqual(
            result["route"]["active_minutes"] + result["route"]["remaining_minutes"],
            30,
        )

    def test_ten_and_sixty_minute_courses_are_exact(self):
        ten = recommend_route("E4-01", 10, "make", now_value=NOW)
        sixty = recommend_route("E3-01", 60, "memory", now_value=NOW)
        self.assertEqual(ten["route"]["total_minutes"], 10)
        self.assertEqual(sixty["route"]["total_minutes"], 60)

    def test_redevelopment_course_labels_new_spaces(self):
        result = recommend_route("E4-01", 30, "make", now_value=NOW)
        labels = {stop["status_label"] for stop in result["route"]["stops"]}
        self.assertIn("신규 조성 예정", labels)
        self.assertEqual(result["request"]["scenario"], "after_redevelopment")

    def test_destination_is_reserved_in_time_budget(self):
        result = recommend_route("E3-01", 60, "look", destination="DDP", now_value=NOW)
        self.assertEqual(result["route"]["path_nodes"][-1], "DDP_GATE")
        self.assertLessEqual(result["route"]["total_minutes"], 60)

    def test_gate_alias_is_supported(self):
        result = recommend_route("DDP", 30, "look", now_value=NOW)
        self.assertEqual(result["gate"]["token"], "DDP-01")


if __name__ == "__main__":
    unittest.main()
