import unittest
import sys
import os

# Add the project root to the Python path to allow direct import of 'app'
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from app.utils import roll_dice

class TestUtils(unittest.TestCase):

    def test_roll_dice_basic(self):
        total, rolls = roll_dice(num_dice=2, num_sides=6)
        self.assertEqual(len(rolls), 2)
        self.assertTrue(1 <= rolls[0] <= 6)
        self.assertTrue(1 <= rolls[1] <= 6)
        self.assertEqual(total, sum(rolls))

    def test_roll_dice_drop_lowest(self):
        # Test with a scenario where dropping is guaranteed to change the sum
        # For example, roll 4d6, drop 1. If rolls are [1, 6, 6, 6], sum is 18.
        # If we didn't drop, sum would be 19.
        # It's hard to guarantee specific rolls, so we check logic.
        total, rolls = roll_dice(num_dice=4, num_sides=6, drop_lowest=1)
        self.assertEqual(len(rolls), 4) # Should show all original rolls
        
        # Sum should be sum of 3 highest rolls
        sorted_rolls = sorted(rolls)
        expected_sum = sum(sorted_rolls[1:])
        self.assertEqual(total, expected_sum)

    def test_roll_dice_drop_multiple(self):
        total, rolls = roll_dice(num_dice=5, num_sides=10, drop_lowest=2)
        self.assertEqual(len(rolls), 5)
        sorted_rolls = sorted(rolls)
        expected_sum = sum(sorted_rolls[2:])
        self.assertEqual(total, expected_sum)

    def test_roll_dice_no_drop(self):
        total, rolls = roll_dice(num_dice=3, num_sides=8, drop_lowest=0)
        self.assertEqual(len(rolls), 3)
        self.assertEqual(total, sum(rolls))

    def test_roll_dice_invalid_inputs(self):
        with self.assertRaises(ValueError):
            roll_dice(num_dice=0, num_sides=6) # Num dice not positive
        with self.assertRaises(ValueError):
            roll_dice(num_dice=2, num_sides=0) # Num sides not positive
        with self.assertRaises(ValueError):
            roll_dice(num_dice=3, num_sides=6, drop_lowest=-1) # Drop lowest negative
        with self.assertRaises(ValueError):
            roll_dice(num_dice=3, num_sides=6, drop_lowest=3) # Drop lowest >= num_dice
        with self.assertRaises(ValueError):
            roll_dice(num_dice=3, num_sides=6, drop_lowest=4) # Drop lowest > num_dice

if __name__ == '__main__':
    unittest.main()
