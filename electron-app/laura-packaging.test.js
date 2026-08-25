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
