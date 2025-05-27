import unittest
import sys
import os

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from app import app as main_app, db
from app.models import User, Race, Class, Spell, Character, Item, Coinage, character_known_spells # Added Item, Coinage

class BasicAppTests(unittest.TestCase):
    def setUp(self):
        # Use an in-memory SQLite database for testing
        main_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        main_app.config['TESTING'] = True
        main_app.config['WTF_CSRF_ENABLED'] = False # Often helpful for tests
        self.app = main_app.test_client()
        self.app_context = main_app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

class TestModelCreation(BasicAppTests):

    def test_create_user(self):
        user = User(google_id="test_google_id_123", email="test@example.com")
        db.session.add(user)
        db.session.commit()
        self.assertIsNotNone(user.id)
        queried_user = User.query.get(user.id)
        self.assertEqual(queried_user.email, "test@example.com")

    def test_create_race(self):
        race = Race(name="Test Elf", speed=30, ability_score_increases='[{"name": "DEX", "bonus": 2}]', age_description="Long-lived", alignment_description="Chaotic Good", size="Medium", size_description="Slender", languages='["Common", "Elvish"]', traits='["Darkvision", "Fey Ancestry"]')
        db.session.add(race)
        db.session.commit()
        self.assertIsNotNone(race.id)
        self.assertEqual(Race.query.get(race.id).name, "Test Elf")

    def test_create_class(self):
        dnd_class = Class(name="Test Wizard", hit_die="d6", spellcasting_ability="INT",
                          # Adding missing required fields based on model definition
                          proficiency_saving_throws='["INT", "WIS"]', 
                          skill_proficiencies_option_count=2, 
                          skill_proficiencies_options='["Arcana", "History", "Investigation", "Medicine"]',
                          starting_equipment='[]') # Empty JSON array if no specific equipment
        db.session.add(dnd_class)
        db.session.commit()
        self.assertIsNotNone(dnd_class.id)
        self.assertEqual(Class.query.get(dnd_class.id).name, "Test Wizard")

    def test_create_spell(self):
        spell = Spell(index="test-fireball", name="Test Fireball", level=3, school="Evocation", 
                      casting_time="1 action", range="150 feet", duration="Instantaneous", 
                      components="V, S, M", description='["A fiery explosion."]',
                      # Adding missing required fields based on model definition
                      classes_that_can_use='["Wizard"]')
        db.session.add(spell)
        db.session.commit()
        self.assertIsNotNone(spell.id)
        self.assertEqual(Spell.query.get(spell.id).name, "Test Fireball")

    def test_create_character_and_relationships(self):
        user = User(google_id="char_creator_google_id", email="char_creator@example.com")
        db.session.add(user)
        db.session.commit()

        race = Race(name="Dwarf", speed=25, ability_score_increases='[{"name": "CON", "bonus": 2}]', languages='["Common", "Dwarvish"]')
        db.session.add(race)
        db.session.commit()

        dnd_class = Class(name="Fighter", hit_die="d10", 
                          proficiency_saving_throws='["STR", "CON"]',
                          skill_proficiencies_option_count=1,
                          skill_proficiencies_options='["Acrobatics", "Athletics"]',
                          starting_equipment='[]')
        db.session.add(dnd_class)
        db.session.commit()
        
        spell1 = Spell(index="ts1", name="Test Spell 1", level=0, school="Test School", description='[]', classes_that_can_use='["Fighter"]') # Added missing fields
        spell2 = Spell(index="ts2", name="Test Spell 2", level=1, school="Test School", description='[]', classes_that_can_use='["Fighter"]') # Added missing fields
        db.session.add_all([spell1, spell2])
        db.session.commit()

        char = Character(
            name="Test Character",
            user_id=user.id,
            race_id=race.id,
            class_id=dnd_class.id,
            level=1, strength=10, dexterity=10, constitution=10,
            intelligence=10, wisdom=10, charisma=10,
            max_hp=10, hp=10, armor_class=10 # speed is not a direct Character model field
        )
        char.known_spells.append(spell1)
        char.known_spells.append(spell2)
        
        db.session.add(char)
        db.session.commit()

        self.assertIsNotNone(char.id)
        queried_char = Character.query.get(char.id)
        self.assertEqual(queried_char.name, "Test Character")
        self.assertEqual(queried_char.race.name, "Dwarf") # Test relationship
        self.assertEqual(queried_char.char_class.name, "Fighter") # Test relationship
        self.assertEqual(queried_char.level, 1)
        self.assertIn(spell1, queried_char.known_spells)
        self.assertIn(spell2, queried_char.known_spells)

    def test_character_xp(self):
        # 1. Create User
        user = User(google_id="xp_test_user_google_id", email="xp_test_user@example.com")
        db.session.add(user)
        db.session.commit()

        # 2. Create Race
        race = Race(name="Test Human for XP", speed=30, 
                    ability_score_increases='[{"name": "STR", "bonus": 1}]', 
                    languages='["Common"]')
        db.session.add(race)
        db.session.commit()

        # 3. Create Class
        dnd_class = Class(name="Test Monk for XP", hit_die="d8",
                          proficiency_saving_throws='["STR", "DEX"]',
                          skill_proficiencies_option_count=2,
                          skill_proficiencies_options='["Acrobatics", "Stealth"]',
                          starting_equipment='[]')
        db.session.add(dnd_class)
        db.session.commit()

        # 4. Create Character
        char = Character(
            name="XP Test Character",
            user_id=user.id,
            race_id=race.id,
            class_id=dnd_class.id,
            # xp should default to 0 as per model definition
            level=1, strength=12, dexterity=12, constitution=12,
            intelligence=12, wisdom=12, charisma=12,
            max_hp=10, hp=10, armor_class=10
        )
        db.session.add(char)
        db.session.commit()

        # 5. Assert default xp
        self.assertEqual(char.xp, 0)

        # 6. Set xp to a new value
        char.xp = 100
        db.session.commit()

        # 7. Assert updated xp
        queried_char = Character.query.get(char.id)
        self.assertEqual(queried_char.xp, 100)

    def test_create_item_and_relationship(self):
        user = User(google_id="item_user_google_id", email="item_user@example.com")
        race = Race(name="Item Test Race", speed=30, ability_score_increases='[]', languages='[]')
        char_class = Class(name="Item Test Class", hit_die="d8", proficiency_saving_throws='[]', skill_proficiencies_option_count=0, skill_proficiencies_options='[]', starting_equipment='[]')
        db.session.add_all([user, race, char_class])
        db.session.commit()

        char = Character(name="Character With Item", user_id=user.id, race_id=race.id, class_id=char_class.id, level=1, strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10, max_hp=10, hp=10, armor_class=10)
        db.session.add(char)
        db.session.commit()

        item = Item(name="Test Sword", description="A shiny test sword.", quantity=1, character_id=char.id)
        db.session.add(item)
        db.session.commit()

        self.assertIsNotNone(item.id)
        queried_item = Item.query.get(item.id)
        self.assertEqual(queried_item.name, "Test Sword")
        self.assertEqual(queried_item.character_id, char.id)
        self.assertIn(queried_item, char.items)
        self.assertEqual(queried_item.character, char)

    def test_create_coinage_and_relationship(self):
        user = User(google_id="coin_user_google_id", email="coin_user@example.com")
        race = Race(name="Coin Test Race", speed=30, ability_score_increases='[]', languages='[]')
        char_class = Class(name="Coin Test Class", hit_die="d8", proficiency_saving_throws='[]', skill_proficiencies_option_count=0, skill_proficiencies_options='[]', starting_equipment='[]')
        db.session.add_all([user, race, char_class])
        db.session.commit()

        char = Character(name="Character With Coins", user_id=user.id, race_id=race.id, class_id=char_class.id, level=1, strength=10, dexterity=10, constitution=10, intelligence=10, wisdom=10, charisma=10, max_hp=10, hp=10, armor_class=10)
        db.session.add(char)
        db.session.commit()

        coin = Coinage(name="Gold Pieces", quantity=100, character_id=char.id)
        db.session.add(coin)
        db.session.commit()

        self.assertIsNotNone(coin.id)
        queried_coin = Coinage.query.get(coin.id)
        self.assertEqual(queried_coin.name, "Gold Pieces")
        self.assertEqual(queried_coin.quantity, 100)
        self.assertEqual(queried_coin.character_id, char.id)
        self.assertIn(queried_coin, char.coinage)
        self.assertEqual(queried_coin.character, char)


if __name__ == '__main__':
    unittest.main()
