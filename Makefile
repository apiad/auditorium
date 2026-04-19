.PHONY: relay relay-install relay-uninstall relay-status relay-logs

RELAY_SERVICE = auditorium-relay
SERVICE_FILE = /etc/systemd/system/$(RELAY_SERVICE).service
RELAY_PORT ?= 4243

relay:
	auditorium relay --port $(RELAY_PORT)

relay-install:
	@echo "Installing $(RELAY_SERVICE) systemd service..."
	sudo cp auditorium/relay.service $(SERVICE_FILE)
	sudo sed -i 's/--port 4243/--port $(RELAY_PORT)/' $(SERVICE_FILE)
	sudo sed -i 's|ExecStart=auditorium|ExecStart=$(shell which auditorium)|' $(SERVICE_FILE)
	sudo systemctl daemon-reload
	sudo systemctl enable $(RELAY_SERVICE)
	sudo systemctl start $(RELAY_SERVICE)
	@echo "$(RELAY_SERVICE) installed and running on port $(RELAY_PORT)"
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
