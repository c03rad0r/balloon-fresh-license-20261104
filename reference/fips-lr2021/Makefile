# Convenience targets for the FIPS over LR2021 reference.
# Override FIPS_DIR to use an existing checkout.

FIPS_DIR ?= $(CURDIR)/build/fips
PROBE ?=
PORT ?=
SEED_USP_WORKSPACE ?= $(CURDIR)/build/seeed-usp-workspace
USP_ZEPHYR_REF ?= 64f416bddd5c95ec4504b00627aa932eb88c7bd5
FLRP_DATA_SIZE ?= (20*1024)
FLRP_LOW_FREQ ?= true
FLRP_CRYPTO ?= true
BAUD ?= 115200

SEED_USP = SEED_USP_WORKSPACE="$(SEED_USP_WORKSPACE)" \
	USP_ZEPHYR_REF="$(USP_ZEPHYR_REF)" \
	FLRP_DATA_SIZE="$(FLRP_DATA_SIZE)" \
	FLRP_LOW_FREQ="$(FLRP_LOW_FREQ)" \
	FLRP_CRYPTO="$(FLRP_CRYPTO)" \
	./scripts/seeed-usp.sh

.PHONY: all bootstrap host-test mock-e2e build-fips build-e80 flash-e80 clean
.PHONY: seeed-setup seeed-doctor seeed-per-build-rx seeed-per-build-tx
.PHONY: seeed-per-flash-rx seeed-per-flash-tx
.PHONY: seeed-flrp-build-initiator seeed-flrp-build-slave
.PHONY: seeed-flrp-flash-initiator seeed-flrp-flash-slave seeed-monitor
.PHONY: seeed-bridge-host-test seeed-bridge-loopback-build

all: host-test mock-e2e build-e80

bootstrap:
	FIPS_DIR=$(FIPS_DIR) ./scripts/bootstrap-fips.sh

host-test:
	FIPS_DIR=$(FIPS_DIR) ./scripts/test-host.sh

mock-e2e:
	FIPS_DIR=$(FIPS_DIR) ./tests/host/run_mock_e2e.sh

build-fips:
	FIPS_DIR=$(FIPS_DIR) ./scripts/build.sh

build-e80:
	./scripts/build-e80-bridge.sh

flash-e80:
	PROBE=$(PROBE) ./scripts/flash-e80-bridge.sh

seeed-setup:
	$(SEED_USP) setup

seeed-doctor:
	$(SEED_USP) doctor

seeed-per-build-rx:
	$(SEED_USP) build per-rx

seeed-per-build-tx:
	$(SEED_USP) build per-tx

seeed-per-flash-rx:
	PROBE="$(PROBE)" $(SEED_USP) flash per-rx

seeed-per-flash-tx:
	PROBE="$(PROBE)" $(SEED_USP) flash per-tx

seeed-flrp-build-initiator:
	$(SEED_USP) build flrp-initiator

seeed-flrp-build-slave:
	$(SEED_USP) build flrp-slave

seeed-flrp-flash-initiator:
	PROBE="$(PROBE)" $(SEED_USP) flash flrp-initiator

seeed-flrp-flash-slave:
	PROBE="$(PROBE)" $(SEED_USP) flash flrp-slave

seeed-monitor:
	PORT="$(PORT)" BAUD="$(BAUD)" $(SEED_USP) monitor

seeed-bridge-host-test:
	./tests/host/run_seeed_bridge_test.sh

seeed-bridge-loopback-build:
	$(SEED_USP) build bridge-loopback

clean:
	rm -rf build firmware/rp2040-bridge/.pio
