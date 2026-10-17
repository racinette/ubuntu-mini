# Proxy service

Ordinary `setup.sh` installs a checksum-pinned Mihomo binary and `minion-proxy.service` alongside the other components. Proxy use is optional: installing or rerunning setup does not enable, start or restart the service, and preserves existing proxy configuration. No subscription or account credentials belong in the repository.

Click **Proxy** in the bottom bar or choose **Proxy dashboard** from the launcher to open the locally installed MetaCubeXD dashboard in Chromium. Under **Proxies**, choose a server in **PROXY**, or **Automatic** for latency-based selection. The dashboard also provides latency tests, connection information and traffic monitoring. Selections are remembered by Mihomo across service restarts and boot. If the proxy is stopped, the launcher offers to start it through a local password terminal.

Run management commands directly from the repository with `sudo python3 setup/proxy/manage.py`. The dashboard launcher is installed as `minion-proxy-ui`; the management helper remains in the repository. The service uses a root-owned runtime copy under `/usr/local/lib/minion-proxy/`, so boot does not depend on the checkout's location, availability or user permissions. Rerunning setup updates that copy. It works independently of Sway.

## Install and enable on the Mini

From your normal account in the repository, on installed Ubuntu 24.04:

```bash
git pull --ff-only
sudo ./setup.sh --check
sudo ./setup.sh
sudo python3 setup/proxy/manage.py configure
sudo systemctl enable --now minion-proxy.service
sudo python3 setup/proxy/manage.py test
```

`configure` privately prompts for an HTTPS subscription URL and defaults to TUN mode. The URL is not echoed or passed as a command argument. Configuration fetches and caches the server list before replacing the installed configuration, and validates it with Mihomo. It does not start or restart the service. Proxy activation itself needs no reboot; ordinary setup may still require rebooting for desktop/networking changes.

For component development or a focused repair, `sudo python3 setup/proxy/provision.py` invokes the same proxy installer directly. Normal installation and updates use `setup.sh` without a proxy flag.

If third-party downloads require the proxy, run `sudo python3 setup/proxy/provision.py` before the full setup, then configure, select a server if needed, enable/start the service and test it using the commands below. Only then run `sudo ./setup.sh`. The proxy installer itself needs access to its pinned GitHub release; this sequence assumes that download and the subscription endpoint are reachable directly.

The service routes public destinations through a subscription server selected by latency checks by default, while local/private networks and multicast bypass the tunnel. Automatic mode checks servers every five minutes; a pinned selection stays on the chosen server. It captures DNS traffic and uses Mihomo's resolver. TUN mode requires Ubuntu's standard `systemd-resolved` service and the `127.0.0.53` stub in `/etc/resolv.conf`. Startup adds a temporary `~.` DNS routing domain on `minion-proxy`; the settings disappear when that interface is removed. Existing NetworkManager connections and Netplan files are not rewritten. HTTPS subscriptions are refreshed hourly with the `minion-proxy/1.0` user agent; the endpoint must return raw or base64-encoded server URIs for that agent. A browser landing page, HAPP-encrypted link or full JSON/YAML configuration is not accepted by this helper. Mihomo handles the server URI formats itself.

Some providers require device registration. The helper creates one random, stable device ID under `/var/lib/minion/proxy/device-id` and sends the documented `x-hwid` and Linux device headers on both initial fetch and automatic refresh. Reruns reuse this identity. Provider device limits still apply: if all slots are occupied, remove an unused device through your provider before retrying. Missing-device and device-limit refusal headers, and all-placeholder subscriptions, are rejected before replacing the working configuration. Keep the device-ID file with your private proxy backup to retain registration across reinstalls.

Local subscription testing also registers a device. To transfer that registration to a fresh Mini, copy the private test `device-id` file to the Mini and install it after proxy setup, before running `configure`:

```bash
sudo install -o root -g root -m 600 /PRIVATE/PATH/device-id /var/lib/minion/proxy/device-id
```

