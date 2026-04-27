#!/usr/bin/env node
/**
 * KEA OpenClaw Post-Install Script
 *
 * Runs after `npm install kea-openclaw` to:
 * 1. Detect Python environment
 * 2. Verify KEA Python tool layer is present
 * 3. Run smoke tests
 * 4. Print setup instructions
 */

const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");

const COLORS = {
  reset: "\x1b[0m",
  green: "\x1b[32m",
  yellow: "\x1b[33m",
  red: "\x1b[31m",
  cyan: "\x1b[36m",
};

function log(level, msg) {
  const color = level === "error" ? COLORS.red : level === "warn" ? COLORS.yellow : COLORS.green;
  console.log(`${color}${msg}${COLORS.reset}`);
}

function checkPython() {
  const candidates = ["python3", "python"];
  for (const cmd of candidates) {
    try {
      const version = execSync(`${cmd} --version`, { encoding: "utf-8", stdio: ["pipe", "pipe", "ignore"] });
      const match = version.match(/Python (\d+)\.(\d+)/);
      if (match) {
        const major = parseInt(match[1], 10);
        const minor = parseInt(match[2], 10);
        if (major > 3 || (major === 3 && minor >= 11)) {
          return { cmd, version: version.trim() };
        }
      }
    } catch {
      // try next
    }
  }
  return null;
}

function findKeaDir() {
  // We are in openclaw/scripts/. Try ../.. then ../../kea
  const scriptDir = __dirname;
  const openclawDir = path.resolve(scriptDir, "..");
  const projectRoot = path.resolve(openclawDir, "..");

  // Case 1: kea/ is sibling of openclaw/
  const sibling = path.join(projectRoot, "kea");
  if (fs.existsSync(path.join(sibling, "kea", "cli.py"))) {
    return sibling;
  }

  // Case 2: kea/ is inside ontology-modeling/ which is sibling of openclaw/
  const nested = path.join(projectRoot, "ontology-modeling", "kea");
  if (fs.existsSync(path.join(nested, "kea", "cli.py"))) {
    return nested;
  }

  // Case 3: current working directory has kea/
  const cwdKea = path.join(process.cwd(), "kea");
  if (fs.existsSync(path.join(cwdKea, "kea", "cli.py"))) {
    return cwdKea;
  }

  return null;
}

function runSmokeTest(keaDir, pythonCmd) {
  try {
    execSync(`${pythonCmd} -m kea --help`, {
      cwd: keaDir,
      encoding: "utf-8",
      stdio: ["pipe", "pipe", "ignore"],
      timeout: 10000,
    });
    return true;
  } catch {
    return false;
  }
}

function main() {
  console.log("");
  console.log("========================================");
  console.log("  KEA OpenClaw Post-Install");
  console.log("========================================");
  console.log("");

  // 1. Check Python
  const python = checkPython();
  if (!python) {
    log("error", "ERROR: Python 3.11+ not found.");
    log("error", "KEA requires Python 3.11 or higher.");
    log("error", "Install from: https://www.python.org/downloads/");
    process.exit(1);
  }
  log("info", `✓ Python found: ${python.version}`);

  // 2. Find KEA dir
  const keaDir = findKeaDir();
  if (!keaDir) {
    log("warn", "WARNING: KEA Python tool layer not found.");
    log("warn", "Expected one of:");
    log("warn", "  ./kea/kea/cli.py");
    log("warn", "  ./ontology-modeling/kea/kea/cli.py");
    log("warn", "");
    log("warn", "Please ensure the kea/ directory is present alongside openclaw/.");
    process.exit(0);
  }
  log("info", `✓ KEA directory: ${keaDir}`);

  // 3. Smoke test
  if (runSmokeTest(keaDir, python.cmd)) {
    log("info", "✓ KEA CLI smoke test passed");
  } else {
    log("warn", "WARNING: KEA CLI smoke test failed.");
    log("warn", `Try manually: cd ${keaDir} && ${python.cmd} -m kea --help`);
  }

  // 4. Print summary
  console.log("");
  console.log("========================================");
  console.log("  KEA is ready!");
  console.log("========================================");
  console.log("");
  console.log("Quick start:");
  console.log(`  cd ${keaDir}`);
  console.log(`  ${python.cmd} -m kea --help`);
  console.log("");
  console.log("Or start a conversation in OpenClaw with:");
  console.log("  'kea', 'ontology', '知识萃取'");
  console.log("");
}

main();
