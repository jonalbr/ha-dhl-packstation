import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import vm from "node:vm";

const source = readFileSync(
  new URL(
    "../../custom_components/dhl_packstation_monitor/www/dhl-packstation-card.js",
    import.meta.url,
  ),
  "utf8",
);
const entity = "binary_sensor.station_407_problem";
const second = "binary_sensor.station_408_problem";

class Element extends EventTarget {
  constructor() {
    super();
    this.children = [];
    this.style = {};
  }
  attachShadow() {
    this.shadowRoot = new Element();
  }
  append(...children) {
    this.children.push(...children);
  }
  replaceChildren(...children) {
    this.children = children;
  }
}

function fixture({ deferred = false, reject = false, language = "en" } = {}) {
  const elements = new Map();
  const tiles = [];
  const window = { customCards: [] };
  const helpers = {
    createCardElement(config) {
      const tile = new Element();
      tile.setConfig = (value) => {
        tile.config = value;
      };
      tile.setConfig(config);
      tiles.push(tile);
      return tile;
    },
  };
  let resolve;
  window.loadCardHelpers = () =>
    reject
      ? Promise.reject(new Error("unavailable"))
      : deferred
        ? new Promise((done) => {
            resolve = () => done(helpers);
          })
        : Promise.resolve(helpers);
  const customElements = {
    get: (name) => elements.get(name),
    define: (name, element) => elements.set(name, element),
  };
  const document = {
    createElement: (name) =>
      elements.has(name) ? new (elements.get(name))() : new Element(),
  };
  vm.runInNewContext(source, {
    HTMLElement: Element,
    CustomEvent,
    customElements,
    document,
    window,
  });
  const attributes = {
    station_id: "1-10117407",
    station_number: "407",
    compartment_summary: "S 3 · M 0 · L 2 · XL 1",
    compartment_total_summary: "Σ 6/12 · S 3 · M 0 · L 2 · XL 1",
    compartment_capacity_summary: "S 3/— · M 0/0 · L 2/3 · XL 1/5",
  };
  const hass = {
    language,
    states: {
      [entity]: { state: "off", attributes },
      [second]: {
        state: "on",
        attributes: {
          ...attributes,
          station_id: "1-10117408",
          station_number: "408",
          compartment_summary: "S — · M — · L — · XL —",
        },
      },
      "binary_sensor.unrelated": { state: "off", attributes: {} },
    },
  };
  return {
    Card: elements.get("dhl-packstation-card"),
    Editor: elements.get("dhl-packstation-card-editor"),
    hass,
    tiles,
    window,
    resolve: () => resolve(),
  };
}

const settle = () => new Promise((done) => setImmediate(done));
const plain = (value) => JSON.parse(JSON.stringify(value));

test("picker defaults and entity suggestions select only Packstations", () => {
  const { Card, hass, window } = fixture();
  assert.equal(
    Card.getStubConfig(hass, ["binary_sensor.unrelated"], [second]).entity,
    second,
  );
  assert.equal(Card.getStubConfig({ states: {} }).entity, "");
  const descriptor = window.customCards[0];
  assert.equal(descriptor.type, "dhl-packstation-card");
  assert.equal(
    descriptor.getEntitySuggestion(hass, "binary_sensor.unrelated"),
    null,
  );
  const suggestions = descriptor.getEntitySuggestion(hass, entity);
  assert.deepEqual(plain(suggestions.map((item) => item.config.display_mode)), [
    "free",
    "total",
    "capacities",
  ]);
});

test("one native Tile follows station, mode, and live diagnostic changes", async () => {
  const { Card, hass, tiles } = fixture();
  const card = new Card();
  card.setConfig({ entity });
  card.hass = hass;
  await settle();
  assert.equal(tiles[0].config.name, "Packstation 407");
  assert.equal(tiles[0].config.state_content, "compartment_summary");
  assert.deepEqual(plain(tiles[0].config.icon_tap_action), {
    action: "more-info",
  });
  card.setConfig({ entity, display_mode: "capacities" });
  await settle();
  assert.equal(tiles[0].config.state_content, "compartment_capacity_summary");
  assert.equal(
    tiles[0].hass.states[entity].attributes.compartment_capacity_summary,
    "S 3/— · M 0/0 · L 2/3 · XL 1/5",
  );
  card.setConfig({ entity: second, display_mode: "total" });
  await settle();
  assert.equal(tiles.length, 1);
  assert.equal(tiles[0].config.entity, second);
  assert.equal(tiles[0].config.state_content, "compartment_total_summary");
  assert.equal(
    tiles[0].hass.states[second].attributes.compartment_summary,
    "S — · M — · L — · XL —",
  );
});

