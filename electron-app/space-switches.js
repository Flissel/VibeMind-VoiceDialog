/**
 * Switches for whole spaces: a space switched off has no tab, no model in the scene and cannot be
 * entered. Its code stays as it is (nothing is deleted); the switch brings it back.
 *
 * Dashboard (clawport) is off by default: its parts are to find another home (list in the notes
 * of 2026-11-24). VIBEMIND_DASHBOARD_SPACE=an turns it on again.
 */
const SWITCHES = Object.freeze([
  { id: 'clawport', env: 'VIBEMIND_DASHBOARD_SPACE', on: false },
]);

const ON = /^(an|ein|on|true|1|ja)$/i;
const OFF = /^(aus|off|false|0|nein)$/i;

/** The ids of the spaces switched off. */
function hiddenSpaces(env = process.env) {
  return SWITCHES.filter((sw) => {
    const value = typeof env[sw.env] === 'string' ? env[sw.env].trim() : '';
    if (ON.test(value)) return false;
    if (OFF.test(value)) return true;
    return !sw.on;
  }).map((sw) => sw.id);
}

module.exports = { SWITCHES, hiddenSpaces };
