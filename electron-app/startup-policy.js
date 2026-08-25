function createStartupPolicy(environment) {
  const isFastStartup = environment.FAST_STARTUP === 'true';

  return Object.freeze({
    isFastStartup,
    async runExternalStartup(_name, start) {
      if (isFastStartup) return false;
      await start();
      return true;
    },
  });
}

module.exports = { createStartupPolicy };
