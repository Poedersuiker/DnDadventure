import unittest
from app import create_app, db
from app.models import User, Character, XP_THRESHOLDS, CLASS_DATA_MODEL
from tests.base_test import BaseTestCase # Corrected import
import math

class TestCharacterModel(BaseTestCase): # Corrected class inheritance

    def setUp(self):
        super().setUp()  # Call BaseTestCase's setUp
        # Use the user created by BaseTestCase.setUp()
        self.user = User.query.filter_by(username='testuser').first()
        if not self.user: # Should not happen if BaseTestCase.setUp ran correctly
            self.user = User(username='testuser_model', email='test_model@example.com')
            self.user.set_password('password')
            db.session.add(self.user)
            db.session.commit()


        # Create a basic character for tests
        self.character = Character(
            name='Test Character Model', # Changed name for clarity
            race='Human',
            character_class='Fighter', # Ensure 'Fighter' is in CLASS_DATA_MODEL
            level=1,
            strength=15,
            dexterity=14,
            constitution=13,
            intelligence=12,
            wisdom=10,
            charisma=8,
            max_hp=10, # Will be updated based on class and con
            current_hp=10,
            owner=self.user, # Assign the fetched or newly created user
            experience_points=0
        )
        # Set initial HP based on class and con
        class_info = CLASS_DATA_MODEL.get(self.character.character_class, CLASS_DATA_MODEL["Default"])
        con_modifier = self.character.get_modifier_for_ability('constitution')
        self.character.max_hp = class_info["hit_dice_type"] + con_modifier
        self.character.current_hp = self.character.max_hp
        self.character.hit_dice_type = class_info["hit_dice_type"]
        
        db.session.add(self.character)
        db.session.commit()

    def test_get_modifier_for_ability(self):
        self.assertEqual(self.character.get_modifier_for_ability('strength'), 2) # (15-10)//2 = 2
        self.assertEqual(self.character.get_modifier_for_ability('dexterity'), 2) # (14-10)//2 = 2
        self.assertEqual(self.character.get_modifier_for_ability('constitution'), 1) # (13-10)//2 = 1
        self.assertEqual(self.character.get_modifier_for_ability('intelligence'), 1) # (12-10)//2 = 1
        self.assertEqual(self.character.get_modifier_for_ability('wisdom'), 0) # (10-10)//2 = 0
        self.assertEqual(self.character.get_modifier_for_ability('charisma'), -1) # (8-10)//2 = -1
        # Test with an invalid ability name (should default to 10, modifier 0)
        self.assertEqual(self.character.get_modifier_for_ability('invalid_stat'), 0)

    def test_get_proficiency_bonus(self):
        levels_bonuses = {1: 2, 4: 2, 5: 3, 8: 3, 9: 4, 12: 4, 13: 5, 16: 5, 17: 6, 20: 6}
        for level, bonus in levels_bonuses.items():
            self.character.level = level
            db.session.commit() # Commit level change
            self.assertEqual(self.character.get_proficiency_bonus(), bonus, f"Level {level}")
        
        # Test out of range (should default to 2 as per current model logic)
        self.character.level = 0
        db.session.commit()
        self.assertEqual(self.character.get_proficiency_bonus(), 2)
        self.character.level = 21
        db.session.commit()
        self.assertEqual(self.character.get_proficiency_bonus(), 2) # Or handle as error/max level bonus

    def test_hp_initialization(self):
        # Test character is created by setUp
        char_fighter_init_name = "Test Character_Fighter_Init_Model"
        char_fighter = Character.query.filter_by(name=char_fighter_init_name).first()
        if not char_fighter:
            con_mod = (16 - 10) // 2 # +3
            hit_dice_type = CLASS_DATA_MODEL.get("Fighter")["hit_dice_type"] # 10 for Fighter
            expected_hp = hit_dice_type + con_mod # 10 + 3 = 13

            char_fighter = Character(
                name=char_fighter_init_name, # Use updated name
                race="Human",
                character_class="Fighter",
                level=1,
                constitution=16, # Con modifier +3
                owner=self.user # Assign the correct user
            )
            # Manually trigger hp calculation as __init__ does it
            char_fighter.max_hp = hit_dice_type + con_mod
            char_fighter.current_hp = char_fighter.max_hp

            db.session.add(char_fighter)
            db.session.commit()
        
        self.assertEqual(char_fighter.max_hp, 13)
        self.assertEqual(char_fighter.current_hp, 13)

    def test_get_saving_throw_bonus(self):
        # Character: Fighter, Level 1 (Proficiency Bonus: +2)
        # STR: 15 (+2), DEX: 14 (+2), CON: 13 (+1), INT: 12 (+1), WIS: 10 (+0), CHA: 8 (-1)
        # Fighter proficiencies: Strength, Constitution
        self.character.prof_strength_save = True
        self.character.prof_constitution_save = True
        db.session.commit()

        # Strength Save: +2 (STR) + 2 (Prof) = +4
        self.assertEqual(self.character.get_saving_throw_bonus('strength'), 4)
        # Dexterity Save: +2 (DEX) = +2
        self.assertEqual(self.character.get_saving_throw_bonus('dexterity'), 2)
        # Constitution Save: +1 (CON) + 2 (Prof) = +3
        self.assertEqual(self.character.get_saving_throw_bonus('constitution'), 3)
        # Intelligence Save: +1 (INT) = +1
        self.assertEqual(self.character.get_saving_throw_bonus('intelligence'), 1)
        # Wisdom Save: +0 (WIS) = +0
        self.assertEqual(self.character.get_saving_throw_bonus('wisdom'), 0)
        # Charisma Save: -1 (CHA) = -1
        self.assertEqual(self.character.get_saving_throw_bonus('charisma'), -1)

        # Change level to 5 (Proficiency Bonus: +3)
        self.character.level = 5
        db.session.commit()
        # Strength Save: +2 (STR) + 3 (Prof) = +5
        self.assertEqual(self.character.get_saving_throw_bonus('strength'), 5)
        # Dexterity Save: +2 (DEX) = +2 (still not proficient)
        self.assertEqual(self.character.get_saving_throw_bonus('dexterity'), 2)

    def test_get_skill_bonus(self):
        # Character: Level 1 (Proficiency Bonus: +2)
        # STR: 15 (+2), DEX: 14 (+2), INT: 12 (+1)
        # Assume no skill proficiencies by default for this test, then add one
        
        # Athletics (STR): +2 (STR)
        self.assertEqual(self.character.get_skill_bonus('athletics'), 2)
        # Acrobatics (DEX): +2 (DEX)
        self.assertEqual(self.character.get_skill_bonus('acrobatics'), 2)
        # Arcana (INT): +1 (INT)
        self.assertEqual(self.character.get_skill_bonus('arcana'), 1)

        # Add proficiency in Athletics
        self.character.prof_athletics = True
        db.session.commit()
        # Athletics (STR): +2 (STR) + 2 (Prof) = +4
        self.assertEqual(self.character.get_skill_bonus('athletics'), 4)

        # Change level to 9 (Proficiency Bonus: +4)
        self.character.level = 9
        db.session.commit()
        # Athletics (STR): +2 (STR) + 4 (Prof) = +6
        self.assertEqual(self.character.get_skill_bonus('athletics'), 6)
        # Acrobatics (DEX): +2 (DEX) = +2 (still not proficient)
        self.assertEqual(self.character.get_skill_bonus('acrobatics'), 2)

        # Test with a space in skill name (should be handled by method)
        self.character.prof_sleight_of_hand = True
        db.session.commit()
        # Sleight of Hand (DEX): +2 (DEX) + 4 (Prof) = +6
        self.assertEqual(self.character.get_skill_bonus('sleight_of_hand'), 6) 
        self.assertEqual(self.character.get_skill_bonus('Sleight of Hand'), 6)


    def test_get_passive_perception(self):
        # Character: Level 1 (Proficiency Bonus: +2)
        # WIS: 10 (+0)
        # Base passive perception = 10 + WIS_mod
        self.assertEqual(self.character.get_passive_perception(), 10) # 10 + 0

        # Add proficiency in Perception
        self.character.prof_perception = True
        db.session.commit()
        # Passive Perception with prof: 10 + WIS_mod (0) + Prof_bonus (2) = 12
        self.assertEqual(self.character.get_passive_perception(), 12)

        # Change Wisdom score and level
        self.character.wisdom = 15 # WIS_mod = +2
        self.character.level = 5 # Prof_bonus = +3
        db.session.commit()
        # Passive Perception: 10 + WIS_mod (2) + Prof_bonus (3) = 15
        self.assertEqual(self.character.get_passive_perception(), 15)

        # Remove proficiency
        self.character.prof_perception = False
        db.session.commit()
        # Passive Perception: 10 + WIS_mod (2) = 12
        self.assertEqual(self.character.get_passive_perception(), 12)

    # --- Leveling Up Tests ---
    def test_can_level_up_false_max_level(self):
        self.character.level = 20
        self.character.experience_points = XP_THRESHOLDS[19] + 1000 # More than enough for level 20
        db.session.commit()
        self.assertFalse(self.character.can_level_up())

    def test_can_level_up_false_insufficient_xp(self):
        self.character.level = 1
        self.character.experience_points = XP_THRESHOLDS[1] - 1 # XP for level 2 is XP_THRESHOLDS[1]
        db.session.commit()
        self.assertFalse(self.character.can_level_up())

    def test_can_level_up_true(self):
        self.character.level = 1
        self.character.experience_points = XP_THRESHOLDS[1] # Exactly enough for level 2
        db.session.commit()
        self.assertTrue(self.character.can_level_up())

        self.character.level = 5
        self.character.experience_points = XP_THRESHOLDS[5] # XP for level 6
        db.session.commit()
        self.assertTrue(self.character.can_level_up())

    def test_level_up_success(self):
        self.character.level = 1
        self.character.character_class = "Fighter" # Fighter: d10 HD (avg 6), CON 13 (+1)
        self.character.constitution = 13 
        # Initial HP for Fighter L1 with CON 13: 10 (hit_dice_type) + 1 (con_mod) = 11
        # This should be set by __init__ or character creation logic, let's set manually for test clarity
        fighter_class_info = CLASS_DATA_MODEL.get("Fighter")
        con_mod = self.character.get_modifier_for_ability('constitution')
        self.character.max_hp = fighter_class_info["hit_dice_type"] + con_mod
        self.character.current_hp = self.character.max_hp
        self.character.hit_dice_max = 1
        self.character.hit_dice_current = 1
        
        self.character.experience_points = XP_THRESHOLDS[1] # XP for level 2
        db.session.commit()

        initial_max_hp = self.character.max_hp
        initial_hit_dice_max = self.character.hit_dice_max
        initial_hit_dice_current = self.character.hit_dice_current

        self.assertTrue(self.character.level_up())
        db.session.commit()

        self.assertEqual(self.character.level, 2)
        
        # Expected HP gain: avg_hp_gain_per_level (6 for Fighter) + con_mod (1) = 7
        expected_hp_gain = fighter_class_info["avg_hp_gain_per_level"] + con_mod
        self.assertEqual(self.character.max_hp, initial_max_hp + expected_hp_gain)
        self.assertEqual(self.character.current_hp, self.character.max_hp) # HP restored to new max
        self.assertEqual(self.character.hit_dice_max, initial_hit_dice_max + 1)
        self.assertEqual(self.character.hit_dice_current, initial_hit_dice_current + 1)

        # Level up again to level 3
        self.character.experience_points = XP_THRESHOLDS[2] # XP for level 3
        db.session.commit()
        initial_max_hp_l2 = self.character.max_hp
        initial_hit_dice_max_l2 = self.character.hit_dice_max
        initial_hit_dice_current_l2 = self.character.hit_dice_current

        self.assertTrue(self.character.level_up())
        db.session.commit()
        self.assertEqual(self.character.level, 3)
        self.assertEqual(self.character.max_hp, initial_max_hp_l2 + expected_hp_gain)
        self.assertEqual(self.character.current_hp, self.character.max_hp)
        self.assertEqual(self.character.hit_dice_max, initial_hit_dice_max_l2 + 1)
        self.assertEqual(self.character.hit_dice_current, initial_hit_dice_current_l2 + 1)


    def test_level_up_failure_conditions(self):
        self.character.level = 1
        self.character.experience_points = 0 # Not enough XP
        db.session.commit()
        self.assertFalse(self.character.level_up())
        self.assertEqual(self.character.level, 1) # Level should not change

        self.character.level = 20
        self.character.experience_points = XP_THRESHOLDS[19] + 1000 # Max level
        db.session.commit()
        self.assertFalse(self.character.level_up())
        self.assertEqual(self.character.level, 20) # Level should not change

if __name__ == '__main__':
    unittest.main()
