# Language guidelines

## Language rules
- US English
- One sentence per line
- Sentence case for titles and headings
- Active tense
- Gender-neutral terms unless referring to a named example person whose gender is clear (e.g. "Ann picked up her parcel" is fine; "the driver picked up their parcel" for generic references)
- Contractions are recommended but not required (don't vs do not)
- No ampersands, write "Pick-up and Delivery Routing model" not "Pick-up & Delivery Routing model"
- Don't use em dashes (—). Instead, split into separate sentences or use a comma.
- Avoid slang, colloquialisms, overly formal or academic language
- Spell out numbers one through ten; use numerals for 11+
- Write ordinals in full for numbers up to ten: "first" not "1st", "second" not "2nd", etc.
- Numbers at the beginning of sentences are always spelled out
- For times, use the 24-hour clock: 18:00, not 6 PM
- Use the serial comma for lists of three or more items: "item a, item b, and item c" not "item a, item b and item c"
- Infeasible (not unfeasible), time zone (not timezone), pick-up (hyphenated)
- Capitalize model names when referring to the model, not the concept
  e.g. "The Field Service Routing model is used for field service routing."
- "Via" only for actual routes/paths (e.g. "travel via Brussels"); use "with"/"through"/"using" otherwise.

## Terminology
- "Dataset" not "run". A dataset is the central concept, and "solving" is an operation on a dataset. "Running" can be used as a verb, e.g. "running the solver", but don't use "run" as a noun to refer to a dataset.
- "The model" (e.g. "the Field Service Routing model"), not "the solver", as the subject that optimizes, plans, or schedules. Reserve "solver" for the Timefold Solver library itself.
- "Log in" not "Sign in"
- "Invite" not "invitation"
- "Add" not "Create", nor "New" for button labels that add a new item
- "Manage tenant" for tenant admin settings
- "Admin" reserved for global admins
- Don't use "account" to mean an individual user's login or profile (account can mean multiple things). Instead: use "user" for the person, "register" / "registration" for the sign-up process, and "user account" for personal settings (e.g. "My user account", not "My Account").