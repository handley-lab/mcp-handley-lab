# Web: Domain Axioms

The website is another medium the one voice runs into, not a separate register. The site at `phujck.github.io` carries the same mark as the paper, the figure, and the canon - composed, austere, nothing decorative. A page is load-bearing or it is gone. See [Voice and Style](canon://aesthetics/voice_and_style.md): the discipline is to render the whole voice into the medium and push the medium's ceiling, not to admit only the web-safe fraction.

This domain is in scaffold state. The structure is laid here so work can start at the low level and the skills can be forged on first real use rather than invented empty.

## What the medium is

- A Jekyll static site built to GitHub Pages. Source is Markdown and HTML with front matter, layouts, and includes. The build is `bundle exec jekyll build`, the deploy is a push to the Pages branch.
- The site is already sectioned: physics, synthetics, writing, talks, music, visualisations, essays, and a `viz/` interactive surface. New material joins an existing section, it does not invent a new top level without reason.
- Deterministic helpers already live in the repo - `check_html.py`, `check_img.py`, `crop_images.py`, `fix_css.py`, `update_mccaul.py`, and the `update.ps1` sync chain. These are the seed backings for the refine third, not throwaway scripts.

## The tripartite shape (generate - stage - refine)

The engine's three activities map onto web work directly. Skills are named here as slots. A slot with no skill yet is a forge target, not a gap to apologise for.

- **generate** - produce the raw web material from source. Turn a result, a figure, a manuscript section, or an idea into page or post content in the site voice. No skill forged yet. First candidate: a `web_page_generator` that drafts a section page from a manuscript or result ledger.
- **stage** - assemble the material into the Jekyll structure: layout, front matter, includes, cross-links, asset sync. The existing web skills sit here and are currently deprecated for non-use, to be revived with real backings when the work resumes: [css_forge](canon://skills/css_forge), [html_mechanic](canon://skills/html_mechanic), [web_deployment_mechanic](canon://skills/web_deployment_mechanic).
- **refine** - lint and verify the rendered site: valid HTML, present and cropped images, voice on the prose, no broken internal links, a clean Jekyll build before deploy. The repo's `check_html.py` / `check_img.py` / `fix_css.py` are the deterministic backings to wrap as an evaluating skill (a `web_ledger`).

## Rules

- **The voice is not partitioned by medium.** Prose on the site reads in the same voice as the paper. British English, the Vonnegut rule, no slop. The verifier's voice check applies to site Markdown and HTML prose, not just LaTeX.
- **Derive the page, do not pad it.** Cut every sentence that is decoration rather than content. A page earns its place the way a result does.
- **Reuse the artifact.** A figure made for a manuscript is reused on the site, not redrawn. Talks, manuscripts, and the site share assets - see [Talks](canon://domains/talks/axioms.md) and the asset sync chain.
- **Verify before deploy.** A push to Pages is outward-facing and hard to unsay. Build clean and lint clean first.
