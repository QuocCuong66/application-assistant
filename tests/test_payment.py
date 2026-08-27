import unittest
import os
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from bson import ObjectId

class MockUsersCollection:
    def __init__(self):
        self.users = {}

    def update_one(self, filter_query, update_query):
        user_id = str(filter_query.get("_id"))
        if user_id in self.users:
            if "$set" in update_query:
                self.users[user_id].update(update_query["$set"])
        res = MagicMock()
        res.modified_count = 1
        return res

class MockDb:
    def __init__(self):
        self.users = MockUsersCollection()

class TestPaymentPromoCode(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockDb()
        user_obj_id = ObjectId()
        self.user_id_str = str(user_obj_id)
        self.mock_db.users.users[self.user_id_str] = {"_id": user_obj_id, "username": "testuser", "is_pro": False}

        from main import app
        app.dependency_overrides = {}

        from database import get_db
        from api.deps import get_current_user

        app.dependency_overrides[get_db] = lambda: self.mock_db
        app.dependency_overrides[get_current_user] = lambda: {"id": self.user_id_str, "username": "testuser"}

        self.client = TestClient(app)

    def tearDown(self):
        from main import app
        app.dependency_overrides = {}

    def test_upgrade_with_valid_code(self):
        res = self.client.post("/payment/upgrade_code", json={"code": "qcdzai"}, headers={"X-Token": "fake"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_pro"])
        self.assertTrue(self.mock_db.users.users[self.user_id_str]["is_pro"])

    def test_upgrade_with_valid_code_case_insensitive(self):
        res = self.client.post("/payment/upgrade_code", json={"code": "QcDzAi"}, headers={"X-Token": "fake"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_pro"])

    def test_upgrade_with_invalid_code(self):
        res = self.client.post("/payment/upgrade_code", json={"code": "wrong_code"}, headers={"X-Token": "fake"})
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("Mã nâng cấp không chính xác", data["detail"])

if __name__ == "__main__":
    unittest.main()
