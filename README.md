# Unlogged Texts

A phone-friendly page for sending trainers their **unlogged session** texts for the exception logs.
Pick **GRIP** or **Elevate**, choose the **pay period**, and each trainer's text is ready to go:
**Text** opens Messages with the trainer's cell number and the text filled in, and **Copy** puts the text
on the clipboard. Each text is editable before you send it, and **Sent** checks off who's done
(remembered on that phone, per pay period). For a trainer with no number on file, tap **add number**
to save one on that phone; **Messages** then opens without a recipient until you do. Notes from the doc's headings (like "SHOW" or "STOPPED HERE")
show as tags, and the doc's "Needs a look" list is at the bottom.

## Where the texts come from

The deploy reads the Google Docs named `<GRIP|Elevate> Unlogged Sessions <pay period>`
(for example "GRIP Unlogged Sessions Nov 1-15") from the **USAPT Data / Unlogged Sessions** Drive folder,
plus any doc listed in `scripts/extra_docs.txt`. It uses their public "Anyone with the link" views, so no
credentials are needed, and a doc that isn't shared that way is skipped (the page says which).
A new pay period shows up on its own once its doc is in the folder: the site rebuilds every 3 hours,
or run the workflow by hand to update right away.

The docs need the same layout as now: a `Trainer Name (Club), N sessions` heading, then the message from
`Hi …` through `Did … Thank you!`, with one session per line in between. Anything after the heading's
` - ` becomes a tag.

Trainer numbers come from the ClubReady staff lists (`stafflist_<date><Brand>.xls`) in the
**USAPT Data / Staff List** folder: the newest list for the brand first, with older lists filling gaps.
A trainer is matched by full name (or first + last name), preferring current staff at the doc's club; if
two different people match equally, no number is used rather than a guess. Upload a new staff list to
the folder to pick up new numbers.

## Files

| File | What it is |
| --- | --- |
| `index.html`, `style.css`, `app.js` | The page |
| `scripts/build_unlogged.py` | Builds `unlogged.json` from the docs and the staff lists |
| `scripts/extra_docs.txt` | Docs outside the Unlogged Sessions folder to include |
| `.github/workflows/deploy.yml` | Builds and publishes to GitHub Pages on each push to `main`, every 3 hours and on demand |

## Privacy

`unlogged.json` (trainer names, clubs and cell numbers, client names and session times) is never committed; it is only part
of the Pages deploy. But **anyone with the site's link can read it**. The page and `robots.txt` ask search
engines not to index it.

## Setup

1. **Pages:** Settings → Pages → Source: **GitHub Actions**. (Pages on a private repo needs a paid GitHub
   plan; otherwise make the repo public. Only code is in it, no client data.)
2. **Deploy:** Actions → Deploy Unlogged Texts → Run workflow.
3. **Docs:** make sure each doc is in the Unlogged Sessions folder, or is listed in `scripts/extra_docs.txt`
   and shared "Anyone with the link can view".
