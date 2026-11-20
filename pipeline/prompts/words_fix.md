`words.json` in the current folder holds the caption words of a reel (Hinglish or English, see script.json "language") as [text, start, end], taken from automatic transcription. `script.json` holds what the speaker was told to say (its "clips").

Speech recognition makes mistakes, for example "9x9x16" for "nine by sixteen", a misheard name, or a wrong spelling. Compare words.json with the script and fix only the TEXT of wrong words so the captions read like the script:
- Spell words the way the script spells them. Numbers may become digits when that reads better ("nine by sixteen" -> "9:16").
- Never change start/end times, never reorder, add or remove entries. If two script words were heard as one entry, put both in that entry's text ("zaroorat hi").
- Keep the sentence punctuation that is already there ("hai." stays "hai.").
- Leave correct words alone.

Overwrite words.json with the fixed list (same JSON shape) and reply with one line: how many words you changed.
