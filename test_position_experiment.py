import unittest

import run_position_experiment as experiment


class PositionExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conditions = experiment.create_conditions(experiment.CONTEXT_SIZES)

    def test_expected_condition_count(self):
        self.assertEqual(len(self.conditions), 36)
        self.assertEqual(
            len({condition["condition_id"] for condition in self.conditions}),
            36,
        )

    def test_each_prompt_has_the_registered_card_count(self):
        for condition in self.conditions:
            self.assertEqual(
                condition["prompt"].count("% Card "),
                condition["context_size_cards"],
            )

    def test_prompt_does_not_hint_at_the_solution_method(self):
        for condition in self.conditions:
            instruction = condition["prompt"].split("% Card 1 Contents %")[0]
            self.assertNotIn("numbered month", instruction.casefold())
            self.assertNotIn("relevant card", instruction.casefold())
            self.assertNotIn("such as", instruction.casefold())

    def test_position_variants_share_distractors(self):
        for item in experiment.EXPERIMENT_ITEMS:
            for context_size in experiment.CONTEXT_SIZES:
                group = [
                    condition
                    for condition in self.conditions
                    if condition["item_id"] == item["item_id"]
                    and condition["context_size_cards"] == context_size
                ]
                self.assertEqual(len(group), 3)
                self.assertEqual(
                    len(
                        {
                            condition["distractor_sha256"]
                            for condition in group
                        }
                    ),
                    1,
                )

    def test_target_positions(self):
        expected = {
            500: {"early": 50, "middle": 250, "late": 450},
            2000: {"early": 200, "middle": 1000, "late": 1800},
            5000: {"early": 500, "middle": 2500, "late": 4500},
        }
        for condition in self.conditions:
            self.assertEqual(
                condition["target_position_card"],
                expected[condition["context_size_cards"]][
                    condition["target_position_name"]
                ],
            )

    def test_conditions_are_deterministic(self):
        repeated = experiment.create_conditions(experiment.CONTEXT_SIZES)
        original_hashes = [
            condition["prompt_sha256"] for condition in self.conditions
        ]
        repeated_hashes = [
            condition["prompt_sha256"] for condition in repeated
        ]
        self.assertEqual(original_hashes, repeated_hashes)

    def test_answer_scoring(self):
        self.assertEqual(
            experiment.score_answer("March", "March"),
            (True, True, ["march"]),
        )
        self.assertEqual(
            experiment.score_answer("The answer is March.", "March"),
            (True, False, ["march"]),
        )
        self.assertEqual(
            experiment.score_answer("March or May", "March"),
            (False, False, ["march", "may"]),
        )
        self.assertEqual(
            experiment.score_answer("April", "March"),
            (False, True, ["april"]),
        )
        self.assertEqual(
            experiment.score_answer("Month three", "March"),
            (True, False, ["march"]),
        )
        self.assertEqual(
            experiment.score_answer("the ninth month", "September"),
            (True, False, ["september"]),
        )

    def test_smoke_test_uses_short_and_long_middle_conditions(self):
        models = [
            {"label": "A", "model": "a", "context_window_tokens": 300000},
            {"label": "B", "model": "b", "context_window_tokens": 300000},
            {"label": "C", "model": "c", "context_window_tokens": 300000},
        ]
        plan = experiment.create_execution_plan(models, self.conditions, True)
        self.assertEqual(len(plan), 6)
        for _, condition in plan:
            self.assertEqual(condition["item_id"], "p01")
            self.assertIn(condition["context_size_cards"], {500, 5000})
            self.assertEqual(condition["target_position_name"], "middle")

    def test_comprehension_conditions_use_only_the_target_card(self):
        conditions = experiment.create_comprehension_conditions()
        self.assertEqual(len(conditions), 4)

        for condition, item in zip(conditions, experiment.EXPERIMENT_ITEMS):
            self.assertEqual(condition["item_id"], item["item_id"])
            self.assertEqual(condition["context_size_cards"], 1)
            self.assertEqual(condition["target_position_card"], 1)
            self.assertEqual(condition["prompt"].count("% Card "), 1)
            self.assertIn(item["target_card"], condition["prompt"])
            self.assertEqual(
                condition["expected_answer"], item["expected_answer"]
            )


if __name__ == "__main__":
    unittest.main()
