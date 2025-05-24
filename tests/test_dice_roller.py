import unittest
from app.utils.dice_roller import roll_ability_scores

class TestDiceRoller(unittest.TestCase):

    def test_roll_ability_scores(self):
        """
        Test that roll_ability_scores generates 6 scores,
        each between 3 and 18 (inclusive).
        """
        scores = roll_ability_scores()

        # Check that 6 scores are generated
        self.assertEqual(len(scores), 6, "Should generate exactly 6 ability scores.")

        # Check that each score is within the valid range (3 to 18)
        # (3 is from 3x 1s, 18 is from 3x 6s after dropping lowest of 4d6)
        for score in scores:
            self.assertTrue(3 <= score <= 18, f"Score {score} is outside the valid range of 3-18.")

if __name__ == '__main__':
    unittest.main()
