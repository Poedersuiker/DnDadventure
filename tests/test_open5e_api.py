import unittest
import json
import sqlite3
import os

# Assuming 'app' is the Flask application instance, imported from your app package
# If your app is created with a factory function, e.g., create_app(), use that.
# from app import create_app
from app import app # Import the global app instance

class TestOpen5eAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up for all tests in this class."""
        # Configure the app for testing
        app.config['TESTING'] = True
        # self.app = create_app() if using a factory
        cls.app = app
        cls.client = cls.app.test_client()

        # Define database path - relative to this test file's location (tests/test_open5e_api.py)
        # So, ../instance/open5e.db
        cls.db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'instance', 'open5e.db'))

        # Ensure the instance directory exists (it should, but good practice)
        os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'instance'), exist_ok=True)

        # Pre-populate database with test data
        # This ensures the DB and tables exist. Run create_db.py if it doesn't.
        cls.populate_test_data()

    @classmethod
    def tearDownClass(cls):
        """Tear down after all tests in this class."""
        cls.clear_test_data()

    @classmethod
    def populate_test_data(cls):
        """Inserts sample data into the database for testing."""
        try:
            conn = sqlite3.connect(cls.db_path)
            cursor = conn.cursor()

            # Sample data
            monster_data = ('test-monster', json.dumps({"name": "Test Monster", "slug": "test-monster", "challenge_rating": "1"}))
            spell_data = ('test-spell', json.dumps({"name": "Test Spell", "slug": "test-spell", "level": 1, "school": "evocation"}))
            manifest_data = ('open5e_manifest_v1', json.dumps({"documents": {"count": 1}, "slug": "open5e_manifest_v1"})) # slug in data too

            # Create tables if they don't exist (basic version for testing)
            tables = {
                "monsters": "CREATE TABLE IF NOT EXISTS monsters (slug TEXT PRIMARY KEY NOT NULL, data TEXT NOT NULL);",
                "spells": "CREATE TABLE IF NOT EXISTS spells (slug TEXT PRIMARY KEY NOT NULL, data TEXT NOT NULL);",
                "manifest": "CREATE TABLE IF NOT EXISTS manifest (slug TEXT PRIMARY KEY NOT NULL, data TEXT NOT NULL);",
            }
            for table_sql in tables.values():
                cursor.execute(table_sql)

            # Insert/replace data
            cursor.execute("INSERT OR REPLACE INTO monsters (slug, data) VALUES (?, ?)", monster_data)
            cursor.execute("INSERT OR REPLACE INTO spells (slug, data) VALUES (?, ?)", spell_data)
            cursor.execute("INSERT OR REPLACE INTO manifest (slug, data) VALUES (?, ?)", manifest_data)

            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error during test data population: {e}")
            raise # Re-raise to fail test setup if DB isn't working
        finally:
            if conn:
                conn.close()

    @classmethod
    def clear_test_data(cls):
        """Clears sample data from the database."""
        try:
            conn = sqlite3.connect(cls.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM monsters WHERE slug='test-monster'")
            cursor.execute("DELETE FROM spells WHERE slug='test-spell'")
            cursor.execute("DELETE FROM manifest WHERE slug='open5e_manifest_v1'")
            conn.commit()
        except sqlite3.Error as e:
            print(f"Database error during test data clearing: {e}")
        finally:
            if conn:
                conn.close()

    def test_get_monsters_list(self):
        """Test fetching the list of monsters."""
        response = self.client.get('/api/v1/monsters/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertGreaterEqual(data['count'], 1)
        self.assertIsInstance(data['results'], list)
        # Check if test monster is in the results (assuming default limit is high enough or it's the only one)
        if data['count'] == 1 and len(data['results']) == 1: # If only our test monster exists
             self.assertEqual(data['results'][0]['name'], 'Test Monster')


    def test_get_monster_detail_exists(self):
        """Test fetching an existing monster's details."""
        response = self.client.get('/api/v1/monsters/test-monster/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'Test Monster')

    def test_get_monster_detail_not_found(self):
        """Test fetching a non-existent monster."""
        response = self.client.get('/api/v1/monsters/nonexistent-monster/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Not found')


    def test_get_spells_list(self):
        """Test fetching the list of spells."""
        response = self.client.get('/api/v2/spells/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertGreaterEqual(data['count'], 1)
        self.assertIsInstance(data['results'], list)
        if data['count'] == 1 and len(data['results']) == 1:
            self.assertEqual(data['results'][0]['name'], 'Test Spell')


    def test_get_spell_detail_exists(self):
        """Test fetching an existing spell's details."""
        response = self.client.get('/api/v2/spells/test-spell/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertEqual(data['name'], 'Test Spell')

    def test_get_spell_detail_not_found(self):
        """Test fetching a non-existent spell."""
        response = self.client.get('/api/v2/spells/nonexistent-spell/')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.content_type, 'application/json')
        data = json.loads(response.data)
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'Not found')

    def test_get_manifest(self):
        """Test fetching the manifest data."""
        response = self.client.get('/api/v1/manifest/')
        self.assertEqual(response.status_code, 200)
        # The manifest endpoint in the API returns raw JSON, not jsonify'd
        # So content_type might be application/json if Flask sets it by default for dicts
        # or could be something else if not explicitly set. Let's check if it's parsable.
        try:
            data = json.loads(response.data)
        except json.JSONDecodeError:
            self.fail("Response was not valid JSON.")

        self.assertIn('documents', data)
        self.assertEqual(data['documents']['count'], 1)

if __name__ == '__main__':
    unittest.main()
