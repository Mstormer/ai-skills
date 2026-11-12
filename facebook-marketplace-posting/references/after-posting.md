# After posting: sold, price drops, relists, stale listings

Use the user's signed-in Facebook in Chrome (background tab, human pace). Each item's `Marketplace Listing.md` "Posting history" section is the record: read it first, and append every change with the date.

Find items by looking in the inventory folder (ask for it if not given) at folders starting with `DONE - ` (posted) and `SOLD - ` (sold).

## Status check: "what hasn't sold?"

1. Open Marketplace → `Selling` and read each active listing's status and whatever interest numbers Facebook shows (clicks, saves, messages).
2. Match each to its item folder by listing URL, then title.
3. Report a table: item, days listed, current price, interest shown, last change. Flag listings with little or no interest after 7 days, and suggest one action each (drop price, relist, add groups, retake the cover photo), using the item's price research and lowest acceptable price.
4. Report only. Change nothing until the user picks actions.

## Mark sold

1. Confirm which item and, optionally, the sale price.
2. On Facebook, open the listing and use `Mark as sold`. Verify the listing shows as sold.
3. If it was cross-posted, mark it sold or close it on each site too (see `cross-posting.md`), and say which.
4. Append to the posting history: date, `SOLD`, sale price if given.
5. Rename `DONE - <name>` to `SOLD - <name>` (stop if that name exists). If a master CSV exists, set `Status` to `SOLD` and update photo paths; same matching rules as posting.

## Drop the price

1. Propose a new price from the stored research (re-check if older than 14 days), never below the lowest acceptable price without the user saying so. The user confirms the exact new price.
2. Edit the listing on Facebook and change only the price. Verify the listing shows the new price.
3. Update cross-posts if any, append the change (old → new price, date) to the posting history, and update the listing file's price.

## Relist / renew

1. If Facebook offers `Renew` or `Relist` for the listing, use that (it keeps the listing). Verify it worked.
2. If the only way is to delete and post again, ask first: deleting is irreversible and loses saves and messages. On a yes, delete it, then post again with the normal flow (outline approval still applies, and only to groups whose posting limits allow it).
3. Append to the posting history.

## Rules

- Every action that changes a live listing (mark sold, edit price, renew, delete) needs the user's explicit yes for that item.
- Never reply to buyers or send messages unless the user asks and approves the exact text.
- Never move or rename a folder whose new name already exists.
