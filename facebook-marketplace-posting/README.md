# Facebook Marketplace Poster

An agent skill that turns folders of item photos into priced Facebook Marketplace listings, and keeps track of them after posting. A listing file is optional.

## Install

Follow the [installation guide](INSTALL.md), or ask your agent to follow it. The guide covers Claude Code and Codex.

## What it does

1. Asks for the folder that holds your item folders, and which items to list (one, several, or all).
2. Works out what each item is from its photos, marking what it saw and what it couldn't tell.
3. Checks that the item can be sold (Facebook's Commerce Policies and product recalls) and flags private details in the photos, such as faces, addresses, licence plates and serial numbers.
4. Asks only the questions that change the price: model, condition, what's included, whether it works, your selling goal and pickup location.
5. Researches prices on Facebook Marketplace, eBay sold listings, other resale sites and trade-in offers in your country, then suggests a listing price and a lowest acceptable price with the comparables behind them.
6. Finds up to 10 of the largest active local buy/sell groups, biggest first. Groups limited to one topic are offered only for items in that topic. It never joins a group for you.
7. Shows a field-by-field outline of exactly what it will fill in, including groups, for your approval.
8. Posts through your signed-in browser, publishing only when you ask, then confirms Facebook's success message.
9. Records the posting history, renames the folder `DONE - <name>`, and updates your tracking CSV if you have one.

It also handles batches, marking items sold, price drops, relisting, stale-listing checks, and optional cross-posting to OfferUp, Craigslist or Mercari.

Nothing is published, joined, paid for or deleted without your explicit approval.

## What you need

- A folder containing one subfolder of photos per item. A `Marketplace Listing.md` in an item folder is optional; if present, its values are used.
- A Facebook account with Marketplace access, signed in to Chrome.
- An agent with access to local files and a browser-control tool that can upload photos, such as Claude in Chrome.

For the complete workflow, see [SKILL.md](SKILL.md).
