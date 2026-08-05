import unittest
from app.vision.manager import vision_manager
from app.vision.schemas import VisionResult, OCRResult, CaptionResult
from app.memory.manager import memory_manager


class TestVisionMemory(unittest.TestCase):

    def test_vision_memory_storage(self):
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 50
        v_result = vision_manager.process_image(png_bytes, "receipt_invoice.png", "image/png")

        mem_item = vision_manager.store_visual_memory(v_result, user_id="test_user")

        self.assertIsNotNone(mem_item)
        self.assertIn("Visual Fact: receipt_invoice.png", mem_item.title)
        self.assertEqual(mem_item.source, "vision_engine")

        stored_memories = memory_manager.get_memories(user_id="test_user")
        self.assertTrue(any(m.id == mem_item.id for m in stored_memories))


if __name__ == "__main__":
    unittest.main()
