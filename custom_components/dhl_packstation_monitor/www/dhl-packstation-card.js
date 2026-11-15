/* Bundled, dependency-free card and visual editor. Rendering stays with HA's Tile. */
const CARD_TYPE = "dhl-packstation-card";
const DOMAIN = "dhl_packstation_monitor";
const MODES = {
  free: "compartment_summary",
  total: "compartment_total_summary",
  capacities: "compartment_capacity_summary",
};
const TEXT = {
  en: {
    entity: "Packstation",
    display_mode: "Display",
    name: "Name (optional)",
    icon: "Icon (optional)",
    free: "Free compartments",
    total: "Free compartments and DHL total capacity",
    capacities: "Free compartments and manual totals by size",
    choose: "Add a Packstation to the integration, then select it here.",
    entity_help: "Select the Packstation to display.",
    mode_help:
      "Manual totals are optional. Empty means unknown; 0 means no compartments of that size.",
    invalid_entity: "Select a Packstation's Problem entity.",
    invalid_mode: "Choose a supported display mode.",
    invalid_text: "Name and icon must be text.",
    load_failed: "The card could not be loaded. Reload the page to try again.",
    description:
      "Packstation availability with a station picker and three display modes.",
  },
  de: {
    entity: "Packstation",
    display_mode: "Darstellung",
    name: "Name (optional)",
    icon: "Symbol (optional)",
    free: "Freie Fächer",
    total: "Freie Fächer und Stationskapazität laut DHL",
    capacities: "Freie Fächer und manuelle Gesamtzahlen je Größe",
    choose:
      "Füge der Integration eine Packstation hinzu und wähle sie hier aus.",
    entity_help: "Wähle die Packstation für diese Karte aus.",
    mode_help:
      "Manuelle Gesamtzahlen sind optional. Leer bedeutet unbekannt; 0 bedeutet keine Fächer dieser Größe.",
    invalid_entity: "Wähle die Problem-Entität einer Packstation aus.",
    invalid_mode: "Wähle eine unterstützte Darstellung aus.",
    invalid_text: "Name und Symbol müssen Text sein.",
    load_failed:
      "Die Karte konnte nicht geladen werden. Lade die Seite neu, um es erneut zu versuchen.",
    description:
      "Freie Packstationsfächer mit Stationsauswahl und drei Darstellungen.",
  },
};

function words(hass) {
  return TEXT[
    (hass?.locale?.language ?? hass?.language ?? "en").startsWith("de")
      ? "de"
      : "en"
  ];
}

function isStation(hass, entityId) {
  const attributes = hass?.states?.[entityId]?.attributes;
  return (
    entityId.startsWith("binary_sensor.") &&
    typeof attributes?.station_id === "string" &&
    typeof attributes?.compartment_summary === "string"
  );
}

function normalizeConfig(config, text) {
  if (
    config.entity !== undefined &&
    (typeof config.entity !== "string" ||
      (config.entity !== "" && !config.entity.startsWith("binary_sensor.")))
  ) {
    throw new Error(text.invalid_entity);
  }
  const mode = config.display_mode ?? "free";
  if (!Object.hasOwn(MODES, mode)) throw new Error(text.invalid_mode);
  for (const field of ["name", "icon"]) {
    if (config[field] !== undefined && typeof config[field] !== "string") {
      throw new Error(text.invalid_text);
    }
  }
  return { ...config, display_mode: mode };
}

class DhlPackstationCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent =
      ":host{display:block;height:100%}hui-tile-card{height:100%}.message{display:block;padding:16px}";
    this._content = document.createElement("div");
    this._content.style.height = "100%";
    this.shadowRoot.append(style, this._content);
  }

  static getConfigElement() {
    return document.createElement(`${CARD_TYPE}-editor`);
  }

  static getStubConfig(hass, entities = [], entitiesFallback = []) {
    const candidates = [
      ...entities,
      ...entitiesFallback,
      ...Object.keys(hass?.states ?? {}),
    ];
    return {
      entity: candidates.find((id) => isStation(hass, id)) ?? "",
      display_mode: "free",
    };
  }

  setConfig(config) {
    this._config = normalizeConfig(config, words(this._hass));
    this._update();
  }

  set hass(hass) {
    this._hass = hass;
    this._update();
  }

  getCardSize() {
    return 1;
  }

  getGridOptions() {
    return { columns: 12, rows: 1, min_columns: 6, min_rows: 1 };
  }

  _message(text) {
    const message = document.createElement("ha-alert");
    message.className = "message";
    message.textContent = text;
    this._content.replaceChildren(message);
    this._card = undefined;
    this._tileConfig = undefined;
  }

  _update() {
    this._render().catch(() => this._message(words(this._hass).load_failed));
  }

  async _render() {
    if (!this._config || !this._hass) return;
    if (!this._config.entity) {
      this._message(words(this._hass).choose);
      return;
    }
    // One shared load; later renders always read the latest configuration and state.
    this._helpersPromise ??= window.loadCardHelpers();
    const helpers = await this._helpersPromise;
    const config = this._config;
    if (!config.entity) return;
    const state = this._hass.states[config.entity];
    if (state && !isStation(this._hass, config.entity)) {
      this._message(words(this._hass).invalid_entity);
      return;
    }
    const registry = this._hass.entities?.[config.entity];
    const device = this._hass.devices?.[registry?.device_id];
    const name =
      config.name ||
      device?.name_by_user ||
      device?.name ||
      (state?.attributes.station_number
        ? `Packstation ${state.attributes.station_number}`
        : undefined);
    const tileConfig = {
      type: "tile",
      entity: config.entity,
      state_content: MODES[config.display_mode],
      icon: config.icon || "mdi:package-variant-closed",
      color: "amber",
      tap_action: { action: "more-info" },
      icon_tap_action: { action: "more-info" },
      ...(name ? { name } : {}),
    };
    const serialized = JSON.stringify(tileConfig);
    if (!this._card) {
      this._card = helpers.createCardElement(tileConfig);
      this._content.replaceChildren(this._card);
    } else if (serialized !== this._tileConfig) {
      this._card.setConfig(tileConfig);
    }
    this._tileConfig = serialized;
    this._card.hass = this._hass;
  }
}

class DhlPackstationCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    this._config = normalizeConfig(config, words(this._hass));
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (event) => {
        event.stopPropagation();
        const config = {
          ...event.detail.value,
          type: this._config.type ?? `custom:${CARD_TYPE}`,
        };
        for (const field of ["name", "icon"]) {
          if (!config[field]) delete config[field];
        }
        this._config = config;
        this.dispatchEvent(
          new CustomEvent("config-changed", {
            detail: { config },
            bubbles: true,
            composed: true,
          }),
        );
      });
      this.shadowRoot.append(this._form);
    }
    const text = words(this._hass);
    if (this._text !== text) {
      this._text = text;
      this._form.schema = [
        {
          name: "entity",
          required: true,
          selector: {
            entity: {
              filter: [{ integration: DOMAIN, domain: "binary_sensor" }],
            },
          },
        },
        {
          name: "display_mode",
          required: true,
          selector: {
            select: {
              mode: "dropdown",
              options: Object.keys(MODES).map((value) => ({
                value,
                label: text[value],
              })),
            },
          },
        },
        { name: "name", selector: { text: {} } },
        { name: "icon", selector: { icon: {} } },
      ];
      this._form.computeLabel = (schema) => text[schema.name];
      this._form.computeHelper = (schema) =>
        schema.name === "entity"
          ? text.entity_help
          : schema.name === "display_mode"
            ? text.mode_help
            : undefined;
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
  }
}

if (!customElements.get(CARD_TYPE))
  customElements.define(CARD_TYPE, DhlPackstationCard);
if (!customElements.get(`${CARD_TYPE}-editor`))
  customElements.define(`${CARD_TYPE}-editor`, DhlPackstationCardEditor);
window.customCards ??= [];
if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "DHL Packstation",
    description: TEXT.en.description,
    preview: true,
    documentationURL: "https://github.com/jonalbr/ha-dhl-packstation#dashboard",
    getEntitySuggestion: (hass, entityId) =>
      isStation(hass, entityId)
        ? Object.keys(MODES).map((mode) => ({
            label: words(hass)[mode],
            config: {
              type: `custom:${CARD_TYPE}`,
              entity: entityId,
              display_mode: mode,
            },
          }))
        : null,
  });
}
