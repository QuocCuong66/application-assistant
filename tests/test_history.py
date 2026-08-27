import unittest
import os
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from bson import ObjectId

class MockCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, key, direction):
        return self

    def limit(self, n):
        return self.docs[:n]

class MockCollection:
    def __init__(self):
        self.docs = []

    def insert_one(self, doc):
        doc = dict(doc)
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        self.docs.append(doc)
        res = MagicMock()
        res.inserted_id = doc["_id"]
        return res

    def find(self, query=None):
        query = query or {}
        matched = []
        for d in self.docs:
            match = True
            for k, v in query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                matched.append(d)
        # Reverse to mock sorting by timestamp desc
        matched = list(reversed(matched))
        return MockCursor(matched)

    def find_one(self, query=None):
        query = query or {}
        for d in self.docs:
            match = True
            for k, v in query.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                return d
        return None

    def delete_one(self, query):
        initial = len(self.docs)
        self.docs = [d for d in self.docs if not (d.get("_id") == query.get("_id") and d.get("user_id") == query.get("user_id"))]
        deleted = initial - len(self.docs)
        res = MagicMock()
        res.deleted_count = deleted
        return res

    def delete_many(self, query):
        initial = len(self.docs)
        self.docs = [d for d in self.docs if d.get("user_id") != query.get("user_id")]
        deleted = initial - len(self.docs)
        res = MagicMock()
        res.deleted_count = deleted
        return res

class MockDatabase:
    def __init__(self):
        self.message_history = MockCollection()

class TestHistoryEndpoints(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockDatabase()

        from main import app
        app.dependency_overrides = {}

        from database import get_db
        from api.deps import get_current_user

        app.dependency_overrides[get_db] = lambda: self.mock_db
        app.dependency_overrides[get_current_user] = lambda: {"id": "user123", "username": "testuser"}

        self.client = TestClient(app)

    def tearDown(self):
        from main import app
        app.dependency_overrides = {}

    def test_get_history_and_delete_message(self):
        # Insert test messages
        msg1_id = self.mock_db.message_history.insert_one({
            "user_id": "user123",
            "message": "Hello 1",
            "response": "Hi 1",
            "timestamp": "2025-01-01T00:00:00Z"
        }).inserted_id

        msg2_id = self.mock_db.message_history.insert_one({
            "user_id": "user123",
            "message": "Hello 2",
            "response": "Hi 2",
            "timestamp": "2025-01-01T00:01:00Z"
        }).inserted_id

        # Insert message for another user
        other_id = self.mock_db.message_history.insert_one({
            "user_id": "other_user",
            "message": "Other message",
            "response": "Other response",
            "timestamp": "2025-01-01T00:02:00Z"
        }).inserted_id

        # Test GET /history
        res = self.client.get("/history", headers={"X-Token": "fake-token"})
        self.assertEqual(res.status_code, 200)
        items = res.json()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], str(msg2_id))
        self.assertEqual(items[1]["id"], str(msg1_id))

        # Test DELETE /history/{message_id} (delete msg1)
        res_del = self.client.delete(f"/history/{str(msg1_id)}", headers={"X-Token": "fake-token"})
        self.assertEqual(res_del.status_code, 200)
        self.assertEqual(res_del.json()["message"], "Message deleted successfully.")

        # Verify msg1 deleted from db, msg2 and other_user remain
        self.assertIsNone(self.mock_db.message_history.find_one({"_id": msg1_id}))
        self.assertIsNotNone(self.mock_db.message_history.find_one({"_id": msg2_id}))
        self.assertIsNotNone(self.mock_db.message_history.find_one({"_id": other_id}))

        # Test DELETE /history (clear all for user123)
        res_clear = self.client.delete("/history", headers={"X-Token": "fake-token"})
        self.assertEqual(res_clear.status_code, 200)
        self.assertEqual(res_clear.json()["deleted_count"], 1)

        # Verify user123 history is empty, other_user remains
        self.assertIsNone(self.mock_db.message_history.find_one({"_id": msg2_id}))
        self.assertIsNotNone(self.mock_db.message_history.find_one({"_id": other_id}))

if __name__ == "__main__":
    unittest.main()
