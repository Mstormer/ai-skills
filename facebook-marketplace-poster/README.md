# Facebook Marketplace Poster

An agent skill that helps prepare and publish one Facebook Marketplace listing from an item folder. It asks for the folder and helps gather any missing listing details.

## Install

Follow the [installation guide](INSTALL.md), or ask your agent to follow it. The guide covers Codex and Claude Code.

## What it does

1. Asks for an item folder if you haven't provided one.
2. Reads the listing details, checks the photos, and asks about missing or unclear information.
3. Helps complete the Marketplace listing in your signed-in browser and reviews it against the source.
4. Publishes only when you have requested publication, then checks for Facebook's confirmation.
5. Updates your folder or tracking CSV only if you have requested or configured that bookkeeping.

It selects only the groups you specify or configure. If it cannot confirm publication, it reports the listing as incomplete.

## What you need

- An item folder containing a Markdown listing file and the item's JPEG photos. The skill prefers a file named `Marketplace Listing.md`.
- Listing details such as title, price, condition, location, and pickup or delivery preferences. The skill will ask about missing details.
- A Facebook account with Marketplace access, signed in to a browser your agent can control.
- An agent with access to local files and a browser computer-use tool that can upload photos. If browser control is unavailable, you can use the prepared details to finish the listing yourself.

For the complete workflow, see [SKILL.md](SKILL.md).
