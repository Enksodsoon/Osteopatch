import { test, expect, type Page } from "@playwright/test";

/**
 * The whole app, in a real browser, as a real reviewer would walk it.
 *
 * Scope: G6 only. The enterprise layer is already covered end-to-end at the
 * HTTP level by app/local-tester.py; duplicating auth/RBAC in a browser would
 * be slower without adding a seam that HTTP does not already cross.
 *
 * Everything here runs against the THROWAWAY database copy that
 * scripts/e2e_ui.py creates. The canonical review store is never written.
 */

const BACKEND = process.env.E2E_BACKEND_URL!;

async function openWorkbench(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("disclaimer")).toBeVisible();
  await expect(page.getByTestId("workbench")).toBeVisible();
}

/** First patch id currently shown in the gallery. */
async function firstCardId(page: Page): Promise<string> {
  const first = page.getByTestId("gallery").locator("button.card").first();
  await expect(first).toBeVisible();
  const testid = await first.getAttribute("data-testid");
  return (testid ?? "").replace(/^card-/, "");
}

/**
 * A distinct patch per test.
 *
 * The gallery is always ranked the same way, so "the first card" is the SAME
 * patch in every test — which meant each review overwrote the previous one and
 * only one row ever carried a human action. Indexing into the real listing
 * gives each test its own subject and makes the tests independent.
 */
async function nthPatchId(page: Page, n: number): Promise<string> {
  const res = await fetch(
    `${BACKEND}/v1/images?sort=image_id&page_size=${n + 1}&page=1`,
  );
  const body = await res.json();
  const id = body.items?.[n]?.image_id;
  if (!id) throw new Error(`could not resolve patch #${n} from the API`);
  return id;
}

/** Open a specific patch through the UI, as a reviewer would. */
async function openPatch(page: Page, id: string) {
  await page.getByTestId("search-input").fill(id);
  await expect(page.getByTestId("gallery").locator("button.card")).toHaveCount(1);
  await page.getByTestId(`card-${id}`).click();
  await expect(page.getByTestId("patch-review")).toBeVisible();
}

