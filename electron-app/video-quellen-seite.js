// The two buttons of the Video space bar; the main process says which source is shown (video-quellen.js).
(function () {
  'use strict';
  var bridge = window.videoQuellen;
  var laura = document.getElementById('laura');
  var marketing = document.getElementById('marketing');
  var hinweis = document.getElementById('hinweis');
  if (!bridge) return;
  laura.addEventListener('click', function () { bridge.waehlen('laura'); });
  marketing.addEventListener('click', function () { bridge.waehlen('marketing'); });
  bridge.beiStand(function (stand) {
    laura.setAttribute('aria-pressed', String(stand.quelle === 'laura'));
    marketing.setAttribute('aria-pressed', String(stand.quelle === 'marketing'));
    marketing.disabled = !stand.marketing;
    hinweis.textContent = stand.marketing ? (stand.quelle === 'marketing' ? 'Reels und Videos aus dem Marketing-Dienst' : '')
      : 'Marketing-Dienst nicht eingerichtet';
  });
})();
