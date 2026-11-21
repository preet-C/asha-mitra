# backend/app/brain/intents.py
# P5b — Intent router.
#
# WHY this file exists: extract_visit() returns an intent label (contract 4.7).
# This module maps that label to a brain action. P5a uses only the basics
# (medical_advice → refuse, notes → normal flow). P5b fills in the rest.
#
# In P5a, dialogue.py handles intent inline. This file is a placeholder
# for the full router that P5b will build here.

# Intent labels defined in contract 4.7.
# dialogue.py imports these for reference.
INTENT_NOTES = "notes"
INTENT_CONFIRM = "confirm"
INTENT_DENY_OR_CORRECT = "deny_or_correct"
INTENT_REPEAT = "repeat"
INTENT_SLOWER = "slower"
INTENT_SKIP_FIELD = "skip_field"
INTENT_LATER = "later"
INTENT_START_OVER = "start_over"
INTENT_SWITCH_LANGUAGE = "switch_language"
INTENT_MEDICAL_ADVICE = "medical_advice"
INTENT_WHO_ARE_YOU = "who_are_you"
INTENT_WHAT_CAN_YOU_DO = "what_can_you_do"
INTENT_HOW_TO_USE = "how_to_use"
INTENT_OFF_TOPIC = "off_topic"

# P5b TODO: implement route(intent, session, draft) → list[dict] | None
# Returns None if the intent is not handled here (falls through to normal flow).
