import unittest
import asyncio
from unittest.mock import MagicMock
from services.pending_actions import set_pending, get_pending
from services.control_center_chat import run_control_center_chat, execute_pending_for_user, ws_manager

class TestControlCenterChatFlow(unittest.TestCase):
    def setUp(self):
        ws_manager.is_connected = MagicMock(return_value=True)

    def test_confirmation_in_chat_stream(self):
        async def run_test():
            # Trigger initial action that requires confirmation
            lines1 = []
            async for line in run_control_center_chat("user_123", "chụp màn hình"):
                lines1.append(line)

            pending = get_pending("user_123")
            self.assertIsNotNone(pending)
            self.assertEqual(pending.get("tool"), "screenshot")

            # Mock desktop executor success
            from services import control_center_chat
            control_center_chat.execute_desktop_action = MagicMock(return_value=asyncio.Future())
            control_center_chat.execute_desktop_action.return_value.set_result({"success": True, "result": {}})

            # Confirm with 'có'
            lines2 = []
            async for line in run_control_center_chat("user_123", "có"):
                lines2.append(line)

            # Assert pending was cleared and executed
            self.assertIsNone(get_pending("user_123"))
            output2 = "".join(lines2)
            self.assertIn("Confirmation received", output2)

        asyncio.run(run_test())

    def test_execute_pending_for_user_via_proxy(self):
        async def run_test():
            set_pending("user_456", {"tool": "open_app", "app_name": "Chrome", "skill_id": "DC"})

            from services import control_center_chat
            control_center_chat.execute_desktop_action = MagicMock(return_value=asyncio.Future())
            control_center_chat.execute_desktop_action.return_value.set_result({"success": True})

            result = await execute_pending_for_user("user_456")
            self.assertTrue(result.get("executed"))
            self.assertIsNone(get_pending("user_456"))

        asyncio.run(run_test())

if __name__ == "__main__":
    unittest.main()
