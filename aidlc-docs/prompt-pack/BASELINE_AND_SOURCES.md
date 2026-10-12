# Baseline, evidence, and limits of this pack

**Prepared:** 5 October 2026. **Inspected remote main:** `57c1efc77e67f691708bb9a825c621953fcea358`.

The repository was read through the connected GitHub tool. The local checkout was inspected read-only through lnwjud and had uncommitted changes in testing/dev tooling. Neither checkout was edited, committed, reset, or deployed to create this pack. Do not overwrite that local work.

Inspected code confirms an existing three-class patch-review contract, append-only human-review representation, model-card limitations, project-wrapper enterprise routes, and a capability-detected WSI reader. These are existing components to extend. This inspection is not a full current runtime/security audit, and no historical passing test count has been treated as a fresh pass.

The known dataset has been described by project evidence as 1,144 local patches and a 50-image public subset. Task code must read the actual authorized scope rather than hardcode those counts. The project’s case/slide-group identifiers have not established patient identities. Model evaluation and original runtime inference are distinct evidence streams; recovered attribution weights must remain separately identified.

The earlier roadmap’s example percentages, confusion matrices, case names, and productivity values were illustrative. They are not valid production facts. This pack replaces those with explicit interfaces, test-only arithmetic fixtures, and evidence gates. Human review agreement is not validation accuracy, and sparse patch counts are not whole-slide tissue composition.

The prior AWS session failed with an expired temporary token. Its current status was not re-tested for this planning request. Z010 must check credentials and destination when deployment is actually authorized; it must not assume the public app has the new backend or UI.

## Primary implementation references

- [Inspected repository snapshot](https://github.com/Enksodsoon/osteopatch-review/tree/57c1efc77e67f691708bb9a825c621953fcea358)
- [Existing API types](https://github.com/Enksodsoon/osteopatch-review/blob/57c1efc77e67f691708bb9a825c621953fcea358/app/g6/frontend/src/types.ts)
- [Existing review and export queries](https://github.com/Enksodsoon/osteopatch-review/blob/57c1efc77e67f691708bb9a825c621953fcea358/app/g6/backend/osteopatch/queries.py)
- [Existing limitations catalog](https://github.com/Enksodsoon/osteopatch-review/blob/57c1efc77e67f691708bb9a825c621953fcea358/app/g6/backend/osteopatch/limitations.py)
- [Existing enterprise authentication and routes](https://github.com/Enksodsoon/osteopatch-review/blob/57c1efc77e67f691708bb9a825c621953fcea358/app/g7-enterprise/backend/enterprise/app.py)
- [Existing capability-detected WSI reader](https://github.com/Enksodsoon/osteopatch-review/blob/57c1efc77e67f691708bb9a825c621953fcea358/app/g6/backend/osteopatch/pathology/reader.py)
- [React: effects, cleanup, and request races](https://react.dev/reference/react/useEffect)
- [FastAPI: request-scoped database sessions](https://fastapi.tiangolo.com/tutorial/sql-databases/)
- [OpenSlide Python: regions, levels, physical metadata](https://openslide.org/api/python/)
- [OpenSeadragon: viewer and tile sources](https://openseadragon.github.io/)
- [scikit-learn: probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [scikit-learn: model evaluation metrics](https://scikit-learn.org/stable/modules/model_evaluation.html)
- [OWASP: file upload security](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [Playwright: testing user-visible behavior](https://playwright.dev/docs/best-practices)
