# Project: phujck.github.io

The personal academic site. Jekyll, deployed to GitHub Pages. This node tracks its state for the engine. It is a scaffold - fill it as the work resumes.

## Location

- Repo: `C:\Users\gerar\VScodeProjects\phujck.github.io`
- Build: `bundle exec jekyll build` (output in `_site/`)
- Deploy: push to the Pages branch. `CNAME` is set, so the live host is the custom domain.

## Structure

- Top-level section pages: `physics.html`, `synthetics.html`, `writing.html`, `talks.html`, `music.html`, `visualisations.html`, plus `essays/` and an interactive `viz/` surface.
- `assets/` holds shared media. Manuscript and talk figures are synced in rather than redrawn (`sync_dynamics_as_computation_assets.ps1`, `update.ps1`).
- Existing deterministic helpers: `check_html.py`, `check_img.py`, `crop_images.py`, `fix_css.py`, `update_mccaul.py`, `replace_nobom.ps1`. These are the refine-third backings to formalise.

## Active state

- Status: scaffold only. No web skill is live yet - the three stage-third skills ([css_forge](canon://skills/css_forge), [html_mechanic](canon://skills/html_mechanic), [web_deployment_mechanic](canon://skills/web_deployment_mechanic)) are deprecated and await revival with the repo's real scripts as backings.
- The `talks` section is the first natural integration point - see [talk_from_manuscript](canon://domains/talks/projects/talk_from_manuscript.md). A talk generated from a manuscript lands here.

## Next concrete step (when the work resumes)

- Decide the first real web task (most likely: publish a generated talk or a manuscript landing page).
- Wrap one repo helper (start with `check_html.py` or `check_img.py`) as the backing for a `web_ledger` evaluating skill, so the refine third has a deterministic check.
- Let the generate and stage skills forge from that first real use, not before.
