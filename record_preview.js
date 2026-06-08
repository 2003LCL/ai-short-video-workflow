let chromium;
try {
  chromium = require('playwright').chromium;
} catch (err) {
  const bundled = 'C:/Users/LCL/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/.pnpm/playwright@1.60.0/node_modules/playwright';
  chromium = require(bundled).chromium;
}
const path = require('path');

async function main() {
  const root = __dirname;
  const outputDir = path.join(root, 'output');
  const htmlPath = path.join(outputDir, 'preview.html');
  const videoDir = path.join(outputDir, 'recording');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 360, height: 640 },
    recordVideo: {
      dir: videoDir,
      size: { width: 360, height: 640 },
    },
  });
  const page = await context.newPage();
  await page.goto('file:///' + htmlPath.replace(/\\/g, '/'));
  await page.waitForFunction(() => window.__VIDEO_DONE__ === true, null, { timeout: 70000 });
  const video = page.video();
  await page.close();
  const saved = await video.path();
  await context.close();
  await browser.close();
  console.log(saved);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
