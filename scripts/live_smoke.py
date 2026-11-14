"""Run a separate live check in a disposable HA instance, never the user's HA."""

import json
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "dhl_packstation_monitor"


def run():
    from playwright.sync_api import sync_playwright

    artifacts = ROOT / ".smoke"
    artifacts.mkdir(exist_ok=True)
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
            [sys.executable, "-m", "homeassistant", "--config", str(config), "--skip-pip"],
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
                    raise RuntimeError(f"Temporary HA stopped; inspect {config / 'server.log'}")
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

            result = call("POST", "/api/config/config_entries/flow", json={"handler": DOMAIN})

            def configure(data):
                nonlocal result
                result = call(
                    "POST", "/api/config/config_entries/flow/" + result["flow_id"], json=data
                )
                assert not result.get("errors"), result.get("errors")

            configure({"next_step_id": "search"})
            configure({"address": "Georgenstr. 31, 10117 Berlin"})
            assert result["step_id"] == "select"
            choices = result["data_schema"][0]["selector"]["select"]["options"]
            selected = [option["value"] for option in choices[:2]]
            assert selected
            configure({"stations": selected})
            assert result["step_id"] == "confirm"
            configure({"stations": selected})
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
                async with aiohttp.ClientSession() as client:
                    async with client.ws_connect(base + "/api/websocket") as ws:
                        await ws.receive_json()
                        await ws.send_json({"type": "auth", "access_token": tokens["access_token"]})
                        assert (await ws.receive_json())["type"] == "auth_ok"
                        await ws.send_json({"id": 1, "type": "config/entity_registry/list"})
                        entities = (await ws.receive_json())["result"]
                        await ws.send_json({"id": 2, "type": "config/device_registry/list"})
                        devices = (await ws.receive_json())["result"]
                        # A new HA HTTP listener needs explicit confirmation. This socket
                        # belongs only to the disposable localhost instance created above.
                        await ws.send_json({"id": 3, "type": "http/config/promote"})
                        assert (await ws.receive_json())["success"]
                        return entities, devices

            entities, devices = asyncio.run(registry())
            own_entities = [entity for entity in entities if entity["platform"] == DOMAIN]
            assert len(own_entities) == 7 * len(selected)
            assert len({entity["device_id"] for entity in own_entities}) == len(selected)
            print(
                f"Live DHL flow created {len(selected)} devices and {len(own_entities)} entities",
                flush=True,
            )
            cards = [
                {
                    "type": "tile",
                    "entity": state["entity_id"],
                    "state_content": "compartment_summary",
                    "name": "Packstation " + state["attributes"]["station_number"],
                    "color": "amber",
                    "icon": "mdi:package-variant-closed",
                    "tap_action": {"action": "more-info"},
                }
                for state in diagnostics
            ]
            (config / "ui-lovelace.yaml").write_text(
                json.dumps(
                    {"title": "Packstations", "views": [{"title": "Packstations", "cards": cards}]}
                ),
                encoding="utf-8",
            )
            with sync_playwright() as browser_api:
                browser = browser_api.chromium.launch()
                page = browser.new_page(viewport={"width": 1280, "height": 800})
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
                summary = diagnostics[0]["attributes"]["compartment_summary"]
                tile.screenshot(path=str(artifacts / "tile-desktop.png"))
                tile.get_by_text(summary, exact=True).wait_for(state="visible", timeout=10000)
                page.set_viewport_size({"width": 375, "height": 700})
                tile.screenshot(path=str(artifacts / "tile-mobile.png"))
                assert tile.bounding_box()["width"] <= 375
                try:
                    tile.click(timeout=10000)
                    page.locator("ha-more-info-dialog").get_by_text(
                        "Data problem", exact=True
                    ).first.wait_for(state="visible", timeout=10000)
                except Exception:
                    page.screenshot(path=str(artifacts / "more-info-failure.png"))
                    print(page.get_by_role("button").all_text_contents(), flush=True)
                    raise
                browser.close()
            report = {
                "homeassistant": "2026.11.1",
                "stations": selected,
                "entities": len(own_entities),
                "devices": len(selected),
                "summaries": [state["attributes"]["compartment_summary"] for state in diagnostics],
                "tile_desktop": True,
                "tile_mobile": True,
                "more_info": True,
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
