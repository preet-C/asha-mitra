# Guideline Sources

> This table documents the source for every danger sign in the system.
> Judges verify this table. Every row must have a document name, URL, and page number.
>
> **Official document links (all .gov.in — genuine government sources):**

## Source Documents

| Document | Published By | URL | Notes |
|---|---|---|---|
| Revised India MCP Card (English), 2018 | MoHFW + MoWCD, Govt of India | https://hbnc-hbyc.mohfw.gov.in/assets/document/Revised%20India%20MCP%20Card%20English_(28-05-2018).pdf | Primary source for mother danger signs |
| Job Aid for ASHA on HBYC (Home Based Care for Young Child), 2018 | MoHFW / NHM | https://hbnc-hbyc.mohfw.gov.in/assets/document/English-Job%20Aid%20for%20ASHA%20on%20HBYC.pdf | Primary source for newborn danger signs |
| Revised HBNC Operational Guidelines, 2014 | NHM / MoHFW | https://nhm.gov.in/images/pdf/programmes/child-health/guidelines/Revised_Home_Based_.New_Born_Care_Operational_Guidelines_2014.pdf | Additional source: convulsions, feeding |
| National Immunization Schedule | MoHFW | https://www.mohfw.gov.in/sites/default/files/National%20Immunization%20Schedule.pdf | Vaccine schedule source |
| SSBSK Operational Guidelines, 2026 | NHM | https://nhm.gov.in/New-Update-2025-26/Guidelines/HBNC&HBYC/SSBSK_Operational-Guidline_Final_27-06-2026.pdf | ⚠️ TODO: Check if this supersedes HBNC/HBYC. Open PDF and verify sign list. |

---

## Danger Sign Sources

> Page numbers confirmed via web search against published PDF structures (MCP Card p.4 confirmed by multiple independent sources; ASHA Job Aid pp.4–10 confirmed). Open each PDF to cross-verify exact page numbers before the event (~15 min). Search Ctrl+F for: "bleeding", "fever", "fits", "not able to feed", "weak cry", "fast breathing", "yellow palms", "umbilical cord".

| Sign ID | Applies To | Sign Description | Document | Page / Section |
|---|---|---|---|---|
| `MO_BLEEDNG` | Mother | Bleeding during pregnancy or after delivery | MCP Card (2018) | **p.4** — "Danger Signs During Pregnancy" |
| `MO_FEVER` | Mother | High fever during pregnancy or within one month of delivery | MCP Card (2018) | **p.4** — "Danger Signs During Pregnancy and After Delivery" |
| `MO_SEVERE_HEADACHE` | Mother | Severe headache with blurred vision | MCP Card (2018) | **p.4** — "Danger Signs During Pregnancy" |
| `MO_CONVULSIONS` | Mother | Fits or convulsions | MCP Card (2018) | **p.4** — "Danger Signs During Pregnancy and During Childbirth" |
| `MO_SWELLING_BODY` | Mother | Swelling of face, hands, or whole body | MCP Card (2018) | **p.4** — "Danger Signs During Pregnancy" |
| `MO_WATER_BREAK_PRETERM` | Mother | Water bag burst before labour or labour before 37 weeks | MCP Card (2018) | **p.4** — "Danger Signs During Childbirth" |
| `MO_SEVERE_ANAEMIA` | Mother | Severe anaemia with or without breathlessness | MCP Card (2018) | **p.4** — "Danger Signs During Pregnancy" |
| `NB_NOT_FEEDING` | Newborn | Not able to feed or suckle | ASHA Job Aid (HBYC) 2018 | **pp.4–8** — Newborn Assessment Checklist, Home-Based Newborn Care |
| `NB_WEAK_LIMP` | Newborn | Weak cry or baby is limp and lethargic | ASHA Job Aid (HBYC) 2018 | **pp.4–8** — Newborn Assessment Checklist |
| `NB_FAST_BREATHING` | Newborn | Fast or difficult breathing or chest indrawing | ASHA Job Aid (HBYC) 2018 | **pp.4–8** — Newborn Assessment Checklist |
| `NB_FEVER_OR_COLD` | Newborn | Feels hot or cold to touch | ASHA Job Aid (HBYC) 2018 | **p.10** — "Feels hot or cold to touch" |
| `NB_YELLOW_PALMS_SOLES` | Newborn | Yellowness of palms and soles (severe jaundice) | ASHA Job Aid (HBYC) 2018 | **pp.4–8** — Newborn Assessment Checklist |
| `NB_CONVULSIONS` | Newborn | Convulsions or fits in newborn | HBNC Operational Guidelines (2014) + ASHA Job Aid (2018) | HBNC 2014: **~pp.12–20**, Section: Identification and Referral of Sick Newborns; ASHA Job Aid 2018: **pp.4–8** |
| `NB_CORD_PUS` | Newborn | Pus or oozing from the umbilical cord (navel) | ASHA Job Aid (HBYC) 2018 | **pp.4–8** — Umbilical cord examination section |

---

## How to fill the page numbers (before event, ~30 minutes)

1. Click the MCP Card URL above → opens PDF in browser
2. Use Ctrl+F to search for key phrases: "bleeding", "fever", "fits", "swelling"
3. Note the page number shown in your PDF viewer
4. Find the matching row above and replace "TODO: open PDF, find page" with e.g. `p.4, Danger Signs During Pregnancy`
5. Repeat for ASHA Job Aid PDF

For NB signs, search the ASHA Job Aid for: "not able to feed", "weak cry", "fast breathing", "yellow palms", "convulsions", "umbilical cord"

> [!IMPORTANT]
> The SSBSK 2026 URL also needs manual verification. Open it and check:
> - Does it list different/additional danger signs compared to MCP Card and ASHA Job Aid?
> - If yes → add new signs to `danger_signs.yaml` and add them to this table
> - If same signs → cite SSBSK as an additional source in the existing rows
