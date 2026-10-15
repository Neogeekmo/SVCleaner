const { JSDOM, VirtualConsole } = require("jsdom");
const { spawn } = require("node:child_process");
const fs = require("node:fs"),
  path = require("node:path"),
  assert = require("node:assert/strict");
const catalogs = JSON.parse(
  fs.readFileSync("companion/web/locales.json", "utf8"),
);
const temp = require("node:os").tmpdir();
const data = fs.mkdtempSync(path.join(temp, "svcleaner-browser-"));
const code =
  "import sys, tempfile; tempfile.tempdir=sys.argv[1]; from pathlib import Path; sys.path.insert(0, str(Path.cwd()/'companion')); from demo import demo_root; from service import Store; from app import create_server; server=create_server(Store(demo_root(),Path(sys.argv[1])/'data'/'demo')); print('http://127.0.0.1:'+str(server.server_port)+'/',flush=True); server.serve_forever()";
const child = spawn(
  process.env.SVC_TEST_PYTHON || "python",
  ["-u", "-c", code, data],
  { windowsHide: true },
);
const childClosed = new Promise((resolve) => child.once("close", resolve));
let output = "",
  errors = [];
child.on("error", (error) => errors.push(error.message));
child.stdout.on("data", (x) => (output += x));
child.stderr.on("data", (x) => errors.push(String(x)));
async function wait(fn) {
  const end = Date.now() + 15000;
  while (!(await fn())) {
    if (Date.now() > end) throw Error("timeout: " + output + " " + errors);
    await new Promise((r) => setTimeout(r, 25));
  }
}
async function browser(url) {
  const vc = new VirtualConsole();
  vc.on("jsdomError", (e) => {
    if (e.type !== "css-parsing") errors.push(e.message);
  });
  const dom = await JSDOM.fromURL(url, {
    resources: "usable",
    runScripts: "dangerously",
    pretendToBeVisual: true,
    virtualConsole: vc,
    beforeParse(w) {
      w.fetch = (u, opts) => fetch(new URL(u, w.location), opts);
      w.structuredClone = structuredClone;
      w.HTMLDialogElement.prototype.showModal = function () {
        this.open = true;
      };
      w.HTMLDialogElement.prototype.close = function () {
        this.open = false;
      };
    },
  });
  await wait(
    () =>
      dom.window.document.querySelector("#language")?.options.length === 11 &&
      dom.window.document.querySelector("#content .metrics"),
  );
  return dom;
}
(async () => {
  let dom;
  try {
    await wait(() => /http:\/\/127.0.0.1:\d+\//.test(output));
    const url = output.match(/http:\/\/127.0.0.1:\d+\//)[0];
    dom = await browser(url);
    const w = dom.window,
      d = w.document;
    const record = w.eval(
      "state.records.find(r=>r.addon==='APR'&&r.scope==='account').id",
    );
    for (const language of Object.keys(catalogs)) {
      const select = d.querySelector("#language");
      select.value = language;
      select.dispatchEvent(new w.Event("change"));
      await wait(
        () => w.eval("!busy") && d.documentElement.lang === w.eval("I18n.tag"),
      );
      assert.equal(d.querySelector("#language").value, language);
      assert.equal(
        d.querySelector('[data-i18n="Langue"]').textContent,
        catalogs[language].Langue,
      );
      for (const page of [
        "overview",
        "files",
        "orphans",
        "characters",
        "diff",
        "cache",
        "history",
      ]) {
        d.querySelector(`nav button[data-page="${page}"]`).click();
        await wait(() => w.eval("!busy") && d.body.dataset.page === page);
        assert.equal(
          d.querySelectorAll(".error-box").length,
          0,
          language + " " + page + " " + d.body.textContent,
        );
      }
      await w.eval(`openFile(${JSON.stringify(record)})`);
      assert.ok(d.querySelector("#tree table"), language + " tree");
      console.log(language + " — all 7 pages and data explorer rendered");
    }
    await w.eval(
      `post('stage',{id:${JSON.stringify(record)},operation:'delete-file'}).then(update)`,
    );
    const select = d.querySelector("#language");
    select.value = "deDE";
    select.dispatchEvent(new w.Event("change"));
    await wait(() => w.eval("!busy") && w.eval("I18n.language") === "deDE");
    assert.equal(w.eval("state.pending.length"), 1);
    assert.equal(
      w.eval("state.pending[0].summary"),
      catalogs.deDE["Mettre le fichier en quarantaine"],
    );
    assert.equal(w.eval('state.records.some(r=>r.addon==="APR")'), true);
    dom.window.close();
    dom = await browser(url);
    assert.equal(dom.window.document.querySelector("#language").value, "deDE");
    assert.equal(dom.window.eval("state.pending.length"), 1);
    assert.deepEqual(errors, []);
    console.log(
      "Language persists after reload; pending basket survives. No script errors.",
    );
  } finally {
    dom?.window.close();
    child.kill();
    await childClosed;
    assert.equal(fs.realpathSync(path.dirname(data)), fs.realpathSync(temp));
    assert.ok(path.basename(data).startsWith("svcleaner-browser-"));
    fs.rmSync(data, {
      recursive: true,
      force: true,
      maxRetries: 3,
      retryDelay: 100,
    });
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
