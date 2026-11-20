Read `edit/work/captions.unknown.json` in the current folder: a list of Devanagari words from a Hinglish transcript. Also read `script.json` (the words the speaker was given) to see how each word is meant.

Write `edit/work/roman_extra.json`: one object that maps every listed Devanagari word to the way a Hinglish viewer would type it in Roman script, matching the script's spelling where the word appears there. Examples: {"मतलब": "matlab", "एजेंट": "agent", "चाहिए।": "chahiye?", "है।": "hai."}. Keep a trailing "।" as "." (or "?" for a question). If the file already exists, keep its entries and add the new ones.

Write the file and reply "ok".
