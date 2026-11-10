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

test_pressure_pair: test_pressure_pair.c $(MAIN)/pressure_pair.c $(MAIN)/pressure_pair.h
	$(CC) $(CFLAGS) -I$(MAIN) -o $@ test_pressure_pair.c $(MAIN)/pressure_pair.c -lm

check-pair: test_pressure_pair
	./test_pressure_pair

check: check-interlock check-analysis check-pair

clean:
	rm -f test_interlock test_pressure_pair

.PHONY: all check check-interlock check-analysis check-pair clean
