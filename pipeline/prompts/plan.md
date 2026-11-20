You plan the on-screen scenes of a nick_saraev-style reel. Read these files in the current folder:
- `script.json`: the script (title, hook_headline, clips, keywords, cta_word)
- `words.json`: every spoken word with its start and end in seconds, as [text, start, end]
- `edit/assets/`: available media. `flow.png` is a screenshot of Google Flow with the avatar clips. `raw.mp4` is a raw avatar clip.
- `edit/work/duration.txt`: the reel length in seconds
- `ref/frames.jpg` and `ref/transcript.txt` (only when there is a reference reel): what the reference showed on screen and when

When there is a reference reel, mirror its visual beats: the same kind of demo at the same moment of the story (repo page, terminal, flow diagram, dashboard, title card). Use REAL screenshots of the real thing whenever it has a public page. Capture one with
`node /opt/aniket-content-agent/pipeline/capture.mjs <url> edit/assets/<name>.png`
(for example the GitHub repo or the product site found in request.txt or script.json sources) and show it with type browser_image. Capture at most 3 pages. Look at each capture (Read the png) and do not use it if it shows a login wall, an error or a cookie banner.

Write `spec.json`, following the schema and scene types documented at the top of `/opt/aniket-content-agent/pipeline/build_reel.py` (read that docstring first).

Rules:
- 8-11 scenes that cover the whole reel with no gaps. Scene 1 starts at 0, each scene starts where the previous ends, and the last ends exactly at the duration. Every scene lasts at least 1.6 s.
- Cut scenes on word boundaries: a scene starts at the start time of the word that begins its idea.
- Scene 1 (hook): face "card", bg "light", line1/box = script.hook_headline, with a strong demo (browser_image of flow.png only if the topic is about making videos; otherwise tiles or terminal).
- The last scene: type "cta", face "full", bg "none". It starts at the word "comment" (or just before the CTA sentence).
- Mix layouts like nick_saraev: about half the scenes face "card" (smaller demo + avatar), some face "none" (bigger demo, avatar hidden), and at most 2 dark "wow" scenes (bg "dark", type bigstat or compare). Never two dark scenes in a row.
- Every non-cta scene has a box of 2-4 words (italic lime line) that names the idea; line1 is optional, 2-3 words.
- Demo content must be TRUE to the script: real commands, real tool names, real steps from the script. No invented numbers or stats. Keep text short: terminal lines under 34 characters, tile texts under 16 characters.
- keywords: copy script.keywords plus the cta_word.
- duration: the value in edit/work/duration.txt.

After writing, run `python3 /opt/aniket-content-agent/pipeline/build_reel.py .` to validate. If it prints spec errors, fix spec.json and run it again until it prints "built". Reply with one line: the number of scenes.
