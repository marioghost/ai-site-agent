#!/usr/bin/env bash
#
# Install Qdrant locally WITHOUT Docker, by downloading the prebuilt binary.
# Run with sudo if installing to /opt:  sudo bash deploy/install_qdrant.sh
#
# This downloads the latest release binary for x86_64 Linux. Adjust QDRANT_VERSION
# / ARCH for your platform if needed. See https://github.com/qdrant/qdrant/releases
#
set -euo pipefail

QDRANT_VERSION="${QDRANT_VERSION:-v1.12.4}"
INSTALL_DIR="${INSTALL_DIR:-/opt/qdrant}"
DATA_DIR="${DATA_DIR:-/var/lib/qdrant}"
ARCH="x86_64-unknown-linux-gnu"

echo "==> Installing Qdrant ${QDRANT_VERSION} to ${INSTALL_DIR}"

TARBALL="qdrant-${ARCH}.tar.gz"
URL="https://github.com/qdrant/qdrant/releases/download/${QDRANT_VERSION}/${TARBALL}"

mkdir -p "$INSTALL_DIR"
mkdir -p "$DATA_DIR/storage" "$DATA_DIR/snapshots"

TMP="$(mktemp -d)"
echo "==> Downloading $URL"
curl -fsSL "$URL" -o "$TMP/$TARBALL"

echo "==> Extracting"
tar -xzf "$TMP/$TARBALL" -C "$INSTALL_DIR"
chmod +x "$INSTALL_DIR/qdrant"
rm -rf "$TMP"

# Minimal config so Qdrant stores data under DATA_DIR.
cat > "$INSTALL_DIR/config.yaml" <<EOF
storage:
  storage_path: ${DATA_DIR}/storage
  snapshots_path: ${DATA_DIR}/snapshots
service:
  host: 127.0.0.1
  http_port: 6333
  grpc_port: 6334
EOF

echo ""
echo "Qdrant binary installed at: $INSTALL_DIR/qdrant"
echo "Config written to:          $INSTALL_DIR/config.yaml"
echo ""
echo "Test it manually with:"
echo "  $INSTALL_DIR/qdrant --config-path $INSTALL_DIR/config.yaml"
echo ""
echo "For a persistent service, install deploy/systemd/qdrant.service."
