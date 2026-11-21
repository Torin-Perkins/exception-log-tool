# Unlogged Texts

A phone-friendly page for sending trainers their **unlogged session** texts for the exception logs.
Pick **GRIP** or **Elevate**, choose the **pay period**, and each trainer's text is ready to go:
**Copy** puts it on the clipboard to paste into Messages, and **Messages** opens a new text with it filled
in (you pick the trainer). Each text is editable before you send it, and **Sent** checks off who's done
(remembered on that phone, per pay period). Notes from the doc's headings (like "SHOW" or "STOPPED HERE")
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

## Files

| File | What it is |
| --- | --- |
| `index.html`, `style.css`, `app.js` | The page |
| `scripts/build_unlogged.py` | Builds `unlogged.json` from the docs |
| `scripts/extra_docs.txt` | Docs outside the Unlogged Sessions folder to include |
| `.github/workflows/deploy.yml` | Builds and publishes to GitHub Pages on each push to `main`, every 3 hours and on demand |

## Privacy

`unlogged.json` (trainer names, clubs, client names and session times) is never committed; it is only part
of the Pages deploy. But **anyone with the site's link can read it**. The page and `robots.txt` ask search
engines not to index it.

## Setup

1. **Pages:** Settings → Pages → Source: **GitHub Actions**. (Pages on a private repo needs a paid GitHub
   plan; otherwise make the repo public. Only code is in it, no client data.)
2. **Deploy:** Actions → Deploy Unlogged Texts → Run workflow.
3. **Docs:** make sure each doc is in the Unlogged Sessions folder, or is listed in `scripts/extra_docs.txt`
   and shared "Anyone with the link can view".
