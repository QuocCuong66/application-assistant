import unittest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from bson import ObjectId
import bcrypt

class MockCollection:
    def __init__(self):
        self.docs = {}

    def find_one(self, filter_query):
        if "_id" in filter_query:
            key = str(filter_query["_id"])
            return self.docs.get(key)
        if "username" in filter_query:
            for doc in self.docs.values():
                if doc.get("username") == filter_query["username"]:
                    return doc
        if "token" in filter_query:
            for doc in self.docs.values():
                if doc.get("token") == filter_query["token"]:
                    return doc
        if "user_id" in filter_query:
            for doc in self.docs.values():
                if doc.get("user_id") == filter_query["user_id"]:
                    return doc
        return None

    def insert_one(self, doc):
        _id = ObjectId()
        doc["_id"] = _id
        self.docs[str(_id)] = doc
        res = MagicMock()
        res.inserted_id = _id
        return res

    def update_one(self, filter_query, update_query):
        target = None
        if "_id" in filter_query:
            target = self.docs.get(str(filter_query["_id"]))
        if target and "$set" in update_query:
            target.update(update_query["$set"])
        if target and "$inc" in update_query:
            for k, v in update_query["$inc"].items():
                target[k] = target.get(k, 0) + v
        res = MagicMock()
        res.modified_count = 1 if target else 0
        return res

    def delete_one(self, filter_query):
        target_id = None
        if "_id" in filter_query:
            key = str(filter_query["_id"])
            if key in self.docs:
                target_id = key
        res = MagicMock()
        if target_id:
            del self.docs[target_id]
            res.deleted_count = 1
        else:
            res.deleted_count = 0
        return res

    def delete_many(self, filter_query):
        res = MagicMock()
        count = len(self.docs)
        self.docs.clear()
        res.deleted_count = count
        return res

    def find(self, *args, **kwargs):
        class MockCursor:
            def __init__(self, items):
                self.items = items
            def sort(self, *a, **k):
                return self
            def limit(self, *a, **k):
                return self
            def __iter__(self):
                return iter(self.items)
        return MockCursor(list(self.docs.values()))


class MockDatabase:
    def __init__(self):
        self.users = MockCollection()
        self.usage = MockCollection()
        self.message_history = MockCollection()
        self.trained_tasks = MockCollection()
        self.transactions = MockCollection()


class TestAuthProAndAgentFeatures(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockDatabase()
        from main import app
        app.dependency_overrides = {}

        from database import get_db
        app.dependency_overrides[get_db] = lambda: self.mock_db

        self.client = TestClient(app)

    def tearDown(self):
        from main import app
        app.dependency_overrides = {}

    def test_registration_automatically_creates_pro_user(self):
        res = self.client.post("/auth/register", json={"username": "newuser", "password": "password123"})
        self.assertEqual(res.status_code, 200)

        # Check DB user
        user = self.mock_db.users.find_one({"username": "newuser"})
        self.assertIsNotNone(user)
        self.assertTrue(user.get("is_pro"))

    def test_login_automatically_ensures_pro_status(self):
        # Insert a user who was previously is_pro: False
        hashed = bcrypt.hashpw("oldpassword".encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        doc = {
            "username": "legacyuser",
            "password": hashed,
            "token": None,
            "is_pro": False
        }
        self.mock_db.users.insert_one(doc)

        res = self.client.post("/auth/login", json={"username": "legacyuser", "password": "oldpassword"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # Token response should be is_pro = True
        self.assertTrue(data.get("is_pro"))

        # Database should be updated to is_pro = True
        user = self.mock_db.users.find_one({"username": "legacyuser"})
        self.assertTrue(user.get("is_pro"))

    def test_usage_limit_allows_unlimited_requests(self):
        # Set up active user
        token = "test-token-pro"
        user_id = str(ObjectId())
        self.mock_db.users.docs[user_id] = {
            "_id": ObjectId(user_id),
            "username": "prouser",
            "token": token,
            "is_pro": True
        }

        # Mock usage already over 20 requests
        self.mock_db.usage.docs["usage-1"] = {
            "_id": ObjectId(),
            "user_id": user_id,
            "request_count": 50,
            "last_reset_date": "2026-08-27"
        }

        from api.deps import check_usage_limit
        from api.deps import get_current_user
        current_user = get_current_user(x_token=token, db=self.mock_db)
        usage = check_usage_limit(current_user=current_user, db=self.mock_db)
        self.assertEqual(usage["request_count"], 50)

    def test_delete_single_history_message(self):
        # Insert a message into history
        user_id = str(ObjectId())
        token = "token-del"
        self.mock_db.users.docs[user_id] = {
            "_id": ObjectId(user_id),
            "username": "deluser",
            "token": token,
            "is_pro": True
        }

        msg_obj_id = ObjectId()
        self.mock_db.message_history.docs[str(msg_obj_id)] = {
            "_id": msg_obj_id,
            "user_id": user_id,
            "message": "Hello to be deleted",
            "response": "Reply to be deleted"
        }

        res = self.client.delete(f"/history/{str(msg_obj_id)}", headers={"X-Token": token})
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(str(msg_obj_id), self.mock_db.message_history.docs)


if __name__ == "__main__":
    unittest.main()