test("device overrides and literal custom names reach the Tile without HTML interpolation", async () => {
  const { Card, hass, tiles } = fixture();
  hass.entities = { [entity]: { device_id: "station" } };
  hass.devices = { station: { name: "Station", name_by_user: "Near home" } };
  const card = new Card();
  card.hass = hass;
  card.setConfig({ entity });
  await settle();
  assert.equal(tiles[0].config.name, "Near home");
  const name = '<img src=x onerror="alert(1)">';
  card.setConfig({ entity, name, icon: "mdi:mailbox" });
  await settle();
  assert.equal(tiles[0].config.name, name);
  assert.equal(tiles[0].config.icon, "mdi:mailbox");
  assert.equal(card._content.children.length, 1);
});

test("rapid configuration changes while helpers load use the latest station and mode", async () => {
  const { Card, hass, tiles, resolve } = fixture({ deferred: true });
  const card = new Card();
  card.setConfig({ entity });
  card.hass = hass;
  card.setConfig({ entity: second, display_mode: "capacities" });
  resolve();
  await settle();
  assert.equal(tiles.length, 1);
  assert.equal(tiles[0].config.entity, second);
  assert.equal(tiles[0].config.state_content, "compartment_capacity_summary");
});

test("missing, foreign, and invalid configurations give useful feedback", async () => {
  const { Card, hass, tiles } = fixture({ language: "de" });
  const card = new Card();
  card.hass = hass;
  card.setConfig({});
  await settle();
  assert.match(card._content.children[0].textContent, /Füge.*Packstation/);
  assert.throws(
    () => card.setConfig({ entity: "sensor.other" }),
    /Problem-Entität/,
  );
  assert.throws(
    () => card.setConfig({ entity, display_mode: "unknown" }),
    /Darstellung/,
  );
  assert.throws(() => card.setConfig({ entity, name: {} }), /Text/);
  card.setConfig({ entity: "binary_sensor.unrelated" });
  await settle();
  assert.match(card._content.children[0].textContent, /Problem-Entität/);
  card.setConfig({ entity: "binary_sensor.removed_station" });
  await settle();
  assert.equal(tiles[0].config.entity, "binary_sensor.removed_station");
});

test("helper loading failures are displayed instead of leaving an empty card", async () => {
  const { Card, hass } = fixture({ reject: true });
  const card = new Card();
  card.setConfig({ entity });
  card.hass = hass;
  await settle();
  assert.match(card._content.children[0].textContent, /Reload the page/);
});

test("visual editor filters stations, translates modes, and saves clearing optional fields", () => {
  const { Editor, hass } = fixture({ language: "de-DE" });
  const editor = new Editor();
  editor.setConfig({
    type: "custom:dhl-packstation-card",
    entity,
    name: "Old name",
  });
  editor.hass = hass;
  const form = editor.shadowRoot.children[0];
  assert.equal(form.computeLabel({ name: "display_mode" }), "Darstellung");
  assert.equal(
    form.schema[0].selector.entity.filter[0].integration,
    "dhl_packstation_monitor",
  );
  assert.match(
    form.schema[1].selector.select.options[2].label,
    /manuelle Gesamtzahlen/,
  );
  assert.match(
    form.computeHelper({ name: "display_mode" }),
    /Leer bedeutet unbekannt; 0/,
  );
  let saved;
  editor.addEventListener("config-changed", (event) => {
    saved = event.detail.config;
  });
  form.dispatchEvent(
    new CustomEvent("value-changed", {
      detail: {
        value: {
          entity: second,
          display_mode: "capacities",
          name: "",
          icon: "",
        },
      },
    }),
  );
  assert.deepEqual(plain(saved), {
    type: "custom:dhl-packstation-card",
    entity: second,
    display_mode: "capacities",
  });
  assert.equal(editor.shadowRoot.children.length, 1);
});