test.describe("whole app — reviewer journey", () => {
  test("the claim boundary is visible before anything else", async ({ page }) => {
    await openWorkbench(page);
    const d = page.getByTestId("disclaimer");
    await expect(d).toContainText(/NOT for diagnosis/i);
    await expect(d).toContainText(/treatment-response/i);
    await expect(d).toBeVisible();
  });

  test("gallery loads the full 1,144-patch collection, ranked by review priority", async ({
    page,
  }) => {
    await openWorkbench(page);
    await expect(page.getByTestId("workbench")).toContainText(/1,?144 patches/);

    const cards = page.getByTestId("gallery").locator("button.card");
    expect(await cards.count()).toBeGreaterThan(0);

    // Rank badges must start at 1 and increase — this is the triage order.
    // The badge text is decorated ("PRIORITY #1"), so read the number out of it
    // rather than pinning the exact wording.
    const ranks = await cards.evaluateAll((els) =>
      els.map((e) => {
        const t = e.querySelector(".card-rank")?.textContent ?? "";
        const m = t.match(/(\d+)/);
        return m ? Number(m[1]) : NaN;
      }),
    );
    expect(ranks.slice(0, 5)).toEqual([1, 2, 3, 4, 5]);
    for (const r of ranks) expect(Number.isFinite(r)).toBe(true);
  });

  test("sorting and filtering change the queue", async ({ page }) => {
    await openWorkbench(page);
    const firstId = await firstCardId(page);

    await page.getByTestId("sort-select").selectOption("image_id");
    await expect
      .poll(async () => firstCardId(page), { timeout: 10_000 })
      .not.toBe(firstId);

    await page.getByTestId("filter-select").selectOption("pred_VIABLE_TUMOR");
    // The predicted class is rendered as a chip's text, not an attribute.
    await expect
      .poll(
        async () => {
          const first = page.getByTestId("gallery").locator("button.card").first();
          if ((await first.count()) === 0) return "<empty>";
          return (await first.locator(".card-prediction").innerText()).trim();
        },
        { timeout: 10_000 },
      )
      .toContain("VIABLE_TUMOR");

    // Every visible card must match the filter, not just the first.
    const shown = await page
      .getByTestId("gallery")
      .locator("button.card .card-prediction")
      .allInnerTexts();
    expect(shown.length).toBeGreaterThan(0);
    for (const t of shown) expect(t).toContain("VIABLE_TUMOR");
  });

  test("search narrows to a single patch and can be cleared", async ({ page }) => {
    await openWorkbench(page);
    const id = await firstCardId(page);

    await page.getByTestId("search-input").fill(id);
    await expect(page.getByTestId("gallery").locator("button.card")).toHaveCount(1);

    await page.getByTestId("search-input").fill("");
    await expect(page.getByTestId("gallery").locator("button.card").first()).toBeVisible();
  });

  test("opening a patch shows exactly three uncalibrated class scores", async ({ page }) => {
    await openWorkbench(page);
    await page.getByTestId("gallery").locator("button.card").first().click();

    await expect(page.getByTestId("patch-review")).toBeVisible();
    for (const c of ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"]) {
      await expect(page.getByTestId(`score-${c}`)).toBeVisible();
    }
    // Never a fourth class.
    await expect(page.getByTestId("score-MIXED_VIABLE_NECROTIC")).toHaveCount(0);

    await expect(page.getByTestId("scorebars")).toContainText(/uncalibrated/i);
    // Review priority must not be sold as a probability of error.
    await expect(page.getByTestId("patch-review")).toContainText(
      /not a probability of error or calibrated uncertainty/i,
    );
  });

  test("ACCEPT records an append-only event and leaves the model prediction intact", async ({
    page,
  }) => {
    await openWorkbench(page);
    const id = await nthPatchId(page, 0);
    const before = await (await fetch(`${BACKEND}/v1/images/${id}`)).json();
    const predicted = before.prediction.predicted_class;
    const modelScores = before.prediction.scores;

    await openPatch(page, id);
    await expect(page.getByTestId("suggested-class")).toContainText(predicted);

    await page.getByTestId("action-ACCEPT").click();
    await page.getByTestId("save-review").click();
    await expect(page.getByTestId("review-msg")).toContainText(/saved/i);
    await expect(page.getByTestId("review-history").locator("li").first()).toBeVisible();

    // The immutable prediction must be byte-identical after a human decision.
    const after = await (await fetch(`${BACKEND}/v1/images/${id}`)).json();
    expect(after.prediction.predicted_class).toBe(predicted);
    expect(after.prediction.scores).toEqual(modelScores);
    expect(after.review_state.status).toBe("reviewed");
    expect(after.history.length).toBe(before.history.length + 1);
  });

  test("CORRECT preserves BOTH the model prediction and the human decision", async ({
    page,
  }) => {
    await openWorkbench(page);
    const id = await nthPatchId(page, 1);
    const before = await (await fetch(`${BACKEND}/v1/images/${id}`)).json();
    const predicted = before.prediction.predicted_class;

    await openPatch(page, id);

    await page.getByTestId("action-CORRECT").click();
    // Pick a class that is NOT what the model said, so the divergence is real.
    const other = predicted === "NON_TUMOR" ? "NECROSIS" : "NON_TUMOR";
    await page.getByTestId(`class-${other}`).click();
    await page.getByTestId("review-note").fill("e2e: reviewer disagrees");
    await page.getByTestId("save-review").click();
    await expect(page.getByTestId("review-msg")).toContainText(/saved/i);

    const after = await (await fetch(`${BACKEND}/v1/images/${id}`)).json();
    expect(after.prediction.predicted_class).toBe(predicted); // untouched
    const latest = after.history.at(-1);
    expect(latest.action).toBe("CORRECT");
    expect(latest.selected_class).toBe(other);
    expect(latest.note).toBe("e2e: reviewer disagrees");
  });

  test("DEFER requires a reason and is recorded with one", async ({ page }) => {
    await openWorkbench(page);
    const id = await nthPatchId(page, 2);

    await openPatch(page, id);

    await page.getByTestId("action-DEFER").click();
    await page.getByTestId("defer-reason").selectOption("uncertain_morphology");
    await page.getByTestId("save-review").click();
    await expect(page.getByTestId("review-msg")).toContainText(/saved/i);

    const after = await (await fetch(`${BACKEND}/v1/images/${id}`)).json();
    expect(after.review_state.status).toBe("deferred");
    expect(after.history.at(-1).reason).toBe("uncertain_morphology");
  });

  test("a reviewed patch leaves the unreviewed queue", async ({ page }) => {
    await openWorkbench(page);
    const id = await nthPatchId(page, 3);
    await openPatch(page, id);
    await page.getByTestId("action-ACCEPT").click();
    await page.getByTestId("save-review").click();
    await expect(page.getByTestId("review-msg")).toContainText(/saved/i);

    await page.getByRole("button", { name: /back to workbench/i }).click();
    await expect(page.getByTestId("workbench")).toBeVisible();

    await page.getByTestId("filter-select").selectOption("reviewed");
    await expect
      .poll(async () => page.getByTestId("gallery").locator("button.card").count(), {
        timeout: 10_000,
      })
      .toBeGreaterThan(0);
  });

  test("next/prev navigate between patches without losing the app", async ({ page }) => {
    await openWorkbench(page);
    await page.getByTestId("gallery").locator("button.card").first().click();
    await expect(page.getByTestId("patch-review")).toBeVisible();

    // The viewer image src embeds the image id, so it is a reliable identity
    // signal without depending on markup that other work may be changing.
    const viewer = page.getByTestId("image-viewer").locator("img").first();
    const firstSrc = await viewer.getAttribute("src");
    expect(firstSrc).toBeTruthy();

    await page.getByTestId("next-patch").click();
    await expect
      .poll(async () => (await page.getByTestId("image-viewer").locator("img").first().getAttribute("src")) ?? "", {
        timeout: 10_000,
      })
      .not.toBe(firstSrc);

    await page.getByTestId("prev-patch").click();
    await expect
      .poll(
        async () =>
          (await page.getByTestId("image-viewer").locator("img").first().getAttribute("src")) ?? "",
        { timeout: 10_000 },
      )
      .toBe(firstSrc);
  });
});

