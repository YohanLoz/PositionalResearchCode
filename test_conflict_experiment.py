import hashlib
import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import run_conflict_experiment as experiment


class ConflictExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conditions = experiment.create_conditions()
        cls.models = experiment.position.load_models(experiment.MODEL_FILE)

    def test_unique_balanced_conditions(self):
        self.assertEqual(len(self.conditions), 48)
        self.assertEqual(len({c['condition_id'] for c in self.conditions}), 48)
        self.assertEqual(len({c['prompt_sha256'] for c in self.conditions}), 48)
        self.assertEqual(Counter(c['arrangement'] for c in self.conditions), dict.fromkeys(('AA', 'BB', 'AB', 'BA'), 12))
        self.assertEqual(Counter(c['condition_type'] for c in self.conditions), {'agreement': 24, 'conflict': 24})

    def test_cards_positions_and_exact_instruction(self):
        expected_header = 'Use only the flashcards below to answer the question. Return only the month name and no explanation.\n\n'
        for c in self.conditions:
            self.assertTrue(c['prompt'].startswith(expected_header))
            cards = re.findall(r'% Card (\d+) Contents %\n(.*?)(?=\n---\n|\n\nQuestion:)', c['prompt'], re.S)
            self.assertEqual(len(cards), 5000)
            self.assertEqual([int(n) for n, _ in cards], list(range(1, 5001)))
            self.assertEqual(cards[c['earlier_position_card'] - 1][1], c['relevant_cards'][0])
            self.assertEqual(cards[c['later_position_card'] - 1][1], c['relevant_cards'][1])
            self.assertLess(c['earlier_position_card'], c['later_position_card'])
            self.assertIn(c['earlier_position_card'], (500, 2500))
            self.assertIn(c['later_position_card'], (2500, 4500))
            self.assertTrue(all(' only in ' in card for card in c['relevant_cards']))
            self.assertEqual(hashlib.sha256(c['prompt'].encode()).hexdigest(), c['prompt_sha256'])

    def test_background_is_preserved_and_has_no_extra_target_fact(self):
        items = {item['item_id']: item for item in experiment.position.EXPERIMENT_ITEMS}
        for c in self.conditions:
            item = items[c['item_id']]
            cards = re.findall(r'% Card \d+ Contents %\n(.*?)(?=\n---\n|\n\nQuestion:)', c['prompt'], re.S)
            distractors = [card for i, card in enumerate(cards, 1) if i not in (c['earlier_position_card'], c['later_position_card'])]
            self.assertEqual(distractors, experiment.position.create_distractor_pool(item, 4999)[:-1])
            exact_fact = re.compile(rf"\b{item['subject']}\b {item['similar_event']}")
            self.assertFalse(any(exact_fact.search(card) for card in distractors))
            self.assertEqual(hashlib.sha256('\n---\n'.join(distractors).encode()).hexdigest(), c['distractor_sha256'])

    def test_matched_conditions_change_only_the_two_months(self):
        for item in experiment.position.EXPERIMENT_ITEMS:
            for pair in (('early', 'middle'), ('early', 'late'), ('middle', 'late')):
                group = [c for c in self.conditions if c['item_id'] == item['item_id'] and (c['earlier_position_name'], c['later_position_name']) == pair]
                self.assertEqual(len(group), 4)
                normalized = set()
                for c in group:
                    text = c['prompt']
                    for card in c['relevant_cards']:
                        text = text.replace(card, 'TARGET MONTH CARD')
                    normalized.add(text)
                self.assertEqual(len(normalized), 1)

    def test_deterministic_generation_and_execution(self):
        self.assertEqual(self.conditions, experiment.create_conditions())
        plan = experiment.execution_plan(self.models, self.conditions)
        self.assertEqual(plan, experiment.execution_plan(self.models, self.conditions))
        self.assertEqual(len(plan), 144)
        self.assertEqual(len({(m['model'], c['condition_id']) for m, c in plan}), 144)

    def test_request_settings_match_position_experiment(self):
        for model in self.models:
            payload = experiment.request_payload(model, self.conditions[0])
            self.assertEqual(payload['seed'], experiment.position.SEED)
            self.assertEqual(payload['max_completion_tokens'], 2048)
            self.assertEqual(payload['messages'], [{'role': 'user', 'content': self.conditions[0]['prompt']}])
            self.assertEqual(payload['provider']['only'], [model['provider']])
            self.assertFalse(payload['provider']['allow_fallbacks'])
            self.assertTrue(payload['provider']['require_parameters'])
            self.assertNotIn('temperature', payload)

    def test_scoring_simple_answers(self):
        for answer, months in [('March', ['march']), ('March.', ['march']), ('March and September', ['march', 'september']), ('September / March', ['march', 'september'])]:
            score = experiment.score_answer(answer)
            self.assertEqual(score['selected_months'], months)
            self.assertFalse(score['needs_review'])
            self.assertFalse(score['conflict_reported'])
        self.assertTrue(experiment.score_answer('March')['format_compliant'])
        self.assertFalse(experiment.score_answer('March.')['format_compliant'])

    def test_negated_and_quoted_months_require_review(self):
        score = experiment.score_answer('March, not September')
        self.assertEqual(score['selected_months'], ['march'])
        self.assertTrue(score['needs_review'])
        for answer in ['The first card says March, but the answer is September.', 'The cards conflict.', 'Unknown', '', 'Neither March nor September', 'The third month']:
            self.assertTrue(experiment.score_answer(answer)['needs_review'])

    def test_classifications_do_not_call_conflict_answers_correct(self):
        conflict = {'condition_type': 'conflict', 'earlier_month': 'March', 'later_month': 'September'}
        for selected, expected in [(['march'], 'earlier'), (['september'], 'later'), (['march', 'september'], 'both'), ([], 'neither'), (['june'], 'neither'), (None, 'unresolved')]:
            self.assertEqual(experiment.classify_selection(selected, conflict), expected)
        agreement = {**conflict, 'condition_type': 'agreement', 'later_month': 'March'}
        self.assertEqual(experiment.classify_selection(['march'], agreement), 'supported')
        self.assertEqual(experiment.classify_selection(['september'], agreement), 'other')

    def test_frozen_files_cannot_be_replaced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'frozen.json'
            experiment.freeze_json(path, {'a': 1})
            experiment.freeze_json(path, {'a': 1})
            with self.assertRaises(ValueError):
                experiment.freeze_json(path, {'a': 2})
            self.assertEqual(json.loads(path.read_text()), {'a': 1})

    def test_budget_stops_before_excess_spending(self):
        for data in [{'limit': None, 'limit_remaining': 10}, {'limit': 10, 'limit_remaining': 9}, {'limit': 5, 'limit_remaining': 0.09}, {'limit': 5, 'limit_remaining': 4, 'limit_reset': 'daily'}]:
            with patch.object(experiment, 'api_request', return_value={'data': data}):
                with self.assertRaises(ValueError):
                    experiment.check_budget('fake-key')
        with patch.object(experiment, 'api_request', return_value={'data': {'limit': 5, 'limit_remaining': 3.33, 'usage': 1.67}}):
            self.assertEqual(experiment.check_budget('fake-key')['remaining'], 3.33)

    def test_higher_account_limit_does_not_raise_experiment_budget(self):
        with patch.object(experiment, 'api_request', return_value={'data': {'limit': 10, 'limit_remaining': 8, 'usage': 2}}):
            self.assertEqual(experiment.check_budget('fake-key')['remaining'], 4)
        with patch.object(experiment, 'api_request', return_value={'data': {'limit': 10, 'limit_remaining': 4.05, 'usage': 5.95}}):
            with self.assertRaises(ValueError):
                experiment.check_budget('fake-key')

    def test_preparation_does_not_call_api(self):
        with patch('sys.argv', ['run_conflict_experiment.py']), patch.object(experiment, 'freeze_json'), patch.object(experiment.position, 'file_sha256', return_value='test'), patch.object(experiment, 'api_request') as api:
            experiment.main()
            api.assert_not_called()

    def test_resume_skips_completed_pairs(self):
        conditions = [self.conditions[0]]
        models = [self.models[0]]
        raw = {'choices': [{'message': {'content': 'March'}, 'finish_reason': 'stop'}], 'usage': {'cost': 0.01}}
        with tempfile.TemporaryDirectory() as directory:
            results_path = Path(directory) / 'results.json'
            with patch.object(experiment, 'RESULTS_FILE', results_path), patch.object(experiment.position, 'file_sha256', return_value='test'), patch.object(experiment, 'check_budget', return_value={'remaining': 3}), patch.dict('os.environ', {'OPENROUTER_API_KEY': 'fake-key'}), patch.object(experiment, 'api_request', return_value=raw) as api:
                experiment.run(models, conditions)
                experiment.run(models, conditions)
                self.assertEqual(api.call_count, 1)
                self.assertEqual(len(json.loads(results_path.read_text())['attempts']), 1)
                with self.assertRaises(ValueError):
                    experiment.run([{**models[0], 'reasoning_effort': 'low'}], conditions)


if __name__ == '__main__':
    unittest.main()
