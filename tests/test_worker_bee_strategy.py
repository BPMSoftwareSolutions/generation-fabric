import unittest

from generation_fabric.worker_bee.strategy import build_default_worker_bee_strategy


class WorkerBeeStrategyTests(unittest.TestCase):
    def test_default_strategy_describes_the_expected_migration_path(self) -> None:
        strategy = build_default_worker_bee_strategy()

        self.assertEqual(strategy.north_star, "planner -> packet -> worker -> fabric -> verifier")
        self.assertIn("planner may use a language model", strategy.planner_reviewer_boundary)

        phase_names = [phase.name for phase in strategy.phases]
        self.assertEqual(
            phase_names,
            [
                "stabilize_surface",
                "planner_contract",
                "executor_contract",
                "verification_loop",
                "operationalize",
            ],
        )

        surface_names = [surface.name for surface in strategy.surfaces]
        self.assertEqual(
            surface_names,
            [
                "contract_pipeline",
                "cli_orchestration",
                "planner_layer",
                "executor_layer",
                "ledger_and_verification",
            ],
        )

        self.assertIn("existing", {surface.status for surface in strategy.surfaces})
        self.assertIn("planned", {surface.status for surface in strategy.surfaces})
        self.assertTrue(all(surface.files for surface in strategy.surfaces))