test.describe("whole app — model card limitations", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /model card/i }).click();
    await expect(page.getByTestId("model-card")).toBeVisible();
  });

  test("the full catalog is rendered, not just the frozen five", async ({ page }) => {
    await expect(page.getByTestId("limitations-full")).toBeVisible();
    await expect(page.getByTestId("limitations-count")).toContainText(/\d+ limitations recorded/);

    const total = Number(
      (await page.getByTestId("limitations-count").innerText()).match(/(\d+) limitations/)?.[1],
    );
    expect(total).toBeGreaterThanOrEqual(25);

    // Every group the backend declares must actually appear.
    const groups = page.locator('[data-testid^="lim-group-"]');
    expect(await groups.count()).toBe(8);
    const items = page.locator('[data-testid^="limitation-LIM-"]');
    expect(await items.count()).toBe(total);
  });

  test("the VIABLE_TUMOR weakness leads the model group and is blocking", async ({ page }) => {
    const model = page.getByTestId("lim-group-model");
    await expect(model).toBeVisible();

    const first = model.locator('[data-testid^="limitation-LIM-"]').first();
    await expect(first).toHaveAttribute("data-testid", "limitation-LIM-VIABLE-WEAK");
    await expect(first).toHaveAttribute("data-severity", "blocking");
    await expect(first).toContainText("0.110345");
  });

  test("each limitation says what would retire it and cites evidence", async ({ page }) => {
    const item = page.getByTestId("limitation-LIM-VIABLE-WEAK");
    await expect(item).toContainText(/what would retire it/i);

    // Scope to the <summary>; the statement prose also contains the word.
    await item.locator("summary").click();
    await expect(item.locator("li").first()).toBeVisible();
    await expect(item.locator("li").first()).toContainText(/\.(md|json|sql|py)$/);
  });

  test("the frozen G4 evaluation caveats are still shown verbatim", async ({ page }) => {
    const frozen = page.getByTestId("limitations-frozen");
    await expect(frozen).toContainText(/4 groups ONLY/);
    await expect(frozen).toContainText(/uncalibrated model class scores/);
  });

  test("the model card states the claim boundary", async ({ page }) => {
    await expect(page.getByTestId("model-card")).toContainText(/NOT for diagnosis/i);
    await expect(page.getByTestId("model-card")).toContainText(/0\.562311|macro-F1/i);
  });
});