The retained test identity for this checkout is in ignored `.local/proxy-qa/live/device-id`. Stop the test client before transferring the registration. An existing configured Mini should retain its own identity.

The local HTTP/SOCKS listener binds only to `127.0.0.1:7890`. The dashboard and authenticated control API bind only to `127.0.0.1:9090`, with static dashboard files served at `/ui/`; they are not exposed on Wi-Fi. The subscription URL, server cache, dashboard identity and runtime state live under root-only `/var/lib/minion/proxy/`. `/etc/minion/proxy-dashboard.json` grants the selected desktop account access to the local control API without granting access to the subscription files. The launcher passes the token through a private Chromium bootstrap file and a URL fragment, keeping it out of process arguments and HTTP request paths. Core output redacts subscription credentials and the dashboard token before reaching the journal. Logs can still contain connection destinations; treat diagnostic reports as private.

Setup installs a checksum-pinned [MetaCubeXD static release](https://github.com/MetaCubeX/metacubexd), retaining its API identity on reruns. Installation does not start or restart the proxy. Restart an already configured service after upgrading to activate the dashboard. No second proxy engine is installed.

## Belarusian website and IP bypass

Default proxy configuration sends `.by` and `.бел` domains directly, including
`hoster.by` and their subdomains. The two native Mihomo rules are:

```text
DOMAIN-SUFFIX,by,DIRECT
DOMAIN-SUFFIX,xn--90ais,DIRECT
```

`xn--90ais` is the ASCII IDNA spelling of `.бел`. These suffix rules require no
downloaded registry or updates and work independently of the optional Russian
bypass lists. They cover these domain zones, not all Belarusian IP addresses
or Belarusian services using other domain suffixes. Earlier personal rules keep
priority. Existing installations retain their config on setup reruns; add these
rules before `MATCH,PROXY` and restart the proxy when upgrading manually.
See [Mihomo suffix rules](https://wiki.metacubex.one/en/config/rules/#domain-suffix).

For numeric IP connections such as SSH, also enable Belarusian IP ranges:

```bash
sudo python3 setup/proxy/manage.py bypass-by on
sudo systemctl restart minion-proxy.service
```

This downloads [MetaCubeX's Belarus IP list](https://raw.githubusercontent.com/MetaCubeX/meta-rules-dat/meta/geo/geoip/by.list),
validates and caches it, then adds `RULE-SET,minion-by-ips,DIRECT` before the
proxy fallback. Mihomo refreshes it daily through the selected proxy and keeps
its cached copy if refresh fails. It includes IPv4 and IPv6 prefixes; geographic
classification may be incomplete. Earlier personal rules and Russian bypasses
retain their priority. `bypass-by off` removes the IP bypass while keeping the
`.by`/`.бел` suffix rules. Ordinary setup reruns preserve the configuration;
fresh configuration can enable both regions with `configure --bypass-ru --bypass-by`.

## Russian website and IP bypass

To route Russian services directly while keeping the proxy for other public destinations:

```bash
sudo python3 setup/proxy/manage.py bypass-ru on
sudo systemctl restart minion-proxy.service
```

This fetches MetaCubeX's Mihomo-compatible `category-ru` domain list and `ru` IP ranges, caches both locally and adds `DIRECT` rules before the final `MATCH,PROXY` fallback. Earlier personal rules retain priority. The dashboard preserves these rules and the current server selection. The lists cover Russian services, including domains outside `.ru`, and Russian IP ranges; classification is maintained upstream and may be incomplete. This is not a list of blocked websites.

Mihomo refreshes the lists daily through the selected proxy and retains its cache when refresh fails. Enabling bypass requires both initial downloads to succeed. Ordinary setup reruns preserve the saved configuration. For a fresh configuration, use `configure --bypass-ru`; running `configure` without that flag regenerates the default routing without Russian bypasses. Disable with `bypass-ru off`, then restart the service.

[Hiddify's Russian lists](https://github.com/hiddify/hiddify-geo/blob/main/.github/workflows/main.yml) use sing-box `.srs` files for `category-ru` domains and Russian IPs. We use [MetaCubeX's rule sets](https://github.com/MetaCubeX/meta-rules-dat) in Mihomo's native format rather than importing a HAPP/Hiddify application profile. These builds can differ in entries and update timing.

## Choose a subscription server

Click **Proxy** in the bar or open **Proxy dashboard** from the launcher. Select
**PROXY**, then a server or **Automatic**; use the dashboard's latency checks to
compare servers. Selection changes take effect without restarting the service,
and Mihomo remembers them across restarts. If a selected server disappears from
the subscription, the native selector falls back to its first option, Automatic.

The old CLI `list` and `select` commands are removed. On upgrade, an older saved
CLI policy is converted once to the native selector, preserving a newer active
dashboard choice when available. Otherwise, an exact saved server pin or
Automatic is restored on the first start. Restoration is confirmed before the
migration record is removed; later dashboard choices are never overridden by
the old CLI policy. Personal regex policies that are not exact saved pins need
manual migration and are retained with an error instead of being guessed.

Proxy configuration, bypass rules, validation and service supervision remain
available through `manage.py`; server selection belongs to the dashboard.

## Test with an explicit proxy first

To check the connection before routing system traffic:

```bash
sudo python3 setup/proxy/manage.py configure --mode proxy
sudo systemctl start minion-proxy.service
sudo python3 setup/proxy/manage.py test
```

In this mode only applications explicitly using the localhost proxy are proxied. `manage.py test` makes HTTPS requests through that listener; it does not test TUN capture. Applications such as curl can also use it explicitly:

```bash
curl --proxy http://127.0.0.1:7890 https://www.gstatic.com/generate_204 -I
```

Switch modes and restart to activate:

```bash
sudo python3 setup/proxy/manage.py mode tun
sudo systemctl restart minion-proxy.service
```

Confirm ordinary browser and terminal requests work without proxy settings. For a full routing check, compare direct and tunneled public egress addresses before/after starting the service, check DNS and local network access, and stop the service to verify direct connectivity returns. These checks are distinct from configuration validation and an explicit HTTP proxy test. Service startup fails if the listener, TUN interface or temporary DNS settings cannot initialize. The tunnel follows the detected uplink; restart the service after switching networks if connectivity fails.

## Management and updates

```bash
sudo systemctl status minion-proxy.service
sudo journalctl -u minion-proxy.service -f
sudo python3 setup/proxy/manage.py validate
sudo systemctl disable --now minion-proxy.service
```

Stopping the service removes its TUN interface and dynamically installed routing. Disabling also prevents startup at boot. The underlying Wi-Fi connection remains managed by NetworkManager. The service runs as root to manage TUN routing; systemd restricts filesystem writes to its private state directory and a private temporary directory.

After pulling source updates, rerun `sudo ./setup.sh` and then restart the service when ready. The installer verifies the installed binary and skips a matching download, retains configuration and leaves activation state alone. The coordinator saves the previous managed configuration, binary and private proxy state in its root-only configuration backup.

For locally controlled automation, `configure --subscription-file /PATH/TO/FILE` reads the URL from a root-owned regular file with no group/other permissions. Use mode 600 and keep the file outside Git. Personal settings can be edited in `/var/lib/minion/proxy/config.json`, followed by validation and restart. Running `configure` again intentionally regenerates this configuration; ordinary installer reruns preserve it.

## Upstream references

- [Mihomo systemd service](https://wiki.metacubex.one/en/startup/service/)
- [Subscription formats](https://wiki.metacubex.one/en/config/proxy-providers/content/)
- [Provider headers and refresh](https://wiki.metacubex.one/en/config/proxy-providers/)
- [TUN routing](https://wiki.metacubex.one/en/config/inbound/tun/)

See [testing](testing.md) for local verification and its limits.
