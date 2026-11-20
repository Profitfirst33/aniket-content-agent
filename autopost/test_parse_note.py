import unittest
from parse_note import parse


class T(unittest.TestCase):
    def test_example(self):
        r = parse("collab @anantgupta tag @wisprflow trial")
        self.assertEqual((r["collab"], r["tag"], r["trial"], r["rest"]), (["anantgupta"], ["wisprflow"], "manual", ""))

    def test_multi_and_rest(self):
        r = parse("english mein banao collab @a.b and @c_d tag @x, @y trial auto")
        self.assertEqual(r["collab"], ["a.b", "c_d"])
        self.assertEqual(r["tag"], ["x", "y"])
        self.assertEqual(r["trial"], "auto")
        self.assertEqual(r["rest"], "english mein banao")

    def test_bare_handle_is_tag(self):
        self.assertEqual(parse("shoutout @nick_saraev")["tag"], ["nick_saraev"])

    def test_empty(self):
        self.assertEqual(parse(""), {"collab": [], "tag": [], "trial": None, "rest": ""})

    def test_dedupe(self):
        self.assertEqual(parse("tag @A @a")["tag"], ["A"])


if __name__ == "__main__":
    unittest.main()
