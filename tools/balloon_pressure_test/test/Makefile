# Host unit tests for the pre-stretch bench firmware logic.
# No ESP-IDF, no hardware: everything below builds with plain gcc.
#
#   make -C tools/balloon_pressure_test/test check
#
CC      ?= gcc
CFLAGS  ?= -std=c11 -Wall -Wextra -Werror -O2
MAIN     = ../main

all: check

# ---- over-pressure interlock (pure C) --------------------------------
test_interlock: test_interlock.c $(MAIN)/interlock.c $(MAIN)/interlock.h
	$(CC) $(CFLAGS) -I$(MAIN) -o $@ test_interlock.c $(MAIN)/interlock.c

check-interlock: test_interlock
	./test_interlock

# ---- leak-rate analysis (pure python, numpy not required) ------------
check-analysis:
	python3 test_plot_pressure.py

check-contract:
	python3 test_pressure_contract.py

check: check-interlock check-analysis check-contract

clean:
	rm -f test_interlock

.PHONY: all check check-interlock check-analysis check-contract clean
