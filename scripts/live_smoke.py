"""Run a separate live check in a disposable HA instance, never the user's HA."""

import json
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from importlib.metadata import version
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "dhl_packstation_monitor"


def run():
    from playwright.sync_api import expect, sync_playwright

    artifacts = ROOT / ".smoke" / version("homeassistant")
    artifacts.mkdir(parents=True, exist_ok=True)
    config = Path(tempfile.mkdtemp(prefix="instance-", dir=artifacts))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    (config / "custom_components").mkdir()
    (config / "custom_components" / DOMAIN).symlink_to(
        ROOT / "custom_components" / DOMAIN, target_is_directory=True
    )
    (config / "configuration.yaml").write_text(
        "homeassistant:\n  name: Packstation smoke test\n  latitude: 52.52\n"
        "  longitude: 13.39\n  elevation: 34\n  unit_system: metric\n"
        "  time_zone: Europe/Berlin\n  country: DE\n"
        f"http:\n  server_host: 127.0.0.1\n  server_port: {port}\n"
        "frontend:\napi:\nconfig:\nlovelace:\n  mode: yaml\n"
        "logger:\n  default: warning\n",
        encoding="utf-8",
    )
    session = requests.Session()
    with (config / "server.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "homeassistant",
                "--config",
                str(config),
                "--skip-pip",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            for _ in range(180):
                try:
                    response = session.get(base + "/api/onboarding", timeout=1)
                    if response.ok:
                        break
                except requests.RequestException:
                    pass
                if process.poll() is not None:
                    raise RuntimeError(
                        f"Temporary HA stopped; inspect {config / 'server.log'}"
                    )
                time.sleep(0.5)
            else:
                raise RuntimeError("Temporary HA startup timed out")
            print("Temporary HA started", flush=True)

            def call(method, path, **kwargs):
                response = session.request(method, base + path, timeout=90, **kwargs)
                response.raise_for_status()
                return response.json() if response.content else None

            client_id = base + "/"
            auth = call(
                "POST",
                "/api/onboarding/users",
                json={
                    "client_id": client_id,
                    "name": "Smoke test",
                    "username": "smoke",
                    "password": secrets.token_urlsafe(32),
                    "language": "en",
                },
            )
            tokens = call(
                "POST",
                "/auth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": auth["auth_code"],
                    "client_id": client_id,
                },
            )
            session.headers["Authorization"] = f"Bearer {tokens['access_token']}"
            for step in call("GET", "/api/onboarding"):
                if not step["done"]:
                    data = {"client_id": client_id}
                    if step["step"] == "integration":
                        data["redirect_uri"] = base + "/?auth_callback=1"
                    call("POST", "/api/onboarding/" + step["step"], json=data)

            result = call(
                "POST", "/api/config/config_entries/flow", json={"handler": DOMAIN}
            )

            def configure(data):
                nonlocal result
                result = call(
                    "POST",
                    "/api/config/config_entries/flow/" + result["flow_id"],
                    json=data,
                )
                assert not result.get("errors"), result.get("errors")

            configure({"next_step_id": "search"})
            address_field = result["data_schema"][0]
            assert address_field["description"]["suggested_value"] == "Home"
            assert not address_field["required"]
            configure({"address": "Home"})
            assert result["step_id"] == "select"
            choices = result["data_schema"][0]["selector"]["select"]["options"]
            selected = [option["value"] for option in choices[:2]]
            assert selected
            configure({"stations": selected})
            assert result["step_id"] == "confirm"
            configure({"stations": selected, "configure_capacities": True})
            for index in range(1, len(selected) + 1):
                assert result["step_id"] == "capacities"
                assert result["description_placeholders"]["current"] == str(index)
                assert result["description_placeholders"]["total"] == str(len(selected))
                configure({})
            assert result["type"] == "create_entry"
            for _ in range(60):
                station_states = [
                    state
                    for state in call("GET", "/api/states")
                    if state["attributes"].get("station_id") in selected
                ]
                diagnostics = [
                    state
                    for state in station_states
                    if state["entity_id"].startswith("binary_sensor.")
                ]
                if len(diagnostics) == len(selected):
                    break
                time.sleep(0.5)
            assert len(diagnostics) == len(selected)
            # Count all entities through the real registry, including unavailable counts.
            import asyncio

            import aiohttp

            async def registry():
                async with (
                    aiohttp.ClientSession() as client,
                    client.ws_connect(base + "/api/websocket") as ws,
                ):
                    await ws.receive_json()
                    await ws.send_json(
                        {"type": "auth", "access_token": tokens["access_token"]}
                    )
                    assert (await ws.receive_json())["type"] == "auth_ok"
                    await ws.send_json({"id": 1, "type": "config/entity_registry/list"})
                    entities = (await ws.receive_json())["result"]
                    await ws.send_json({"id": 2, "type": "config/device_registry/list"})
                    devices = (await ws.receive_json())["result"]
                    # A new HA HTTP listener needs explicit confirmation. This socket
                    # belongs only to the disposable localhost instance created above.
                    await ws.send_json({"id": 3, "type": "http/config/promote"})
                    assert (await ws.receive_json())["success"]
                    entry_id = next(
                        entity["config_entry_id"]
                        for entity in entities
                        if entity["platform"] == DOMAIN
                    )
                    await ws.send_json(
                        {
                            "id": 4,
                            "type": "config_entries/subentries/list",
                            "entry_id": entry_id,
                        }
                    )
                    subentries = (await ws.receive_json())["result"]
                    await ws.send_json(
                        {
                            "id": 5,
                            "type": "lovelace/dashboards/create",
                            "url_path": "dhl-card-test",
                            "title": "DHL card test",
                            "mode": "storage",
                            "show_in_sidebar": False,
                            "require_admin": False,
                        }
                    )
                    assert (await ws.receive_json())["success"]
                    await ws.send_json(
                        {
                            "id": 6,
                            "type": "lovelace/config/save",
                            "url_path": "dhl-card-test",
                            "config": {
                                "views": [
                                    {
                                        "title": "Packstations",
                                        "type": "sections",
                                        "sections": [{"type": "grid", "cards": []}],
                                    }
                                ]
                            },
                        }
                    )
                    assert (await ws.receive_json())["success"]
                    return entities, devices, entry_id, subentries

            entities, devices, entry_id, subentries = asyncio.run(registry())
            own_entities = [
                entity for entity in entities if entity["platform"] == DOMAIN
            ]
            assert len(own_entities) == 9 * len(selected)
            station_device_ids = {entity["device_id"] for entity in own_entities}
            assert len(station_device_ids) == len(selected)
            assert station_device_ids <= {device["id"] for device in devices}
            print(
                f"Live DHL flow created {len(selected)} devices and {len(own_entities)} entities",
                flush=True,
            )
            edited = call(
                "POST",
                "/api/config/config_entries/subentries/flow",
                json={
                    "handler": [entry_id, "station"],
                    "subentry_id": subentries[0]["subentry_id"],
                },
            )
            assert edited["step_id"] == "reconfigure"
            # Illustrative display metadata, not an assertion about the real locker.
            manual_capacities = {"s": 40, "m": 30, "l": 20, "xl": 15}
            edited = call(
                "POST",
                "/api/config/config_entries/subentries/flow/" + edited["flow_id"],
                json={
                    "name": subentries[0]["title"],
                    "display_capacities": manual_capacities,
                },
            )
            assert (
                edited["type"] == "abort"
                and edited["reason"] == "reconfigure_successful"
            )
            for _ in range(60):
                diagnostics = [
                    state
                    for state in call("GET", "/api/states")
                    if state["entity_id"].startswith("binary_sensor.")
                    and state["attributes"].get("station_id") in selected
                ]
                if any(
                    state["attributes"].get("display_capacities") == manual_capacities
                    for state in diagnostics
                ):
                    break
                time.sleep(0.5)
            diagnostics.sort(
                key=lambda state: state["attributes"]["station_id"] != selected[0]
            )
            assert (
                diagnostics[0]["attributes"]["display_capacities"] == manual_capacities
            )
            variants = {
                "free": "compartment_summary",
                "total": "compartment_total_summary",
                "capacities": "compartment_capacity_summary",
            }
            preview_device = next(
                entity["device_id"]
                for entity in own_entities
                if entity["entity_id"] == diagnostics[0]["entity_id"]
            )
            cards = [
                {
                    "type": "custom:dhl-packstation-card",
                    "device_id": preview_device,
                    "display_mode": mode,
                }
                for mode in variants
            ]
            (config / "ui-lovelace.yaml").write_text(
                json.dumps(
                    {
                        "title": "Packstations",
                        "views": [{"title": "Packstations", "cards": cards}],
                    }
                ),
                encoding="utf-8",
            )
            with sync_playwright() as browser_api:
                browser = browser_api.chromium.launch()
                page = browser.new_page(
                    viewport={"width": 1280, "height": 800}, color_scheme="light"
                )
                browser_tokens = {
                    **tokens,
                    "hassUrl": base,
                    "clientId": client_id,
                    "expires": int(time.time() * 1000) + 1800000,
                }
                page.add_init_script(
                    "localStorage.setItem('hassTokens', "
                    + json.dumps(json.dumps(browser_tokens))
                    + ");"
                )
                page.goto(base + "/lovelace/0")
                tile = page.locator("hui-tile-card").first
                try:
                    tile.wait_for(state="visible", timeout=30000)
                except Exception:
                    page.screenshot(path=str(artifacts / "browser-failure.png"))
                    print(page.locator("body").inner_text()[:2000], flush=True)
                    raise
                tile_backgrounds = {}
                for scheme in ("light", "dark"):
                    page.emulate_media(color_scheme=scheme)
                    page.wait_for_function(
                        "(dark) => document.querySelector('home-assistant')"
                        "?.hass?.themes.darkMode === dark",
                        arg=scheme == "dark",
                    )
                    suffix = "-dark" if scheme == "dark" else ""
                    page.set_viewport_size({"width": 1280, "height": 800})
                    for index, variant in enumerate(variants.values()):
                        card = page.locator("hui-tile-card").nth(index)
                        card.get_by_text(
                            diagnostics[0]["attributes"][variant], exact=True
                        ).wait_for(state="visible", timeout=10000)
                    tile.screenshot(
                        path=str(artifacts / f"tile-desktop{suffix}.png"),
                        animations="disabled",
                    )
                    tile_backgrounds[scheme] = tile.locator("ha-card").evaluate(
                        "el => getComputedStyle(el).backgroundColor"
                    )
                    page.set_viewport_size({"width": 375, "height": 700})
                    tile.screenshot(
                        path=str(artifacts / f"tile-mobile{suffix}.png"),
                        animations="disabled",
                    )
                    for index, variant in enumerate(variants.values()):
                        page.locator("hui-tile-card").nth(index).screenshot(
                            path=str(artifacts / f"{variant}-mobile{suffix}.png"),
                            animations="disabled",
                        )
                    first_box = tile.bounding_box()
                    last_box = page.locator("hui-tile-card").last.bounding_box()
                    assert first_box["width"] <= 375
                    page.screenshot(
                        path=str(artifacts / f"tiles-mobile{suffix}.png"),
                        animations="disabled",
                        clip={
                            "x": first_box["x"],
                            "y": first_box["y"],
                            "width": first_box["width"],
                            "height": last_box["y"]
                            + last_box["height"]
                            - first_box["y"],
                        },
                    )
                assert tile_backgrounds["light"] != tile_backgrounds["dark"]
                page.set_viewport_size({"width": 1280, "height": 900})
                try:
                    page.goto(base + "/dhl-card-test/0")
                    page.wait_for_function(
                        "window.customCards?.some(card => card.type === 'dhl-packstation-card')"
                    )
                    page.get_by_role(
                        "button", name="Open dashboard menu", exact=True
                    ).click()
                    page.get_by_text("Edit dashboard", exact=True).click()
                    page.get_by_role(
                        "button", name="Add card", exact=True
                    ).first.click()
                    page.get_by_role("tab", name="By card", exact=True).click()
                    page.get_by_role("textbox").fill("DHL")
                    page.screenshot(
                        path=str(artifacts / "dhl-card-picker.png"),
                        animations="disabled",
                    )
                    page.get_by_text("DHL Packstation", exact=True).locator(
                        ".."
                    ).click()
                    editor = page.locator("dhl-packstation-card-editor")
                    editor.wait_for(state="visible")
                    page.screenshot(
                        path=str(artifacts / "dhl-card-editor.png"),
                        animations="disabled",
                    )
                    mode_button = editor.get_by_role(
                        "button", name="Display * Free compartments", exact=True
                    )
                    if mode_button.count():
                        mode_button.click()
                    else:
                        editor.get_by_role("listitem").nth(1).click()
                    page.get_by_text(
                        "Free compartments and manual totals by size", exact=True
                    ).click()
                    name_input = editor.get_by_role("textbox", name="Name (optional)")
                    name_input.fill("Near home")
                    page.locator("dhl-packstation-card").get_by_text(
                        "Near home", exact=True
                    ).wait_for(state="visible")
                    name_input.fill("")
                    editor.locator("ha-device-picker").click()
                    device_search = page.locator("ha-picker-combo-box input")
                    device_search.fill(subentries[1]["title"])
                    page.get_by_text(subentries[1]["title"], exact=True).last.click()
                    page.locator("dhl-packstation-card").get_by_text(
                        diagnostics[1]["attributes"]["compartment_capacity_summary"],
                        exact=True,
                    ).wait_for(state="visible")
                    page.get_by_role("button", name="Save", exact=True).click()
                    page.get_by_role("button", name="Done", exact=True).click()
                    custom_card = page.locator("dhl-packstation-card")
                    custom_card.wait_for(state="visible")
                    card_device = custom_card.evaluate("el => el._config.device_id")
                    assert custom_card.evaluate("el => el._config.entity") is None
                    card_entity = diagnostics[1]["entity_id"]
                    assert card_device == next(
                        entity["device_id"]
                        for entity in own_entities
                        if entity["entity_id"] == card_entity
                    )
                    state = call("GET", "/api/states/" + card_entity)
                    custom_card.get_by_text(
                        state["attributes"]["compartment_capacity_summary"], exact=True
                    ).wait_for(state="visible")
                    for scheme in ("light", "dark"):
                        page.emulate_media(color_scheme=scheme)
                        page.wait_for_function(
                            "(dark) => document.querySelector('home-assistant')"
                            "?.hass?.themes.darkMode === dark",
                            arg=scheme == "dark",
                        )
                        for width in (1280, 375):
                            page.set_viewport_size({"width": width, "height": 900})
                            custom_card.screenshot(
                                path=str(artifacts / f"dhl-card-{width}-{scheme}.png"),
                                animations="disabled",
                            )
                            assert custom_card.bounding_box()["width"] <= width
                    custom_card.locator("ha-tile-icon").click()
                    page.locator("ha-more-info-dialog").get_by_text(
                        "Free compartments total", exact=True
                    ).first.wait_for(state="visible")
                    page.locator("ha-more-info-dialog").get_by_role(
                        "button", name=subentries[1]["title"], exact=True
                    ).wait_for(state="visible")
                    page.goto(base + "/dhl-card-test/0")
                    custom_card.get_by_role(
                        "button",
                        name=(
                            subentries[1]["title"]
                            + " "
                            + state["attributes"]["compartment_capacity_summary"]
                        ),
                        exact=True,
                    ).click()
                    page.wait_for_url(base + "/config/devices/device/" + card_device)
                    page.get_by_text(
                        "Free compartments total", exact=True
                    ).first.wait_for(state="visible")
                except Exception:
                    page.screenshot(path=str(artifacts / "dhl-card-ui-failure.png"))
                    print(page.locator("body").aria_snapshot()[:12000], flush=True)
                    raise
                page.set_viewport_size({"width": 1280, "height": 900})
                page.goto(base + "/config/integrations/integration/" + DOMAIN)
                try:
                    for value in ("90", ""):
                        page.get_by_role(
                            "button", name="Configure", exact=True
                        ).first.click()
                        page.get_by_text("Global updates", exact=True).wait_for(
                            state="visible"
                        )
                        age = page.locator('input[type="number"]').nth(1)
                        interval = page.locator('input[type="number"]').first
                        expect(age).to_have_value("" if value else "90")
                        expect(interval).to_have_value("" if value else "30")
                        page.get_by_text(
                            "Recommended: 75 minutes.",
                            exact=False,
                        ).wait_for(state="visible")
                        page.get_by_text(
                            "Recommended: 15 minutes.",
                            exact=False,
                        ).wait_for(state="visible")
                        age.fill(value)
                        interval.fill("30" if value else "")
                        page.get_by_role("button", name="Submit", exact=True).click()
                        page.get_by_text("Global updates", exact=True).wait_for(
                            state="hidden"
                        )
                        page.get_by_role("button", name="Finish", exact=True).click()
                    page.get_by_role(
                        "button", name="Configure", exact=True
                    ).first.click()
                    age = page.locator('input[type="number"]').nth(1)
                    expect(age).to_have_value("")
                    expect(page.locator('input[type="number"]').first).to_have_value("")
                    page.screenshot(
                        path=str(artifacts / "recommended-settings.png"),
                        animations="disabled",
                    )
                    page.get_by_role("button", name="Submit", exact=True).click()
                    page.get_by_text("Global updates", exact=True).wait_for(
                        state="hidden"
                    )
                    page.get_by_role("button", name="Finish", exact=True).click()
                    page.locator("ha-button").filter(
                        has_text="Add station"
                    ).first.click(timeout=15000)
                    page.get_by_text(
                        "Search an address or postal code", exact=True
                    ).click()
                    home = page.get_by_text("Home", exact=True)
                    home.wait_for(state="visible")
                    page.get_by_text(
                        "Georgenstraße 31, 10117 Berlin", exact=False
                    ).wait_for(state="visible")
                    page.screenshot(path=str(artifacts / "home-location.png"))
                    page.locator("ha-picker-field .clear").click()
                    home.wait_for(state="hidden")
                    page.screenshot(path=str(artifacts / "home-location-cleared.png"))
                    page.locator("ha-picker-field").click()
                    page.locator("ha-picker-combo-box input").fill("Hamburg")
                    page.get_by_text("Add custom item", exact=True).click()
                    page.locator("ha-picker-field").get_by_text(
                        "Hamburg", exact=True
                    ).wait_for(state="visible")
                    page.screenshot(path=str(artifacts / "home-location-replaced.png"))
                    page.get_by_role("button", name="Submit", exact=True).click()
                    page.get_by_role("radio").first.check()
                    page.get_by_role("button", name="Submit", exact=True).click()
                    page.locator("ha-switch").click()
                    expect(page.locator("ha-switch")).to_have_js_property(
                        "checked", True
                    )
                    page.screenshot(path=str(artifacts / "confirm-capacities.png"))
                    page.get_by_role("button", name="Submit", exact=True).click()
                    page.get_by_text(
                        "Compartment totals (1 of 1)", exact=True
                    ).wait_for(state="visible")
                    inputs = page.locator('input[type="number"]')
                    inputs.first.wait_for(state="visible")
                    assert inputs.count() == 4
                    assert all(field.input_value() == "" for field in inputs.all())
                    page.get_by_text(
                        "Empty means unknown; 0 means there are no compartments of that size.",
                        exact=False,
                    ).wait_for(state="visible")
                    page.screenshot(path=str(artifacts / "add-station-capacities.png"))
                    page.goto(base + "/config/integrations/integration/" + DOMAIN)
                    page.locator("ha-config-sub-entry-row").filter(
                        has_text=subentries[0]["title"]
                    ).get_by_role("button", name="Edit station", exact=True).click()
                    page.get_by_text(
                        "Compartment totals (optional, display only)", exact=True
                    ).click()
                    inputs = page.locator('input[type="number"]')
                    inputs.first.wait_for(state="visible")
                    assert [field.input_value() for field in inputs.all()] == [
                        str(value) for value in manual_capacities.values()
                    ]
                    page.screenshot(path=str(artifacts / "edit-capacities.png"))
                    inputs.first.fill("")
                    page.get_by_role("button", name="Submit", exact=True).click()
                    for _ in range(60):
                        state = call(
                            "GET", "/api/states/" + diagnostics[0]["entity_id"]
                        )
                        if state["attributes"].get("display_capacities") == {
                            key: value
                            for key, value in manual_capacities.items()
                            if key != "s"
                        }:
                            break
                        time.sleep(0.5)
                    else:
                        raise AssertionError(
                            "Clearing a capacity must remove it and preserve others"
                        )
                except Exception:
                    page.screenshot(path=str(artifacts / "search-ui-failure.png"))
                    print(page.locator("body").inner_text()[:3000], flush=True)
                    print(page.get_by_role("button").all_text_contents(), flush=True)
                    raise
                browser.close()
            report = {
                "homeassistant": version("homeassistant"),
                "stations": selected,
                "entities": len(own_entities),
                "devices": len(selected),
                "summaries": [
                    state["attributes"]["compartment_summary"] for state in diagnostics
                ],
                "tile_desktop": True,
                "tile_mobile": True,
                "card_display_modes": list(variants),
                "tile_color_schemes": tile_backgrounds,
                "custom_card_picker": True,
                "custom_card_visual_editor": True,
                "custom_card_station_selection": True,
                "custom_card_device_navigation": True,
                "custom_card_total_history": True,
                "custom_card_mobile_and_desktop": True,
                "custom_card_light_and_dark": True,
                "recommended_settings_clearable": True,
                "more_info": True,
                "home_location_clear": True,
                "home_location_replace": True,
                "address_format_help": True,
                "setup_capacity_walkthrough": True,
                "add_station_capacity_dialog": True,
                "manual_capacity_editor": True,
                "manual_capacity_clear": True,
                "manual_capacity_reconfigure": True,
                "display_capacities_are_illustrative": True,
            }
            (artifacts / "live-result.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            print(json.dumps(report), flush=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    run()