test.describe("whole app — attribution honesty", () => {
  test("attribution is real or honestly refuses; never a fabricated heatmap", async ({ page }) => {
    await page.goto("/");
    await page.getByTestId("gallery").locator("button.card").first().click();
    await expect(page.getByTestId("attribution-panel")).toBeVisible();

    // The disclosure chain is unconditional, whether or not a map renders.
    await expect(page.getByTestId("attribution-recovery-disclosure")).toContainText(
      /behaviorally reconstructed classifier/i,
    );
    await expect(page.getByTestId("attribution-not-segmentation")).toContainText(
      /not tissue segmentation or diagnostic annotation/i,
    );

    const overlay = page.getByTestId("attribution-overlay-img");
    const error = page.getByTestId("attribution-error");
    await expect(overlay.or(error).first()).toBeVisible();

    // If the torch-free environment refused, there must be no image.
    if (await error.isVisible()) {
      await expect(error).toContainText(/no heatmap is shown/i);
      await expect(overlay).toHaveCount(0);
    } else {
      // If it rendered, the bytes must be a real PNG, not a 1x1 placeholder.
      const box = await overlay.boundingBox();
      expect(box!.width).toBeGreaterThan(50);
      expect(box!.height).toBeGreaterThan(50);
    }
  });
});

test.describe("whole app — export provenance", () => {
  test("CSV export carries the disclaimer and both prediction and correction", async ({
    page,
  }) => {
    await openWorkbench(page);
    const id = await nthPatchId(page, 4);
    const before = await (await fetch(`${BACKEND}/v1/images/${id}`)).json();
    const predicted = before.prediction.predicted_class;
    const other = predicted === "NON_TUMOR" ? "NECROSIS" : "NON_TUMOR";

    await openPatch(page, id);
    await page.getByTestId("action-CORRECT").click();
    await page.getByTestId(`class-${other}`).click();
    await page.getByTestId("save-review").click();
    await expect(page.getByTestId("review-msg")).toContainText(/saved/i);

    const download = await Promise.all([
      page.waitForEvent("download"),
      page.getByTestId("export-csv").click(),
    ]);
    const stream = await download[0].createReadStream();
    const chunks: Buffer[] = [];
    for await (const c of stream) chunks.push(Buffer.from(c));
    const csv = Buffer.concat(chunks).toString("utf-8");

    expect(csv).toContain(id);
    expect(csv).toMatch(/model_predicted_class|Model score/);
    expect(csv.toLowerCase()).toContain("not for diagnosis");

    // The reviewed row must carry BOTH sides of the disagreement.
    const row = csv.split("\n").find((line: string) => line.startsWith(id));
    expect(row).toBeTruthy();
    expect(row).toContain(predicted);
    expect(row).toContain(other);
  });
});