# Autopost: Aniket AI Instagram

Built 3 Nov 2026. Not hooked into the bot yet and nothing has been posted.

## Files
- post.py: posts a reel, carousel, image or story through the Instagram API with Instagram Login (graph.instagram.com/v23.0). Every post gets is_ai_generated=true (the "AI info" label, which can only be set at creation). Reels also take --trial manual|auto (trial_params.graduation_strategy MANUAL or SS_PERFORMANCE), --tag and --collab (max 3), and audio name "Aniket AI · Original audio". Waits for status_code FINISHED, publishes, reads back permalink + is_ai_generated, prints JSON. --dry-run prints every request and sends nothing. --refresh-token renews the 60 day token (needs a token at least 24 h old).
- caption.py: writes caption.txt for a job (prompts/caption.md), checks the rules (3 to 5 lines, "Comment WORD", no "link", no dashes, max 5 hashtags) and retries once. Works on copies; use --out to keep it out of the job dir.
- parse_note.py: reads "collab @a tag @b trial" from the Telegram note. Tests: python3 -m unittest test_parse_note
- ig.example.json: config shape. Real file = ig.json, chmod 600.
- test/: dry-run log and sample captions.

## Hooking into the bot (later, after his go)
1. run_reel.py finishes -> caption.py <job> -> deliver.py sends the reel with the caption and inline buttons Post / Trial / Skip (reply_markup inline_keyboard, callback_data "post:<job>", "trial:<job>", "skip:<job>").
2. bot.py polls getUpdates with callback_query too: answerCallbackQuery, then runs post.py <job> --type reel [--trial manual] plus tags/collabs from parse_note(item note), and replies with the permalink and whether the AI label is on.
3. After a post: create the tracked go. address, then the Comment Watchdog automation in the VPS browser (CDP 9225).
4. Cron: post.py --refresh-token every 50 days.

## Still needed
- Token + ig_user_id for the new account (Meta app with Instagram Login, account added as Instagram tester).
- Public media folder. Proposal: add to the YOUR-DOMAIN block in /etc/caddy/Caddyfile
    handle_path /ig-media/* { root * /opt/aniket-content-agent/autopost/public; file_server }
  (demo is already noindex). Files are deleted right after publishing. Caddy NOT changed yet.
- Comment Watchdog: account connected + signed in once in the VPS browser.
