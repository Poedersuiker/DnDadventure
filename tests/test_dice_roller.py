import unittest
from unittest.mock import patch
import dice_roller

class TestDiceRoller(unittest.TestCase):

    def test_roll_dice_valid(self):
        # Patch random.randint to return a predictable sequence of numbers
        with patch('random.randint', side_effect=[3, 4, 5, 6]):
            rolls, total = dice_roller.roll_dice('4d6')
            self.assertEqual(rolls, [3, 4, 5, 6])
            self.assertEqual(total, 18)

    def test_roll_dice_with_modifier(self):
        with patch('random.randint', side_effect=[10, 5]):
            rolls, total = dice_roller.roll_dice('2d10+5')
            self.assertEqual(rolls, [10, 5])
            self.assertEqual(total, 20)

    def test_roll_dice_invalid_string(self):
        with self.assertRaises(ValueError):
            dice_roller.roll_dice('invalid')

    def test_roll_heroic(self):
        with patch('random.randint', side_effect=[6, 5, 4, 1]):
            result = dice_roller._roll_heroic('4d6')
            self.assertEqual(result['total'], 15)
            self.assertEqual(result['rolls'], [6, 5, 4, 1])
            self.assertEqual(result['dropped'], [1])

    def test_roll_classic(self):
        with patch('random.randint', side_effect=[3, 4, 5]):
            result = dice_roller._roll_classic('3d6')
            self.assertEqual(result['total'], 12)
            self.assertEqual(result['rolls'], [3, 4, 5])

    def test_roll_high_floor(self):
        with patch('random.randint', side_effect=[1, 1]):
            result = dice_roller._roll_high_floor()
            self.assertEqual(result['total'], 8) # 1 + 1 + 6
            self.assertEqual(result['rolls'], [1, 1])

    def test_roll_percentile(self):
        with patch('random.randint', return_value=78):
            result = dice_roller._roll_percentile()
            self.assertEqual(result['total'], 78)
            self.assertEqual(result['rolls'], [78])

    def test_roll_function_single(self):
        mock_classic_roll = unittest.mock.Mock(return_value={"total": 10, "rolls": [3, 3, 4]})
        with patch.dict(dice_roller.MECHANICS, {'Classic': mock_classic_roll}):
            results = dice_roller.roll(mechanic='Classic', dice='3d6')
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['total'], 10)
            mock_classic_roll.assert_called_once_with(dice_string='3d6')

    def test_roll_function_multiple(self):
        mock_classic_roll = unittest.mock.Mock(side_effect=[{"total": 10}, {"total": 12}])
        with patch.dict(dice_roller.MECHANICS, {'Classic': mock_classic_roll}):
            results = dice_roller.roll(mechanic='Classic', dice='3d6', num_rolls=2)
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]['total'], 10)
            self.assertEqual(results[1]['total'], 12)
            self.assertEqual(mock_classic_roll.call_count, 2)

    def test_roll_function_advantage(self):
        mock_classic_roll = unittest.mock.Mock(side_effect=[
            {"total": 10, "rolls": [3, 3, 4]},
            {"total": 15, "rolls": [5, 5, 5]}
        ])
        with patch.dict(dice_roller.MECHANICS, {'Classic': mock_classic_roll}):
            results = dice_roller.roll(mechanic='Classic', dice='3d6', advantage=True)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['total'], 15)
            self.assertEqual(mock_classic_roll.call_count, 2)

    def test_roll_function_disadvantage(self):
        mock_classic_roll = unittest.mock.Mock(side_effect=[
            {"total": 10, "rolls": [3, 3, 4]},
            {"total": 15, "rolls": [5, 5, 5]}
        ])
        with patch.dict(dice_roller.MECHANICS, {'Classic': mock_classic_roll}):
            results = dice_roller.roll(mechanic='Classic', dice='3d6', disadvantage=True)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['total'], 10)
            self.assertEqual(mock_classic_roll.call_count, 2)

    def test_roll_function_advantage_and_disadvantage(self):
        mock_classic_roll = unittest.mock.Mock(return_value={"total": 12, "rolls": [4, 4, 4]})
        with patch.dict(dice_roller.MECHANICS, {'Classic': mock_classic_roll}):
            results = dice_roller.roll(mechanic='Classic', dice='3d6', advantage=True, disadvantage=True)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['total'], 12)
            mock_classic_roll.assert_called_once_with(dice_string='3d6')

    def test_roll_function_unknown_mechanic(self):
        with self.assertRaises(ValueError):
            dice_roller.roll(mechanic='UnknownMechanic', dice='1d6')

    def test_roll_function_missing_dice_string(self):
        with self.assertRaises(ValueError):
            dice_roller.roll(mechanic='Heroic')
        with self.assertRaises(ValueError):
            dice_roller.roll(mechanic='Classic')

if __name__ == '__main__':
    unittest.main()
