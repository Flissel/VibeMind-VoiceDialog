const assert = require('node:assert/strict');
const { test } = require('node:test');

const packageConfig = require('./package.json');

test('package build creates and bundles the Laura renderer exactly once', () => {
  assert.equal(packageConfig.scripts['video:build'], 'npm run laura:build');
  assert.equal(
    packageConfig.scripts.build,
    'npm run dashboard:build && npm run agentfarm:build && npm run video:build && electron-builder',
  );
  assert.ok(packageConfig.scripts['test:unit'].split(' ').includes('laura-packaging.test.js'));

  const lauraResources = packageConfig.build.extraResources.filter(
    (resource) => resource.to === 'laura-renderer',
  );
  assert.deepEqual(lauraResources, [{
    from: '../../spaces/video/laura/apps/desktop/dist',
    to: 'laura-renderer',
    filter: ['**/*'],
  }]);
});

test('platform package entry points build Laura immediately before electron-builder', () => {
  assert.deepEqual(
    {
      win: packageConfig.scripts['build:win'],
      mac: packageConfig.scripts['build:mac'],
      linux: packageConfig.scripts['build:linux'],
    },
    {
      win: 'npm run video:build && electron-builder --win',
      mac: 'npm run video:build && electron-builder --mac',
      linux: 'npm run video:build && electron-builder --linux',
    },
  );
});
