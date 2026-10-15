# Organic CO₂ Electrosynthesis Literature Radar

This version is tuned for **organic CO₂ electrosynthesis**, with extra weight on **electrochemical analysis, reaction mechanism and condition optimization**. Catalyst/material design is strongly down-ranked or rejected.

## Daily behavior

- Runs every day at **08:00 Europe/Berlin** via GitHub Actions.
- Targets **10 previously unseen relevant papers** per run.
- Papers from the prior run are automatically marked `archive: true` and shown in **历史记录**.
- DOI/title keys from all historical papers are used for de-duplication, so a pushed paper is not pushed again.
- If fewer than ten sufficiently relevant unseen papers can be found, the script deliberately returns fewer rather than padding the digest with catalyst-design/off-topic papers.
- When recent papers are insufficient, it rotates through older literature pages to provide useful *new-to-you* papers without repeats.

## Research priority

1. Organic CO₂ electrosynthesis / electrocarboxylation / CO₂ incorporation.
2. Electroanalysis and mechanism: CV, kinetics, radical/intermediate evidence, spectroscopy, DFT as mechanistic support.
3. Condition optimization: solvent, supporting electrolyte, potential/current, CO₂ pressure, concentration and cell configuration.

Typical catalyst-design terms such as `nanoparticle`, `single atom`, `heterostructure`, `active site`, `doped`, and `alloy catalyst` receive strong penalties unless the paper also contains substantial organic-synthesis/mechanistic/optimization content.

## Important upgrade instruction

If this is replacing your existing radar, **keep your existing `data/papers.json`**. Do not overwrite it with an empty file. The first run of the new script will automatically move all previously pushed items into history and use them as the de-duplication set.

Replace these files/directories:

- `.github/workflows/update.yml`
- `scripts/update_papers.py`
- `data/keywords.json`
- `data/journal_metrics.json`
- `index.html`
- `app.js`
- `styles.css`
- `requirements.txt`

Then set `Settings → Pages → Source = GitHub Actions` and manually run the workflow once.

## Impact factor display

Journal IF values come from the manually maintained `data/journal_metrics.json` snapshot. ISSN matching is preferred; journal-name aliases are the fallback. Unknown journals display `IF —` instead of a guessed value. Update the JSON when a new JIF/JCR release becomes available.

## Keyword editing

The web page can add/delete keywords locally and export a new `keywords.json`. Because GitHub Pages is static, replace `data/keywords.json` in the repository with the exported file if you want the next 08:00 search to use those edits.
