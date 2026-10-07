#!/usr/bin/env bash
# Run only inside the freshly built disposable demo VM, before seal-guest.py.
set -euo pipefail
test "$(hostname)" = roleweaver-demo
test -f /root/roleweaver-disposable-build
install -m 755 /home/roleweaver/guest-firstboot.py /usr/local/sbin/roleweaver-firstboot
cat >/etc/systemd/system/roleweaver-firstboot.service <<'EOF'
[Unit]
Description=Initialize this portable Role Weaver demo
After=local-fs.target
Before=ssh.service roleweaver-demo.service

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /usr/local/sbin/roleweaver-firstboot
RemainAfterExit=yes
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
EOF
mkdir -p /etc/systemd/system/roleweaver-demo.service.d /etc/systemd/system/ssh.service.d
for service in roleweaver-demo ssh; do
cat >"/etc/systemd/system/$service.service.d/portable.conf" <<'EOF'
[Unit]
Requires=roleweaver-firstboot.service
After=roleweaver-firstboot.service
EOF
done
cat >/etc/systemd/system/roleweaver-demo.service.d/passwords.conf <<'EOF'
[Service]
Environment=ROLEWEAVER_PORTABLE_SETTINGS=/home/roleweaver/demo/.demo/qemu_demo/settings.json
EOF
systemctl disable ssh.socket 2>/dev/null || true
mkdir -p /etc/systemd/system/roleweaver-dashboard-relay.service.d
cat >/etc/systemd/system/roleweaver-dashboard-relay.service.d/portable.conf <<'EOF'
[Unit]
Requires=roleweaver-firstboot.service
After=roleweaver-firstboot.service

[Service]
EnvironmentFile=/run/roleweaver/dashboard.env
ExecStart=
ExecStart=/usr/bin/socat TCP-LISTEN:8748,bind=0.0.0.0,reuseaddr,fork TCP:127.0.0.1:${ROLEWEAVER_DASHBOARD_PORT}
EOF
systemctl enable ssh.service roleweaver-firstboot.service
systemctl daemon-reload
