---
name: facebook-marketplace-posting
description: Identify, price and post items to Facebook Marketplace from a local folder of item photos, then manage them after posting. Use when the user asks to list, price, sell, create, publish, or repeat a Facebook Marketplace listing from a folder of item folders (photos, with or without a listing file), or to mark an item sold, drop a price, relist, or cross-post to OfferUp, Craigslist or Mercari. Works out what each item is from its photos, asks the questions needed to value it, researches what it sells for online in that condition, proposes a price and groups for approval, then posts.
---

# Facebook Marketplace Posting

Turn folders of item photos into priced Facebook Marketplace listings and post them through Chrome. A listing file is optional: when there is none, work out the details from the photos, ask the user, and research the price.

Modes:
- **List** (default): steps 0–6 below.
- **After posting** — "mark sold", "drop the price", "relist", "what hasn't sold?": read `references/after-posting.md`.
- **Cross-post** to OfferUp, Craigslist or Mercari: offered at step 4b; read `references/cross-posting.md` when the user wants it.

## Inputs

- **Inventory folder:** the folder that holds the item folders. Always ask the user for it at the start, unless they already gave it in this request. Never assume a default path. If they give an item folder directly, use its parent as the inventory folder.
- **Item folders:** `<inventory folder>/<item folder>`. Unposted items are folders not starting with `DONE - ` or `SOLD - `. If the user hasn't said which items, list the unposted ones and ask: one item, a chosen few, or all of them (batch mode).
- **Photos:** the JPEG/HEIC/PNG images in each item folder. These are the main evidence for what the item is.
- **Listing file (optional):** `Marketplace Listing.md`, or the only non-sample `.md` in the folder. When present, its values are the user's and win over anything guessed. Run the price research only if it has no price, its research is stale (step 3a), or the user asks.
- **Location and country:** the pickup city/area and country. Ask once per run. The country decides the price sources, currency, policies and recall databases.
- **Facebook groups:** proposed by the skill (step 3b) or named by the user. Never post to a group the user hasn't approved for this item.
- **Topic-limited groups** (any group for one kind of item: a religion's or subject's books, cameras, baby gear, one college's textbooks, one brand, etc.) may be used only when this item clearly belongs to that topic, by the user's word or clear evidence in the photos (e.g. publisher, author, brand, label). Never post an off-topic item to them, even if the group is large or the user is a member.

## Batch mode

When more than one item is chosen, work in phases across all items instead of one item at a time, so the user answers questions and approves once:

1. Identify every item (step 1) and run the photo and policy checks (step 2) for each.
2. Ask all questions (step 3) in one message, grouped by item, plus the shared ones (location, delivery, selling goal) once.
3. Research prices (step 3a) and groups (step 3b) for every item. Fetch-based research can run in parallel; browser research runs one tab at a time.
4. Show one summary table — item, suggested price, lowest acceptable, research confidence, groups, any flags — followed by each item's full outline (step 4b). The user can approve all, approve some, or change any item.
5. Post approved items one at a time (step 5).

## 1. Identify the item

1. Look at every photo in the item folder. Read any visible text: brand, model, model/serial plates, labels, packaging, book titles/authors/publishers/editions, sizes, capacities.
2. Use filenames and any notes in the folder as hints, not proof.
3. Write down what you can see: item type, brand, model, variant, quantity/set contents, accessories shown, visible wear or damage.
4. Mark every detail as either **seen** (visible in a photo) or **unknown**. Never present a guess as fact. If the photos can't tell two models apart, say so and ask.

## 2. Checks before pricing

### Can it be sold?
- Check the item against Facebook's Commerce Policies (`https://www.facebook.com/policies_center/commerce`). Items Facebook prohibits (e.g. weapons and ammunition, animals, medical devices and prescription items, alcohol and tobacco, adult items, recalled products, digital/subscription items, and others the page lists) can't be listed. If the item is prohibited or borderline, stop for this item and tell the user which rule applies, with the link.
- **Recalls:** for baby and children's products (car seats, cribs, strollers, high chairs, toys), helmets, appliances, heaters, chargers/batteries and other safety-related items, search the recall database for the user's country (e.g. US CPSC `cpsc.gov/Recalls` and NHTSA for car seats; Health Canada recalls; UK Product Safety Database; EU Safety Gate; Australia `productsafety.gov.au`) by brand and model. A recalled item must not be listed; tell the user what the recall says and what remedy it offers. If the model/date can't be confirmed, ask for the label details.

### Privacy in the photos
Look at every photo for: faces (especially children), mail, shipping or address labels, house numbers and street signs, licence plates, serial numbers or IMEIs on devices, screens or documents showing personal information, family photos in the background. List each finding by photo filename and offer, per photo: exclude it, or use a cropped/blurred copy (made in the working folder, never by editing the original). Serial numbers can stay only if the user wants them shown.

### Photo prep
- Read Facebook's photo limit from the listing form when posting; if the item has more photos than that, ask which to leave out.
- Pick the clearest, best-lit photo that shows the whole item as the cover (first) photo, then detail and flaw shots. Show the proposed order in the outline.
- HEIC, or anything Facebook won't take, is converted to JPEG copies in a working folder outside the item folder (macOS: `sips -s format jpeg <in> --out <out>`; elsewhere ImageMagick or Pillow). Strip location (GPS) metadata from all upload copies. Never modify or delete the user's originals.

## 3. Ask the questions that set the value

Ask the user, in one compact list, only what the photos cannot answer and that changes price or the listing. Pick from:

- Exact model, size, capacity, edition or year, when not readable.
- Condition: New / Used – Like New / Used – Good / Used – Fair, plus any faults, missing parts, repairs or cosmetic damage not shown.
- Does it work / fully tested? (electronics, appliances, tools)
- What's included: box, manual, charger, cables, accessories, full set vs partial.
- Age, original purchase price, receipts or warranty, if they affect value.
- Selling goal: quick sale, or best price and willing to wait.
- Pickup location and country, local pickup vs shipping, public meetup yes/no — ask once and reuse for later items in the same run.

Skip questions already answered by the photos, a listing file, or earlier in this conversation. Wait for answers before pricing.

## 3a. Research the price

Find what this item actually sells for in this condition. Use the sites for the user's country (e.g. the matching eBay site such as ebay.com, ebay.co.uk, ebay.ca, ebay.com.au, ebay.de; local resale apps; local trade-in services) and give prices in the local currency.

**Stale research:** if a listing file already has research older than 14 days (or the user asks), redo it before posting and show what changed.

Check all of these source groups every time (skip a group only when it has nothing for this kind of item or isn't available in the user's country, and say so):

1. **Facebook Marketplace** — search near the user's location (signed-in Chrome) for the same or very similar item. These are local asking prices; discount them, and note any marked sold/pending.
2. **eBay** — sold/completed listings (`LH_Sold=1&LH_Complete=1`) are the best signal of real sale prices. Match model and condition; note the price excluding shipping. Glance at active listings too for current competition.
3. **Other online sellers** — whichever carry this kind of item in the user's country, for example (US names; use local equivalents elsewhere, e.g. Gumtree, Kijiji, Vinted, Kleinanzeigen, Leboncoin, Trade Me): Mercari, OfferUp, Craigslist, Poshmark, Amazon (used and new), big retailers or the manufacturer (new retail price = ceiling), Back Market or Swappa (phones, tablets, laptops), Reverb (music gear), AbeBooks/BookFinder/ThriftBooks (books), Chairish/1stDibs (furniture, decor), StockX (sneakers, collectibles), PriceCharting (games, cards).
4. **Trade-in / buyback offers** — what a company would pay right now, for example: Apple Trade In, Best Buy Trade-In, Amazon Trade-In, GameStop, Decluttr, Gazelle, Back Market trade-in, Swappa/ecoATM (devices), BookScouter (books and textbooks), Guitar Center/Music Go Round (instruments), or local equivalents (e.g. CeX, musicMagpie, WeBuyBooks). Trade-in is the price **floor**: the user can get at least this with no buyer hassle, so say so if the Marketplace price would barely beat it.

Rules:
- Compare like with like: same model/edition, same condition, same included items. Drop listings that don't match, and say why.
- Aim for 5+ usable sale/asking comparables plus any trade-in quotes. If fewer exist, say the estimate is low-confidence.
- Trade-in sites often need a condition questionnaire; answer it from the user's stated condition only, and never submit a trade-in, enter personal details, or create an account — only read the quoted offer.
- Never invent a price or a source. Every number in the report must come from a listing you saw.
- **Blocked sites (eBay especially):** if eBay or any other source refuses web fetch, curl or other command-line access (403, "Pardon our interruption", bot check, empty results), don't keep retrying from the command line. Switch to the user's real, signed-in Chrome with computer control (Claude in Chrome tools, or another Chrome-control tool if those aren't connected):
  - Warm it up first: open the site's home page in one worker tab, let it load, then search through the site's own search box like a person rather than jumping straight to a deep search URL.
  - Pace actions at human speed (a few seconds apart) and read results from the page (`get_page_text` / `read_page`) rather than scraping in bulk.
  - Work in a background tab and don't steal the user's cursor or focus.
  - If a CAPTCHA or "verify you're human" page appears, stop and ask the user to clear it in that tab; never try to solve or bypass it. Then carry on.
  - If the site still blocks access, report that source as unavailable and price from the others.

Report to the user before going further:
- What you think the item is, and anything still uncertain.
- A short comparables table: source, title, condition, price, type (sold / asking / new retail / trade-in offer), link.
- The trade-in floor and new-retail ceiling, where found.
- Range: low / typical / high for this condition.
- **Suggested listing price** and a **lowest acceptable price**, with one or two sentences on why (e.g. "sold comps cluster at $40–50; listing at $55 leaves room to negotiate"). Adjust for the user's selling goal.

Wait for the user to accept or change the price. Never post at a price the user hasn't confirmed.

## 3b. Find groups to post in

Look for groups where this item would reach local buyers. Use the user's signed-in Chrome (same pacing and background-tab rules as above).

1. **Groups the user is already in:** check Facebook's groups page (`facebook.com/groups/joins`) and note buy/sell, swap or marketplace groups for their area plus any groups that fit the item's category.
2. **Other large local groups:** search Facebook groups for the user's city, nearby towns and region, e.g. "buy sell <city>", "<city> marketplace", "<county> yard sale", "<city> swap", plus category groups (e.g. "<city> furniture", "<region> camera gear", "used textbooks <college>").
3. For each candidate, record: name, link, member count, public/private, whether the user is a member (or has a pending request), how active it is (recent posts), and any posting rules shown in the About section (allowed items, price required, one post per day, no shipping, etc.).
4. Keep groups that are active, large (prefer thousands of members), local to the pickup location, and allow this kind of item. Drop groups whose rules forbid it, and say why.

Topic-limited groups (see Inputs) are candidates only when the item is in that group's category; read the group's name, description and rules to decide its topic. General local buy/sell groups accept any allowed item. In the approval list, mark each group as **general** or **topic: <topic>** and say how the item fits the topic.

Do not join, request to join, or answer membership questions for any group. Groups the user isn't in are listed as suggestions to join; joining is the user's decision and needs their explicit yes per group (and Facebook may need admin approval, so those can't be posted to in this run).

**Group pacing:** propose up to 10 groups per item by default (the user may approve more), picking the 10 largest suitable groups and listing them by member count, biggest first. Respect each group's posting limits (e.g. one post per day) using the posting history in the item listing files (step 6). Avoid putting the same item in the same group twice.

## 4. Write the listing file

Once the user confirms the price, save `Marketplace Listing.md` in the item folder (don't overwrite an existing one without asking) with: title, price, lowest acceptable price, currency, category, condition, description, location, delivery method, public meetup, photo filenames in upload order (and which are excluded or replaced by cropped copies), and a "Price research" section (range, date, links). This file is now the source of truth for posting.

## 4b. Approve the listing outline

Before opening the Facebook listing form, show the user exactly what will be filled in, field by field, and wait for approval:

| Field | Will fill as |
|---|---|
| Photos | count + filenames in upload order (cover first), and any excluded or blurred |
| Title | exact text |
| Price | exact amount (and lowest acceptable, kept private) |
| Category | Facebook category path |
| Condition | Facebook condition option |
| Description | full text, exactly as it will appear |
| Location | city/area |
| Delivery | local pickup / shipping |
| Public meetup | yes / no |
| Marketplace public listing | on |
| Groups | numbered list sorted by member count (biggest first): name, members, member? (yes / not a member), general or topic, why it fits, any posting rule that matters — or "none" |
| Cross-post | none, or OfferUp / Craigslist / Mercari (optional, see `references/cross-posting.md`) |

Show the groups list separately too, split into **Will post in** (member groups) and **Suggested to join** (not a member yet), each sorted biggest first, and ask the user to approve, remove or add groups. Only approved groups get selected.

Also list any optional Facebook fields you will leave blank or set (e.g. brand, colour, SKU, tags), any value that is still a guess, and any policy, recall or privacy flags from step 2.

- Apply any changes the user asks for, update `Marketplace Listing.md`, and show the changed fields again.
- Do not open the Facebook listing form until the user approves the outline.
- Approval of the outline is not permission to click Publish unless the user says so (see step 5.9).

## Listing copy style

Titles: brand + model + key spec, plain and searchable, no ALL CAPS or emoji spam.

Descriptions must sound like ordinary Marketplace sale posts. State what the item is, visible condition, included items, and price-relevant facts. Do not tell buyers to test, verify, count, inspect, or confirm anything at pickup; do not write internal notes such as `per seller`, setup warnings, or procedural disclaimers into buyer-facing copy. Use concise wording such as `Sold as pictured` when useful. Never claim something you only guessed (e.g. "works perfectly" without the user saying so). Never include the user's address, phone number or email.

## 5. Post (browser workflow)

Use Chrome against the user's signed-in Facebook session, in a background tab, at human pace.

1. Open `https://www.facebook.com/marketplace`.
2. Choose `Selling`, then `Create listing`.
3. Choose `Item for sale` if Facebook presents listing-type choices.
4. Add the approved photos (upload copies where converted or blurred) in the approved order. Verify uploaded thumbnails, order and count.
5. Fill title, price, category, condition, and description exactly as approved in the outline (4b).
   - If Facebook generates a description, replace it with the listing file's description.
   - Choose the closest accurate Facebook category. Do not silently substitute a misleading category.
   - Use the confirmed price exactly.
6. Continue to delivery details.
   - Set the location from the listing; select the matching official suggestion.
   - Select `Local pickup` when the listing says local pickup.
   - Enable `Public meetup` when the listing says yes.
   - Do not change account-wide default delivery settings unless the user asks.
7. Continue to audience/placement.
   - Keep Marketplace public listing enabled.
   - Select only the groups the user approved in 4b. If an approved group doesn't appear in Facebook's list, stop and say so; never pick a substitute.
   - Never select a topic-limited group unless the item clearly belongs to its topic.
   - Verify each selected group is correct before continuing.
8. Review the preview against the approved outline: photos, title, price, category, condition, description, location, delivery, meetup, and groups.
9. Click `Publish` only when the user explicitly asked to post and the review passes. If anything on Facebook differs from the approved outline (Facebook forced a different category, trimmed text, a group was missing), stop and show the difference before publishing.
10. Verify Facebook shows a success/posted state or listing confirmation. If Publish is disabled, loading, or confirmation is absent, report incomplete status; do not claim it posted.
11. **No waiting needed:** groups are chosen inside the listing form and Facebook shares the listing to them when it publishes, so there are no separate group posts to space out. Move straight on to the next item in a batch. If Facebook ever shows a warning, rate limit or "you're posting too fast" message, stop and report; don't retry around it.

## 6. After confirmed posting

Only after Facebook confirms the listing:

- Add a "Posting history" section to `Marketplace Listing.md`: date and time, listing URL, price, groups posted to, cross-posts, status `POSTED`. Later price drops, relists and sales are appended here (see `references/after-posting.md`).
- Rename the item folder from `<name>` to `DONE - <name>`. If that name already exists, stop and report; never overwrite.
- If a master CSV exists (normally `<inventory folder>/facebook_marketplace_listings.csv`), set the matching row's `Status` to `POSTED` (match by photo filename first, then exact title; add a `Status` column if absent, preserving all existing columns and rows) and update stored photo paths to the renamed folder. If the match isn't unique, stop and report. If there is no CSV, skip this and say so — don't create one unless the user asks.
- Verify the renamed folder exists and all photos and the listing file remain inside it.
- Remove only the working upload copies this run created (converted/blurred JPEGs), by moving them to the Trash, never permanent deletion.

## Common UI traps

- Facebook may insert AI-generated text after photos upload. Replace it.
- Category suggestions can be wrong. Select an accurate category or pause for user choice.
- Group lists can change. Never assume a prior group selection still exists.
- A disabled Publish button can mean required fields or upload processing remain. Wait briefly, inspect validation messages, then fix only listing-backed fields.
- Never paste passwords, payment details, or other sensitive data into the listing.

## Completion report

For each item: title, price (and the research range it came from), photo count (and any excluded or blurred), selected groups, cross-posts, Facebook confirmation and listing URL, folder rename, and CSV status (updated or no CSV). Include any field that required user input, any flag from step 2, and anything left unresolved.
