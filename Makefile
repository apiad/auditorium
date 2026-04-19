.PHONY: relay relay-install relay-uninstall relay-status relay-logs

RELAY_SERVICE = auditorium-relay
SERVICE_FILE = /etc/systemd/system/$(RELAY_SERVICE).service
RELAY_PORT ?= 4243
AUDITORIUM_BIN ?= $(shell command -v auditorium 2>/dev/null || echo "auditorium")

relay:
	auditorium relay --port $(RELAY_PORT)

relay-install:
	@command -v auditorium >/dev/null 2>&1 || { echo "Error: auditorium not found in PATH. Install with: pip install auditorium"; exit 1; }
	@echo "Installing $(RELAY_SERVICE) systemd service..."
	@echo '[Unit]' | sudo tee $(SERVICE_FILE) > /dev/null
	@echo 'Description=Auditorium Relay Server' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo 'After=network.target' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo '' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo '[Service]' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo 'Type=simple' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo 'ExecStart=$(AUDITORIUM_BIN) relay --port $(RELAY_PORT)' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo 'Restart=always' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo 'RestartSec=5' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo '' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo '[Install]' | sudo tee -a $(SERVICE_FILE) > /dev/null
	@echo 'WantedBy=multi-user.target' | sudo tee -a $(SERVICE_FILE) > /dev/null
	sudo systemctl daemon-reload
	sudo systemctl enable $(RELAY_SERVICE)
	sudo systemctl restart $(RELAY_SERVICE)
	@echo ""
	@echo "$(RELAY_SERVICE) installed and running on port $(RELAY_PORT)"
	@echo "Binary: $(AUDITORIUM_BIN)"
	@sudo systemctl status $(RELAY_SERVICE) --no-pager

relay-uninstall:
	sudo systemctl stop $(RELAY_SERVICE) || true
	sudo systemctl disable $(RELAY_SERVICE) || true
	sudo rm -f $(SERVICE_FILE)
	sudo systemctl daemon-reload
	@echo "$(RELAY_SERVICE) removed"

relay-status:
	sudo systemctl status $(RELAY_SERVICE) --no-pager

relay-logs:
	sudo journalctl -u $(RELAY_SERVICE) -f
