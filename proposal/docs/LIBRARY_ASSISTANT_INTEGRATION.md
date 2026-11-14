# Ask Library Next: conversational student helper

The assistant accepts free-text requests. It does not begin with preset search buttons or force the student to choose a task menu. It identifies itself as a virtual helper, not human staff.

## Book conversations

Examples:

- `The Digital Edge`
- `I’m looking for a book called The Digital Edge`
- `Recommend books about digital inequality`
- Follow-up: `something after 2017`
- Follow-up: `the first one`
- Follow-up: `more`

Book searches run independently from the main page's current form state. OpenSquare is searched locally; broader Google Books discovery is attempted for an unknown known-item query or when few supported local records are found. Actual retrieved metadata supplies the book cards and snippets. The assistant does not manufacture titles or bibliographic details.

Each result message offers **See more results for [query]**. That action opens the site's search page, copies the conversation query and applicable filters, and closes the chat panel. Clicking a book card opens its record on the same site. A short follow-up keeps the previous topic and updates its constraints. The assistant's retrieval is not an independently validated relevance benchmark.

## Room conversations

Examples:

- `I want an individual room from 3-5pm on November 19`
- `I need a group room tomorrow from 3 to 5pm for four people`
- Follow-up: `tomorrow instead`
- Follow-up: `actually 4-6pm`

Natural-date parsing uses New York calendar dates, not the browser's local timezone. The helper asks for missing room type, date, start/end, or group size. It clarifies ambiguous morning/afternoon ranges. Policy validation checks the 14-day window, future start, half-hour increments, maximum three-hour session, and suitable individual/group size. Official NYU rules remain authoritative and can change.

### State without NYU API access

The application currently has no LibCal credentials. It prepares and retains the request inside the conversation, explains that it cannot verify availability, and returns no room cards. It does not substitute sample rooms, scraped stale search results, or “unavailable” for a missing integration. The user authorized preparing the integration until sponsor access is available.

### Configuration NYU must provide

Store these in the host's server environment; mark credentials as secrets:

- `LIBCAL_CLIENT_ID`
- `LIBCAL_CLIENT_SECRET`
- `LIBCAL_INDIVIDUAL_CATEGORY_ID`
- `LIBCAL_GROUP_CATEGORY_ID`
- Optional `LIBCAL_API_BASE`, default `https://nyu.libcal.com/1.1`

The sponsor should provision read-only space/category access in LibCal Admin → API and identify the public Bobst categories appropriate to the intended students. Confirm their institution's v1.1 API route and response schema before enabling production. The adapter's schema is grounded in the publicly documented Springshare client example below; it has not been validated against NYU's authenticated instance.

### Prepared live flow

1. `POST /api/rooms/availability` receives only structured room type, date, start/end, and party size.
2. The server obtains an OAuth client-credentials token using `POST /1.1/oauth/token`. Credentials/tokens never go to the browser.
3. It reads `GET /1.1/space/category/{categoryId}?availability=YYYY-MM-DD&details=1` for the configured category.
4. Only rooms whose availability intervals cover the **entire** session are returned. Contiguous slots can be combined; gaps and partial overlaps are rejected. Unknown data shapes fail closed.
5. The student sees real provider-returned rooms inside the chat and selects one.
6. `POST /api/rooms/checkout` rechecks availability. A stale selection returns a conflict and no checkout action.
7. For a still-available room, the site shows a **Continue with NYU NetID** link to `https://nyu.libcal.com/space/{roomId}`. Only the student decides to leave for official checkout.

The site never asks for an NYU password, treats an `@nyu.edu` email address as proof of identity, posts a reservation under a service account, or marks a room booked/held. Identity, final eligibility, one-reservation-per-day policy, and the actual booking remain with NYU. The canonical room link does not guarantee prefilling the date/time; NYU may ask the student to select them again. A tighter handoff needs an NYU-approved checkout/session integration. Do not bypass NetID authentication or imitate NYU's login form.

Verified sources:

- https://nyu.libcal.com/reserve/bobst-individual-study
- https://nyu.libcal.com/reserve/bobst-group-study
- https://library.nyu.edu/spaces/bobst-group-study-rooms/
- https://github.com/BGSU-LITS/libcal (LibCal v1.1 OAuth, category availability, and item schema reference)

## Optional generative reply wording

The contextual helper works without an LLM key. For generative phrasing, configure a separate server secret `GEMINI_API_KEY` and optionally `GEMINI_MODEL` (default `gemini-2.5-flash-lite`), with that API enabled and permitted in the key's project. The existing Books-only key is not reused or assumed to authorize Gemini.

`GET /api/assistant/status` reports the configured mode. If enabled, the chat discloses Google Gemini processing. `POST /api/assistant/reply` receives short recent text and a source-grounded draft, not credentials or full book files. The model may reword greetings or service guidance; critical room states, book metadata, missing-detail questions, and checkout actions stay deterministic. API failure, empty output, or unsafe confirmation wording falls back to the original draft. A Gemini key has not been configured or live-tested in this deployment.

The endpoint has per-isolate rate limits and bounded input/output. Before a wider institutional launch, use the sponsor's approved provider, privacy terms, global quota/rate controls, accessibility checks, and reviewed knowledge base.

## Verification

Automated tests cover multi-turn parsing, morning/afternoon ambiguity, duration/party-size disambiguation, DST, privacy routing, exact-title suggestions, independent chat/page state, preserved full-search queries, in-chat room cards, full-interval availability, rechecking stale rooms, no-credentials states, and official checkout URLs. Room success data is isolated test-fixture data and is never shipped as live availability. Neither actual NYU authenticated availability nor a booking has been claimed as verified.
