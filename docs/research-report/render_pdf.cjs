const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { chromium } = require("playwright");

async function main() {
  const dir = __dirname;
  const htmlPath = path.join(dir, "index.html");
  const pdfPath = path.join(dir, "OsteoPatch_Full_Research_Report.pdf");
  const previewPath = path.join(dir, "report-preview.png");
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1050 }, deviceScaleFactor: 1 });
    await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    const images = await page.locator("img").evaluateAll((nodes) =>
      nodes.map((img) => ({ src: img.getAttribute("src"), loaded: img.complete && img.naturalWidth > 0 })),
    );
    const broken = images.filter((img) => !img.loaded);
    if (broken.length) throw new Error("Broken report images: " + JSON.stringify(broken));
    await page.screenshot({ path: previewPath, fullPage: false });
    await page.pdf({
      path: pdfPath,
      format: "Letter",
      printBackground: true,
      preferCSSPageSize: true,
      displayHeaderFooter: true,
      headerTemplate: '<div style="font:8px Arial;color:#637277;width:100%;padding:0 0.72in;">OSTEOPATCH / FULL RESEARCH REPORT</div>',
      footerTemplate: '<div style="font:8px Arial;color:#637277;width:100%;padding:0 0.72in;text-align:right;">Evidence snapshot · 8 Oct 2026 · <span class="pageNumber"></span></div>',
      margin: { top: "0.7in", right: "0.72in", bottom: "0.75in", left: "0.72in" },
    });
    console.log("Printed " + images.length + " figures to " + pdfPath);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
