import unittest
import sys
import os

# Add root directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.agent_memory import AgentMemory
from services.agent_loop import scale_coordinates

class TestCoordinateScaling(unittest.TestCase):

    def test_pixel_space_scaling_normal(self):
        """Test standard 1:1 display (1920x1080 screenshot, 1920x1080 logical screen size)"""
        memory = AgentMemory("test_goal")
        memory.coord_space = "pixel"
        # 1920x1080 scaled down to 1280x720 thumbnail
        memory.set_screen_info(
            resolution={"width": 1920, "height": 1080},
            thumbnail_size={"width": 1280, "height": 720},
            logical_size={"width": 1920, "height": 1080}
        )
        # Target center of thumbnail (640, 360) -> Should map to (960, 540)
        x, y = scale_coordinates(640, 360, memory)
        self.assertEqual((x, y), (960, 540))

    def test_pixel_space_scaling_high_dpi(self):
        """Test High DPI display (e.g. 150% scaling: 2880x1800 screenshot, 1920x1200 logical screen size)"""
        memory = AgentMemory("test_goal")
        memory.coord_space = "pixel"
        # 2880x1800 screenshot scaled to 1280x800 thumbnail
        # PyAutoGUI logical screen is 1920x1200
        memory.set_screen_info(
            resolution={"width": 2880, "height": 1800},
            thumbnail_size={"width": 1280, "height": 800},
            logical_size={"width": 1920, "height": 1200}
        )
        # Target in thumbnail (640, 400) -> Should map to logical (960, 600)
        x, y = scale_coordinates(640, 400, memory)
        self.assertEqual((x, y), (960, 600))

    def test_normalized_1000_scaling(self):
        """Test Gemini normalized 0-1000 grid space scaling to logical screen size"""
        memory = AgentMemory("test_goal")
        memory.coord_space = "normalized_1000"
        memory.set_screen_info(
            resolution={"width": 2880, "height": 1800},
            thumbnail_size={"width": 1280, "height": 800},
            logical_size={"width": 1920, "height": 1200}
        )
        # Center in 0-1000 grid (500, 500) -> Should map to logical (960, 600)
        x, y = scale_coordinates(500, 500, memory)
        self.assertEqual((x, y), (960, 600))

if __name__ == "__main__":
    unittest.main()
