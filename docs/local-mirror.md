# Local download mirror for tests

The test mirror downloads Ubuntu archive/security objects once and serves cached copies on later requests. APT continues to verify signed metadata and package hashes. Pinned shell archives and signed browser files can also be cached for setup tests. The device's normal setup uses its existing repositories and upstream downloads.

## Start and inspect the mirror

Run from the repository root:

```bash
python3 tests/local-mirror.py --port 43385
# Alternatively, detach the server:
python3 tests/local-mirror.py --port 43385 --daemon
python3 tests/mirror-statistics.py
```

The server binds to host loopback `127.0.0.1`. QEMU's user-network guest reaches it at `http://10.0.2.2:43385`. Addresses, process state, cache objects and traffic events live under ignored `.local/mirror/`. The first uncached request still uses the external network. Incomplete downloads are discarded; mutable repository indices refresh after one hour.

For manual VM installation, enter `http://10.0.2.2:43385/ubuntu` as the Ubuntu archive mirror. After installation, inspect `/etc/apt/sources.list.d/ubuntu.sources` and use these URIs for the respective stanzas:

```text
# noble, noble-updates and noble-backports
URIs: http://10.0.2.2:43385/ubuntu

# noble-security
URIs: http://10.0.2.2:43385/ubuntu-security
```

Retain the existing suites, components and `Signed-By` fields. Run `sudo apt-get update` inside the guest and inspect mirror statistics to confirm reuse. Keep these host-specific URLs confined to the VM.

## Cache setup downloads

```bash
python3 tests/cache-provisioning.py
python3 tests/cache-provisioning.py --check
```

The first command fetches missing shell artifacts and pinned browser/Snap files; it verifies their checksums and stages the browser test page. `--check` verifies existing cached assets without downloading. Manifests live in [setup/shell/artifacts.json](../setup/shell/artifacts.json) and [setup/desktop/browser-snaps.json](../setup/desktop/browser-snaps.json). An upstream checksum/assertion change requires a reviewed manifest update.

Inside the guest, explicitly select the cache:

```bash
sudo ./setup.sh --asset-url http://10.0.2.2:43385/assets
```

APT still uses the guest's configured package repositories. Setup verifies shell/browser checksums and Snap assertions. Some tests instead launch with `--setup-assets` to expose the fixed host cache as a read-only 9p directory.

For a single reviewed artifact:

```bash
python3 tests/cache-asset.py HTTPS_URL EXPECTED_SHA256 ARTIFACT_FILENAME
```

Stop a foreground server with Ctrl+C. For a detached server, identify its process from `.local/mirror/server.json` before stopping it. Restarting on the same port preserves guest URLs. Do not delete cached objects while tests are running. Incidental guest traffic and automatic Snap refreshes are outside this cache's coverage.
