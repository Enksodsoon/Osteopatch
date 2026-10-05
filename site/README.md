# Public project website

This is a small static documentation/product site, not the reviewer application. It uses Python's standard library and reuses the three approved product screenshots in `docs/images/`.

`layout.html` supplies shared navigation, metadata, security policy and footer. `pages/` contains six explicit pages. `styles.css` supplies responsive typography/layout and keyboard/reduced-motion support. The builder reads project version and selected frozen evaluation metrics; it never copies the runtime or arbitrary repository content.

```sh
python -m unittest discover -s tests/tooling -v
python scripts/build_site.py
python scripts/check_site.py
python -m http.server 8765 --bind 127.0.0.1 --directory _site
```

The output allowlist is defined in `scripts/build_site.py`. Generated `_site/` is ignored. Changes to the allowlist require tests and a publication/privacy review. Internal links are relative so project Pages works without a custom domain.

The site has no trackers, webfonts, JavaScript dependencies, forms or embedded live app. Screenshots are explicitly labeled as screenshots. Software/model status and the separate AWS demo remain qualified.
