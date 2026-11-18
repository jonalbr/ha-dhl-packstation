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
    device_id: "Packstation",
    display_mode: "Display",
    name: "Name (optional)",
    icon: "Icon (optional)",
    free: "Free compartments",
    total: "Free compartments and DHL total capacity",
    capacities: "Free compartments and manual totals by size",
    choose: "Add a Packstation to the integration, then select it here.",
    device_id_help:
      "Tap the card for the device; tap its icon for total-count history.",
    mode_help:
      "Manual totals are optional. Empty means unknown; 0 means no compartments of that size.",
    invalid_entity: "Select a Packstation device.",
    missing:
      "This Packstation's entities are unavailable or disabled. Check the device in Settings.",
    invalid_mode: "Choose a supported display mode.",
    invalid_text: "Name and icon must be text.",
    load_failed: "The card could not be loaded. Reload the page to try again.",
    description:
      "Packstation availability with a station picker and three display modes.",
  },
  de: {
    device_id: "Packstation",
    display_mode: "Darstellung",
    name: "Name (optional)",
    icon: "Symbol (optional)",
    free: "Freie Fächer",
    total: "Freie Fächer und Stationskapazität laut DHL",
    capacities: "Freie Fächer und manuelle Gesamtzahlen je Größe",
    choose:
      "Füge der Integration eine Packstation hinzu und wähle sie hier aus.",
    device_id_help:
      "Tippe auf die Karte für das Gerät, auf das Symbol für den Verlauf der Gesamtzahl.",
    mode_help:
      "Manuelle Gesamtzahlen sind optional. Leer bedeutet unbekannt; 0 bedeutet keine Fächer dieser Größe.",
    invalid_entity: "Wähle ein Packstationsgerät aus.",
    missing:
      "Die Entitäten dieser Packstation sind nicht verfügbar oder deaktiviert. Prüfe das Gerät in den Einstellungen.",
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
  const entry = hass?.entities?.[entityId];
  const attributes = hass?.states?.[entityId]?.attributes;
  return (
    entityId.startsWith("binary_sensor.") &&
    ((entry?.platform === DOMAIN && entry.translation_key === "data_problem") ||
      (typeof attributes?.station_id === "string" &&
        typeof attributes?.compartment_summary === "string"))
  );
}

function stationDevice(hass, deviceId) {
  return (
    hass?.devices?.[deviceId]?.identifiers?.some(([domain]) => domain === DOMAIN) ||
    Object.values(hass?.entities ?? {}).some(
      (entry) => entry.device_id === deviceId && entry.platform === DOMAIN,
    )
  );
}

function stationEntities(hass, config) {
  const deviceId = config.device_id || hass?.entities?.[config.entity]?.device_id;
  if (!deviceId) return { problem: config.entity };
  const siblings = Object.entries(hass?.entities ?? {}).filter(
    ([, entry]) => entry.device_id === deviceId && entry.platform === DOMAIN,
  );
  const find = (key) =>
    siblings.find(([, entry]) => entry.translation_key === key)?.[0];
  return {
    deviceId,
    problem: find("data_problem") || (!config.device_id ? config.entity : undefined),
    total: find("free_total"),
  };
}

function normalizeConfig(config, text) {
  if (config.device_id !== undefined && typeof config.device_id !== "string") {
    throw new Error(text.invalid_entity);
  }
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
    const deviceId = candidates
      .map((id) => hass?.entities?.[id])
      .find((entry) => entry?.platform === DOMAIN && entry.device_id)?.device_id;
    return {
      device_id:
        deviceId ||
        Object.keys(hass?.devices ?? {}).find((id) => stationDevice(hass, id)) ||
        "",
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
    if (!this._config.device_id && !this._config.entity) {
      this._message(words(this._hass).choose);
      return;
    }
    // One shared load; later renders always read the latest configuration and state.
    this._helpersPromise ??= window.loadCardHelpers();
    const helpers = await this._helpersPromise;
    const config = this._config;
    if (!config.device_id && !config.entity) return;
    const { deviceId, problem, total } = stationEntities(this._hass, config);
    if (
      (config.device_id && !stationDevice(this._hass, config.device_id)) ||
      (!config.device_id &&
        this._hass.states[config.entity] &&
        !isStation(this._hass, config.entity))
    ) {
      this._message(words(this._hass).invalid_entity);
      return;
    }
    // The diagnostic retains summaries when numeric sensors expire. Navigation
    // and history are independent of this internal rendering source.
    const entity = problem || total;
    if (!entity) {
      this._message(words(this._hass).missing);
      return;
    }
    const state = this._hass.states[entity];
    const device = this._hass.devices?.[deviceId];
    const name =
      config.name ||
      device?.name_by_user ||
      device?.name ||
      (state?.attributes.station_number
        ? `Packstation ${state.attributes.station_number}`
        : undefined);
    const tileConfig = {
      type: "tile",
      entity,
      state_content: MODES[config.display_mode],
      icon: config.icon || "mdi:package-variant-closed",
      color: "amber",
      tap_action: deviceId
        ? {
            action: "navigate",
            navigation_path: `/config/devices/device/${encodeURIComponent(deviceId)}`,
          }
        : { action: "none" },
      icon_tap_action: total
        ? { action: "more-info", entity: total }
        : { action: "none" },
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
          ...this._config,
          ...event.detail.value,
          type: this._config.type ?? `custom:${CARD_TYPE}`,
        };
        // Upgrade legacy entity-based cards only when the editor is saved.
        if (Object.hasOwn(event.detail.value, "device_id")) delete config.entity;
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
          name: "device_id",
          required: true,
          selector: {
            device: {
              filter: [{ integration: DOMAIN }],
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
        schema.name === "device_id"
          ? text.device_id_help
          : schema.name === "display_mode"
            ? text.mode_help
            : undefined;
    }
    this._form.hass = this._hass;
    this._form.data = {
      ...this._config,
      device_id: stationEntities(this._hass, this._config).deviceId || "",
    };
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
      hass?.entities?.[entityId]?.platform === DOMAIN &&
      hass.entities[entityId].device_id
        ? Object.keys(MODES).map((mode) => ({
            label: words(hass)[mode],
            config: {
              type: `custom:${CARD_TYPE}`,
              device_id: hass.entities[entityId].device_id,
              display_mode: mode,
            },
          }))
        : null,
  });
}
