local ROSETTA_DIR = getenv("ROSETTA_DIR") || "";

dofile(ROSETTA_DIR + "mocks.nut", true);
dofile(ROSETTA_DIR + "scripts/!mods_preload/!rosetta.nut", true);
