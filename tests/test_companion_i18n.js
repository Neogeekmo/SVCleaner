"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const root = path.join(__dirname, "..");
const source = fs.readFileSync(path.join(root, "companion/web/app.js"), "utf8");
const catalogs = JSON.parse(
  fs.readFileSync(path.join(root, "companion/web/locales.json"), "utf8"),
);
const node = { dataset: { i18n: "Sauvegardes" }, textContent: "" };
const label = {
  getAttribute: () => "Langue",
  setAttribute: (name, value) => {
    label[name] = value;
  },
};
const document = {
  documentElement: {},
  querySelectorAll: (selector) =>
    selector === "[data-i18n]"
      ? [node]
      : selector === "[data-i18n-aria-label]"
        ? [label]
        : [],
};
const context = vm.createContext({ document, console });
vm.runInContext(
  fs.readFileSync(path.join(root, "companion/web/i18n.js"), "utf8") +
    "\nglobalThis.api = I18n;",
  context,
);
const api = context.api;
api.load(catalogs);
assert.deepEqual(Object.keys(api.names).sort(), Object.keys(catalogs).sort());
const keys = [
  ...source.matchAll(/\bt\(\s*("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/g),
].map((match) => vm.runInNewContext(match[1]));
for (const [language, catalog] of Object.entries(catalogs)) {
  api.select(language);
  api.apply();
  assert.equal(document.documentElement.lang, api.tags[language]);
  assert.equal(node.textContent, catalog.Sauvegardes);
  assert.equal(label["aria-label"], catalog.Langue);
  for (const key of keys)
    assert.equal(typeof catalog[key], "string", `${language}: missing ${key}`);
  const input = "<img src=x onerror=alert(1)> Vue d’ensemble {count}";
  assert.ok(api.t("Copier vers {target}", { target: input }).includes(input));
}
for (const [value, expected] of Object.entries({
  "en-GB": "enUS",
  ptPT: "ptBR",
  "fr-CA": "frFR",
  "es-AR": "esMX",
  "zh-Hant": "zhTW",
  "zh-HK": "zhTW",
  "ko-KR": "koKR",
  unknown: "enUS",
}))
  assert.equal(api.normalize(value), expected);
api.select("deDE");
const dateFunctions = source.slice(
  source.indexOf("function bytes("),
  source.indexOf("function pathText("),
);
vm.runInContext(
  dateFunctions +
    "\nglobalThis.formatBytes = bytes; globalThis.formatDate = date;",
  context,
);
assert.match(context.formatBytes(1.5 * 1048576), /1,5 MiB/);
api.select("enUS");
assert.match(context.formatBytes(1.5 * 1048576), /1\.5 MiB/);
assert.equal(api.t("missing-key"), "missing-key");
console.log(
  `Browser i18n verified: ${Object.keys(catalogs).length} catalogs, ${keys.length} literal UI lookups, aliases, DOM text, accessibility and number formatting.`,
);
