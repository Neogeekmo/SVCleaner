"use strict";
const I18n = (() => {
  const names = {
    enUS: "English",
    frFR: "Français",
    deDE: "Deutsch",
    esES: "Español (España)",
    esMX: "Español (Latinoamérica)",
    itIT: "Italiano",
    ptBR: "Português (Brasil)",
    ruRU: "Русский",
    koKR: "한국어",
    zhCN: "简体中文",
    zhTW: "繁體中文",
  };
  const tags = {
    enUS: "en-US",
    frFR: "fr-FR",
    deDE: "de-DE",
    esES: "es-ES",
    esMX: "es-MX",
    itIT: "it-IT",
    ptBR: "pt-BR",
    ruRU: "ru-RU",
    koKR: "ko-KR",
    zhCN: "zh-CN",
    zhTW: "zh-TW",
  };
  let language = "enUS",
    catalogs = {};
  function normalize(value) {
    const code = String(value || "")
      .replace(/[-_]/g, "")
      .toLowerCase();
    if (code.startsWith("zhhant") || code === "zhhk" || code === "zhmo")
      return "zhTW";
    if (code.startsWith("es") && code !== "es" && code !== "eses")
      return "esMX";
    return (
      Object.keys(names).find((key) => key.toLowerCase() === code) ||
      {
        en: "enUS",
        fr: "frFR",
        de: "deDE",
        es: "esES",
        it: "itIT",
        pt: "ptBR",
        ru: "ruRU",
        ko: "koKR",
        zh: "zhCN",
      }[code.slice(0, 2)] ||
      "enUS"
    );
  }
  function translate(key, values = {}) {
    const template = catalogs[language]?.[key] ?? catalogs.enUS?.[key] ?? key;
    return template.replace(/\{(\w+)\}/g, (token, name) =>
      Object.hasOwn(values, name) ? String(values[name]) : token,
    );
  }
  function select(value) {
    language = normalize(value);
    document.documentElement.lang = tags[language];
  }
  function apply(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = translate(node.dataset.i18n);
    });
    for (const attribute of ["aria-label", "alt", "title", "placeholder"]) {
      root.querySelectorAll(`[data-i18n-${attribute}]`).forEach((node) => {
        node.setAttribute(
          attribute,
          translate(node.getAttribute(`data-i18n-${attribute}`)),
        );
      });
    }
  }
  return {
    names,
    tags,
    normalize,
    select,
    apply,
    t: translate,
    load: (data) => {
      catalogs = data;
    },
    get language() {
      return language;
    },
    get tag() {
      return tags[language];
    },
  };
})();
const t = (key, values) => I18n.t(key, values);
