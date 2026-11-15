from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


HTML_PATH = Path(__file__).resolve().parents[1] / "index.html"
HTML = HTML_PATH.read_text(encoding="utf-8")


class AccessibilityMarkupParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.labels_for = set()
        self.nested_label_ids = set()
        self.inputs = []
        self.dialogs = []
        self.buttons = []
        self.images = []
        self.label_depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)

        if attributes.get("id"):
            self.ids.add(attributes["id"])

        if tag == "label":
            self.label_depth += 1
            if attributes.get("for"):
                self.labels_for.add(attributes["for"])

        if tag == "input":
            input_id = attributes.get("id")
            self.inputs.append(input_id)
            if input_id and self.label_depth:
                self.nested_label_ids.add(input_id)

        if tag == "div" and attributes.get("role") == "dialog":
            self.dialogs.append(attributes)

        if tag == "button":
            self.buttons.append(attributes)

        if tag == "img":
            self.images.append(attributes)

    def handle_endtag(self, tag):
        if tag == "label" and self.label_depth:
            self.label_depth -= 1


class AccessibilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.parser = AccessibilityMarkupParser()
        cls.parser.feed(HTML)
        cls.parser.close()
        cls.script_match = re.search(r"<script>(.*?)</script>", HTML, re.DOTALL)
        cls.script = cls.script_match.group(1) if cls.script_match else ""

    def test_every_search_input_has_an_associated_label(self):
        self.assertEqual(len(self.parser.inputs), 3)
        for input_id in self.parser.inputs:
            self.assertTrue(input_id, "Every input must have an id")
            self.assertTrue(
                input_id in self.parser.labels_for
                or input_id in self.parser.nested_label_ids,
                f"Input {input_id!r} has no associated label",
            )

    def test_modal_exposes_a_named_modal_dialog(self):
        self.assertEqual(len(self.parser.dialogs), 1)
        dialog = self.parser.dialogs[0]
        self.assertEqual(dialog.get("aria-modal"), "true")
        self.assertEqual(dialog.get("tabindex"), "-1")
        self.assertIn(dialog.get("aria-labelledby"), self.parser.ids)
        described_by = dialog.get("aria-describedby", "").split()
        self.assertTrue(described_by)
        self.assertTrue(all(identifier in self.parser.ids for identifier in described_by))

    def test_modal_has_a_labeled_native_close_button(self):
        close_buttons = [
            button for button in self.parser.buttons
            if button.get("aria-label") == "Close hotel details"
        ]
        self.assertEqual(len(close_buttons), 1)
        self.assertEqual(close_buttons[0].get("type"), "button")

    def test_hotel_detail_actions_are_keyboard_operable_buttons(self):
        actions = [
            button for button in self.parser.buttons
            if button.get("data-hotel-name")
        ]
        self.assertEqual(len(actions), 3)
        for action in actions:
            self.assertEqual(action.get("type"), "button")
            self.assertTrue(action.get("data-hotel-price"))

    def test_modal_script_handles_escape_focus_trapping_and_focus_restore(self):
        self.assertTrue(self.script_match, "Expected one inline script")
        self.assertIn('event.key === "Escape"', self.script)
        self.assertIn('event.key !== "Tab"', self.script)
        self.assertIn("previousFocus.focus()", self.script)
        self.assertIn("getClientRects()", self.script)
        self.assertIn('modal.setAttribute("aria-hidden", "false")', self.script)
        self.assertIn('modal.setAttribute("aria-hidden", "true")', self.script)

    def test_motion_and_keyboard_preferences_are_respected(self):
        self.assertIn("@media (prefers-reduced-motion: reduce)", HTML)
        self.assertIn(":focus-visible", HTML)
        self.assertIn("prefers-reduced-motion: reduce", self.script)
        self.assertNotIn('addEventListener("mousemove"', self.script)

    def test_hotel_images_have_alt_text_and_deferred_loading(self):
        self.assertEqual(len(self.parser.images), 3)
        for image in self.parser.images:
            self.assertTrue(image.get("alt"))
            self.assertEqual(image.get("loading"), "lazy")
            self.assertEqual(image.get("decoding"), "async")

    def test_demo_does_not_claim_to_create_a_reservation(self):
        self.assertIn("no reservation will be created", HTML)
        self.assertNotIn("Continue Booking", HTML)


if __name__ == "__main__":
    unittest.main()
