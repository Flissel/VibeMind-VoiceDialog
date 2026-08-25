const { stripVTControlCharacters } = require('node:util');

const DOCKER_BOOTSTRAP_MARKER =
  '[Main] NORMAL_STARTUP Docker bootstrap entered: stale-container cleanup and media Docker';

function createStartupPolicy(environment) {
  const isIsolatedStartup = environment.VIBEMIND_E2E_ISOLATED_STARTUP === 'true';

  return Object.freeze({
    isIsolatedStartup,
    async runExternalStartup(_name, start) {
      if (isIsolatedStartup) return false;
      await start();
      return true;
    },
  });
}

function stripAnsi(value) {
  return stripVTControlCharacters(String(value));
}

function findForbiddenStartupMarkers(output, markers) {
  const normalized = stripAnsi(output);
  return markers.filter((marker) => normalized.includes(marker));
}

function createStartupAudit() {
  let dockerBootstrapStarted = false;
  return Object.freeze({
    markDockerBootstrapStarted() {
      dockerBootstrapStarted = true;
    },
    publicMarkers() {
      return dockerBootstrapStarted ? [DOCKER_BOOTSTRAP_MARKER] : [];
    },
  });
}

module.exports = {
  DOCKER_BOOTSTRAP_MARKER,
  createStartupAudit,
  createStartupPolicy,
  findForbiddenStartupMarkers,
  stripAnsi,
};
